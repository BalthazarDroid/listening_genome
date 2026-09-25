"""Tests for the settings (options) flow: defaults, validation, reload, and the rebuild after."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType, InvalidData

from custom_components.listening_genome.core.constants import (
    CONF_ENRICH_ENABLED,
    CONF_MIN_SECONDS_PLAYED,
    CONF_OBSCURITY_PERCENTILE,
    CONF_REBUILD_SCHEDULE_HOUR,
    CONF_RECENCY_HALF_LIFE_DAYS,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

VALID = {
    CONF_RECENCY_HALF_LIFE_DAYS: 548,
    CONF_OBSCURITY_PERCENTILE: "25",
    CONF_MIN_SECONDS_PLAYED: 30,
    CONF_REBUILD_SCHEDULE_HOUR: 4,
    CONF_ENRICH_ENABLED: False,
}


@pytest.fixture
async def loaded(
    hass: HomeAssistant, genome_entry: MockConfigEntry, seeded_store: object, test_baseline: object
) -> MockConfigEntry:
    genome_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(genome_entry.entry_id)
    await hass.async_block_till_done()
    return genome_entry


def _defaults(result: dict) -> dict[str, object]:
    return {key.schema: key.default() for key in result["data_schema"].schema}


async def test_form_shows_the_forks_defaults(hass: HomeAssistant, loaded: MockConfigEntry) -> None:
    result = await hass.config_entries.options.async_init(loaded.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert _defaults(result) == {
        CONF_RECENCY_HALF_LIFE_DAYS: 548,
        CONF_OBSCURITY_PERCENTILE: "25",
        CONF_MIN_SECONDS_PLAYED: 30,
        CONF_REBUILD_SCHEDULE_HOUR: 4,
        CONF_ENRICH_ENABLED: True,
    }


async def test_saving_stores_typed_options_and_reloads(
    hass: HomeAssistant, loaded: MockConfigEntry
) -> None:
    before = loaded.runtime_data
    result = await hass.config_entries.options.async_init(loaded.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**VALID, CONF_REBUILD_SCHEDULE_HOUR: 6}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done(wait_background_tasks=True)
    assert loaded.options == {
        CONF_RECENCY_HALF_LIFE_DAYS: 548,
        CONF_OBSCURITY_PERCENTILE: 25,
        CONF_MIN_SECONDS_PLAYED: 30,
        CONF_REBUILD_SCHEDULE_HOUR: 6,
        CONF_ENRICH_ENABLED: False,
    }
    assert loaded.state is ConfigEntryState.LOADED
    after = loaded.runtime_data
    assert after is not before  # reloaded
    assert after.settings.rebuild_schedule_hour == 6
    assert after.settings.enrich_enabled is False
    # nothing the genome depends on changed, so no rebuild was started
    assert after.jobs.get("rebuild")["state"] != "running"
    assert after.service.last_rebuild_at is None


async def test_changing_an_engine_setting_rebuilds_after_the_reload(
    hass: HomeAssistant, loaded: MockConfigEntry
) -> None:
    assert hass.states.get("sensor.listening_genome_obscurity_index").state == "75.0"
    result = await hass.config_entries.options.async_init(loaded.entry_id)
    # at the 5th percentile (10 listeners) neither artist is obscure any more
    await hass.config_entries.options.async_configure(
        result["flow_id"], {**VALID, CONF_OBSCURITY_PERCENTILE: "5"}
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    runtime = loaded.runtime_data
    assert runtime.service.settings.obscurity_percentile == 5
    assert runtime.service.last_rebuild_at is not None
    assert runtime.coordinator.data["obscurity"]["percentile"] == 5
    assert hass.states.get("sensor.listening_genome_obscurity_index").state == "0.0"


@pytest.mark.parametrize(
    ("key", "value"),
    [
        (CONF_REBUILD_SCHEDULE_HOUR, 24),
        (CONF_REBUILD_SCHEDULE_HOUR, -1),
        (CONF_RECENCY_HALF_LIFE_DAYS, 3651),
        (CONF_RECENCY_HALF_LIFE_DAYS, -5),
        (CONF_MIN_SECONDS_PLAYED, 601),
        (CONF_MIN_SECONDS_PLAYED, 12.5),
        (CONF_OBSCURITY_PERCENTILE, "20"),
    ],
)
async def test_out_of_range_values_are_rejected(
    hass: HomeAssistant, loaded: MockConfigEntry, key: str, value: object
) -> None:
    runtime = loaded.runtime_data
    result = await hass.config_entries.options.async_init(loaded.entry_id)
    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(result["flow_id"], {**VALID, key: value})
    await hass.async_block_till_done()
    assert loaded.options == {}
    assert loaded.runtime_data is runtime  # not reloaded
