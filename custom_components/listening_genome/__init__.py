"""
Listening Genome — a listening-taste profile for Home Assistant.

The Home Assistant side of the integration: config entry setup, the coordinator, the websocket
API and the sensors. Everything that computes or stores the genome is in the HA-free ``core``
package; the modules at this level only wire it into Home Assistant.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .baseline import load_baseline
from .const import DOMAIN, PLATFORMS, STORAGE_DIRNAME, UPDATE_INTERVAL
from .core.constants import LISTENER_HOUSEHOLD, LOGGER
from .core.service import GenomeService, GenomeServiceSettings
from .core.store import GenomeStore
from .websocket_api import async_register_websocket_commands

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

    from .core.models import GenomeResult

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass(slots=True)
class ListeningGenomeData:
    """Runtime state for a loaded entry, kept on ``entry.runtime_data``."""

    store: GenomeStore
    service: GenomeService
    coordinator: DataUpdateCoordinator[GenomeResult]


type ListeningGenomeConfigEntry = ConfigEntry[ListeningGenomeData]


def tz_offset_seconds() -> int:
    """
    Return Home Assistant's current local UTC offset, in seconds.

    The fork's ``_tz_offset_seconds`` did ``datetime.now(LOCAL_TIMEZONE).utcoffset()`` with the
    MA server's zone; here the zone is the one configured in Home Assistant, which
    ``dt_util.now()`` uses. Read at every rebuild, so a DST change is picked up.
    """
    offset = dt_util.now().utcoffset()
    return int(offset.total_seconds()) if offset is not None else 0


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the websocket commands once, independent of any entry."""
    async_register_websocket_commands(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ListeningGenomeConfigEntry) -> bool:
    """Open the store, load the baseline, and serve the genome through a coordinator."""
    storage_dir = hass.config.path(STORAGE_DIRNAME)
    await hass.async_add_executor_job(lambda: os.makedirs(storage_dir, exist_ok=True))

    store = GenomeStore(storage_dir)
    await store.setup()
    try:
        baseline = await load_baseline()
        service = GenomeService(
            store,
            baseline,
            GenomeServiceSettings(),
            tz_offset_seconds=tz_offset_seconds,
            # build_genome is CPU-bound (seconds on a large history): keep it off the loop
            run_sync=hass.async_add_executor_job,
            clock=lambda: dt_util.utcnow().timestamp(),
        )

        async def _async_update_data() -> GenomeResult:
            try:
                return await service.get(LISTENER_HOUSEHOLD)
            except Exception as err:
                raise UpdateFailed(f"Could not read the listening genome: {err}") from err

        coordinator: DataUpdateCoordinator[GenomeResult] = DataUpdateCoordinator(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            update_method=_async_update_data,
        )
        await coordinator.async_config_entry_first_refresh()
    except BaseException:
        await store.close()
        raise

    entry.runtime_data = ListeningGenomeData(store=store, service=service, coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ListeningGenomeConfigEntry) -> bool:
    """Unload the platforms and close the store."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.store.close()
    return unloaded
