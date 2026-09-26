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
import contextlib
import csv
import pathlib
import sqlite3
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..enrich.listenbrainz import artist_popularity
from ..enrich.musicbrainz import MusicBrainzPassReport, run_musicbrainz_pass
from ..importers.apple_csv import ApplePlayActivityStats, parse_play_activity
from ..importers.apple_csv import _open_csv as open_csv
from ..importers.apple_daily_tracks import is_daily_tracks_header, parse_daily_tracks
from ..importers.lastfm import LastfmImporter
from .constants import (
    GENOME_ENRICHMENT_BATCH_LIMIT,
    GENOME_MB_ENRICHMENT_MIN_INTERVAL_SECONDS,
    LISTENER_HOUSEHOLD,
    LOGGER,
    RESOLVE_STATE_ERROR,
    RESOLVE_STATE_NOT_FOUND,
    RESOLVE_STATE_OK,
    RESOLVE_STATE_PENDING,
    SOURCE_MA_PLAYLOG,
)
from .discovery import DiscoveryRunner
from .http import describe_http_error
from .jobs import (
    JOB_APPLE_IMPORT,
    JOB_DISCOVERY,
    JOB_DUPLICATES,
    JOB_ENRICHMENT,
    JOB_LASTFM_IMPORT,
    JOB_REBUILD,
)
from .models import Listen

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .discovery import DiscoveryReport, LibrarySource
    from .http import HttpClient
    from .jobs import JobTracker
    from .live import CapturedListen
    from .models import GenomeImportResult, GenomeRebuildResult, GenomeResult
    from .service import GenomeService
    from .store import DuplicateRemoval


# see GenomeOperations._already_captured
_SAME_PLAY_WINDOW_SECONDS = 120

# parsed Apple listens stored per add_listens call (see GenomeOperations._ingest_apple_csv)
_APPLE_IMPORT_BATCH = 5000


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
        lastfm_client: HttpClient | None = None,
        enrichment_limit: int = GENOME_ENRICHMENT_BATCH_LIMIT,
        enrichment_min_interval_seconds: float = GENOME_MB_ENRICHMENT_MIN_INTERVAL_SECONDS,
    ) -> None:
        """
        Initialize the operations.

        :param service: The genome service rebuilds go through.
        :param jobs: Where every run's outcome is recorded.
        :param musicbrainz_client: Throttled, identified client for musicbrainz.org.
        :param listenbrainz_client: Throttled, identified client for api.listenbrainz.org.
        :param lastfm_client: Identified client for ws.audioscrobbler.com (Last.fm imports).
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
        self.lastfm_client = lastfm_client
        self.enrichment_limit = enrichment_limit
        self.enrichment_min_interval_seconds = enrichment_min_interval_seconds
        self._enrichment_lock = asyncio.Lock()
        # one Last.fm import at a time: a scheduled poll landing on a manual import would page
        # through the same history twice
        self._lastfm_lock = asyncio.Lock()
        self._apple_lock = asyncio.Lock()
        self._discovery_lock = asyncio.Lock()
        self.discovery = (
            DiscoveryRunner(self.store, lastfm_client=lastfm_client)
            if lastfm_client is not None
            else None
        )

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

    # --- imports (2c) -----------------------------------------------------------------------

    @property
    def lastfm_import_running(self) -> bool:
        """Return whether a Last.fm import (manual or scheduled) is in progress."""
        return self._lastfm_lock.locked()

    async def import_lastfm(
        self, username: str, api_key: str, *, max_pages: int = 0
    ) -> GenomeImportResult | None:
        """
        Fetch new Last.fm scrobbles, store them, and drop the ones already recorded elsewhere.

        The first run sweeps the whole history; later runs fetch only what is new (see
        :meth:`LastfmImporter.import_since`). Recorded as the ``lastfm_import`` job. Returns
        ``None`` without doing anything when another Last.fm import is already running.
        Raises what the import raised, after recording it - the API key is never in the text.
        """
        if self.lastfm_client is None:
            msg = "No Last.fm client configured"
            raise RuntimeError(msg)
        if self._lastfm_lock.locked():
            LOGGER.info("Last.fm import skipped: the previous one is still running")
            return None
        async with self._lastfm_lock:
            await self.jobs.start(JOB_LASTFM_IMPORT, f"Importing scrobbles for {username}...")
            importer = LastfmImporter(self.lastfm_client, username, api_key)
            try:
                if await self.store.use_lastfm_account(username):
                    LOGGER.info(
                        "Last.fm account changed to %s: importing its whole history", username
                    )
                added_after = await self.store.max_listen_id()
                result = await importer.import_since(
                    self.store, listener=LISTENER_HOUSEHOLD, max_pages=max_pages
                )
                removed = await self._remove_duplicates_after(result, added_after)
            except asyncio.CancelledError:
                raise
            except Exception as err:
                message = f"Last.fm import failed: {err}"
                await self.jobs.fail(JOB_LASTFM_IMPORT, message)
                LOGGER.warning("%s", message)
                raise
            message = import_summary("Last.fm import", result, removed)
            await self.jobs.finish(JOB_LASTFM_IMPORT, message)
            LOGGER.info("%s", message)
            return result

    async def import_apple(self, path: str, *, display_name: str) -> GenomeImportResult:
        """
        Parse an Apple Music export CSV at ``path``, store it, and drop Last.fm doubles of it.

        Either Apple file works: the header decides between the "Play History Daily Tracks"
        parser (the one with artists) and the older "Play Activity" one. Recorded as the
        ``apple_import`` job; raises what the import raised, after recording it.

        :param path: The CSV on disk (an HA upload's temporary file, or a file under /config).
        :param display_name: What to call it in messages (the original file name).
        """
        async with self._apple_lock:
            await self.jobs.start(JOB_APPLE_IMPORT, f"Importing {display_name}...")
            try:
                added_after = await self.store.max_listen_id()
                result = await self._ingest_apple_csv(path)
                removed = await self._remove_duplicates_after(result, added_after)
            except asyncio.CancelledError:
                raise
            except Exception as err:
                message = f"Apple Music import of {display_name} failed: {err}"
                await self.jobs.fail(JOB_APPLE_IMPORT, message)
                LOGGER.warning("%s", message)
                raise
            message = import_summary(f"Apple Music import of {display_name}", result, removed)
            await self.jobs.finish(JOB_APPLE_IMPORT, message)
            LOGGER.info("%s", message)
            for warning in result["warnings"]:
                LOGGER.warning("Apple Music import: %s", warning)
            return result

    async def record_live(self, captured: Sequence[CapturedListen]) -> int:
        """
        Store plays captured live from Music Assistant; return how many were new.

        Grouped by MA user, since the store attributes a batch to one user. Then the Last.fm
        rows those plays make redundant (MA's own scrobbles of them) are removed - normally
        none yet, as the scrobble arrives with a later poll, which removes it then.
        """
        added_after = await self.store.max_listen_id()
        by_user: dict[str | None, list[Listen]] = {}
        for item in captured:
            if await self._already_captured(item.listen):
                continue
            by_user.setdefault(item.userid, []).append(item.listen)
        added = 0
        for userid, listens in by_user.items():
            result = await self.store.add_listens(
                listens, listener=LISTENER_HOUSEHOLD, ma_userid=userid
            )
            added += result["rows_imported"]
        if added:
            played = [item.listen.played_at for item in captured]
            await self.store.remove_duplicate_listens(
                LISTENER_HOUSEHOLD, since=min(played), until=max(played), added_after_id=added_after
            )
        return added

    @property
    def discovery_running(self) -> bool:
        """Return whether a discovery pass is in progress."""
        return self._discovery_lock.locked()

    async def discover(
        self, library: LibrarySource | None, lastfm_api_key: str | None
    ) -> DiscoveryReport | None:
        """
        Run one discovery pass, recorded as the ``discovery`` job; ``None`` if one is running.

        Never raises for a network problem (a failing Last.fm seed or library read is part of
        the report); an unexpected error is recorded on the job and re-raised.
        """
        if self.discovery is None:
            msg = "No Last.fm client configured"
            raise RuntimeError(msg)
        if self._discovery_lock.locked():
            return None
        async with self._discovery_lock:
            await self.jobs.start(JOB_DISCOVERY, "Looking for music to discover...")
            try:
                genome = await self.service.get_cached(LISTENER_HOUSEHOLD)
                report = await self.discovery.run(genome, library, lastfm_api_key)
            except asyncio.CancelledError:
                raise
            except Exception as err:
                await self.jobs.fail(JOB_DISCOVERY, f"Discovery failed: {err}")
                raise
            summary = report.summary()
            await self.jobs.finish(JOB_DISCOVERY, f"Discovery finished: {summary}")
            LOGGER.info("Discovery finished: %s", summary)
            return report

    async def import_fork_live_plays(self, path: str, *, dry_run: bool = False) -> dict[str, Any]:
        """
        Bring over the plays the Music Assistant fork captured live after the last export.

        Phase 4: the fork kept recording until it was switched off, and a live-captured play
        exists nowhere else (no import can recreate it). Only its ``ma_playlog`` rows are taken,
        and only those BEFORE this integration's own live capture began - from then on both
        recorded the same plays, and the fork stamped a play when MA reported it rather than
        when it started, so the two copies would not collapse into one. Everything else in the
        export (Apple, Last.fm) is already here, deliberately cleaned of duplicates, and must not
        come back. The file is opened read-only.

        :param path: A database exported by the fork (``genome/export_db``).
        :param dry_run: Count only; change nothing.
        """
        cutoff = await self.store.first_own_live_capture(LISTENER_HOUSEHOLD)
        rows = await asyncio.to_thread(_read_fork_live_rows, path)
        eligible = [row for row in rows if cutoff is None or row["played_at"] < cutoff]
        report: dict[str, Any] = {
            "fork_live_plays": len(rows),
            "before_own_capture": len(eligible),
            "own_capture_started": cutoff,
            "added": 0,
            "dry_run": dry_run,
        }
        if dry_run or not eligible:
            return report
        by_user: dict[str | None, list[Listen]] = {}
        for row in eligible:
            by_user.setdefault(row["ma_userid"], []).append(_listen_from_row(row))
        for userid, listens in by_user.items():
            result = await self.store.add_listens(
                listens, listener=LISTENER_HOUSEHOLD, ma_userid=userid
            )
            report["added"] += result["rows_imported"]
        LOGGER.warning(
            "Imported %d live play(s) from the fork's export %s (%d there, %d before this "
            "integration's own capture began)",
            report["added"],
            path,
            report["fork_live_plays"],
            report["before_own_capture"],
        )
        return report

    async def _already_captured(self, listen: Listen) -> bool:
        """
        Whether this play was already written by a capture that stopped part-way through it.

        A reload (saving the settings) or a restart mid-track writes what was heard so far;
        the new capture then picks the same play up and computes its start again from the
        progress MA reports - usually the same minute, which the store's dedupe key absorbs,
        but a second of jitter across a minute boundary would slip through. A live row for the
        same track starting within half the track's length (at most two minutes) is that play.
        """
        half = (listen.duration_ms or 240_000) // 2000
        window = min(_SAME_PLAY_WINDOW_SECONDS, half)
        return await self.store.has_live_listen_near(
            LISTENER_HOUSEHOLD, listen.artist_key, listen.track_key, listen.played_at, window
        )

    async def remove_duplicates_once(self) -> DuplicateRemoval | None:
        """
        The one-time whole-history duplicate removal; ``None`` if it has already run.

        Recorded as the ``duplicates`` job. Imports afterwards clean their own time range.
        """
        if await self.store.duplicate_cleanup_done():
            return None
        before = await self.store.count_listens(LISTENER_HOUSEHOLD)
        await self.jobs.start(JOB_DUPLICATES, "Removing plays recorded twice...")
        try:
            removed = await self.store.remove_duplicate_listens(LISTENER_HOUSEHOLD)
        except Exception as err:
            await self.jobs.fail(JOB_DUPLICATES, f"Duplicate removal failed: {err}")
            raise
        await self.store.mark_duplicate_cleanup_done()
        after = await self.store.count_listens(LISTENER_HOUSEHOLD)
        message = (
            f"Removed {removed.total} Last.fm plays already recorded by another source "
            f"({removed.apple} by Apple Music the same day, {removed.music_assistant} by Music "
            f"Assistant); {before} listens before, {after} after"
        )
        await self.jobs.finish(JOB_DUPLICATES, message)
        LOGGER.warning("Listening Genome one-time cleanup: %s", message)
        return removed

    async def _remove_duplicates_after(
        self, result: GenomeImportResult, added_after_id: int
    ) -> DuplicateRemoval | None:
        """Clean the days an import touched (nothing to do when it added nothing)."""
        first, last = result["first_played_at"], result["last_played_at"]
        if not result["rows_imported"] or first is None or last is None:
            return None
        return await self.store.remove_duplicate_listens(
            LISTENER_HOUSEHOLD, since=first, until=last, added_after_id=added_after_id
        )

    async def _ingest_apple_csv(self, path: str) -> GenomeImportResult:
        """
        Parse with whichever Apple parser the header calls for, storing the listens in batches.

        Batches of :data:`_APPLE_IMPORT_BATCH`, like the Last.fm importer's pages: a full Apple
        export is ~300k rows, and holding every parsed :class:`Listen` at once cost ~150 MB on
        the Home Assistant host. Each batch is one :meth:`GenomeStore.add_listens` transaction;
        the counters are summed, so the result is the one a single call would have returned.
        """
        min_seconds = self.service.settings.min_seconds_played
        headers = await asyncio.to_thread(read_csv_header, path)
        parser = parse_daily_tracks if is_daily_tracks_header(headers) else parse_play_activity
        stats = ApplePlayActivityStats()
        result: GenomeImportResult | None = None
        batch: list[Listen] = []
        async for listen in parser(path, min_seconds=min_seconds, stats=stats):
            batch.append(listen)
            if len(batch) >= _APPLE_IMPORT_BATCH:
                result = _merge_import_results(
                    result, await self.store.add_listens(batch, listener=LISTENER_HOUSEHOLD)
                )
                batch = []
        if batch or result is None:
            result = _merge_import_results(
                result, await self.store.add_listens(batch, listener=LISTENER_HOUSEHOLD)
            )
        # the parser's own tally is the truth for rows read and skipped: the store only ever
        # sees the rows that survived parsing
        result["rows_read"] = stats.rows_read
        result["rows_skipped"] = stats.rows_skipped
        stats.summarise()
        result["warnings"] = list(stats.warnings)
        return result

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


_FORK_LIVE_COLUMNS = (
    "ma_userid, played_at, artist_key, artist_name, track_key, track_name, album_name, "
    "source, player_id, duration_ms, played_ms, fully_played, confidence"
)


def _read_fork_live_rows(path: str) -> list[dict[str, Any]]:
    """The fork export's live-captured rows (blocking; read-only - the file is never written)."""
    uri = f"file:{pathlib.Path(path).resolve()}?mode=ro"
    with contextlib.closing(sqlite3.connect(uri, uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"SELECT {_FORK_LIVE_COLUMNS} FROM genome_listens "
            f"WHERE source = '{SOURCE_MA_PLAYLOG}' AND listener = '{LISTENER_HOUSEHOLD}' "
            "ORDER BY played_at"
        ).fetchall()
    return [dict(row) for row in rows]


def _listen_from_row(row: dict[str, Any]) -> Listen:
    return Listen(
        played_at=int(row["played_at"]),
        artist_key=row["artist_key"],
        artist_name=row["artist_name"],
        track_key=row["track_key"],
        track_name=row["track_name"],
        album_name=row["album_name"],
        source=row["source"],
        player_id=row["player_id"],
        duration_ms=row["duration_ms"],
        played_ms=row["played_ms"],
        fully_played=None if row["fully_played"] is None else bool(row["fully_played"]),
        confidence=float(row["confidence"]),
    )


def _merge_import_results(
    total: GenomeImportResult | None, batch: GenomeImportResult
) -> GenomeImportResult:
    """Fold one batch's :meth:`GenomeStore.add_listens` result into the running total."""
    if total is None:
        return batch
    for key in ("rows_read", "rows_imported", "rows_skipped", "rows_duplicate"):
        total[key] += batch[key]
    first, last = batch["first_played_at"], batch["last_played_at"]
    if first is not None and (total["first_played_at"] is None or first < total["first_played_at"]):
        total["first_played_at"] = first
    if last is not None and (total["last_played_at"] is None or last > total["last_played_at"]):
        total["last_played_at"] = last
    total["warnings"].extend(batch["warnings"])
    return total


def read_csv_header(path: str) -> list[str]:
    """Read only the header row of a CSV (blocking; run it in a thread)."""
    with open_csv(path) as csv_file:
        return list(next(csv.reader(csv_file), []))


def import_summary(
    label: str, result: GenomeImportResult, removed: DuplicateRemoval | None = None
) -> str:
    """
    Render an import as the one sentence a person needs to read (the fork's wording).

    This text is the whole outcome once the request that started the import is gone, so it
    carries the counts and any warnings rather than "import finished".
    """
    summary = (
        f"{label} finished: {result['rows_imported']} imported, "
        f"{result['rows_skipped']} skipped, {result['rows_duplicate']} duplicate "
        f"(of {result['rows_read']} rows read)"
    )
    if removed is not None and removed.total:
        summary += (
            f"; {removed.total} Last.fm plays removed as already recorded "
            f"({removed.apple} by Apple Music, {removed.music_assistant} by Music Assistant)"
        )
    warnings = list(result.get("warnings") or ())
    if warnings:
        summary += ". Warnings: " + "; ".join(warnings)
    return summary


__all__ = ["EnrichmentReport", "GenomeOperations", "PopularityReport", "import_summary"]
