"""Tests for Listening Genome setup/unload, its sensors and its websocket command."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import PERCENTAGE
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.listening_genome.const import DOMAIN, STORAGE_DIRNAME
from custom_components.listening_genome.core.store import GenomeStore

if TYPE_CHECKING:
    from pathlib import Path

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from pytest_homeassistant_custom_component.typing import WebSocketGenerator

FROZEN_NOW = "2026-09-25T12:00:00+00:00"

# Expected from the seeded store (tests/ha/conftest.py) against TEST_BASELINE, all four listens
# equally weighted:
#   obscurity index: 3 of 4 listens are Alpha, under the 1000-listener threshold -> 0.75 -> 75 %
#   divergence: household {rock: 1} vs baseline {rock: .5, jazz: .5}; m = {rock: .75, jazz: .25}
#     JSD = .5*log2(1/.75) + .5*.5*log2(.5/.75) + .5*.5*log2(.5/.25) = 0.31128
#     score = sqrt(JSD) = 0.5579 -> 56 %
#   top artist: Alpha (3 plays); listens: 4; last rebuild: the frozen "now"
SENSORS = {
    "sensor.listening_genome_obscurity_index": "75.0",
    "sensor.listening_genome_divergence": "56",
    "sensor.listening_genome_top_artist": "Alpha",
    "sensor.listening_genome_listens_stored": "4",
    "sensor.listening_genome_last_rebuild": FROZEN_NOW,
}


@pytest.fixture
async def loaded_entry(
    hass: HomeAssistant,
    genome_entry: MockConfigEntry,
    seeded_store: Path,
    test_baseline: object,
    freezer: object,
) -> MockConfigEntry:
    """Set up the integration over the seeded store, with time frozen."""
    freezer.move_to(FROZEN_NOW)  # type: ignore[attr-defined]
    genome_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(genome_entry.entry_id)
    await hass.async_block_till_done()
    return genome_entry


async def test_setup_and_unload(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    assert loaded_entry.state is ConfigEntryState.LOADED
    data = loaded_entry.runtime_data
    assert data.coordinator.data["stats"]["total_listens"] == 4
    # the first refresh found no cache, so it rebuilt and wrote one
    assert data.service.last_rebuild_at is not None
    assert await data.store.get_cached_genome("household") is not None

    with patch.object(data.store, "close", wraps=data.store.close) as close:
        assert await hass.config_entries.async_unload(loaded_entry.entry_id)
        await hass.async_block_till_done()
    assert loaded_entry.state is ConfigEntryState.NOT_LOADED
    close.assert_called_once_with()
    # and really closed: the connection no longer answers
    with pytest.raises(ValueError, match="no active connection"):
        await data.store.count_listens("household")


async def test_setup_on_a_fresh_install_creates_the_store(
    hass: HomeAssistant, genome_entry: MockConfigEntry, test_baseline: object
) -> None:
    genome_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(genome_entry.entry_id)
    await hass.async_block_till_done()
    db_path = os.path.join(hass.config.path(STORAGE_DIRNAME), "genome.db")
    assert await hass.async_add_executor_job(os.path.isfile, db_path)
    # an empty store still yields a genome, and the sensors report it rather than failing
    assert hass.states.get("sensor.listening_genome_listens_stored").state == "0"
    assert hass.states.get("sensor.listening_genome_top_artist").state == "unknown"


async def test_sensor_states(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    for entity_id, expected in SENSORS.items():
        state = hass.states.get(entity_id)
        assert state is not None, entity_id
        assert state.state == expected, entity_id

    obscurity = hass.states.get("sensor.listening_genome_obscurity_index")
    assert obscurity.attributes["unit_of_measurement"] == PERCENTAGE
    assert obscurity.attributes["friendly_name"] == "Listening Genome Obscurity index"
    divergence = hass.states.get("sensor.listening_genome_divergence")
    assert divergence.attributes["unit_of_measurement"] == PERCENTAGE
    listens = hass.states.get("sensor.listening_genome_listens_stored")
    assert listens.attributes["state_class"] == "measurement"
    rebuild = hass.states.get("sensor.listening_genome_last_rebuild")
    assert rebuild.attributes["device_class"] == "timestamp"


async def test_entities_share_one_service_device(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    entries = er.async_entries_for_config_entry(entity_registry, loaded_entry.entry_id)
    assert {entry.unique_id for entry in entries} == {
        f"{loaded_entry.entry_id}_{key}"
        for key in ("obscurity_index", "divergence", "top_artist", "listens_stored", "last_rebuild")
    }
    [device_id] = {entry.device_id for entry in entries}
    device = device_registry.async_get(device_id)
    assert device.name == "Listening Genome"
    assert device.entry_type is dr.DeviceEntryType.SERVICE
    assert device.identifiers == {(DOMAIN, loaded_entry.entry_id)}


async def test_cached_genome_is_served_without_rebuilding(
    hass: HomeAssistant,
    genome_entry: MockConfigEntry,
    seeded_store: Path,
    test_baseline: object,
    freezer: object,
) -> None:
    """A genome already in the cache is what the sensors show; setup does not recompute it."""
    freezer.move_to(FROZEN_NOW)  # type: ignore[attr-defined]
    store = GenomeStore(str(seeded_store))
    await store.setup()
    try:
        from custom_components.listening_genome.core.service import (
            GenomeService,
        )

        service = GenomeService(store, test_baseline, tz_offset_seconds=lambda: 0)  # type: ignore[arg-type]
        await service.rebuild(now=1_000_000_000)  # 2001-09-09T01:46:40Z
    finally:
        await store.close()

    genome_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(genome_entry.entry_id)
    await hass.async_block_till_done()
    assert genome_entry.runtime_data.service.last_rebuild_at is None
    state = hass.states.get("sensor.listening_genome_last_rebuild")
    assert state.state == "2001-09-09T01:46:40+00:00"


async def test_ws_get_returns_the_genome(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "listening_genome/get"})
    msg = await client.receive_json()
    assert msg["success"], msg
    genome = msg["result"]
    assert genome == loaded_entry.runtime_data.coordinator.data
    assert genome["top_artists"][0]["name"] == "Alpha"
    assert genome["divergence"]["percent"] == 56


async def test_ws_get_errors_when_not_loaded(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    await hass.async_block_till_done()
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "listening_genome/get"})
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "not_found"
