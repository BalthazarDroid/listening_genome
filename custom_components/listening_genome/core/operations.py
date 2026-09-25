"""
The integration's two long-running operations, rebuild and enrichment, recorded as jobs.

A Home-Assistant-free port of the fork controller's ``rebuild``/``_scheduled_enrichment``/
``_background_enrichment``/``_enrich_pending``/``_drain_popularity_backlog``. Scheduling is not
here: the caller (Home Assistant's timers, a button, a websocket command) decides *when*; this
module decides *what* happens and writes the outcome down through :class:`~.jobs.JobTracker`.

One deliberate change from the fork: an enrichment pass requested while another is running is
SKIPPED, where the fork queued it behind an ``asyncio.Lock``. Both passes would work through the
same pending queue under the same pacing, so a queued second pass only doubles the time spent
talking to MusicBrainz for nothing; the next hourly run picks up whatever is left.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..enrich.listenbrainz import artist_popularity
from ..enrich.musicbrainz import MusicBrainzPassReport, run_musicbrainz_pass
from .constants import (
    GENOME_ENRICHMENT_BATCH_LIMIT,
    GENOME_MB_ENRICHMENT_MIN_INTERVAL_SECONDS,
    LISTENER_HOUSEHOLD,
    LOGGER,
    RESOLVE_STATE_ERROR,
    RESOLVE_STATE_NOT_FOUND,
    RESOLVE_STATE_OK,
    RESOLVE_STATE_PENDING,
)
from .http import describe_http_error
from .jobs import JOB_ENRICHMENT, JOB_REBUILD

if TYPE_CHECKING:
    from .http import HttpClient
    from .jobs import JobTracker
    from .models import GenomeRebuildResult, GenomeResult
    from .service import GenomeService


@dataclass(slots=True)
class PopularityReport:
    """What one ListenBrainz popularity backfill did."""

    looked_up: int = 0
    updated: int = 0
    unknown: int = 0
    #: why the backfill failed outright, or ``None`` if it did not
    error: str | None = None


@dataclass(slots=True)
class EnrichmentReport:
    """The outcome of one enrichment pass: MusicBrainz, then ListenBrainz popularity."""

    musicbrainz: MusicBrainzPassReport = field(default_factory=MusicBrainzPassReport)
    popularity: PopularityReport = field(default_factory=PopularityReport)
    #: ``artist_resolution_counts()`` after the pass: what is still pending or failed
    counts_after: dict[str, int] = field(default_factory=dict)
    duration_s: float = 0.0

    def summary(self) -> str:
        """Render the pass as the one sentence the job and the log carry."""
        mb = self.musicbrainz
        pop = self.popularity
        parts = [
            f"MusicBrainz: {mb.resolved} resolved, {mb.not_found} not found, "
            f"{mb.failed} failed (of {mb.attempted} due)"
        ]
        if mb.failures:
            parts.append(
                "failures: "
                + ", ".join(f"{reason} x{n}" for reason, n in mb.failure_reasons().items())
            )
        if pop.error is not None:
            parts.append(f"ListenBrainz popularity failed: {pop.error}")
        else:
            parts.append(
                f"ListenBrainz popularity: {pop.updated} of {pop.looked_up} updated, "
                f"{pop.unknown} unknown to ListenBrainz"
            )
        counts = self.counts_after
        if counts:
            parts.append(
                f"now {counts.get(RESOLVE_STATE_OK, 0)} identified, "
                f"{counts.get(RESOLVE_STATE_NOT_FOUND, 0)} not on MusicBrainz, "
                f"{counts.get(RESOLVE_STATE_PENDING, 0)} pending, "
                f"{counts.get(RESOLVE_STATE_ERROR, 0)} failed"
            )
        return "; ".join(parts)


class GenomeOperations:
    """Run rebuilds and enrichment passes, and record each run as a job."""

    def __init__(
        self,
        service: GenomeService,
        jobs: JobTracker,
        *,
        musicbrainz_client: HttpClient,
        listenbrainz_client: HttpClient,
        enrichment_limit: int = GENOME_ENRICHMENT_BATCH_LIMIT,
        enrichment_min_interval_seconds: float = GENOME_MB_ENRICHMENT_MIN_INTERVAL_SECONDS,
    ) -> None:
        """
        Initialize the operations.

        :param service: The genome service rebuilds go through.
        :param jobs: Where every run's outcome is recorded.
        :param musicbrainz_client: Throttled, identified client for musicbrainz.org.
        :param listenbrainz_client: Throttled, identified client for api.listenbrainz.org.
        :param enrichment_limit: Per-pass ceiling, for MusicBrainz and separately for the
            popularity backlog (the fork's ``GENOME_ENRICHMENT_BATCH_LIMIT``, 500).
        :param enrichment_min_interval_seconds: Spacing between artists' MusicBrainz lookups
            (the fork's 2.5 s).
        """
        self.service = service
        self.store = service.store
        self.jobs = jobs
        self.musicbrainz_client = musicbrainz_client
        self.listenbrainz_client = listenbrainz_client
        self.enrichment_limit = enrichment_limit
        self.enrichment_min_interval_seconds = enrichment_min_interval_seconds
        self._enrichment_lock = asyncio.Lock()

    @property
    def enrichment_running(self) -> bool:
        """Return whether an enrichment pass is in progress."""
        return self._enrichment_lock.locked()

    async def get_genome(self, listener: str = LISTENER_HOUSEHOLD) -> GenomeResult:
        """
        Return the cached genome (flagged ``stale`` when it is), or rebuild when there is none.

        :meth:`GenomeService.get`, except that a rebuild it falls through to is recorded as the
        ``rebuild`` job like any other.
        """
        cached = await self.service.get_cached(listener)
        if cached is not None:
            return cached
        return (await self.rebuild(listener))["genome"]

    async def rebuild(self, listener: str = LISTENER_HOUSEHOLD) -> GenomeRebuildResult:
        """
        Rebuild and cache the genome, recording the run as the ``rebuild`` job.

        Pure recomputation over what is stored (no network, as in the fork). Raises whatever
        the rebuild raised, after recording it.
        """
        await self.jobs.start(JOB_REBUILD, "Rebuilding the listening genome...")
        try:
            result = await self.service.rebuild_with_stats(listener)
        except Exception as err:
            await self.jobs.fail(JOB_REBUILD, f"Rebuild failed: {err}")
            raise
        genome = result["genome"]
        stats = genome["stats"]
        await self.jobs.finish(
            JOB_REBUILD,
            f"Rebuilt from {result['listens_scanned']} stored listens "
            f"({stats['total_listens']} long enough to count) in {result['duration_ms']} ms; "
            f"{stats['artists_pending']} artists pending, {stats['artists_failed']} failed",
        )
        return result

    async def enrich(self) -> EnrichmentReport | None:
        """
        Run one enrichment pass, or return ``None`` at once if one is already running.

        MusicBrainz first (pending artists, paced), then the ListenBrainz popularity backlog
        (every artist with an ``mbid`` but no listener count, not only the ones just resolved).
        Never raises for a network problem: individual MusicBrainz failures mark that artist
        ``error``; a ListenBrainz failure leaves its backlog for the next pass. An unexpected
        error is recorded on the job and logged, then swallowed - this runs detached, with no
        caller left to catch it. Cancellation propagates.
        """
        if self._enrichment_lock.locked():
            LOGGER.info("Enrichment pass skipped: the previous pass is still running")
            return None
        async with self._enrichment_lock:
            start = time.monotonic()
            report = EnrichmentReport()
            await self.jobs.start(JOB_ENRICHMENT, "Looking up artists on MusicBrainz...")
            try:
                report.musicbrainz = await run_musicbrainz_pass(
                    self.store,
                    client=self.musicbrainz_client,
                    limit=self.enrichment_limit,
                    min_interval_seconds=self.enrichment_min_interval_seconds,
                    on_progress=self._musicbrainz_progress,
                )
                self.jobs.update(JOB_ENRICHMENT, message="Fetching ListenBrainz popularity...")
                report.popularity = await self._drain_popularity_backlog()
                report.counts_after = await self.store.artist_resolution_counts()
            except asyncio.CancelledError:
                raise
            except Exception as err:
                LOGGER.warning("Enrichment pass failed", exc_info=True)
                await self.jobs.fail(JOB_ENRICHMENT, f"Enrichment failed: {err}")
                return report
            report.duration_s = round(time.monotonic() - start, 1)
            summary = report.summary()
            LOGGER.info("Enrichment pass finished in %.1fs: %s", report.duration_s, summary)
            await self.jobs.finish(JOB_ENRICHMENT, summary)
            return report

    def _musicbrainz_progress(self, done: int, total: int, report: MusicBrainzPassReport) -> None:
        """In-memory progress for the panel. Never writes the database (see ``jobs.py``)."""
        self.jobs.update(
            JOB_ENRICHMENT,
            message=(
                f"MusicBrainz: {done} of {total} looked up "
                f"({report.resolved} resolved, {report.not_found} not found, "
                f"{report.failed} failed)"
            ),
            progress=int(done * 100 / total) if total else None,
        )
        if done % 50 == 0 and done < total:
            LOGGER.info(
                "MusicBrainz enrichment: %d of %d looked up (%d resolved, %d not found, %d failed)",
                done,
                total,
                report.resolved,
                report.not_found,
                report.failed,
            )

    async def _drain_popularity_backlog(self) -> PopularityReport:
        """
        Backfill ListenBrainz popularity for artists with an ``mbid`` but no ``lb_listeners``.

        The fork's ``_drain_popularity_backlog``: a ListenBrainz failure is logged and leaves
        the backlog for the next pass; an artist ListenBrainz has nothing for is bumped to the
        back of the queue (``mark_popularity_attempted``) so it is not retried every pass.
        """
        report = PopularityReport()
        backlog = await self.store.pending_popularity_keys(limit=self.enrichment_limit)
        if not backlog:
            LOGGER.debug("ListenBrainz popularity: no artists are missing a listener count")
            return report
        mbid_by_key = dict(backlog)
        report.looked_up = len(mbid_by_key)
        try:
            popularity = await artist_popularity(
                list({*mbid_by_key.values()}), client=self.listenbrainz_client
            )
        except Exception as err:
            report.error = describe_http_error(err)
            LOGGER.warning(
                "ListenBrainz popularity backfill failed for %d artists: %s",
                report.looked_up,
                report.error,
                exc_info=True,
            )
            return report
        updates = {
            artist_key: (pop.listeners, pop.listen_count)
            for artist_key, mbid in mbid_by_key.items()
            if (pop := popularity.get(mbid)) is not None
        }
        if updates:
            await self.store.update_lb_popularity(updates)
        still_missing = [key for key in mbid_by_key if key not in updates]
        if still_missing:
            await self.store.mark_popularity_attempted(still_missing)
        report.updated = len(updates)
        report.unknown = len(still_missing)
        LOGGER.info(
            "ListenBrainz popularity backfill: %d/%d backlog artists updated, %d still unknown",
            report.updated,
            report.looked_up,
            report.unknown,
        )
        return report


__all__ = ["EnrichmentReport", "GenomeOperations", "PopularityReport"]
