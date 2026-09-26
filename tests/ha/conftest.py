"""
Fixtures for the Home Assistant integration tests.

Everything here imports the integration as ``custom_components.listening_genome`` - the name
Home Assistant's loader gives it - never as the bare ``listening_genome`` the core tests use.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.listening_genome.const import CONF_MA_ENTRY_ID, DOMAIN, STORAGE_DIRNAME
from custom_components.listening_genome.core.constants import (
    RESOLVE_STATE_OK,
    RESOLVE_STATE_PENDING,
)
from custom_components.listening_genome.core.models import ArtistMeta, Baseline, Listen
from custom_components.listening_genome.core.store import GenomeStore

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

# every seeded listen is played at this instant, so all carry the same recency weight and the
# expected values below can be worked out by hand
PLAYED_AT = 1_790_000_000  # 2026-09-21T14:13:20Z

# A two-genre baseline the expected values are derived against.
TEST_BASELINE = Baseline(
    version="test",
    genre_shares={"rock": 0.5, "jazz": 0.5},
    era_shares={},
    listener_percentiles={5: 10, 10: 100, 25: 1000, 50: 10_000, 75: 100_000, 90: 1_000_000},
    concentration=0.1,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load integrations from ``custom_components``."""


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir: str) -> str:
    """Give every test its own config dir, so genome.db never lands in site-packages."""
    return hass_tmp_config_dir


@pytest.fixture
def test_baseline() -> Iterator[Baseline]:
    """Serve :data:`TEST_BASELINE` instead of the shipped baseline."""
    with patch(
        "custom_components.listening_genome.load_baseline",
        new=AsyncMock(return_value=TEST_BASELINE),
    ):
        yield TEST_BASELINE


def _listen(artist: str, track: str) -> Listen:
    return Listen(
        played_at=PLAYED_AT,
        artist_key=artist.lower(),
        artist_name=artist,
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


def _meta(artist: str, genres: tuple[str, ...], lb_listeners: int) -> ArtistMeta:
    return ArtistMeta(
        artist_key=artist.lower(),
        artist_name=artist,
        mbid=None,
        genres=genres,
        first_release_year=None,
        lb_listeners=lb_listeners,
        lb_listen_count=None,
    )


@pytest.fixture
async def seeded_store(hass_tmp_config_dir: str) -> Path:
    """
    Seed ``<config>/listening_genome/genome.db`` with four listens and no cached genome.

    Alpha (rock, 500 LB listeners - under the 25th-percentile threshold of 1000): 3 listens.
    Beta (rock, 5000 LB listeners): 1 listen.
    """
    from pathlib import Path

    storage = Path(hass_tmp_config_dir) / STORAGE_DIRNAME
    storage.mkdir(parents=True, exist_ok=True)
    store = GenomeStore(str(storage))
    await store.setup()
    try:
        await store.add_listens(
            [
                _listen("Alpha", "One"),
                _listen("Alpha", "Two"),
                _listen("Alpha", "Three"),
                _listen("Beta", "Four"),
            ],
            listener="household",
        )
        await store.upsert_artist_meta(
            [_meta("Alpha", ("rock",), 500), _meta("Beta", ("rock",), 5000)],
            state=RESOLVE_STATE_OK,
        )
    finally:
        await store.close()
    return storage


@pytest.fixture
def genome_entry() -> MockConfigEntry:
    """A Listening Genome entry linked to a (not loaded) Music Assistant entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Listening Genome",
        data={CONF_MA_ENTRY_ID: "ma-entry-1"},
        entry_id="genome-entry-1",
    )


# artists a test puts in the MusicBrainz queue: two the fixtures resolve, one MusicBrainz does
# not know, and one whose lookup fails with HTTP 503 (see `music_apis`)
PENDING_ARTISTS = ("Sigur Rós", "Kasabian", "Nobody Known", "Radiohead")
FAILING_ARTIST = "Radiohead"


@pytest.fixture
async def pending_artists(seeded_store: Path) -> Path:
    """
    Add :data:`PENDING_ARTISTS` to the seeded store, all due for resolution.

    Each gets one listen first: resolution counts and failure lists only cover artists in the
    listening history, and the upsert below then overwrites the stub `add_listens` inserts.
    """
    store = GenomeStore(str(seeded_store))
    await store.setup()
    try:
        await store.add_listens(
            [_listen(name, f"{name} Track") for name in PENDING_ARTISTS], listener="household"
        )
        await store.upsert_artist_meta(
            [_meta(name, (), 0) for name in PENDING_ARTISTS], state=RESOLVE_STATE_PENDING
        )
        # _meta gives every artist a listener count; pending ones must not have one yet
        await store.database.execute(  # type: ignore[union-attr]
            "UPDATE genome_artist_meta SET lb_listeners = NULL WHERE resolve_state = 'pending'"
        )
        await store.database.commit()  # type: ignore[union-attr]
    finally:
        await store.close()
    return seeded_store


@pytest.fixture
def fast_enrichment() -> Iterator[None]:
    """
    Drop the MusicBrainz pacing and throttles, so a pass never sleeps.

    Real pacing is 2.5 s per artist and 1 request/second; under a frozen clock a throttle
    waiting for time to pass would wait forever.
    """
    with (
        patch("custom_components.listening_genome.GENOME_MB_ENRICHMENT_MIN_INTERVAL_SECONDS", 0),
        patch("custom_components.listening_genome.MUSICBRAINZ_RATE_LIMIT", 1000),
        patch("custom_components.listening_genome.LISTENBRAINZ_RATE_LIMIT", 1000),
    ):
        yield


@pytest.fixture
def music_apis(aioclient_mock: AiohttpClientMocker, fast_enrichment: None) -> AiohttpClientMocker:
    """
    Answer musicbrainz.org and api.listenbrainz.org from the fixtures, through HA's session.

    The requests really go through the ``AiohttpClient`` built on ``async_get_clientsession``,
    so ``aioclient_mock.mock_calls`` records the headers each one carried.
    """
    import re

    from conftest import FixtureHttpClient
    from pytest_homeassistant_custom_component.test_util.aiohttp import (
        AiohttpClientMockResponse,
    )

    fixtures = FixtureHttpClient()

    async def musicbrainz(method: str, url: Any, data: Any) -> AiohttpClientMockResponse:
        params = dict(url.query)
        if FAILING_ARTIST in params.get("query", ""):
            return AiohttpClientMockResponse(method, url, status=503)
        body = await fixtures.get_json(str(url.with_query(None)), params=params)
        return AiohttpClientMockResponse(method, url, json=body)

    async def listenbrainz(method: str, url: Any, data: Any) -> AiohttpClientMockResponse:
        body = await fixtures.post_json(str(url), json=data)
        return AiohttpClientMockResponse(method, url, json=body)

    aioclient_mock.get(re.compile(r"^https://musicbrainz\.org/ws/2/"), side_effect=musicbrainz)
    aioclient_mock.post(
        re.compile(r"^https://api\.listenbrainz\.org/1/popularity/artist"),
        side_effect=listenbrainz,
    )
    return aioclient_mock
