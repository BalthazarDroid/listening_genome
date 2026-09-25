"""
Websocket API for Listening Genome, for the panel coming in Phase 3.

Ports of the fork's ``genome/*`` commands. The read-only ones (``get``, ``jobs``,
``unresolved_artists``) answer from memory or the local database and never touch the network.
``rebuild`` awaits the rebuild (seconds, in the executor) and only *dispatches* enrichment.
``retry_artists`` and ``dismiss_unresolved`` only change stored state: the next enrichment pass
does the MusicBrainz work, on its own schedule. The commands that change anything need an admin.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import callback

from .const import (
    DOMAIN,
    WS_TYPE_DISMISS_UNRESOLVED,
    WS_TYPE_GET,
    WS_TYPE_JOBS,
    WS_TYPE_REBUILD,
    WS_TYPE_RETRY_ARTISTS,
    WS_TYPE_UNRESOLVED_ARTISTS,
)
from .core.constants import LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .runtime import ListeningGenomeData

ERR_REBUILD_FAILED = "rebuild_failed"


@callback
def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register the integration's websocket commands (once, from ``async_setup``)."""
    for command in (
        ws_get_genome,
        ws_rebuild,
        ws_jobs,
        ws_unresolved_artists,
        ws_retry_artists,
        ws_dismiss_unresolved,
    ):
        websocket_api.async_register_command(hass, command)


def _runtime(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> ListeningGenomeData | None:
    """Return the loaded entry's runtime data, or answer ``not_found`` and return ``None``."""
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "Listening Genome is not loaded"
        )
        return None
    runtime: ListeningGenomeData = entries[0].runtime_data
    return runtime


@websocket_api.websocket_command({vol.Required("type"): WS_TYPE_GET})
@callback
def ws_get_genome(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """
    Return the genome the coordinator currently holds for the loaded entry.

    Answers from memory: no rebuild, no database read, no network.
    """
    if (runtime := _runtime(hass, connection, msg)) is None:
        return
    genome = runtime.coordinator.data
    if genome is None:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "No genome has been computed yet"
        )
        return
    connection.send_result(msg["id"], genome)


@websocket_api.websocket_command(
    {vol.Required("type"): WS_TYPE_REBUILD, vol.Optional("enrich", default=True): bool}
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_rebuild(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """
    Rebuild now and return ``{listener, listens_scanned, duration_ms, genome}`` (fork: rebuild).

    The sensors update from the same result. With ``enrich`` (the default) a background
    enrichment pass is dispatched, never awaited; ``genome.stats.artists_pending`` says how much
    is still to resolve.
    """
    if (runtime := _runtime(hass, connection, msg)) is None:
        return
    try:
        result = await runtime.async_rebuild(enrich=msg["enrich"])
    except Exception as err:
        LOGGER.exception("%s failed", WS_TYPE_REBUILD)
        connection.send_error(msg["id"], ERR_REBUILD_FAILED, f"Rebuild failed: {err}")
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({vol.Required("type"): WS_TYPE_JOBS})
@callback
def ws_jobs(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return the last known state of every job, from memory (no database, no network)."""
    if (runtime := _runtime(hass, connection, msg)) is None:
        return
    connection.send_result(msg["id"], runtime.jobs.get_all())


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_UNRESOLVED_ARTISTS,
        vol.Optional("limit", default=100): vol.All(int, vol.Range(min=1, max=1000)),
    }
)
@websocket_api.async_response
async def ws_unresolved_artists(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return the artists whose MusicBrainz lookup failed, newest first (database only)."""
    if (runtime := _runtime(hass, connection, msg)) is None:
        return
    connection.send_result(msg["id"], await runtime.store.failed_artist_keys(limit=msg["limit"]))


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_RETRY_ARTISTS,
        vol.Optional("artist_keys", default=None): vol.Any(None, [str]),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_retry_artists(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """
    Move failed artists back to pending, ignoring the error cooldown; return how many moved.

    No network here: the next enrichment pass (hourly, or after a rebuild) retries them.
    ``artist_keys`` omitted or ``null`` retries every failed artist.
    """
    if (runtime := _runtime(hass, connection, msg)) is None:
        return
    connection.send_result(msg["id"], await runtime.store.retry_failed_artists(msg["artist_keys"]))


@websocket_api.websocket_command({vol.Required("type"): WS_TYPE_DISMISS_UNRESOLVED})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_dismiss_unresolved(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Dismiss the notice for the artists failing right now; return whether all are dismissed."""
    if (runtime := _runtime(hass, connection, msg)) is None:
        return
    connection.send_result(msg["id"], await runtime.service.dismiss_unresolved())
