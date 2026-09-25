"""Websocket API for Listening Genome: read-only access to the current genome."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import callback

from .const import DOMAIN, WS_TYPE_GET

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@callback
def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register the integration's websocket commands (once, from ``async_setup``)."""
    websocket_api.async_register_command(hass, ws_get_genome)


@websocket_api.websocket_command({vol.Required("type"): WS_TYPE_GET})
@callback
def ws_get_genome(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """
    Return the genome the coordinator currently holds for the loaded entry.

    Answers from memory: no rebuild, no database read, no network. The coordinator is what
    keeps that value current.
    """
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "Listening Genome is not loaded"
        )
        return
    genome = entries[0].runtime_data.coordinator.data
    if genome is None:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "No genome has been computed yet"
        )
        return
    connection.send_result(msg["id"], genome)
