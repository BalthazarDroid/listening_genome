"""
Tests for ``core/operations.py`` (rebuild and enrichment recorded as jobs), the User-Agent and
the settings object. HA-free; every HTTP request is answered from fixtures.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pytest
from listening_genome.baseline import load_baseline
from listening_genome.core.constants import (
    DEFAULT_OBSCURITY_PERCENTILE,
    OBSCURITY_PERCENTILE_CHOICES,
    RESOLVE_STATE_ERROR,
    RESOLVE_STATE_NOT_FOUND,
    RESOLVE_STATE_OK,
    RESOLVE_STATE_PENDING,
)
from listening_genome.core.http import AiohttpClient, describe_http_error, user_agent
from listening_genome.core.jobs import JOB_ENRICHMENT, JOB_REBUILD, JobTracker
from listening_genome.core.models import ArtistMeta, Baseline, Listen
from listening_genome.core.operations import GenomeOperations
from listening_genome.core.service import GenomeService, GenomeServiceSettings
from listening_genome.core.store import GenomeStore

if TYPE_CHECKING:
    from pathlib import Path

    from conftest import FixtureHttpClient

NOW = 1_790_000_000
SIGUR_ROS_MBID = "f6f2326f-6b25-4170-b89d-e235b25508e8"

BASELINE = Baseline(
    version="test",
    genre_shares={"rock": 0.5, "jazz": 0.5},
    era_shares={},
    listener_percentiles={5: 10, 10: 100, 25: 1000, 50: 10_000, 75: 100_000, 90: 1_000_000},
    concentration=0.1,
)


class _HttpError(Exception):
    """Shaped like ``aiohttp.ClientResponseError``: a ``status`` and a ``message``."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class _FlakyClient:
    """Fixture answers, except one artist whose search always fails with HTTP 503."""

    def __init__(self, inner: FixtureHttpClient, *, failing: str) -> None:
        self.inner = inner
        self.failing = failing

    async def get_json(self, url: str, *, params: Any = None, headers: Any = None) -> Any:
        if params and self.failing in params.get("query", ""):
            raise _HttpError(503, "Service Unavailable")
        return await self.inner.get_json(url, params=params, headers=headers)

    async def post_json(self, url: str, *, json: Any, headers: Any = None) -> Any:
        return await self.inner.post_json(url, json=json, headers=headers)


def _pending(name: str) -> ArtistMeta:
    return ArtistMeta(
        artist_key=name.lower(),
        artist_name=name,
        mbid=None,
        genres=(),
        first_release_year=None,
        lb_listeners=None,
        lb_listen_count=None,
    )


def _listen(artist: str, track: str) -> Listen:
    return Listen(
        played_at=NOW,
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


async def _store_with_pending(tmp_path: Path, *names: str) -> GenomeStore:
    store = GenomeStore(str(tmp_path))
    await store.setup()
    # every artist gets a listen: resolution counts and failure lists only cover artists in the
    # listening history. Each listen creates a pending stub the upserts below overwrite.
    await store.add_listens(
        [_listen("Alpha", "One"), *(_listen(name, f"{name} Track") for name in names)],
        listener="household",
    )
    # resolve Alpha so only `names` are due
    await store.upsert_artist_meta([_pending("Alpha")], state=RESOLVE_STATE_OK)
    await store.upsert_artist_meta([_pending(name) for name in names], state=RESOLVE_STATE_PENDING)
    return store


def _operations(store: GenomeStore, client: Any) -> GenomeOperations:
    service = GenomeService(store, BASELINE, tz_offset_seconds=lambda: 0)
    return GenomeOperations(
        service,
        JobTracker(store),
        musicbrainz_client=client,
        listenbrainz_client=client,
        enrichment_min_interval_seconds=0,
    )


async def test_enrich_resolves_pending_artists_and_backfills_popularity(
    tmp_path: Path, fixture_http_client: FixtureHttpClient
) -> None:
    store = await _store_with_pending(
        tmp_path, "Sigur Rós", "Kasabian", "Nobody Known", "Radiohead"
    )
    client = _FlakyClient(fixture_http_client, failing="Radiohead")
    try:
        ops = _operations(store, client)
        report = await ops.enrich()
        meta = await store.get_artist_meta(["sigur rós", "kasabian"])
        counts = await store.artist_resolution_counts()
        job = ops.jobs.get(JOB_ENRICHMENT)
        failed = await store.failed_artist_keys()
    finally:
        await store.close()
    assert report is not None
    mb = report.musicbrainz
    assert (mb.attempted, mb.resolved, mb.not_found, mb.failed) == (4, 2, 1, 1)
    assert mb.failures == [("Radiohead", "HTTP 503 Service Unavailable")]
    assert (report.popularity.looked_up, report.popularity.updated) == (2, 2)
    assert meta["sigur rós"].lb_listeners == 118_422
    assert meta["kasabian"].lb_listeners == 61
    assert counts == {RESOLVE_STATE_OK: 3, RESOLVE_STATE_NOT_FOUND: 1, RESOLVE_STATE_ERROR: 1}
    assert [row["artist_name"] for row in failed] == ["Radiohead"]
    assert job["state"] == "ok"
    assert "2 resolved, 1 not found, 1 failed (of 4 due)" in job["message"]
    assert "HTTP 503 Service Unavailable x1" in job["message"]
    assert "now 3 identified, 1 not on MusicBrainz, 0 pending, 1 failed" in job["message"]


async def test_enrich_with_nothing_due_makes_no_requests(
    tmp_path: Path, fixture_http_client: FixtureHttpClient
) -> None:
    store = await _store_with_pending(tmp_path)
    try:
        report = await _operations(store, fixture_http_client).enrich()
    finally:
        await store.close()
    assert report is not None
    assert report.musicbrainz.attempted == 0
    assert fixture_http_client.calls == []


async def test_a_listenbrainz_failure_is_reported_and_leaves_the_backlog(
    tmp_path: Path, fixture_http_client: FixtureHttpClient
) -> None:
    class _NoListenBrainz(_FlakyClient):
        async def post_json(self, url: str, *, json: Any, headers: Any = None) -> Any:
            raise TimeoutError

    store = await _store_with_pending(tmp_path, "Sigur Rós")
    try:
        ops = _operations(store, _NoListenBrainz(fixture_http_client, failing="-"))
        report = await ops.enrich()
        backlog = await store.pending_popularity_keys()
    finally:
        await store.close()
    assert report is not None
    assert report.popularity.error == "timed out"
    assert backlog == [("sigur rós", SIGUR_ROS_MBID)]
    assert "ListenBrainz popularity failed: timed out" in ops.jobs.get(JOB_ENRICHMENT)["message"]


async def test_an_overlapping_enrichment_pass_is_skipped(
    tmp_path: Path, fixture_http_client: FixtureHttpClient
) -> None:
    release = asyncio.Event()

    class _Blocking(_FlakyClient):
        async def get_json(self, url: str, *, params: Any = None, headers: Any = None) -> Any:
            await release.wait()
            return await super().get_json(url, params=params, headers=headers)

    store = await _store_with_pending(tmp_path, "Sigur Rós")
    try:
        ops = _operations(store, _Blocking(fixture_http_client, failing="-"))
        first = asyncio.create_task(ops.enrich())
        await asyncio.sleep(0.01)
        assert ops.enrichment_running
        assert await ops.enrich() is None  # skipped, not queued
        release.set()
        report = await first
    finally:
        await store.close()
    assert report is not None
    assert report.musicbrainz.resolved == 1
    assert not ops.enrichment_running


async def test_rebuild_is_recorded_as_a_job(tmp_path: Path) -> None:
    store = await _store_with_pending(tmp_path)
    try:
        ops = _operations(store, None)
        result = await ops.rebuild()
    finally:
        await store.close()
    job = ops.jobs.get(JOB_REBUILD)
    assert result["listens_scanned"] == 1
    assert job["state"] == "ok"
    assert job["message"].startswith("Rebuilt from 1 stored listens (1 long enough to count)")


async def test_a_failed_rebuild_is_recorded_and_raised(tmp_path: Path) -> None:
    store = await _store_with_pending(tmp_path)
    ops = _operations(store, None)
    await store.close()  # every read now fails
    with pytest.raises(ValueError, match="no active connection"):
        await ops.rebuild()
    job = ops.jobs.get(JOB_REBUILD)
    assert job["state"] == "error"
    assert job["message"].startswith("Rebuild failed:")


def test_user_agent_follows_musicbrainz_rules() -> None:
    assert user_agent("0.1.0") == (
        "ListeningGenome/0.1.0 ( https://github.com/BalthazarDroid/listening_genome )"
    )


class _RecordingSession:
    """Records the headers of each request an :class:`AiohttpClient` makes."""

    def __init__(self) -> None:
        self.headers: list[dict[str, str] | None] = []

    def get(self, url: str, *, params: Any = None, headers: Any = None) -> _Response:
        self.headers.append(headers)
        return _Response()

    def post(self, url: str, *, json: Any = None, headers: Any = None) -> _Response:
        self.headers.append(headers)
        return _Response()


class _Response:
    async def __aenter__(self) -> _Response:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    async def json(self, loads: Any = None) -> Any:
        return {}


async def test_aiohttp_client_sends_the_user_agent_on_every_request() -> None:
    session = _RecordingSession()
    client = AiohttpClient(session, rate_limit=100, period=1.0, user_agent="UA/1 ( x )")  # type: ignore[arg-type]
    await client.get_json("https://musicbrainz.org/ws/2/artist")
    await client.post_json("https://api.listenbrainz.org/1/popularity/artist", json={})
    await client.get_json("https://example.org", headers={"Accept": "application/json"})
    assert session.headers == [
        {"User-Agent": "UA/1 ( x )"},
        {"User-Agent": "UA/1 ( x )"},
        {"User-Agent": "UA/1 ( x )", "Accept": "application/json"},
    ]


def test_describe_http_error() -> None:
    assert describe_http_error(_HttpError(403, "Forbidden")) == "HTTP 403 Forbidden"
    assert describe_http_error(TimeoutError()) == "timed out"
    assert (
        describe_http_error(ConnectionRefusedError())
        == "connection failed (ConnectionRefusedError)"
    )
    assert describe_http_error(KeyError("x")) == "KeyError"


def test_settings_defaults_are_the_forks() -> None:
    settings = GenomeServiceSettings.from_options({})
    assert settings == GenomeServiceSettings()
    # the fork's constants.py values: 548-day half-life, 25th percentile, 30 s, 04:00, enrich on
    assert (
        settings.half_life_days,
        settings.obscurity_percentile,
        settings.min_seconds_played,
        settings.rebuild_schedule_hour,
        settings.enrich_enabled,
    ) == (548, 25, 30, 4, True)
    assert settings.engine_settings() == (548, 25, 30)


async def test_percentile_choices_are_the_shipped_baselines() -> None:
    """The engine only has a threshold for the baseline's own percentiles."""
    baseline = await load_baseline()
    assert tuple(sorted(baseline.listener_percentiles)) == OBSCURITY_PERCENTILE_CHOICES
    assert DEFAULT_OBSCURITY_PERCENTILE in OBSCURITY_PERCENTILE_CHOICES
