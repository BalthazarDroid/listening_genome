"""The "Rebuild now" button: recompute the genome immediately and update the sensors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .const import DEVICE_NAME, DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import ListeningGenomeConfigEntry

# a press awaits a rebuild; the service serializes rebuilds itself, so no platform-level limit
PARALLEL_UPDATES = 0

REBUILD_DESCRIPTION = ButtonEntityDescription(
    key="rebuild_now",
    translation_key="rebuild_now",
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ListeningGenomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the rebuild button for a loaded entry."""
    async_add_entities([RebuildButton(entry)])


class RebuildButton(ButtonEntity):
    """Rebuild the genome now (the fork's "Rebuild now" config action)."""

    _attr_has_entity_name = True
    entity_description = REBUILD_DESCRIPTION

    def __init__(self, entry: ListeningGenomeConfigEntry) -> None:
        """Initialize the button on the entry's single service device."""
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{REBUILD_DESCRIPTION.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=DEVICE_NAME,
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_press(self) -> None:
        """
        Rebuild, push the result to the sensors, and start a background enrichment pass.

        The rebuild itself takes seconds (in the executor); enrichment is only dispatched.
        """
        try:
            await self._entry.runtime_data.async_rebuild()
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="rebuild_failed",
                translation_placeholders={"error": str(err)},
            ) from err
