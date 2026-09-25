"""Sensors for Listening Genome: a handful of headline numbers from the current genome."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DEVICE_NAME, DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import ListeningGenomeConfigEntry
    from .core.models import GenomeResult

# the sensors only read the coordinator's data, which rebuilds push; they never touch the store
PARALLEL_UPDATES = 0


def _obscurity_percent(genome: GenomeResult) -> float:
    # `index` is a 0..1 fraction already rounded to 4 places; x100 then 2 places keeps it
    # exact (0.1731 -> 17.31, not 17.310000000000002)
    return round(genome["obscurity"]["index"] * 100, 2)


def _top_artist(genome: GenomeResult) -> str | None:
    artists = genome["top_artists"]
    return artists[0]["name"] if artists else None


def _generated_at(genome: GenomeResult) -> datetime:
    return datetime.fromtimestamp(genome["generated_at"], UTC)


@dataclass(frozen=True, kw_only=True)
class GenomeSensorDescription(SensorEntityDescription):
    """A sensor whose state is a pure function of the genome."""

    value_fn: Callable[[GenomeResult], str | int | float | datetime | None]
    attributes_fn: Callable[[GenomeResult], dict[str, Any]] | None = None


SENSORS: tuple[GenomeSensorDescription, ...] = (
    GenomeSensorDescription(
        key="obscurity_index",
        translation_key="obscurity_index",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        value_fn=_obscurity_percent,
    ),
    GenomeSensorDescription(
        key="divergence",
        translation_key="divergence",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda genome: genome["divergence"]["percent"],
    ),
    GenomeSensorDescription(
        key="top_artist",
        translation_key="top_artist",
        value_fn=_top_artist,
    ),
    GenomeSensorDescription(
        key="listens_stored",
        translation_key="listens_stored",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda genome: genome["stats"]["total_listens"],
    ),
    GenomeSensorDescription(
        key="last_rebuild",
        translation_key="last_rebuild",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_generated_at,
        # whether listens that would count have been stored since this genome was computed
        attributes_fn=lambda genome: {"stale": bool(genome.get("stale", False))},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ListeningGenomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the genome sensors for a loaded entry."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(GenomeSensor(coordinator, entry, description) for description in SENSORS)


class GenomeSensor(CoordinatorEntity[DataUpdateCoordinator["GenomeResult"]], SensorEntity):
    """One headline number from the household genome."""

    _attr_has_entity_name = True
    entity_description: GenomeSensorDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[GenomeResult],
        entry: ListeningGenomeConfigEntry,
        description: GenomeSensorDescription,
    ) -> None:
        """Initialize the sensor on the entry's single service device."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=DEVICE_NAME,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> str | int | float | datetime | None:
        """Return the value from the coordinator's current genome."""
        genome = self.coordinator.data
        if genome is None:
            return None
        return self.entity_description.value_fn(genome)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the description's extra attributes for the current genome, if it has any."""
        attributes_fn = self.entity_description.attributes_fn
        genome = self.coordinator.data
        if attributes_fn is None or genome is None:
            return None
        return attributes_fn(genome)
