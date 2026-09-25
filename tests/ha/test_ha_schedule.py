"""
Tests for the schedules: the daily rebuild at a local hour, the hourly enrichment pass, the
User-Agent every outgoing request carries, job state across reloads, and clean unload.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.listening_genome.core.constants import (
    CONF_ENRICH_ENABLED,
    CONF_REBUILD_SCHEDULE_HOUR,
    RESOLVE_STATE_ERROR,
    RESOLVE_STATE_NOT_FOUND,
    RESOLVE_STATE_OK,
)
from custom_components.listening_genome.core.jobs import JOB_ENRICHMENT, JOB_REBUILD
from custom_components.listening_genome.core.models import Listen
from custom_components.listening_genome.core.store import GenomeStore

from .conftest import PLAYED_AT

if TYPE_CHECKING:
    from pathlib import Path

    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

TZ = "America/Chicago"
# 03:30 CDT on 2026-09-25
START = "2026-09-25T08:30:00+00:00"
EXPECTED_USER_AGENT = "ListeningGenome/0.1.0 ( https://github.com/BalthazarDroid/listening_genome )"


def _new_listen(track: str, played_at: int = PLAYED_AT + 60) -> Listen:
    return Listen(
        played_at=played_at,
        artist_key="alpha",
        artist_name="Alpha",
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


async def _setup(hass: HomeAssistant, entry: MockConfigEntry, **options: Any) -> MockConfigEntry:
    if options:
        entry.add_to_hass(hass)
        hass.config_entries.async_update_entry(entry, options=options)
    else:
        entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _advance(hass: HomeAssistant, freezer: FrozenDateTimeFactory, to: str) -> None:
    freezer.move_to(to)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.fixture
async def chicago(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Home Assistant in America/Chicago, at 03:30 local."""
    await hass.config.async_set_time_zone(TZ)
    freezer.move_to(START)


@pytest.mark.usefixtures("chicago", "seeded_store", "test_baseline")
async def test_daily_rebuild_runs_at_the_configured_local_hour(
    hass: HomeAssistant, genome_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-09-25T03:00:00+00:00")  # 22:00 CDT on the 24th
    entry = await _setup(hass, genome_entry, **{CONF_ENRICH_ENABLED: False})
    runtime = entry.runtime_data
    assert hass.states.get("sensor.listening_genome_listens_stored").state == "4"
    # setup found no cache and rebuilt, and that rebuild is a recorded job like any other
    assert runtime.jobs.get(JOB_REBUILD)["started_at"] == 1_790_305_200
    await runtime.store.add_listens([_new_listen("Five")], listener="household")

    # 04:00 UTC is 23:00 in Chicago: hour 4, but not local hour 4, so nothing happens
    await _advance(hass, freezer, "2026-09-25T04:00:00+00:00")
    assert hass.states.get("sensor.listening_genome_listens_stored").state == "4"
    assert runtime.jobs.get(JOB_REBUILD)["started_at"] == 1_790_305_200

    # 04:00 CDT is 09:00 UTC: the daily rebuild runs, and the sensors follow without a poll
    await _advance(hass, freezer, "2026-09-25T09:00:00+00:00")
    assert hass.states.get("sensor.listening_genome_listens_stored").state == "5"
    assert (
        hass.states.get("sensor.listening_genome_last_rebuild").state == "2026-09-25T09:00:00+00:00"
    )
    job = runtime.jobs.get(JOB_REBUILD)
    assert job["state"] == "ok"
    assert job["started_at"] == 1_790_326_800


@pytest.mark.usefixtures("chicago", "seeded_store", "test_baseline")
async def test_daily_rebuild_hour_comes_from_the_options(
    hass: HomeAssistant, genome_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    entry = await _setup(
        hass, genome_entry, **{CONF_REBUILD_SCHEDULE_HOUR: 22, CONF_ENRICH_ENABLED: False}
    )
    runtime = entry.runtime_data
    await runtime.store.add_listens([_new_listen("Five")], listener="household")
    await _advance(hass, freezer, "2026-09-25T09:00:00+00:00")  # 04:00 CDT: not any more
    assert hass.states.get("sensor.listening_genome_listens_stored").state == "4"
    await _advance(hass, freezer, "2026-09-26T03:00:00+00:00")  # 22:00 CDT
    assert hass.states.get("sensor.listening_genome_listens_stored").state == "5"


@pytest.mark.usefixtures("pending_artists", "test_baseline")
async def test_hourly_enrichment_resolves_pending_artists(
    hass: HomeAssistant,
    genome_entry: MockConfigEntry,
    music_apis: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(START)
    entry = await _setup(hass, genome_entry)
    runtime = entry.runtime_data
    # enrichment never runs as part of setup
    assert music_apis.call_count == 0
    assert runtime.jobs.get(JOB_ENRICHMENT)["state"] == "idle"

    await _advance(hass, freezer, "2026-09-25T09:30:01+00:00")  # one hour on
    meta = await runtime.store.get_artist_meta(["sigur rós", "kasabian", "nobody known"])
    counts = await runtime.store.artist_resolution_counts()
    assert meta["sigur rós"].mbid == "f6f2326f-6b25-4170-b89d-e235b25508e8"
    assert meta["sigur rós"].lb_listeners == 118_422
    assert meta["kasabian"].lb_listeners == 61
    assert counts == {RESOLVE_STATE_OK: 4, RESOLVE_STATE_NOT_FOUND: 1, RESOLVE_STATE_ERROR: 1}
    failed = await runtime.store.failed_artist_keys()
    assert [row["artist_name"] for row in failed] == ["Radiohead"]
    job = runtime.jobs.get(JOB_ENRICHMENT)
    assert job["state"] == "ok"
    assert "2 resolved, 1 not found, 1 failed (of 4 due)" in job["message"]
    assert "HTTP 503" in job["message"]


@pytest.mark.usefixtures("pending_artists", "test_baseline")
async def test_every_outgoing_request_carries_the_user_agent(
    hass: HomeAssistant, genome_entry: MockConfigEntry, music_apis: AiohttpClientMocker
) -> None:
    entry = await _setup(hass, genome_entry)
    assert entry.runtime_data.user_agent == EXPECTED_USER_AGENT
    await entry.runtime_data.operations.enrich()
    hosts = {url.host for _method, url, _data, _headers in music_apis.mock_calls}
    assert hosts == {"musicbrainz.org", "api.listenbrainz.org"}
    # search + lookup for two artists, a search each for the other two, one popularity POST
    assert len(music_apis.mock_calls) == 7
    for method, url, _data, headers in music_apis.mock_calls:
        assert headers == {"User-Agent": EXPECTED_USER_AGENT}, (method, str(url))


@pytest.mark.usefixtures("pending_artists", "test_baseline")
async def test_enrichment_does_not_run_when_disabled(
    hass: HomeAssistant,
    genome_entry: MockConfigEntry,
    music_apis: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(START)
    entry = await _setup(hass, genome_entry, **{CONF_ENRICH_ENABLED: False})
    for hours in range(1, 4):
        await _advance(hass, freezer, f"2026-09-25T{8 + hours:02d}:30:01+00:00")
    # nor after a rebuild, which otherwise dispatches a pass
    await entry.runtime_data.async_rebuild()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert music_apis.call_count == 0
    assert entry.runtime_data.jobs.get(JOB_ENRICHMENT)["state"] == "idle"
    assert await entry.runtime_data.store.artist_resolution_counts() == {
        RESOLVE_STATE_OK: 2,
        "pending": 4,
    }


@pytest.mark.usefixtures("pending_artists", "test_baseline", "fast_enrichment")
async def test_an_overlapping_enrichment_pass_is_skipped(
    hass: HomeAssistant,
    genome_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    release = asyncio.Event()
    first_search = asyncio.Event()
    searches: list[str] = []

    async def slow_musicbrainz(method: str, url: Any, data: Any) -> Any:
        from pytest_homeassistant_custom_component.test_util.aiohttp import (
            AiohttpClientMockResponse,
        )

        searches.append(url.query.get("query", ""))
        first_search.set()
        await release.wait()
        return AiohttpClientMockResponse(method, url, json={"artists": []})

    import re

    aioclient_mock.get(re.compile(r"^https://musicbrainz\.org/"), side_effect=slow_musicbrainz)
    freezer.move_to(START)
    entry = await _setup(hass, genome_entry)
    runtime = entry.runtime_data

    await _advance_without_waiting(hass, freezer, "2026-09-25T09:30:01+00:00")
    await asyncio.wait_for(first_search.wait(), 5)
    assert runtime.operations.enrichment_running
    assert len(searches) == 1  # stuck on the first artist's search

    await _advance_without_waiting(hass, freezer, "2026-09-25T10:30:02+00:00")
    assert "the previous pass is still running" in caplog.text
    assert len(searches) == 1  # the second pass never started
    assert runtime.jobs.get(JOB_ENRICHMENT)["state"] == "running"

    release.set()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert not runtime.operations.enrichment_running
    assert len(searches) == 4  # one pass, four artists
    assert runtime.jobs.get(JOB_ENRICHMENT)["state"] == "ok"


async def _advance_without_waiting(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, to: str
) -> None:
    """Fire the timers for ``to`` without waiting for the background work they start."""
    freezer.move_to(to)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("test_baseline")
async def test_a_job_left_running_is_interrupted_after_restart(
    hass: HomeAssistant, genome_entry: MockConfigEntry, seeded_store: Path
) -> None:
    """A process that died mid-pass left the job "running"; the next start says what happened."""
    store = GenomeStore(str(seeded_store))
    await store.setup()
    try:
        await store.set_jobs(
            {JOB_ENRICHMENT: {"job": JOB_ENRICHMENT, "state": "running", "started_at": 1}}
        )
    finally:
        await store.close()
    entry = await _setup(hass, genome_entry, **{CONF_ENRICH_ENABLED: False})
    job = entry.runtime_data.jobs.get(JOB_ENRICHMENT)
    assert job["state"] == "interrupted"
    assert (await entry.runtime_data.store.get_jobs())[JOB_ENRICHMENT]["state"] == "interrupted"


@pytest.mark.usefixtures("pending_artists", "test_baseline", "fast_enrichment")
async def test_a_pass_running_during_reload_is_interrupted(
    hass: HomeAssistant, genome_entry: MockConfigEntry, aioclient_mock: AiohttpClientMocker
) -> None:
    import re

    started = asyncio.Event()

    async def hang(method: str, url: Any, data: Any) -> Any:
        started.set()
        await asyncio.Event().wait()  # never answers

    aioclient_mock.get(re.compile(r"^https://musicbrainz\.org/"), side_effect=hang)
    entry = await _setup(hass, genome_entry)
    first_runtime = entry.runtime_data
    assert first_runtime.async_request_enrichment()
    await asyncio.wait_for(started.wait(), 5)
    assert first_runtime.jobs.get(JOB_ENRICHMENT)["state"] == "running"

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    # the in-flight pass was cancelled before the store closed, and recorded as interrupted
    assert not first_runtime.operations.enrichment_running
    assert entry.runtime_data is not first_runtime
    job = entry.runtime_data.jobs.get(JOB_ENRICHMENT)
    assert job["state"] == "interrupted"
    # the artist in flight was not marked as failed by the cancellation
    counts = await entry.runtime_data.store.artist_resolution_counts()
    assert RESOLVE_STATE_ERROR not in counts


@pytest.mark.usefixtures("chicago", "seeded_store", "test_baseline")
async def test_unload_cancels_the_timers(
    hass: HomeAssistant, genome_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    entry = await _setup(hass, genome_entry)
    runtime = entry.runtime_data
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert runtime._unsubscribers == []
    # neither schedule fires any more: a firing would hit the closed store and fail loudly
    await _advance(hass, freezer, "2026-09-25T09:00:00+00:00")
    await _advance(hass, freezer, "2026-09-25T12:00:00+00:00")
    assert runtime._tasks == set()
    assert runtime.jobs.get(JOB_REBUILD)["started_at"] == 1_790_325_000
    assert runtime.jobs.get(JOB_ENRICHMENT)["state"] == "idle"
    # nothing is left behind either: the harness itself fails a test on a lingering timer
