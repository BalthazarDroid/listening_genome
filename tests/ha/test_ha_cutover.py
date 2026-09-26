"""Phase 4, the move off the fork: following a replaced MA entry, and the fork's last plays."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.listening_genome.core.models import Listen
from custom_components.listening_genome.core.store import GenomeStore

from .test_ha_live import FakeMusicAssistant, fake_ma  # noqa: F401 - fixture

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

CUTOFF = 1_790_300_000  # when "this integration" began capturing, in the fixtures below


def _listen(artist: str, played_at: int, *, source: str, player_id: str | None) -> Listen:
    return Listen(
        played_at=played_at,
        artist_key=artist.lower(),
        artist_name=artist,
        track_key="song",
        track_name="Song",
        album_name=None,
        source=source,
        player_id=player_id,
        duration_ms=200_000,
        played_ms=200_000,
        fully_played=True,
        confidence=1.0,
    )


@pytest.fixture
async def fork_export(tmp_path: Path) -> Path:
    """A fork export: two live plays before the cutoff, one after, and a Last.fm row."""
    folder = tmp_path / "fork"
    folder.mkdir()
    store = GenomeStore(str(folder))
    await store.setup()
    try:
        await store.add_listens(
            [
                _listen("Early", CUTOFF - 7200, source="ma_playlog", player_id=None),
                _listen("Earlier", CUTOFF - 90_000, source="ma_playlog", player_id=None),
                _listen("Late", CUTOFF + 600, source="ma_playlog", player_id=None),
            ],
            listener="household",
        )
        await store.add_listens(
            [_listen("Scrobbled", CUTOFF - 5000, source="lastfm", player_id=None)],
            listener="household",
        )
    finally:
        await store.close()
    return folder / "genome.db"


@pytest.fixture
async def loaded(
    hass: HomeAssistant,
    fake_ma: type[FakeMusicAssistant],  # noqa: F811
    genome_entry: MockConfigEntry,
    seeded_store: Path,
    test_baseline: object,
) -> MockConfigEntry:
    # this integration's own first live capture, with its player
    store = GenomeStore(str(seeded_store))
    await store.setup()
    try:
        await store.add_listens(
            [_listen("Own", CUTOFF, source="ma_playlog", player_id="kitchen")],
            listener="household",
        )
    finally:
        await store.close()
    MockConfigEntry(
        domain="music_assistant", entry_id="ma-entry-1", data={"url": "http://dev:8095"}
    ).add_to_hass(hass)
    genome_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(genome_entry.entry_id)
    await hass.async_block_till_done()
    return genome_entry


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def test_fork_import_takes_only_live_plays_from_before_our_own_capture(
    hass: HomeAssistant, loaded: MockConfigEntry, fork_export: Path
) -> None:
    hass.config.allowlist_external_dirs = {str(fork_export.parent)}
    before = await hass.async_add_executor_job(_sha, fork_export)

    dry: Any = await hass.services.async_call(
        "listening_genome",
        "import_fork_export",
        {"path": str(fork_export), "dry_run": True},
        blocking=True,
        return_response=True,
    )
    assert dry == {
        "fork_live_plays": 3,
        "before_own_capture": 2,
        "own_capture_started": CUTOFF,
        "added": 0,
        "dry_run": True,
    }
    store = loaded.runtime_data.store
    assert (await store.source_counts("household"))["ma_playlog"] == 1

    report: Any = await hass.services.async_call(
        "listening_genome",
        "import_fork_export",
        {"path": str(fork_export)},
        blocking=True,
        return_response=True,
    )
    assert report["added"] == 2
    counts = await store.source_counts("household")
    assert counts["ma_playlog"] == 3  # own + Early + Earlier; not Late
    assert "lastfm" not in counts  # the export's other rows never come back
    # read-only: the export is exactly as it was
    assert await hass.async_add_executor_job(_sha, fork_export) == before

    again: Any = await hass.services.async_call(
        "listening_genome",
        "import_fork_export",
        {"path": str(fork_export)},
        blocking=True,
        return_response=True,
    )
    assert again["added"] == 0  # idempotent


async def test_capture_follows_the_music_assistant_entry_that_replaced_the_linked_one(
    hass: HomeAssistant,
    loaded: MockConfigEntry,
    fake_ma: type[FakeMusicAssistant],  # noqa: F811
) -> None:
    """DEV stopped and its entry deleted, production added: the link moves, capture reconnects."""
    fake_ma.instances[-1].drop()  # the DEV add-on stopped
    await hass.async_block_till_done()
    await hass.config_entries.async_remove("ma-entry-1")
    MockConfigEntry(
        domain="music_assistant", entry_id="ma-prod", data={"url": "http://prod:8095"}
    ).add_to_hass(hass)
    loaded.runtime_data.capture._attempt()
    await hass.async_block_till_done()
    assert loaded.data["ma_entry_id"] == "ma-prod"
    assert fake_ma.instances[-1].url == "http://prod:8095"
    assert (
        hass.states.get("binary_sensor.listening_genome_music_assistant_connection").state == "on"
    )


async def test_with_two_music_assistant_entries_nothing_is_guessed(
    hass: HomeAssistant, loaded: MockConfigEntry
) -> None:
    await hass.config_entries.async_remove("ma-entry-1")
    for entry_id in ("ma-a", "ma-b"):
        MockConfigEntry(
            domain="music_assistant", entry_id=entry_id, data={"url": f"http://{entry_id}"}
        ).add_to_hass(hass)
    loaded.runtime_data.capture._attempt()
    await hass.async_block_till_done()
    assert loaded.data["ma_entry_id"] == "ma-entry-1"


async def test_reconfigure_picks_the_music_assistant_entry(
    hass: HomeAssistant, loaded: MockConfigEntry
) -> None:
    MockConfigEntry(
        domain="music_assistant", entry_id="ma-prod", title="Production", data={"url": "x"}
    ).add_to_hass(hass)
    result = await loaded.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"ma_entry_id": "ma-prod"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert loaded.data["ma_entry_id"] == "ma-prod"
