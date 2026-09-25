"""Diagnostic: is live capture connected to Music Assistant, and what has it recorded."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .const import DEVICE_NAME, DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import ListeningGenomeConfigEntry
    from .live_capture import MusicAssistantCapture

# state comes from the capture's own callbacks, never polled
PARALLEL_UPDATES = 0

CONNECTION_DESCRIPTION = BinarySensorEntityDescription(
    key="music_assistant_connection",
    translation_key="music_assistant_connection",
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ListeningGenomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the connection sensor for a loaded entry."""
    async_add_entities([LiveCaptureConnection(entry, entry.runtime_data.capture)])


class LiveCaptureConnection(BinarySensorEntity):
    """On while plays are being captured live from Music Assistant."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    entity_description = CONNECTION_DESCRIPTION

    def __init__(self, entry: ListeningGenomeConfigEntry, capture: MusicAssistantCapture) -> None:
        """Initialize the sensor on the entry's single service device."""
        self._capture = capture
        self._attr_unique_id = f"{entry.entry_id}_{CONNECTION_DESCRIPTION.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=DEVICE_NAME,
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        """Follow the capture's status."""
        self.async_on_remove(self._capture.async_add_listener(self.async_write_ha_state))

    @property
    def is_on(self) -> bool:
        """Whether the session to Music Assistant is up."""
        return self._capture.status.connected

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """What has been captured since Home Assistant started, and why it is down if it is."""
        status = self._capture.status
        return {
            "server_version": status.server_version,
            "plays_captured": status.plays_captured,
            "last_play": status.last_play,
            "last_play_started": (
                datetime.fromtimestamp(status.last_play_at, UTC).isoformat()
                if status.last_play_at is not None
                else None
            ),
            "last_error": status.last_error,
        }
