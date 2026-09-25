"""
Fixtures for the Home Assistant integration tests.

Everything here imports the integration as ``custom_components.listening_genome`` - the name
Home Assistant's loader gives it - never as the bare ``listening_genome`` the core tests use.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.listening_genome.const import CONF_MA_ENTRY_ID, DOMAIN, STORAGE_DIRNAME
from custom_components.listening_genome.core.constants import RESOLVE_STATE_OK
from custom_components.listening_genome.core.models import ArtistMeta, Baseline, Listen
from custom_components.listening_genome.core.store import GenomeStore

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

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
