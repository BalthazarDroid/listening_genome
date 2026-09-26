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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .const import (
    DOMAIN,
    WS_TYPE_DISCOVERY,
    WS_TYPE_DISCOVERY_REFRESH,
    WS_TYPE_DISMISS_UNRESOLVED,
    WS_TYPE_GET,
    WS_TYPE_IMPORT_APPLE,
    WS_TYPE_IMPORT_LASTFM,
    WS_TYPE_JOBS,
    WS_TYPE_LIVE,
    WS_TYPE_PLAY,
    WS_TYPE_PLAYERS,
    WS_TYPE_REBUILD,
    WS_TYPE_RETRY_ARTISTS,
    WS_TYPE_UNRESOLVED_ARTISTS,
)
from .core.constants import LOGGER
from .core.jobs import JOB_APPLE_IMPORT, JOB_DISCOVERY, JOB_LASTFM_IMPORT
from .uploads import UploadError, async_take_upload

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .runtime import ListeningGenomeData

ERR_REBUILD_FAILED = "rebuild_failed"
ERR_NOT_CONFIGURED = "not_configured"
ERR_ALREADY_RUNNING = "already_running"
ERR_UPLOAD = "upload_failed"
ERR_PLAY_FAILED = "play_failed"
ERR_NOT_A_SPEAKER = "not_a_speaker"

# Home Assistant's Music Assistant integration, whose play_media action plays a discovery song
MA_DOMAIN = "music_assistant"
MA_SERVICE_PLAY_MEDIA = "play_media"


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
        ws_import_lastfm,
        ws_import_apple,
        ws_live,
        ws_discovery,
        ws_discovery_refresh,
        ws_players,
        ws_play,
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


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_IMPORT_LASTFM,
        vol.Optional("max_pages", default=0): vol.All(int, vol.Range(min=0)),
    }
)
@websocket_api.require_admin
@callback
def ws_import_lastfm(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """
    Start a Last.fm import now, with the account from the settings; return the job's state.

    The import runs in the background (the first one sweeps the whole history - minutes); its
    outcome is the ``lastfm_import`` job. Rebuilds afterwards when it added anything.
    """
    if (runtime := _runtime(hass, connection, msg)) is None:
        return
    if not runtime.settings.lastfm_configured:
        connection.send_error(
            msg["id"],
            ERR_NOT_CONFIGURED,
            "Last.fm is not set up: add the username and API key in the integration's settings",
        )
        return
    if not runtime.async_request_lastfm_import(max_pages=msg["max_pages"], rebuild=True):
        connection.send_error(msg["id"], ERR_ALREADY_RUNNING, "A Last.fm import is already running")
        return
    connection.send_result(msg["id"], runtime.jobs.get(JOB_LASTFM_IMPORT))


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_IMPORT_APPLE,
        vol.Required("file_id"): str,
        vol.Optional("filename", default=""): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_import_apple(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """
    Import an Apple Music export uploaded through Home Assistant's ``/api/file_upload``.

    The upload is copied out of Home Assistant's temporary upload area straight away (that area
    is emptied when the request ends), then imported in the background; the outcome is the
    ``apple_import`` job, which this returns in its starting state.
    """
    if (runtime := _runtime(hass, connection, msg)) is None:
        return
    display_name = msg["filename"] or "the uploaded file"
    try:
        path = await async_take_upload(hass, msg["file_id"])
    except UploadError as err:
        connection.send_error(msg["id"], ERR_UPLOAD, str(err))
        return
    runtime.async_request_apple_import(path, display_name, cleanup=True)
    connection.send_result(msg["id"], runtime.jobs.get(JOB_APPLE_IMPORT))


@websocket_api.websocket_command({vol.Required("type"): WS_TYPE_LIVE})
@callback
def ws_live(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return the live-capture connection status (memory only)."""
    if (runtime := _runtime(hass, connection, msg)) is None:
        return
    connection.send_result(msg["id"], runtime.capture.status.as_dict())


@websocket_api.websocket_command({vol.Required("type"): WS_TYPE_DISCOVERY})
@websocket_api.async_response
async def ws_discovery(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """
    Return discovery as the last pass stored it: suggestions and cold corners, a song each.

    Database only - never a network request (see ``core/discovery.py``). ``suggested_state``
    says whether Last.fm is set up (``unavailable``), not yet asked (``pending``) or ``ready``.
    """
    if (runtime := _runtime(hass, connection, msg)) is None:
        return
    discovery = runtime.operations.discovery
    assert discovery is not None
    result = await discovery.read(lastfm_configured=runtime.settings.lastfm_configured)
    connection.send_result(msg["id"], result.to_dict())


@websocket_api.websocket_command({vol.Required("type"): WS_TYPE_DISCOVERY_REFRESH})
@websocket_api.require_admin
@callback
def ws_discovery_refresh(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Start a discovery pass in the background; return the ``discovery`` job's state."""
    if (runtime := _runtime(hass, connection, msg)) is None:
        return
    if not runtime.async_request_discovery():
        connection.send_error(msg["id"], ERR_ALREADY_RUNNING, "Discovery is already running")
        return
    connection.send_result(msg["id"], runtime.jobs.get(JOB_DISCOVERY))


def _ma_speakers(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Music Assistant's media players, as the speaker menu lists them (enabled, by name)."""
    registry = er.async_get(hass)
    speakers = []
    for entry in registry.entities.values():
        if entry.platform != MA_DOMAIN or entry.domain != "media_player" or entry.disabled:
            continue
        state = hass.states.get(entry.entity_id)
        name = (
            state.attributes.get("friendly_name")
            if state is not None
            else entry.name or entry.original_name
        ) or entry.entity_id
        speakers.append(
            {
                "entity_id": entry.entity_id,
                "name": name,
                "available": state is not None and state.state != "unavailable",
            }
        )
    speakers.sort(key=lambda speaker: str(speaker["name"]).casefold())
    return speakers


@websocket_api.websocket_command({vol.Required("type"): WS_TYPE_PLAYERS})
@websocket_api.async_response
async def ws_players(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """The speakers a discovery song can play on, and the one used last (the menu's default)."""
    if (runtime := _runtime(hass, connection, msg)) is None:
        return
    connection.send_result(
        msg["id"],
        {"players": _ma_speakers(hass), "last_used": await runtime.store.last_player()},
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_PLAY,
        vol.Required("entity_id"): str,
        vol.Required("artist"): vol.All(str, vol.Length(min=1)),
        vol.Required("song"): vol.All(str, vol.Length(min=1)),
    }
)
@websocket_api.async_response
async def ws_play(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """
    Play ONE song on a Music Assistant speaker, replacing what is queued there.

    Bob, 2026-09-25: a click plays just that song, on the speaker picked from the menu. Goes
    through Home Assistant's own ``music_assistant.play_media`` action, with the calling user's
    context (so it is logged as theirs and their permissions apply): Music Assistant searches
    its providers for "song" by "artist". The queue is replaced and radio mode is off, so
    nothing is added after it - unless the speaker's own "don't stop the music" setting is on
    in Music Assistant, which this does not change. When Music Assistant cannot find the song,
    the error comes back as ``play_failed`` with its message, for the panel to show.
    """
    if (runtime := _runtime(hass, connection, msg)) is None:
        return
    entity_id = msg["entity_id"]
    if entity_id not in {speaker["entity_id"] for speaker in _ma_speakers(hass)}:
        connection.send_error(
            msg["id"], ERR_NOT_A_SPEAKER, f"{entity_id} is not a Music Assistant speaker"
        )
        return
    try:
        await hass.services.async_call(
            MA_DOMAIN,
            MA_SERVICE_PLAY_MEDIA,
            {
                "entity_id": entity_id,
                "media_id": msg["song"],
                "media_type": "track",
                "artist": msg["artist"],
                "enqueue": "replace",
                "radio_mode": False,
            },
            blocking=True,
            context=connection.context(msg),
        )
    except HomeAssistantError as err:
        connection.send_error(msg["id"], ERR_PLAY_FAILED, str(err))
        return
    await runtime.store.set_last_player(entity_id)
    connection.send_result(msg["id"], {"playing": msg["song"], "on": entity_id})
