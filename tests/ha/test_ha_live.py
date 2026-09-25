"""
Live capture, Last.fm and Apple imports, and the duplicate cleanup, through Home Assistant (2c).

Music Assistant is a fake client (:class:`FakeMusicAssistant`) that does what the real one does
at its public edge: ``subscribe``, ``connect``, ``start_listening`` until disconnected,
``players``. Events are the wire form a real server sends (``MassEvent`` with a ``dict`` payload).
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON
from music_assistant_models.enums import EventType
from music_assistant_models.event import MassEvent
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.listening_genome.core.constants import (
    CONF_LASTFM_API_KEY,
    CONF_LASTFM_POLL_ENABLED,
    CONF_LASTFM_POLL_INTERVAL_HOURS,
    CONF_LASTFM_USERNAME,
)
from custom_components.listening_genome.core.models import Listen
from custom_components.listening_genome.core.store import GenomeStore

from .conftest import PLAYED_AT

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
    from pytest_homeassistant_custom_component.typing import WebSocketGenerator

CONNECTION = "binary_sensor.listening_genome_music_assistant_connection"
KEY = "0123456789abcdef0123456789abcdef"
T0 = 1_790_100_000.0


@dataclass
class FakePlayer:
    player_id: str
    name: str


@dataclass
class FakeServerInfo:
    server_version: str = "2.9.0"


class FakeMusicAssistant:
    """The public surface of ``MusicAssistantClient`` live capture uses."""

    instances: list[FakeMusicAssistant] = []  # noqa: RUF012 - per-test, reset by the fixture
    refuse = False

    def __init__(self, url: str, session: Any, token: str | None) -> None:
        self.url = url
        self.token = token
        self.server_info: FakeServerInfo | None = None
        self.players = [FakePlayer("kitchen", "Kitchen speaker")]
        self._subscribers: list[tuple[Callable[[MassEvent], None], tuple[EventType, ...]]] = []
        self._closed = asyncio.Event()
        FakeMusicAssistant.instances.append(self)

    def subscribe(
        self, callback: Callable[[MassEvent], None], event_filter: Any = None
    ) -> Callable[[], None]:
        filters = (event_filter,) if isinstance(event_filter, EventType) else tuple(event_filter)
        entry = (callback, filters)
        self._subscribers.append(entry)
        return lambda: self._subscribers.remove(entry)

    async def connect(self) -> None:
        if FakeMusicAssistant.refuse:
            raise ConnectionRefusedError("Connection refused")
        self.server_info = FakeServerInfo()

    async def start_listening(self, init_ready: asyncio.Event | None = None) -> None:
        if init_ready is not None:
            init_ready.set()
        await self._closed.wait()

    async def disconnect(self) -> None:
        self._closed.set()

    def drop(self) -> None:
        """The server went away: ``start_listening`` returns, as on ConnectionClosed."""
        self._closed.set()

    def emit(self, event: EventType, data: dict[str, Any]) -> None:
        message = MassEvent(event=event, object_id=data.get("uri"), data=data)
        for callback, filters in list(self._subscribers):
            if event in filters:
                callback(message)


def _progress(**overrides: Any) -> dict[str, Any]:
    """A ``media_item_played`` payload as MA sends it (MediaItemPlaybackProgressReport)."""
    data: dict[str, Any] = {
        "uri": "library://track/7",
        "media_type": "track",
        "name": "Bohemian Like You",
        "artist": "The Dandy Warhols",
        "artists": ["The Dandy Warhols"],
        "album": "Thirteen Tales from Urban Bohemia",
        "duration": 211,
        "seconds_played": 30,
        "fully_played": False,
        "is_playing": True,
        "userid": "bob",
        "player_id": "kitchen",
    }
    data.update(overrides)
    return data


@pytest.fixture
def fake_ma() -> Iterator[type[FakeMusicAssistant]]:
    """Every capture connects to a :class:`FakeMusicAssistant` instead of a real server."""
    FakeMusicAssistant.instances = []
    FakeMusicAssistant.refuse = False
    with patch(
        "custom_components.listening_genome.live_capture._default_client_factory",
        new=FakeMusicAssistant,
    ):
        yield FakeMusicAssistant


@pytest.fixture
def ma_entry(hass: HomeAssistant) -> MockConfigEntry:
    """The linked Music Assistant entry: only its URL and token are read."""
    entry = MockConfigEntry(
        domain="music_assistant",
        entry_id="ma-entry-1",
        title="Music Assistant",
        data={"url": "http://ma.local:8095", "token": "ma-token"},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def loaded(
    hass: HomeAssistant,
    fake_ma: type[FakeMusicAssistant],
    ma_entry: MockConfigEntry,
    genome_entry: MockConfigEntry,
    seeded_store: Path,
    test_baseline: object,
) -> MockConfigEntry:
    genome_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(genome_entry.entry_id)
    await hass.async_block_till_done()
    return genome_entry


async def _listens(hass: HomeAssistant, entry: MockConfigEntry) -> list[Listen]:
    return [listen async for listen in entry.runtime_data.store.iter_listens("household")]


async def _settle(hass: HomeAssistant) -> None:
    """Let the capture's background writes finish (not the listening task: it never ends)."""
    await hass.async_block_till_done()
    writes = list(
        hass.config_entries.async_loaded_entries("listening_genome")[0].runtime_data.capture._writes
    )
    if writes:
        await asyncio.gather(*writes)


# --- live capture -----------------------------------------------------------------------------


async def test_capture_connects_with_the_ma_entrys_url_and_token(
    hass: HomeAssistant, loaded: MockConfigEntry, fake_ma: type[FakeMusicAssistant]
) -> None:
    [client] = fake_ma.instances
    assert (client.url, client.token) == ("http://ma.local:8095", "ma-token")
    state = hass.states.get(CONNECTION)
    assert state.state == STATE_ON
    assert state.attributes["server_version"] == "2.9.0"
    assert state.attributes["plays_captured"] == 0


async def test_a_played_track_becomes_one_stored_listen_with_its_room(
    hass: HomeAssistant, loaded: MockConfigEntry, fake_ma: type[FakeMusicAssistant]
) -> None:
    runtime = loaded.runtime_data
    now = [T0]
    runtime.capture.clock = lambda: now[0]
    [client] = fake_ma.instances
    for elapsed in (30, 60, 90, 120, 150, 180):
        now[0] = T0 + elapsed
        client.emit(EventType.MEDIA_ITEM_PLAYED, _progress(seconds_played=elapsed))
    now[0] = T0 + 211
    client.emit(
        EventType.MEDIA_ITEM_PLAYED,
        _progress(seconds_played=209, fully_played=True, is_playing=False),
    )
    await _settle(hass)

    live = [listen for listen in await _listens(hass, loaded) if listen.source == "ma_playlog"]
    assert len(live) == 1
    assert live[0].played_at == int(T0)
    assert live[0].player_id == "kitchen"
    assert live[0].artist_key == "the dandy warhols"
    assert live[0].fully_played is True
    state = hass.states.get(CONNECTION)
    assert state.attributes["plays_captured"] == 1
    assert state.attributes["last_play"] == "The Dandy Warhols - Bohemian Like You"
    # the room is named the way Music Assistant names the player
    assert await runtime.store.player_names() == {"kitchen": "Kitchen speaker"}


async def test_radio_and_podcasts_are_not_captured(
    hass: HomeAssistant, loaded: MockConfigEntry, fake_ma: type[FakeMusicAssistant]
) -> None:
    [client] = fake_ma.instances
    client.emit(
        EventType.MEDIA_ITEM_PLAYED,
        _progress(media_type="radio", seconds_played=600, fully_played=True, is_playing=False),
    )
    await _settle(hass)
    assert all(listen.source != "ma_playlog" for listen in await _listens(hass, loaded))


async def test_a_track_still_playing_is_written_when_the_integration_unloads(
    hass: HomeAssistant, loaded: MockConfigEntry, fake_ma: type[FakeMusicAssistant]
) -> None:
    [client] = fake_ma.instances
    client.emit(EventType.MEDIA_ITEM_PLAYED, _progress(seconds_played=95))
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(loaded.entry_id)
    store = GenomeStore(hass.config.path("listening_genome"))
    await store.setup()
    try:
        counts = await store.source_counts("household")
    finally:
        await store.close()
    assert counts.get("ma_playlog") == 1


async def test_a_dropped_connection_turns_the_sensor_off_and_reconnects(
    hass: HomeAssistant, loaded: MockConfigEntry, fake_ma: type[FakeMusicAssistant]
) -> None:
    [first] = fake_ma.instances
    first.drop()
    await hass.async_block_till_done()
    state = hass.states.get(CONNECTION)
    assert state.state == STATE_OFF
    assert "closed the connection" in state.attributes["last_error"]
    # the retry is a timer, not a sleeping task: fire it
    runtime = loaded.runtime_data
    assert runtime.capture._unsub_retry is not None
    runtime.capture._attempt()
    await hass.async_block_till_done()
    assert len(fake_ma.instances) == 2
    assert hass.states.get(CONNECTION).state == STATE_ON


async def test_music_assistant_down_at_start_up_does_not_block_setup(
    hass: HomeAssistant,
    fake_ma: type[FakeMusicAssistant],
    ma_entry: MockConfigEntry,
    genome_entry: MockConfigEntry,
    seeded_store: Path,
    test_baseline: object,
) -> None:
    fake_ma.refuse = True
    genome_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(genome_entry.entry_id)
    await hass.async_block_till_done()
    assert genome_entry.state is ConfigEntryState.LOADED
    state = hass.states.get(CONNECTION)
    assert state.state == STATE_OFF
    assert "ConnectionRefusedError" in state.attributes["last_error"]
    # the genome is still served
    assert hass.states.get("sensor.listening_genome_listens_stored").state == "4"


async def test_a_missing_music_assistant_entry_is_reported_not_raised(
    hass: HomeAssistant,
    fake_ma: type[FakeMusicAssistant],
    genome_entry: MockConfigEntry,
    seeded_store: Path,
    test_baseline: object,
) -> None:
    genome_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(genome_entry.entry_id)
    await hass.async_block_till_done()
    assert fake_ma.instances == []
    state = hass.states.get(CONNECTION)
    assert state.state == STATE_OFF
    assert "was not found" in state.attributes["last_error"]


async def test_ws_live_reports_the_connection(
    hass: HomeAssistant, loaded: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "listening_genome/live"})
    msg = await client.receive_json()
    assert msg["success"], msg
    assert msg["result"]["connected"] is True
    assert msg["result"]["server_version"] == "2.9.0"


# --- one-time duplicate cleanup ----------------------------------------------------------------


@pytest.fixture
async def doubled_store(seeded_store: Path) -> Path:
    """Two of the seeded Apple plays also scrobbled to Last.fm the same day."""
    store = GenomeStore(str(seeded_store))
    await store.setup()
    try:
        await store.add_listens(
            [
                Listen(
                    played_at=PLAYED_AT + 600 * n,
                    artist_key="alpha",
                    artist_name="Alpha",
                    track_key=track,
                    track_name=track.title(),
                    album_name=None,
                    source="lastfm",
                    player_id=None,
                    duration_ms=None,
                    played_ms=None,
                    fully_played=None,
                    confidence=1.0,
                )
                for n, track in enumerate(("one", "two"), start=1)
            ],
            listener="household",
        )
    finally:
        await store.close()
    return seeded_store


async def test_setup_removes_existing_doubles_once_and_rebuilds(
    hass: HomeAssistant,
    fake_ma: type[FakeMusicAssistant],
    ma_entry: MockConfigEntry,
    genome_entry: MockConfigEntry,
    doubled_store: Path,
    test_baseline: object,
) -> None:
    genome_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(genome_entry.entry_id)
    await hass.async_block_till_done()
    await asyncio.gather(*genome_entry.runtime_data._tasks)
    runtime = genome_entry.runtime_data
    job = runtime.jobs.get("duplicates")
    assert job["state"] == "ok"
    assert job["message"].startswith("Removed 2 Last.fm plays")
    assert await runtime.store.source_counts("household") == {"apple_export": 4}
    # the sensors show the corrected genome: rebuilt from 4, not 6
    assert hass.states.get("sensor.listening_genome_listens_stored").state == "4"

    # a reload does not run it again
    await hass.config_entries.async_reload(genome_entry.entry_id)
    await hass.async_block_till_done()
    assert genome_entry.runtime_data.jobs.get("duplicates")["started_at"] == job["started_at"]


# --- Last.fm -----------------------------------------------------------------------------------

LASTFM = re.compile(r"^https://ws\.audioscrobbler\.com/2\.0/")


def _scrobbles(*tracks: tuple[str, str, int]) -> dict[str, Any]:
    return {
        "recenttracks": {
            "@attr": {"page": "1", "totalPages": "1"},
            "track": [
                {
                    "artist": {"#text": artist},
                    "name": name,
                    "album": {"#text": ""},
                    "date": {"uts": str(uts)},
                }
                for artist, name, uts in tracks
            ],
        }
    }


@pytest.fixture
async def with_lastfm(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    fake_ma: type[FakeMusicAssistant],
    ma_entry: MockConfigEntry,
    seeded_store: Path,
    test_baseline: object,
) -> MockConfigEntry:
    """A loaded entry with a Last.fm account (poll off, so only explicit imports run)."""
    entry = MockConfigEntry(
        domain="listening_genome",
        title="Listening Genome",
        data={"ma_entry_id": "ma-entry-1"},
        entry_id="genome-entry-1",
        options={
            CONF_LASTFM_USERNAME: "Bob_Baird",
            CONF_LASTFM_API_KEY: KEY,
            CONF_LASTFM_POLL_ENABLED: False,
            CONF_LASTFM_POLL_INTERVAL_HOURS: 1,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_ws_import_lastfm_imports_and_removes_mas_own_scrobble(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    with_lastfm: MockConfigEntry,
    fake_ma: type[FakeMusicAssistant],
    hass_ws_client: WebSocketGenerator,
) -> None:
    runtime = with_lastfm.runtime_data
    # a play captured live from MA...
    now = [T0]
    runtime.capture.clock = lambda: now[0]
    [client] = fake_ma.instances
    client.emit(EventType.MEDIA_ITEM_PLAYED, _progress(seconds_played=30))
    now[0] = T0 + 211
    client.emit(
        EventType.MEDIA_ITEM_PLAYED,
        _progress(seconds_played=209, fully_played=True, is_playing=False),
    )
    await _settle(hass)
    # ...which MA's scrobbler sent to Last.fm when it finished, plus one from elsewhere
    aioclient_mock.get(
        LASTFM,
        json=_scrobbles(
            ("The Dandy Warhols", "Bohemian Like You", int(T0) + 212),
            ("Sigur Rós", "Svefn-g-englar", int(T0) + 5000),
        ),
    )
    ws = await hass_ws_client(hass)
    await ws.send_json_auto_id({"type": "listening_genome/import_lastfm"})
    msg = await ws.receive_json()
    assert msg["success"], msg
    assert msg["result"]["state"] == "running"
    await asyncio.gather(*runtime._tasks)
    await hass.async_block_till_done()

    job = runtime.jobs.get("lastfm_import")
    assert job["state"] == "ok", job
    assert "2 imported" in job["message"]
    assert "1 Last.fm plays removed" in job["message"]
    assert KEY not in job["message"]
    counts = await runtime.store.source_counts("household")
    assert counts == {"apple_export": 4, "ma_playlog": 1, "lastfm": 1}
    # an import that added listens is followed by a rebuild
    assert hass.states.get("sensor.listening_genome_listens_stored").state == "6"
    # the API key only ever went to Last.fm, as a query parameter
    assert all(str(call[1].host) == "ws.audioscrobbler.com" for call in aioclient_mock.mock_calls)


async def test_ws_import_lastfm_without_an_account_says_so(
    hass: HomeAssistant, loaded: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    ws = await hass_ws_client(hass)
    await ws.send_json_auto_id({"type": "listening_genome/import_lastfm"})
    msg = await ws.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "not_configured"


async def test_polling_on_schedules_an_early_poll_and_the_interval(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    with_lastfm: MockConfigEntry,
) -> None:
    aioclient_mock.get(LASTFM, json=_scrobbles())
    hass.config_entries.async_update_entry(
        with_lastfm, options={**with_lastfm.options, CONF_LASTFM_POLL_ENABLED: True}
    )
    await hass.config_entries.async_reload(with_lastfm.entry_id)
    await hass.async_block_till_done()
    runtime = with_lastfm.runtime_data
    # daily rebuild, hourly enrichment, the Last.fm interval and its start-up one-shot
    assert len(runtime._unsubscribers) == 4
    runtime._handle_lastfm_interval(None)
    await asyncio.gather(*runtime._tasks)
    assert runtime.jobs.get("lastfm_import")["state"] == "ok"
    assert aioclient_mock.call_count == 1


# --- Apple Music -------------------------------------------------------------------------------

DAILY_TRACKS = (
    "Country,Track Identifier,Media type,Date Played,Hours,Play Duration Milliseconds,"
    "Source Type,Play Count,Skip Count,Ignore For Recommendations,Track Reference,"
    "Track Description\n"
    "US,1,AUDIO,20260920,14,420000,IPHONE,2,0,,1,Sigur Rós - Hoppípolla\n"
)


async def test_import_apple_csv_action_imports_a_file_under_media(
    hass: HomeAssistant, loaded: MockConfigEntry, tmp_path: Path
) -> None:
    csv_path = tmp_path / "Apple Music - Play History Daily Tracks.csv"
    await hass.async_add_executor_job(csv_path.write_text, DAILY_TRACKS, "utf-8")
    hass.config.allowlist_external_dirs = {str(tmp_path)}
    await hass.services.async_call(
        "listening_genome", "import_apple_csv", {"path": str(csv_path)}, blocking=True
    )
    runtime = loaded.runtime_data
    await asyncio.gather(*runtime._tasks)
    job = runtime.jobs.get("apple_import")
    assert job["state"] == "ok", job
    assert "2 imported" in job["message"]
    assert (await runtime.store.source_counts("household"))["apple_export"] == 6
    # the user's own file is left where it was
    assert await hass.async_add_executor_job(csv_path.exists)


async def test_import_apple_csv_refuses_a_path_home_assistant_may_not_read(
    hass: HomeAssistant, loaded: MockConfigEntry
) -> None:
    from homeassistant.exceptions import ServiceValidationError

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "listening_genome", "import_apple_csv", {"path": "/etc/passwd"}, blocking=True
        )


async def test_ws_import_apple_takes_an_upload_and_removes_its_copy(
    hass: HomeAssistant, loaded: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    upload = Path(hass.config.path("upload-source.csv"))
    await hass.async_add_executor_job(upload.write_text, DAILY_TRACKS, "utf-8")

    from contextlib import contextmanager

    @contextmanager
    def fake_upload(_hass: HomeAssistant, file_id: str) -> Iterator[Path]:
        assert file_id == "upload-1"
        yield upload

    with patch("custom_components.listening_genome.uploads.process_uploaded_file", fake_upload):
        ws = await hass_ws_client(hass)
        await ws.send_json_auto_id(
            {
                "type": "listening_genome/import_apple",
                "file_id": "upload-1",
                "filename": "Apple Music - Play History Daily Tracks.csv",
            }
        )
        msg = await ws.receive_json()
    assert msg["success"], msg
    runtime = loaded.runtime_data
    await asyncio.gather(*runtime._tasks)
    assert runtime.jobs.get("apple_import")["state"] == "ok"
    uploads = Path(hass.config.path("listening_genome", "uploads"))
    assert await hass.async_add_executor_job(lambda: list(uploads.iterdir())) == []


async def test_ws_import_apple_with_an_unknown_upload_is_an_error(
    hass: HomeAssistant, loaded: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    ws = await hass_ws_client(hass)
    await ws.send_json_auto_id(
        {"type": "listening_genome/import_apple", "file_id": "nope", "filename": "x.csv"}
    )
    msg = await ws.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "upload_failed"


async def test_home_assistant_stopping_writes_the_track_still_playing(
    hass: HomeAssistant, loaded: MockConfigEntry, fake_ma: type[FakeMusicAssistant]
) -> None:
    """A stop does not unload entries; the stop listener must write the open play itself."""
    from homeassistant.const import EVENT_HOMEASSISTANT_STOP

    [client] = fake_ma.instances
    client.emit(EventType.MEDIA_ITEM_PLAYED, _progress(seconds_played=95))
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    counts = await loaded.runtime_data.store.source_counts("household")
    assert counts.get("ma_playlog") == 1


async def test_a_reload_mid_track_does_not_count_it_twice(
    hass: HomeAssistant, loaded: MockConfigEntry, fake_ma: type[FakeMusicAssistant]
) -> None:
    """
    Saving the settings reloads mid-track: the partial play is written, and the new capture
    picks the same play up. Its start is recomputed a little differently (here across a minute
    boundary, which the per-minute dedupe key alone would miss) - it is still one listen.
    """
    runtime = loaded.runtime_data
    runtime.capture.clock = lambda: 1_790_100_059.0
    [client] = fake_ma.instances
    client.emit(EventType.MEDIA_ITEM_PLAYED, _progress(seconds_played=60))  # start ...:59:59
    await hass.async_block_till_done()
    await hass.config_entries.async_reload(loaded.entry_id)
    await hass.async_block_till_done()
    runtime = loaded.runtime_data
    runtime.capture.clock = lambda: 1_790_100_212.0
    client = fake_ma.instances[-1]
    client.emit(
        EventType.MEDIA_ITEM_PLAYED,
        _progress(seconds_played=210, fully_played=True, is_playing=False),
    )  # start recomputed as ...:00:02 - the next minute
    await _settle(hass)
    counts = await runtime.store.source_counts("household")
    assert counts.get("ma_playlog") == 1


async def test_a_client_that_cannot_be_built_still_retries(
    hass: HomeAssistant,
    ma_entry: MockConfigEntry,
    genome_entry: MockConfigEntry,
    seeded_store: Path,
    test_baseline: object,
) -> None:
    def broken(*_args: Any) -> Any:
        raise ValueError("bad url")

    with patch(
        "custom_components.listening_genome.live_capture._default_client_factory", new=broken
    ):
        genome_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(genome_entry.entry_id)
        await hass.async_block_till_done()
        capture = genome_entry.runtime_data.capture
        assert "bad url" in capture.status.last_error
        assert capture._unsub_retry is not None
