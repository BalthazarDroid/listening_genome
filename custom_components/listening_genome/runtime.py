"""
Runtime state of a loaded entry, and the Home Assistant scheduling around it.

What runs (rebuild, enrichment) and how it is recorded lives in ``core/operations.py``. This
module decides *when*: a daily rebuild at the configured local hour, an hourly enrichment pass
when enrichment is enabled, and on demand from the button or the websocket API. Everything
detached runs as a config-entry background task, tracked here so unload can cancel it and wait
for it BEFORE the store closes (Home Assistant's own cancellation of entry background tasks
happens only after ``async_unload_entry`` has returned, by which point the database is gone).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change, async_track_time_interval

from .const import ENRICHMENT_INTERVAL
from .core.constants import LOGGER

if TYPE_CHECKING:
    from collections.abc import Coroutine
    from datetime import datetime

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

    from .core.jobs import JobTracker
    from .core.models import GenomeRebuildResult, GenomeResult
    from .core.operations import EnrichmentReport, GenomeOperations
    from .core.service import GenomeService, GenomeServiceSettings
    from .core.store import GenomeStore


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
    _unsubscribers: list[CALLBACK_TYPE] = field(default_factory=list)
    _tasks: set[asyncio.Task[Any]] = field(default_factory=set)

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
        LOGGER.info(
            "Listening Genome scheduled: daily rebuild at %02d:00 local time; enrichment %s",
            hour,
            f"every {ENRICHMENT_INTERVAL}" if self.settings.enrich_enabled else "disabled",
        )

    async def async_shutdown(self) -> None:
        """
        Stop the timers, cancel and await in-flight work, then record it as interrupted.

        Must run before the store closes: a cancelled pass may be between two writes, and the
        interrupted state is itself a write.
        """
        while self._unsubscribers:
            self._unsubscribers.pop()()
        tasks = [task for task in self._tasks if not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        interrupted = await self.jobs.interrupt_running()
        if interrupted:
            LOGGER.info("Listening Genome stopped while running: %s", ", ".join(interrupted))

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
    def _handle_daily_rebuild(self, now: datetime) -> None:
        """Time-change listener: the daily rebuild."""
        self.async_request_rebuild("daily schedule")

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

    async def _background_enrichment(self) -> EnrichmentReport | None:
        """Run one enrichment pass; the operation records and logs its own outcome."""
        return await self.operations.enrich()

    @callback
    def _spawn(self, coro: Coroutine[Any, Any, Any], name: str) -> asyncio.Task[Any]:
        """Start ``coro`` as an entry background task that unload can cancel and await."""
        task = self.entry.async_create_background_task(self.hass, coro, name)
        if not task.done():
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        return task


__all__ = ["ListeningGenomeData"]
