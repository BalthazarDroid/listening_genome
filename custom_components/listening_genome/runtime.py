"""
Runtime state of a loaded entry, and the Home Assistant scheduling around it.

What runs (rebuild, enrichment, imports) and how it is recorded lives in ``core/operations.py``.
This module decides *when*: a daily rebuild at the configured local hour, an hourly enrichment
pass when enrichment is enabled, a Last.fm poll every N hours when it is configured (plus one
shortly after start-up, to catch up on whatever was scrobbled while Home Assistant was down),
the one-time duplicate cleanup, and on demand from the button, the actions or the websocket API. Everything
detached runs as a config-entry background task, tracked here so unload can cancel it and wait
for it BEFORE the store closes (Home Assistant's own cancellation of entry background tasks
happens only after ``async_unload_entry`` has returned, by which point the database is gone).
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_call_later,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .const import DISCOVERY_STARTUP_DELAY, ENRICHMENT_INTERVAL, LASTFM_STARTUP_POLL_DELAY
from .core.constants import GENOME_DISCOVERY_REFRESH_INTERVAL_HOURS, LOGGER
from .ma_library import MusicAssistantLibrary

if TYPE_CHECKING:
    from collections.abc import Coroutine
    from datetime import datetime

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

    from .core.jobs import JobTracker
    from .core.models import GenomeImportResult, GenomeRebuildResult, GenomeResult
    from .core.operations import EnrichmentReport, GenomeOperations
    from .core.service import GenomeService, GenomeServiceSettings
    from .core.store import GenomeStore
    from .live_capture import MusicAssistantCapture


@dataclass(slots=True)
class ListeningGenomeData:
    """Runtime state for a loaded entry, kept on ``entry.runtime_data``."""

    hass: HomeAssistant
    entry: ConfigEntry
    store: GenomeStore
    service: GenomeService
    jobs: JobTracker
    operations: GenomeOperations
    coordinator: DataUpdateCoordinator[GenomeResult]
    settings: GenomeServiceSettings
    user_agent: str
    capture: MusicAssistantCapture
    _unsubscribers: list[CALLBACK_TYPE] = field(default_factory=list)
    _tasks: set[asyncio.Task[Any]] = field(default_factory=set)
    _close_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _closed: bool = False

    @callback
    def async_start_schedules(self) -> None:
        """Register the daily rebuild and, when enabled, the hourly enrichment pass."""
        hour = self.settings.rebuild_schedule_hour
        self._unsubscribers.append(
            async_track_time_change(
                self.hass, self._handle_daily_rebuild, hour=hour, minute=0, second=0
            )
        )
        if self.settings.enrich_enabled:
            self._unsubscribers.append(
                async_track_time_interval(
                    self.hass,
                    self._handle_enrichment_interval,
                    ENRICHMENT_INTERVAL,
                    name="Listening Genome enrichment",
                    cancel_on_shutdown=True,
                )
            )
        self._unsubscribers.append(
            async_call_later(self.hass, DISCOVERY_STARTUP_DELAY, self._handle_discovery_startup)
        )
        lastfm = self.settings.lastfm_poll_enabled and self.settings.lastfm_configured
        if lastfm:
            self._unsubscribers.append(
                async_track_time_interval(
                    self.hass,
                    self._handle_lastfm_interval,
                    timedelta(hours=self.settings.lastfm_poll_interval_hours),
                    name="Listening Genome Last.fm poll",
                    cancel_on_shutdown=True,
                )
            )
            self._unsubscribers.append(
                async_call_later(self.hass, LASTFM_STARTUP_POLL_DELAY, self._handle_lastfm_interval)
            )
        LOGGER.info(
            "Listening Genome scheduled: daily rebuild at %02d:00 local time; enrichment %s; "
            "Last.fm poll %s",
            hour,
            f"every {ENRICHMENT_INTERVAL}" if self.settings.enrich_enabled else "disabled",
            f"every {self.settings.lastfm_poll_interval_hours} h" if lastfm else "off",
        )

    async def async_shutdown(self) -> None:
        """
        Stop the timers, cancel and await in-flight work, then record it as interrupted.

        Must run before the store closes: a cancelled pass may be between two writes, and the
        interrupted state is itself a write.
        """
        while self._unsubscribers:
            self._unsubscribers.pop()()
        # the capture writes its open plays on the way out, so it stops before the tasks are
        # cancelled and long before the store closes
        await self.capture.async_stop()
        tasks = [task for task in self._tasks if not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        interrupted = await self.jobs.interrupt_running()
        if interrupted:
            LOGGER.info("Listening Genome stopped while running: %s", ", ".join(interrupted))

    async def async_close(self, _event: Any = None) -> None:
        """
        Shut everything down (:meth:`async_shutdown`), then close the store - once.

        Two paths lead here and both may run: Home Assistant stopping (a stop does not unload
        config entries, and the aiosqlite worker is a non-daemon thread - left open, it holds
        up the end of every shutdown and skips ``PRAGMA optimize``), and an unload, which can
        come after the stop. The second caller waits for the first and then does nothing, so
        nothing touches the store once it is closed: the schedules and capture timers are
        gone and the in-flight work was cancelled and awaited before the close.
        """
        async with self._close_lock:
            if self._closed:
                return
            try:
                await self.async_shutdown()
            finally:
                self._closed = True
                await self.store.close()

    async def async_rebuild(self, *, enrich: bool = True) -> GenomeRebuildResult:
        """
        Rebuild now, push the new genome to the sensors, then (optionally) start enrichment.

        The fork's ``genome/rebuild``: the rebuild is awaited (seconds, in the executor, no
        network), enrichment is only dispatched - it can run for twenty minutes.
        """
        result = await self.operations.rebuild()
        self.coordinator.async_set_updated_data(result["genome"])
        if enrich and self.settings.enrich_enabled:
            self.async_request_enrichment()
        return result

    @callback
    def async_request_rebuild(self, reason: str) -> None:
        """Start a rebuild in the background (used where nothing waits on the result)."""
        self._spawn(self._background_rebuild(reason), f"Listening Genome rebuild ({reason})")

    @callback
    def async_request_enrichment(self) -> bool:
        """Start an enrichment pass in the background; ``False`` if one is already running."""
        if self.operations.enrichment_running:
            LOGGER.info("Enrichment not started: the previous pass is still running")
            return False
        self._spawn(self._background_enrichment(), "Listening Genome enrichment")
        return True

    @callback
    def async_request_lastfm_import(self, *, max_pages: int = 0, rebuild: bool = False) -> bool:
        """
        Start a Last.fm import in the background; ``False`` if one is already running.

        :param max_pages: Stop after this many pages (``0``: until done).
        :param rebuild: Rebuild afterwards if anything was added (a manual import: the person
            who asked wants to see the result; the hourly poll leaves it to the daily rebuild).
        """
        if self.operations.lastfm_import_running:
            return False
        self._spawn(
            self._background_lastfm_import(max_pages, rebuild=rebuild),
            "Listening Genome Last.fm import",
        )
        return True

    @callback
    def async_request_apple_import(self, path: str, display_name: str, *, cleanup: bool) -> None:
        """Import an Apple Music CSV in the background, then rebuild if it added anything."""
        self._spawn(
            self._background_apple_import(path, display_name, cleanup=cleanup),
            f"Listening Genome Apple Music import ({display_name})",
        )

    @callback
    def async_request_discovery(self) -> bool:
        """Start a discovery pass in the background; ``False`` if one is already running."""
        if self.operations.discovery_running:
            return False
        self._spawn(self._background_discovery(), "Listening Genome discovery")
        return True

    @callback
    def _handle_discovery_startup(self, now: datetime) -> None:
        """Start-up: refresh discovery if the stored pass is missing or more than a day old."""
        self._spawn(self._discovery_if_stale(), "Listening Genome discovery (start-up)")

    async def _discovery_if_stale(self) -> None:
        cached = await self.store.get_cached_discovery("household") or {}
        age = dt_util.utcnow().timestamp() - float(cached.get("generated_at") or 0)
        if age >= GENOME_DISCOVERY_REFRESH_INTERVAL_HOURS * 3600:
            await self._background_discovery()

    async def _background_discovery(self) -> None:
        client = self.capture.client
        library = MusicAssistantLibrary(client) if client is not None else None
        api_key = self.settings.lastfm_api_key if self.settings.lastfm_configured else None
        try:
            await self.operations.discover(library, api_key)
        except Exception:  # recorded on the job
            LOGGER.warning("Listening Genome discovery pass failed", exc_info=True)

    @callback
    def async_request_duplicate_cleanup(self) -> None:
        """Run the one-time duplicate cleanup in the background (a no-op once it has run)."""
        self._spawn(self._background_duplicate_cleanup(), "Listening Genome duplicate cleanup")

    @callback
    def _handle_lastfm_interval(self, now: datetime) -> None:
        """Interval listener (and the start-up one-shot): poll Last.fm."""
        self.async_request_lastfm_import()

    async def _background_lastfm_import(self, max_pages: int, *, rebuild: bool) -> None:
        settings = self.settings
        if not settings.lastfm_configured:
            return
        try:
            result = await self.operations.import_lastfm(
                settings.lastfm_username, settings.lastfm_api_key, max_pages=max_pages
            )
        except Exception:  # recorded on the job and logged by the operation, key never in it
            return
        await self._rebuild_after_import(result, rebuild=rebuild)

    async def _background_apple_import(
        self, path: str, display_name: str, *, cleanup: bool
    ) -> None:
        try:
            result = await self.operations.import_apple(path, display_name=display_name)
        except Exception:  # recorded on the job and logged by the operation
            return
        finally:
            if cleanup:
                await self.hass.async_add_executor_job(_remove_file, path)
        await self._rebuild_after_import(result, rebuild=True)

    async def _rebuild_after_import(
        self, result: GenomeImportResult | None, *, rebuild: bool
    ) -> None:
        if rebuild and result is not None and result["rows_imported"]:
            await self._background_rebuild("import added listens")

    async def _background_duplicate_cleanup(self) -> None:
        """The one-time cleanup, then a rebuild so the sensors show the corrected genome."""
        try:
            removed = await self.operations.remove_duplicates_once()
        except Exception:
            LOGGER.exception("Listening Genome duplicate cleanup failed")
            return
        if removed is not None and removed.total:
            await self._background_rebuild("duplicates removed")

    @callback
    def _handle_daily_rebuild(self, now: datetime) -> None:
        """Time-change listener: the daily rebuild."""
        self.async_request_rebuild(DAILY_REBUILD_REASON)

    @callback
    def _handle_enrichment_interval(self, now: datetime) -> None:
        """Interval listener: the hourly enrichment pass."""
        self.async_request_enrichment()

    async def _background_rebuild(self, reason: str) -> None:
        """Run a rebuild nobody awaits: its outcome is logged and recorded on the job."""
        LOGGER.info("Listening Genome rebuild starting (%s)", reason)
        try:
            await self.async_rebuild()
        except Exception:
            LOGGER.exception("Listening Genome rebuild (%s) failed", reason)
            return
        if reason == DAILY_REBUILD_REASON:
            # the genome it steers by has just been recomputed: a daily discovery pass
            await self._background_discovery()

    async def _background_enrichment(self) -> EnrichmentReport | None:
        """Run one enrichment pass; the operation records and logs its own outcome."""
        return await self.operations.enrich()

    @callback
    def _spawn(self, coro: Coroutine[Any, Any, Any], name: str) -> asyncio.Task[Any] | None:
        """
        Start ``coro`` as an entry background task that unload can cancel and await.

        Not once :meth:`async_close` has begun: shutdown only cancels the tasks that exist when
        it starts, so work requested after that (a websocket command during Home Assistant's
        stop) would run against a closed store.
        """
        if self._closed or self._close_lock.locked():
            LOGGER.debug("Listening Genome is shutting down: %s not started", name)
            coro.close()
            return None
        task = self.entry.async_create_background_task(self.hass, coro, name)
        if not task.done():
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        return task


DAILY_REBUILD_REASON = "daily schedule"


def _remove_file(path: str) -> None:
    """Delete a temporary upload copy (blocking; runs in the executor)."""
    with contextlib.suppress(FileNotFoundError):
        os.remove(path)


__all__ = ["ListeningGenomeData"]
