"""
Listening Genome — a listening-taste profile for Home Assistant.

The Home Assistant side of the integration: config entry setup, the coordinator, the schedules,
the websocket API, the sensors and the rebuild button. Everything that computes or stores the
genome is in the HA-free ``core`` package; the modules at this level only wire it into Home
Assistant.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.loader import async_get_integration
from homeassistant.util import dt as dt_util

from .baseline import load_baseline
from .compat import preload_transliteration
from .const import DOMAIN, PLATFORMS, STORAGE_DIRNAME
from .core.constants import (
    GENOME_ENRICHMENT_BATCH_LIMIT,
    GENOME_MB_ENRICHMENT_MIN_INTERVAL_SECONDS,
    LASTFM_RATE_LIMIT,
    LASTFM_RATE_PERIOD_SECONDS,
    LISTENBRAINZ_RATE_LIMIT,
    LISTENBRAINZ_RATE_PERIOD_SECONDS,
    LISTENER_HOUSEHOLD,
    LOGGER,
    MUSICBRAINZ_RATE_LIMIT,
    MUSICBRAINZ_RATE_PERIOD_SECONDS,
)
from .core.http import AiohttpClient, user_agent
from .core.jobs import JobTracker
from .core.operations import GenomeOperations
from .core.service import GenomeService, GenomeServiceSettings
from .core.store import GenomeStore
from .live_capture import MusicAssistantCapture
from .panel import async_register_panel, async_remove_panel
from .runtime import ListeningGenomeData
from .services import async_register_services
from .websocket_api import async_register_websocket_commands

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

    from .core.models import GenomeResult

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

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
    """Register the websocket commands and actions once, independent of any entry."""
    async_register_websocket_commands(hass)
    async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ListeningGenomeConfigEntry) -> bool:
    """Open the store, load the baseline, serve the genome, and start the schedules."""
    storage_dir = hass.config.path(STORAGE_DIRNAME)
    await hass.async_add_executor_job(lambda: os.makedirs(storage_dir, exist_ok=True))
    # artist keys are built on the event loop; their lookup tables must not be read there
    await hass.async_add_executor_job(preload_transliteration)

    # the version MusicBrainz sees is the one manifest.json states, read through HA's loader
    integration = await async_get_integration(hass, DOMAIN)
    agent = user_agent(str(integration.version))
    session = async_get_clientsession(hass)
    settings = GenomeServiceSettings.from_options(entry.options)

    store = GenomeStore(storage_dir)
    await store.setup()
    try:
        # after store.setup(): a job a previous run left "running" becomes "interrupted" here
        jobs = JobTracker(store, clock=lambda: dt_util.utcnow().timestamp())
        await jobs.load()
        baseline = await load_baseline()
        service = GenomeService(
            store,
            baseline,
            settings,
            tz_offset_seconds=tz_offset_seconds,
            # build_genome is CPU-bound (seconds on a large history): keep it off the loop
            run_sync=hass.async_add_executor_job,
            clock=lambda: dt_util.utcnow().timestamp(),
        )
        operations = GenomeOperations(
            service,
            jobs,
            musicbrainz_client=AiohttpClient(
                session,
                rate_limit=MUSICBRAINZ_RATE_LIMIT,
                period=MUSICBRAINZ_RATE_PERIOD_SECONDS,
                user_agent=agent,
            ),
            listenbrainz_client=AiohttpClient(
                session,
                rate_limit=LISTENBRAINZ_RATE_LIMIT,
                period=LISTENBRAINZ_RATE_PERIOD_SECONDS,
                user_agent=agent,
            ),
            lastfm_client=AiohttpClient(
                session,
                rate_limit=LASTFM_RATE_LIMIT,
                period=LASTFM_RATE_PERIOD_SECONDS,
                user_agent=agent,
            ),
            enrichment_limit=GENOME_ENRICHMENT_BATCH_LIMIT,
            enrichment_min_interval_seconds=GENOME_MB_ENRICHMENT_MIN_INTERVAL_SECONDS,
        )

        async def _async_update_data() -> GenomeResult:
            # only the first refresh (and an explicit homeassistant.update_entity) comes here:
            # the cached genome, or a rebuild when there is none yet
            try:
                return await operations.get_genome(LISTENER_HOUSEHOLD)
            except Exception as err:
                raise UpdateFailed(f"Could not read the listening genome: {err}") from err

        # no update_interval: rebuilds push their result with async_set_updated_data
        coordinator: DataUpdateCoordinator[GenomeResult] = DataUpdateCoordinator(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_method=_async_update_data,
        )
        await coordinator.async_config_entry_first_refresh()
    except BaseException:
        await store.close()
        raise

    capture = MusicAssistantCapture(hass, entry, operations)
    # rebuilds name each room by what Music Assistant calls the player right now
    store.player_name_resolver = capture.player_name

    runtime = ListeningGenomeData(
        hass=hass,
        entry=entry,
        store=store,
        service=service,
        jobs=jobs,
        operations=operations,
        coordinator=coordinator,
        settings=settings,
        user_agent=agent,
        capture=capture,
    )
    entry.runtime_data = runtime
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    runtime.async_start_schedules()
    await async_register_panel(hass)
    # before the capture starts: its first attempt may already change the entry (following a
    # replaced Music Assistant entry, see live_capture._relink)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    capture.async_start()
    # a stop does not unload entries: write the plays still open, finish or interrupt what is
    # running, then close the store (after all of that - the writes need it). async_listen, not
    # async_listen_once: an unload after the stop removes the listener, and removing a
    # once-listener that already fired is logged as an error. The stop only fires once.
    entry.async_on_unload(hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, runtime.async_close))
    runtime.async_request_duplicate_cleanup()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ListeningGenomeConfigEntry) -> bool:
    """Unload the platforms, stop the schedules and in-flight work, and close the store."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        async_remove_panel(hass)
        # a no-op when Home Assistant's stop already closed everything
        await entry.runtime_data.async_close()
    return unloaded


async def _async_options_updated(hass: HomeAssistant, entry: ListeningGenomeConfigEntry) -> None:
    """
    Apply changed options: reload, then rebuild if a setting the genome depends on changed.

    The reload re-registers the schedules with the new hour and enrichment toggle. Without the
    rebuild, a changed half-life or percentile would not show until the next daily run.

    A change to the entry's DATA alone is the Music Assistant link moving to a replacement
    entry (``live_capture._relink``): the capture already follows it, so reloading would only
    drop and re-open that connection. (Reconfigure reloads by itself.)
    """
    before = entry.runtime_data.settings
    if GenomeServiceSettings.from_options(entry.options) == before:
        return
    await hass.config_entries.async_reload(entry.entry_id)
    if entry.state is not ConfigEntryState.LOADED:
        return
    after = entry.runtime_data.settings
    if after.engine_settings() != before.engine_settings():
        entry.runtime_data.async_request_rebuild("settings changed")
