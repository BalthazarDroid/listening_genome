"""
The genome's read/rebuild service: a Home-Assistant-free port of the fork controller's logic.

Ported from ``GenomeController`` in the Music Assistant fork
(``controllers/genome/controller.py``): :meth:`GenomeService.rebuild` is ``_rebuild`` plus
``_apply_resolution_counts``/``_unresolved_dismissed``, and :meth:`GenomeService.get` is the
``genome/get`` command. What the controller read from MA's config (the three engine settings)
and from MA's helpers (the clock, the local UTC offset) is injected here instead, so the same
code runs under Home Assistant, in a script, or in a test with a frozen ``now``.

Like the controller's rebuild, this is pure recomputation over what the store already holds:
nothing here touches the network.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from .constants import (
    CONF_ENRICH_ENABLED,
    CONF_MIN_SECONDS_PLAYED,
    CONF_OBSCURITY_PERCENTILE,
    CONF_REBUILD_SCHEDULE_HOUR,
    CONF_RECENCY_HALF_LIFE_DAYS,
    DEFAULT_ENRICH_ENABLED,
    DEFAULT_HALF_LIFE_DAYS,
    DEFAULT_MIN_SECONDS_PLAYED,
    DEFAULT_NEW_ARTIST_WINDOW_DAYS,
    DEFAULT_OBSCURITY_PERCENTILE,
    DEFAULT_REBUILD_SCHEDULE_HOUR,
    DEFAULT_TOP_N,
    LISTENER_HOUSEHOLD,
    LOGGER,
    RESOLVE_STATE_ERROR,
    RESOLVE_STATE_NOT_FOUND,
    RESOLVE_STATE_OK,
    RESOLVE_STATE_PENDING,
)
from .engine import build_genome
from .models import EngineParams, GenomeInputs

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping

    from .models import Baseline, GenomeRebuildResult, GenomeResult
    from .store import GenomeStore

    type SyncRunner = Callable[[Callable[[], GenomeResult]], Awaitable[GenomeResult]]


@dataclass(frozen=True, slots=True)
class GenomeServiceSettings:
    """
    The settings the fork read from its core config (same keys, same defaults).

    The first three drive the engine. The last two are scheduling settings the service itself
    never reads; they live here so one object, built once from the entry's options, carries
    every setting the integration has.
    """

    half_life_days: int = DEFAULT_HALF_LIFE_DAYS
    obscurity_percentile: int = DEFAULT_OBSCURITY_PERCENTILE
    min_seconds_played: int = DEFAULT_MIN_SECONDS_PLAYED
    rebuild_schedule_hour: int = DEFAULT_REBUILD_SCHEDULE_HOUR
    enrich_enabled: bool = DEFAULT_ENRICH_ENABLED

    @classmethod
    def from_options(cls, options: Mapping[str, object]) -> GenomeServiceSettings:
        """Build settings from stored options, keyed by the fork's config keys; missing = default."""

        def _int(key: str, default: int) -> int:
            value = options.get(key, default)
            return int(value) if isinstance(value, int | float | str) else default

        return cls(
            half_life_days=_int(CONF_RECENCY_HALF_LIFE_DAYS, DEFAULT_HALF_LIFE_DAYS),
            obscurity_percentile=_int(CONF_OBSCURITY_PERCENTILE, DEFAULT_OBSCURITY_PERCENTILE),
            min_seconds_played=_int(CONF_MIN_SECONDS_PLAYED, DEFAULT_MIN_SECONDS_PLAYED),
            rebuild_schedule_hour=_int(CONF_REBUILD_SCHEDULE_HOUR, DEFAULT_REBUILD_SCHEDULE_HOUR),
            enrich_enabled=bool(options.get(CONF_ENRICH_ENABLED, DEFAULT_ENRICH_ENABLED)),
        )

    def engine_settings(self) -> tuple[int, int, int]:
        """Return the three settings a rebuild's result depends on."""
        return (self.half_life_days, self.obscurity_percentile, self.min_seconds_played)


async def _run_inline(func: Callable[[], GenomeResult]) -> GenomeResult:
    """Run ``func`` on the calling thread: the default when no executor is supplied."""
    return func()


class GenomeService:
    """Serve the cached genome, and rebuild it from the store on demand."""

    def __init__(
        self,
        store: GenomeStore,
        baseline: Baseline,
        settings: GenomeServiceSettings | None = None,
        *,
        tz_offset_seconds: Callable[[], int],
        run_sync: SyncRunner | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        """
        Initialize the service.

        :param store: An already set-up :class:`GenomeStore`.
        :param baseline: The loaded population baseline.
        :param settings: Engine settings; defaults match the fork's config defaults.
        :param tz_offset_seconds: Returns the current local UTC offset, as the fork's
            ``_tz_offset_seconds`` did. Called once per rebuild, at rebuild time.
        :param run_sync: Runs the CPU-bound :func:`build_genome` call. Defaults to inline;
            Home Assistant passes its executor so a large history never stalls the event loop.
        :param clock: Wall clock (unix seconds) for ``now`` when a rebuild is not given one;
            defaults to :func:`time.time`, looked up at call time.
        """
        self.store = store
        self.baseline = baseline
        self.settings = settings or GenomeServiceSettings()
        self._tz_offset_seconds = tz_offset_seconds
        self._run_sync: SyncRunner = run_sync or _run_inline
        self._clock = clock
        self.last_rebuild_at: int | None = None
        # a coordinator refresh and a websocket read can both find the cache empty at once;
        # the second waits for, and then serves, the first one's result instead of rebuilding
        self._rebuild_lock = asyncio.Lock()

    async def get(
        self, listener: str = LISTENER_HOUSEHOLD, *, refresh: bool = False
    ) -> GenomeResult:
        """
        Return ``listener``'s genome, from cache unless ``refresh`` is set (fork: ``genome/get``).

        A cached result is still returned when the store has moved on since it was computed,
        but with ``stale`` set. "Moved on" is judged like-for-like: the cached
        ``stats.total_listens`` counts only listens that cleared ``min_seconds_played``, so it
        is compared with the store's count of listens a rebuild would count *now*
        (:meth:`GenomeStore.count_eligible_listens`), not with every stored row.

        The fork compared it with the raw row count, so any history containing one listen
        under 30 seconds was reported stale forever (221,179 rows vs 221,178 counted on the
        real data). Here a new sub-threshold listen leaves the genome current - it would not
        change a rebuild - while a new qualifying listen makes it stale. A changed
        ``min_seconds_played`` usually shows as stale too, which is right: a rebuild under the
        new threshold would count differently.
        """
        if not refresh:
            cached = await self.get_cached(listener)
            if cached is not None:
                return cached
        return (await self.rebuild_with_stats(listener))["genome"]

    async def get_cached(self, listener: str = LISTENER_HOUSEHOLD) -> GenomeResult | None:
        """
        Return the cached genome with ``stale`` set as :meth:`get` describes, or ``None``.

        Never rebuilds.
        """
        cached = await self.store.get_cached_genome(listener)
        if cached is None:
            return None
        current_count = await self.store.count_eligible_listens(
            listener, min_seconds_played=self.settings.min_seconds_played
        )
        if current_count == cached["stats"]["total_listens"]:
            return cached
        return cast("GenomeResult", {**cached, "stale": True})

    async def rebuild(
        self, listener: str = LISTENER_HOUSEHOLD, *, now: int | None = None
    ) -> GenomeResult:
        """Recompute, cache and return ``listener``'s genome (fork: ``_rebuild``)."""
        return (await self.rebuild_with_stats(listener, now=now))["genome"]

    async def rebuild_with_stats(
        self, listener: str = LISTENER_HOUSEHOLD, *, now: int | None = None
    ) -> GenomeRebuildResult:
        """
        Recompute and cache the genome, returning it with the fork's rebuild bookkeeping.

        :param listener: The listener id (``"household"`` in v1).
        :param now: The unix time the rebuild is "as of" (recency weighting, the new-artist
            window, ``generated_at``). Defaults to the wall clock, as in the fork.
        """
        async with self._rebuild_lock:
            start = time.monotonic()
            listens = [listen async for listen in self.store.iter_listens(listener)]
            artist_keys = sorted({listen.artist_key for listen in listens})
            artist_meta = await self.store.get_artist_meta(artist_keys)
            player_names = await self.store.player_names()
            settings = self.settings
            params = EngineParams(
                now=int(self._now()) if now is None else int(now),
                half_life_days=settings.half_life_days,
                obscurity_percentile=settings.obscurity_percentile,
                min_seconds_played=settings.min_seconds_played,
                top_n=DEFAULT_TOP_N,
                new_artist_window_days=DEFAULT_NEW_ARTIST_WINDOW_DAYS,
            )
            inputs = GenomeInputs(
                listener=listener,
                listens=listens,
                artist_meta=artist_meta,
                baseline=self.baseline,
                params=params,
                player_names=player_names,
            )
            # the offset is read now, on the event loop, not inside the executor job
            tz_offset = self._tz_offset_seconds()
            genome = await self._run_sync(lambda: build_genome(inputs, tz_offset_seconds=tz_offset))
            await self._apply_resolution_counts(genome)
            await self.store.set_cached_genome(listener, genome)
            self.last_rebuild_at = params.now
            duration_ms = int((time.monotonic() - start) * 1000)
            LOGGER.info(
                "Genome rebuilt for %s: %d listens, %d%% divergence, %dms",
                listener,
                len(listens),
                genome["divergence"]["percent"],
                duration_ms,
            )
            return {
                "listener": listener,
                "listens_scanned": len(listens),
                "duration_ms": duration_ms,
                "genome": genome,
            }

    def _now(self) -> float:
        """Return the current unix time from the injected clock, else :func:`time.time`."""
        return self._clock() if self._clock is not None else time.time()

    async def _apply_resolution_counts(self, genome: GenomeResult) -> None:
        """Overwrite the engine's placeholder resolution counts with the store's real ones."""
        try:
            counts = await self.store.artist_resolution_counts()
        except Exception:  # pragma: no cover - defensive, must never fail a rebuild
            LOGGER.debug("Could not read artist resolution counts", exc_info=True)
            return
        stats: Any = genome["stats"]
        stats["artists_pending"] = counts.get(RESOLVE_STATE_PENDING, 0)
        stats["artists_failed"] = counts.get(RESOLVE_STATE_ERROR, 0)
        stats["artists_resolved"] = counts.get(RESOLVE_STATE_OK, 0) + counts.get(
            RESOLVE_STATE_NOT_FOUND, 0
        )
        stats["unresolved_dismissed"] = await self._unresolved_dismissed()

    async def dismiss_unresolved(self) -> bool:
        """
        Dismiss the "could not be identified" notice for the artists failing right now.

        The fork's ``genome/dismiss_unresolved``: records a fingerprint of the artists currently
        in the ``error`` state rather than muting the notice outright, so a different (or an
        additional) failing artist brings it back. No network.

        :return: Whether the current failed-artist set is now fully dismissed.
        """
        failed = await self.store.all_failed_artist_keys()
        await self.store.dismiss_unresolved(sorted(failed))
        return await self._unresolved_dismissed()

    async def _unresolved_dismissed(self) -> bool:
        """Return whether the currently-failed artist set exactly matches the dismissed one."""
        try:
            dismissed = await self.store.unresolved_dismissed_keys()
            if dismissed is None:
                return False
            return dismissed == await self.store.all_failed_artist_keys()
        except Exception:  # pragma: no cover - defensive, must never fail a rebuild
            LOGGER.debug("Could not compute unresolved_dismissed", exc_info=True)
            return False
