"""Tests for the user-facing controls: the Rebuild button and the websocket commands."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.button import SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.exceptions import HomeAssistantError

from custom_components.listening_genome.core.constants import RESOLVE_STATE_ERROR
from custom_components.listening_genome.core.models import Listen

from .conftest import PLAYED_AT

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
    from pytest_homeassistant_custom_component.typing import WebSocketGenerator

BUTTON = "button.listening_genome_rebuild_now"
FROZEN_NOW = "2026-09-25T12:00:00+00:00"
LATER = "2026-09-25T13:00:00+00:00"


def _listen(track: str) -> Listen:
    return Listen(
        played_at=PLAYED_AT + 60,
        artist_key="beta",
        artist_name="Beta",
        track_key=track.lower(),
        track_name=track,
        album_name=None,
        source="apple_export",
        player_id=None,
        duration_ms=200_000,
        played_ms=200_000,
        fully_played=True,
        confidence=1.0,
    )


@pytest.fixture
async def loaded(
    hass: HomeAssistant,
    genome_entry: MockConfigEntry,
    seeded_store: object,
    test_baseline: object,
    freezer: object,
    music_apis: AiohttpClientMocker,
) -> MockConfigEntry:
    """The seeded entry, loaded with enrichment on; every HTTP request is a fixture."""
    freezer.move_to(FROZEN_NOW)  # type: ignore[attr-defined]
    genome_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(genome_entry.entry_id)
    await hass.async_block_till_done()
    return genome_entry


async def test_button_rebuilds_and_updates_the_sensors(
    hass: HomeAssistant, loaded: MockConfigEntry, freezer: object
) -> None:
    state = hass.states.get(BUTTON)
    assert state is not None
    assert state.attributes["friendly_name"] == "Listening Genome Rebuild now"
    runtime = loaded.runtime_data
    await runtime.store.add_listens([_listen("Five")], listener="household")
    freezer.move_to(LATER)  # type: ignore[attr-defined]

    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: BUTTON}, blocking=True
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("sensor.listening_genome_listens_stored").state == "5"
    assert hass.states.get("sensor.listening_genome_top_artist").state == "Alpha"
    assert hass.states.get("sensor.listening_genome_last_rebuild").state == LATER
    assert runtime.jobs.get("rebuild")["state"] == "ok"
    # and, as the fork's rebuild did, it started an enrichment pass (nothing was due)
    enrichment = runtime.jobs.get("enrichment")
    assert enrichment["state"] == "ok"
    assert enrichment["started_at"] == 1_790_341_200


async def test_button_reports_a_failed_rebuild(
    hass: HomeAssistant, loaded: MockConfigEntry
) -> None:
    runtime = loaded.runtime_data
    with (
        patch.object(runtime.service, "rebuild_with_stats", side_effect=RuntimeError("disk")),
        pytest.raises(HomeAssistantError, match="could not be rebuilt: disk"),
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: BUTTON}, blocking=True
        )
    assert runtime.jobs.get("rebuild")["state"] == "error"


async def test_last_rebuild_sensor_reports_stale(
    hass: HomeAssistant, loaded: MockConfigEntry
) -> None:
    runtime = loaded.runtime_data
    assert hass.states.get("sensor.listening_genome_last_rebuild").attributes["stale"] is False
    await runtime.store.add_listens([_listen("Five")], listener="household")
    await runtime.coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.listening_genome_last_rebuild").attributes["stale"] is True
    assert hass.states.get("sensor.listening_genome_listens_stored").state == "4"


async def test_ws_rebuild(
    hass: HomeAssistant,
    loaded: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    freezer: object,
) -> None:
    runtime = loaded.runtime_data
    await runtime.store.add_listens([_listen("Five")], listener="household")
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "listening_genome/rebuild", "enrich": False})
    msg = await client.receive_json()
    assert msg["success"], msg
    result = msg["result"]
    assert result["listener"] == "household"
    assert result["listens_scanned"] == 5
    assert result["genome"]["stats"]["total_listens"] == 5
    assert runtime.coordinator.data == result["genome"]
    assert hass.states.get("sensor.listening_genome_listens_stored").state == "5"
    await hass.async_block_till_done(wait_background_tasks=True)
    assert runtime.jobs.get("enrichment")["state"] == "idle"  # enrich: false
    await client.close()


async def test_ws_rebuild_needs_an_admin(
    hass: HomeAssistant,
    loaded: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    client = await hass_ws_client(hass, hass_read_only_access_token)
    for command in (
        {"type": "listening_genome/rebuild"},
        {"type": "listening_genome/retry_artists"},
        {"type": "listening_genome/dismiss_unresolved"},
    ):
        await client.send_json_auto_id(command)
        msg = await client.receive_json()
        assert not msg["success"], command
        assert msg["error"]["code"] == "unauthorized", command


async def test_ws_jobs(
    hass: HomeAssistant,
    loaded: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    music_apis: AiohttpClientMocker,
) -> None:
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "listening_genome/jobs"})
    msg = await client.receive_json()
    assert msg["success"], msg
    assert set(msg["result"]) == {
        "rebuild",
        "enrichment",
        "lastfm_import",
        "apple_import",
        "duplicates",
        "discovery",
    }
    # setup rebuilt (no cache yet), and that is recorded
    assert msg["result"]["rebuild"]["state"] == "ok"
    assert msg["result"]["rebuild"]["message"].startswith("Rebuilt from 4 stored listens")
    assert msg["result"]["enrichment"]["state"] == "idle"
    assert music_apis.call_count == 0


async def _fail_beta_and_gamma(loaded: MockConfigEntry) -> None:
    store = loaded.runtime_data.store
    await store.upsert_artist_meta_full(
        [
            {"artist_key": "beta", "artist_name": "Beta"},
            {"artist_key": "gamma", "artist_name": "Gamma"},
        ],
        state=RESOLVE_STATE_ERROR,
    )


async def test_ws_unresolved_artists(
    hass: HomeAssistant,
    loaded: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    music_apis: AiohttpClientMocker,
) -> None:
    await _fail_beta_and_gamma(loaded)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "listening_genome/unresolved_artists"})
    msg = await client.receive_json()
    assert msg["success"], msg
    assert {row["artist_name"] for row in msg["result"]} == {"Beta", "Gamma"}
    await client.send_json_auto_id({"type": "listening_genome/unresolved_artists", "limit": 1})
    msg = await client.receive_json()
    assert len(msg["result"]) == 1
    await client.send_json_auto_id({"type": "listening_genome/unresolved_artists", "limit": 0})
    msg = await client.receive_json()
    assert msg["error"]["code"] == "invalid_format"
    assert music_apis.call_count == 0


async def test_ws_retry_artists(
    hass: HomeAssistant,
    loaded: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    music_apis: AiohttpClientMocker,
) -> None:
    await _fail_beta_and_gamma(loaded)
    store = loaded.runtime_data.store
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "listening_genome/retry_artists", "artist_keys": ["gamma"]}
    )
    msg = await client.receive_json()
    assert msg == {**msg, "success": True, "result": 1}
    assert [row["artist_key"] for row in await store.failed_artist_keys()] == ["beta"]
    assert ("gamma", "Gamma") in await store.pending_artist_keys()

    await client.send_json_auto_id({"type": "listening_genome/retry_artists"})
    msg = await client.receive_json()
    assert msg["result"] == 1
    assert await store.failed_artist_keys() == []
    # it only moves them back to the queue: the MusicBrainz work is the next pass's
    await hass.async_block_till_done(wait_background_tasks=True)
    assert music_apis.call_count == 0


async def test_ws_dismiss_unresolved(
    hass: HomeAssistant,
    loaded: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    music_apis: AiohttpClientMocker,
) -> None:
    await _fail_beta_and_gamma(loaded)
    store = loaded.runtime_data.store
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "listening_genome/dismiss_unresolved"})
    msg = await client.receive_json()
    assert msg["success"], msg
    assert msg["result"] is True
    assert await store.unresolved_dismissed_keys() == frozenset({"beta", "gamma"})
    # a newly failing artist brings the notice back (the fork's fingerprint rule)
    await store.upsert_artist_meta_full(
        [{"artist_key": "alpha", "artist_name": "Alpha"}], state=RESOLVE_STATE_ERROR
    )
    genome = await loaded.runtime_data.service.rebuild()
    assert genome["stats"]["unresolved_dismissed"] is False
    assert music_apis.call_count == 0


@pytest.mark.parametrize(
    "command",
    [
        {"type": "listening_genome/rebuild"},
        {"type": "listening_genome/jobs"},
        {"type": "listening_genome/unresolved_artists"},
        {"type": "listening_genome/retry_artists"},
        {"type": "listening_genome/dismiss_unresolved"},
    ],
)
async def test_ws_commands_error_when_not_loaded(
    hass: HomeAssistant,
    loaded: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    command: dict[str, str],
) -> None:
    assert await hass.config_entries.async_unload(loaded.entry_id)
    await hass.async_block_till_done()
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(command)
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "not_found"
