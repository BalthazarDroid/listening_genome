"""Discovery through Home Assistant (2d): the read, the refresh, the speaker menu, and play."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.listening_genome.core.discovery import LibraryArtist

if TYPE_CHECKING:
    from pathlib import Path

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.typing import WebSocketGenerator

OFFICE = "media_player.office_speaker"
KITCHEN = "media_player.kitchen_speaker"


@pytest.fixture
async def loaded(
    hass: HomeAssistant, genome_entry: MockConfigEntry, seeded_store: Path, test_baseline: object
) -> MockConfigEntry:
    genome_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(genome_entry.entry_id)
    await hass.async_block_till_done()
    return genome_entry


@pytest.fixture
def speakers(hass: HomeAssistant) -> None:
    """Two Music Assistant speakers, and one media player from another integration."""
    registry = er.async_get(hass)
    for entity_id, name in ((OFFICE, "Office speaker"), (KITCHEN, "Kitchen speaker")):
        object_id = entity_id.split(".")[1]
        registry.async_get_or_create(
            "media_player", "music_assistant", object_id, suggested_object_id=object_id
        )
        hass.states.async_set(entity_id, "idle", {"friendly_name": name})
    registry.async_get_or_create("media_player", "cast", "tv", suggested_object_id="tv")
    hass.states.async_set("media_player.tv", "idle", {"friendly_name": "TV"})


@pytest.fixture
def play_media(hass: HomeAssistant) -> list[ServiceCall]:
    """Stand in for Music Assistant's play_media action; fails for a song called "Missing"."""
    calls: list[ServiceCall] = []

    async def handle(call: ServiceCall) -> None:
        if call.data["media_id"] == "Missing":
            raise HomeAssistantError("Could not resolve ['Missing'] to playable media item")
        calls.append(call)

    hass.services.async_register("music_assistant", "play_media", handle)
    return calls


async def test_players_lists_only_music_assistant_speakers(
    hass: HomeAssistant, loaded: MockConfigEntry, speakers: None, hass_ws_client: WebSocketGenerator
) -> None:
    ws = await hass_ws_client(hass)
    await ws.send_json_auto_id({"type": "listening_genome/players"})
    msg = await ws.receive_json()
    assert msg["success"], msg
    assert [p["entity_id"] for p in msg["result"]["players"]] == [KITCHEN, OFFICE]
    assert msg["result"]["last_used"] is None


async def test_play_plays_one_song_and_remembers_the_speaker(
    hass: HomeAssistant,
    loaded: MockConfigEntry,
    speakers: None,
    play_media: list[ServiceCall],
    hass_ws_client: WebSocketGenerator,
) -> None:
    ws = await hass_ws_client(hass)
    await ws.send_json_auto_id(
        {
            "type": "listening_genome/play",
            "entity_id": OFFICE,
            "artist": "Deerhunter",
            "song": "Desire Lines",
        }
    )
    msg = await ws.receive_json()
    assert msg["success"], msg
    [call] = play_media
    assert call.data == {
        "entity_id": OFFICE,
        "media_id": "Desire Lines",
        "media_type": "track",
        "artist": "Deerhunter",
        # just that one song: the queue is replaced, no radio after it
        "enqueue": "replace",
        "radio_mode": False,
    }
    # played as the person who clicked
    assert call.context.user_id is not None
    await ws.send_json_auto_id({"type": "listening_genome/players"})
    assert (await ws.receive_json())["result"]["last_used"] == OFFICE


async def test_a_song_music_assistant_cannot_find_is_reported(
    hass: HomeAssistant,
    loaded: MockConfigEntry,
    speakers: None,
    play_media: list[ServiceCall],
    hass_ws_client: WebSocketGenerator,
) -> None:
    ws = await hass_ws_client(hass)
    await ws.send_json_auto_id(
        {"type": "listening_genome/play", "entity_id": OFFICE, "artist": "X", "song": "Missing"}
    )
    msg = await ws.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "play_failed"
    assert "Could not resolve" in msg["error"]["message"]


async def test_play_refuses_a_media_player_that_is_not_music_assistants(
    hass: HomeAssistant,
    loaded: MockConfigEntry,
    speakers: None,
    play_media: list[ServiceCall],
    hass_ws_client: WebSocketGenerator,
) -> None:
    ws = await hass_ws_client(hass)
    await ws.send_json_auto_id(
        {
            "type": "listening_genome/play",
            "entity_id": "media_player.tv",
            "artist": "X",
            "song": "Y",
        }
    )
    msg = await ws.receive_json()
    assert msg["error"]["code"] == "not_a_speaker"
    assert play_media == []


class _Library:
    async def artists(self) -> list[LibraryArtist]:
        return [LibraryArtist("tame impala", "Tame Impala", ("rock",), ref=1)]

    async def track_names(self, artist: LibraryArtist) -> list[str]:
        return ["Let It Happen"]


async def test_refresh_then_read_serves_what_the_pass_stored(
    hass: HomeAssistant, loaded: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    runtime = loaded.runtime_data
    ws = await hass_ws_client(hass)
    with (
        patch(
            "custom_components.listening_genome.runtime.MusicAssistantLibrary",
            return_value=_Library(),
        ),
        patch.object(type(runtime.capture), "client", new=object()),
    ):
        await ws.send_json_auto_id({"type": "listening_genome/discovery_refresh"})
        msg = await ws.receive_json()
        assert msg["success"], msg
        await asyncio.gather(*runtime._tasks)
    assert runtime.jobs.get("discovery")["state"] == "ok"
    await ws.send_json_auto_id({"type": "listening_genome/discovery"})
    result = (await ws.receive_json())["result"]
    # no Last.fm account in this entry: suggestions unavailable, the library half still there
    assert result["suggested_state"] == "unavailable"
    assert [(row["artist_name"], row["song"]) for row in result["in_library"]] == [
        ("Tame Impala", "Let It Happen")
    ]
