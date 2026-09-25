"""Tests for the settings (options) flow: defaults, validation, reload, and the rebuild after."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType, InvalidData

from custom_components.listening_genome.config_flow import SECTION_LASTFM
from custom_components.listening_genome.core.constants import (
    CONF_ENRICH_ENABLED,
    CONF_LASTFM_API_KEY,
    CONF_LASTFM_POLL_ENABLED,
    CONF_LASTFM_POLL_INTERVAL_HOURS,
    CONF_LASTFM_USERNAME,
    CONF_MIN_SECONDS_PLAYED,
    CONF_OBSCURITY_PERCENTILE,
    CONF_REBUILD_SCHEDULE_HOUR,
    CONF_RECENCY_HALF_LIFE_DAYS,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

NO_LASTFM = {
    CONF_LASTFM_USERNAME: "",
    CONF_LASTFM_API_KEY: "",
    CONF_LASTFM_POLL_ENABLED: False,
    CONF_LASTFM_POLL_INTERVAL_HOURS: 1,
}

VALID = {
    CONF_RECENCY_HALF_LIFE_DAYS: 548,
    CONF_OBSCURITY_PERCENTILE: "25",
    CONF_MIN_SECONDS_PLAYED: 30,
    CONF_REBUILD_SCHEDULE_HOUR: 4,
    CONF_ENRICH_ENABLED: False,
    SECTION_LASTFM: NO_LASTFM,
}

# what saving VALID stores: flat, typed, Last.fm off
STORED = {
    CONF_RECENCY_HALF_LIFE_DAYS: 548,
    CONF_OBSCURITY_PERCENTILE: 25,
    CONF_MIN_SECONDS_PLAYED: 30,
    CONF_REBUILD_SCHEDULE_HOUR: 4,
    CONF_ENRICH_ENABLED: False,
    CONF_LASTFM_USERNAME: "",
    CONF_LASTFM_API_KEY: "",
    CONF_LASTFM_POLL_ENABLED: False,
    CONF_LASTFM_POLL_INTERVAL_HOURS: 1,
}

KEY = "0123456789abcdef0123456789abcdef"
LASTFM_URL = "https://ws.audioscrobbler.com/2.0/"
ONE_SCROBBLE = {
    "recenttracks": {
        "@attr": {"page": "1", "totalPages": "1"},
        "track": [
            {
                "artist": {"#text": "Sigur Rós"},
                "name": "Svefn-g-englar",
                "album": {"#text": ""},
                "date": {"uts": "1790000000"},
            }
        ],
    }
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
    defaults: dict[str, object] = {}
    for key, value in result["data_schema"].schema.items():
        if key.schema == SECTION_LASTFM:
            defaults[key.schema] = {inner.schema: inner.default() for inner in value.schema.schema}
        else:
            defaults[key.schema] = key.default()
    return defaults


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
        SECTION_LASTFM: NO_LASTFM,
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
    assert loaded.options == {**STORED, CONF_REBUILD_SCHEDULE_HOUR: 6}
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


# --- Last.fm (2c) ---------------------------------------------------------------------------


def _with_lastfm(**lastfm: object) -> dict[str, object]:
    return {**VALID, SECTION_LASTFM: {**NO_LASTFM, **lastfm}}


# NB: `aioclient_mock` is requested BEFORE `loaded` everywhere here - it has to patch Home
# Assistant's client session before the entry's setup creates it, or requests go to the network


async def test_lastfm_credentials_are_checked_with_lastfm_and_saved(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, loaded: MockConfigEntry
) -> None:
    aioclient_mock.get(LASTFM_URL, json=ONE_SCROBBLE)
    result = await hass.config_entries.options.async_init(loaded.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        _with_lastfm(
            **{
                CONF_LASTFM_USERNAME: "Bob_Baird",
                CONF_LASTFM_API_KEY: KEY,
                CONF_LASTFM_POLL_ENABLED: True,
            }
        ),
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert loaded.options[CONF_LASTFM_USERNAME] == "Bob_Baird"
    assert loaded.options[CONF_LASTFM_API_KEY] == KEY
    assert loaded.options[CONF_LASTFM_POLL_ENABLED] is True
    assert aioclient_mock.call_count == 1


async def test_the_api_key_is_never_sent_back_to_the_form(
    hass: HomeAssistant, loaded: MockConfigEntry
) -> None:
    hass.config_entries.async_update_entry(
        loaded,
        options={**STORED, CONF_LASTFM_USERNAME: "Bob_Baird", CONF_LASTFM_API_KEY: KEY},
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(loaded.entry_id)
    lastfm = _defaults(result)[SECTION_LASTFM]
    assert lastfm[CONF_LASTFM_USERNAME] == "Bob_Baird"
    assert lastfm[CONF_LASTFM_API_KEY] == ""
    assert KEY not in repr(result)


async def test_an_empty_key_field_keeps_the_saved_key_without_asking_lastfm(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, loaded: MockConfigEntry
) -> None:
    hass.config_entries.async_update_entry(
        loaded,
        options={**STORED, CONF_LASTFM_USERNAME: "Bob_Baird", CONF_LASTFM_API_KEY: KEY},
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(loaded.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        _with_lastfm(**{CONF_LASTFM_USERNAME: "Bob_Baird", CONF_LASTFM_POLL_INTERVAL_HOURS: 3}),
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert loaded.options[CONF_LASTFM_API_KEY] == KEY
    assert loaded.options[CONF_LASTFM_POLL_INTERVAL_HOURS] == 3
    assert aioclient_mock.call_count == 0


async def test_clearing_the_username_forgets_the_key(
    hass: HomeAssistant, loaded: MockConfigEntry
) -> None:
    hass.config_entries.async_update_entry(
        loaded,
        options={**STORED, CONF_LASTFM_USERNAME: "Bob_Baird", CONF_LASTFM_API_KEY: KEY},
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(loaded.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], VALID)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert loaded.options[CONF_LASTFM_API_KEY] == ""


@pytest.mark.parametrize(
    ("lastfm", "error"),
    [
        (
            {CONF_LASTFM_USERNAME: "Bob_Baird", CONF_LASTFM_API_KEY: "not-a-key"},
            "lastfm_key_format",
        ),
        ({CONF_LASTFM_USERNAME: "Bob_Baird"}, "lastfm_key_missing"),
        ({CONF_LASTFM_POLL_ENABLED: True}, "lastfm_poll_needs_account"),
    ],
)
async def test_lastfm_form_errors_are_caught_before_asking_lastfm(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    loaded: MockConfigEntry,
    lastfm: dict[str, object],
    error: str,
) -> None:
    result = await hass.config_entries.options.async_init(loaded.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], _with_lastfm(**lastfm)
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert "not-a-key" not in repr(result)
    assert aioclient_mock.call_count == 0
    assert loaded.options == {}


async def test_lastfm_refusal_is_shown_without_the_key(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, loaded: MockConfigEntry
) -> None:
    aioclient_mock.get(
        LASTFM_URL,
        status=403,
        json={"error": 10, "message": "Invalid API key - You must be granted a valid key"},
    )
    result = await hass.config_entries.options.async_init(loaded.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        _with_lastfm(**{CONF_LASTFM_USERNAME: "Bob_Baird", CONF_LASTFM_API_KEY: KEY}),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "lastfm_rejected"}
    assert "API key" in result["description_placeholders"]["reason"]
    assert KEY not in repr(result)
    assert loaded.options == {}
