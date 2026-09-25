"""Tests for :class:`GenomeService`, the HA-free port of the fork controller's rebuild/get."""

from __future__ import annotations

from typing import TYPE_CHECKING

from listening_genome.core.constants import (
    RESOLVE_STATE_ERROR,
    RESOLVE_STATE_NOT_FOUND,
    RESOLVE_STATE_OK,
)
from listening_genome.core.models import ArtistMeta, Baseline, Listen
from listening_genome.core.service import GenomeService, GenomeServiceSettings
from listening_genome.core.store import GenomeStore

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

NOW = 1_790_000_000

BASELINE = Baseline(
    version="test",
    genre_shares={"rock": 0.5, "jazz": 0.5},
    era_shares={},
    listener_percentiles={5: 10, 10: 100, 25: 1000, 50: 10_000, 75: 100_000, 90: 1_000_000},
    concentration=0.1,
)


def _listen(artist: str, track: str, played_at: int = NOW, **overrides: object) -> Listen:
    values: dict[str, object] = {
        "played_at": played_at,
        "artist_key": artist.lower(),
        "artist_name": artist,
        "track_key": track.lower(),
        "track_name": track,
        "album_name": None,
        "source": "apple_export",
        "player_id": None,
        "duration_ms": 200_000,
        "played_ms": 200_000,
        "fully_played": True,
        "confidence": 1.0,
    }
    values.update(overrides)
    return Listen(**values)  # type: ignore[arg-type]


def _meta(artist: str, genres: tuple[str, ...], lb_listeners: int | None) -> ArtistMeta:
    return ArtistMeta(
        artist_key=artist.lower(),
        artist_name=artist,
        mbid=None,
        genres=genres,
        first_release_year=None,
        lb_listeners=lb_listeners,
        lb_listen_count=None,
    )


async def _seeded_store(tmp_path: Path) -> GenomeStore:
    store = GenomeStore(str(tmp_path))
    await store.setup()
    await store.add_listens(
        [
            _listen("Alpha", "One"),
            _listen("Alpha", "Two"),
            _listen("Alpha", "Three"),
            _listen("Beta", "Four"),
            # under min_seconds_played (30s): stored, but not counted by the engine
            _listen("Beta", "Short", played_ms=10_000, fully_played=False),
        ],
        listener="household",
    )
    await store.upsert_artist_meta([_meta("Alpha", ("rock",), 500)], state=RESOLVE_STATE_OK)
    await store.upsert_artist_meta([_meta("Beta", ("rock",), 5000)], state=RESOLVE_STATE_ERROR)
    return store


def _service(store: GenomeStore, **kwargs: object) -> GenomeService:
    kwargs.setdefault("tz_offset_seconds", lambda: 0)
    return GenomeService(store, BASELINE, GenomeServiceSettings(), **kwargs)  # type: ignore[arg-type]


async def test_rebuild_uses_injected_now_and_settings(tmp_path: Path) -> None:
    store = await _seeded_store(tmp_path)
    try:
        genome = await _service(store).rebuild(now=NOW + 86_400)
    finally:
        await store.close()
    assert genome["generated_at"] == NOW + 86_400
    assert genome["half_life_days"] == 548
    assert genome["obscurity"]["percentile"] == 25
    # 3 of the 4 eligible (equally weighted) listens are by an artist under the 1000 threshold
    assert genome["obscurity"]["index"] == 0.75
    assert genome["stats"]["total_listens"] == 4
    assert genome["top_artists"][0]["name"] == "Alpha"


async def test_rebuild_caches_with_real_resolution_counts(tmp_path: Path) -> None:
    store = await _seeded_store(tmp_path)
    try:
        await store.upsert_artist_meta([_meta("Gamma", (), None)], state=RESOLVE_STATE_NOT_FOUND)
        service = _service(store)
        genome = await service.rebuild(now=NOW)
        cached = await store.get_cached_genome("household")
    finally:
        await store.close()
    assert genome["stats"]["artists_pending"] == 0
    assert genome["stats"]["artists_failed"] == 1  # Beta
    assert genome["stats"]["artists_resolved"] == 2  # Alpha (ok) + Gamma (not_found)
    assert genome["stats"]["unresolved_dismissed"] is False
    assert cached == genome
    assert service.last_rebuild_at == NOW


async def test_unresolved_dismissed_when_failed_set_matches(tmp_path: Path) -> None:
    store = await _seeded_store(tmp_path)
    try:
        await store.dismiss_unresolved(["beta"])
        genome = await _service(store).rebuild(now=NOW)
    finally:
        await store.close()
    assert genome["stats"]["unresolved_dismissed"] is True


async def test_get_rebuilds_only_when_nothing_is_cached(tmp_path: Path) -> None:
    store = await _seeded_store(tmp_path)
    clock_calls: list[int] = []

    def clock() -> float:
        clock_calls.append(1)
        return NOW + len(clock_calls)

    try:
        service = _service(store, clock=clock)
        first = await service.get()
        second = await service.get()
    finally:
        await store.close()
    assert len(clock_calls) == 1
    assert first["generated_at"] == NOW + 1
    # served from cache (the stale flag is the short listen; see the next test)
    assert second == {**first, "stale": True}


async def test_get_flags_stale_on_count_mismatch_as_the_fork_does(tmp_path: Path) -> None:
    """
    The fork compares the store's RAW listen count with the cached, post-filter total.

    Ported as-is: with one sub-30s listen stored, the two never agree, so a cached genome is
    always served with ``stale`` set. Pinned here so that changing it is a deliberate choice.
    """
    store = await _seeded_store(tmp_path)
    try:
        service = _service(store)
        await service.rebuild(now=NOW)
        served = await service.get()
    finally:
        await store.close()
    assert served["stats"]["total_listens"] == 4
    assert served["stale"] is True


async def test_get_refresh_forces_a_rebuild(tmp_path: Path) -> None:
    store = await _seeded_store(tmp_path)
    try:
        service = _service(store, clock=lambda: NOW + 99)
        await service.rebuild(now=NOW)
        genome = await service.get(refresh=True)
    finally:
        await store.close()
    assert genome["generated_at"] == NOW + 99


async def test_build_runs_through_run_sync_with_the_tz_offset(tmp_path: Path) -> None:
    store = await _seeded_store(tmp_path)
    ran: list[bool] = []

    async def run_sync(func: Callable[[], object]) -> object:
        ran.append(True)
        return func()

    try:
        genome = await _service(store, run_sync=run_sync, tz_offset_seconds=lambda: 3600).rebuild(
            now=NOW
        )
    finally:
        await store.close()
    assert ran == [True]
    # NOW is 2026-09-21 14:13:20 UTC (a Monday); at +1h every listen lands in the 15:00 cell
    [cell] = [c for c in genome["rhythm"] if c["weight"] > 0]
    assert (cell["weekday"], cell["hour"]) == (0, 15)
