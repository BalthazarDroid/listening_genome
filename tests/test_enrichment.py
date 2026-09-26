"""
Tests for MusicBrainz and ListenBrainz enrichment (§3.8, §3.9).

Ported from the fork with one signature change: these functions took a ``mass`` argument used to
prefer Music Assistant's own loaded ``musicbrainz`` provider, which routed through MA's mirror.
That path leaves with the process, and it is no loss - the mirror gates on a Music Assistant
User-Agent the fork had already decided not to spoof - so every request now goes to
musicbrainz.org through the injected, throttled client.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from listening_genome.core.constants import (
    RESOLVE_OK_COOLDOWN_DAYS,
    RESOLVE_STATE_ERROR,
    RESOLVE_STATE_OK,
)
from listening_genome.core.models import ArtistMeta, Listen
from listening_genome.core.store import GenomeStore
from listening_genome.enrich.listenbrainz import artist_popularity
from listening_genome.enrich.musicbrainz import (
    enrich_pending_artists,
    resolve_artist,
    run_musicbrainz_pass,
)

if TYPE_CHECKING:
    from pathlib import Path

    from conftest import FixtureHttpClient

_SIGUR_ROS_MBID = "f6f2326f-6b25-4170-b89d-e235b25508e8"
_KASABIAN_MBID = "c3ae7ee4-8b02-4c33-8ae9-3d15fcb9d4d0"


async def _new_store(tmp_path: Path) -> GenomeStore:
    store = GenomeStore(str(tmp_path))
    await store.setup()
    return store


async def test_resolve_artist_maps_tags_to_genres(fixture_http_client: FixtureHttpClient) -> None:
    """A confident match returns mbid, begin_year, country and mapped genres, best tag first."""
    update = await resolve_artist("Sigur Rós", client=fixture_http_client)
    assert update is not None
    assert update.mbid == _SIGUR_ROS_MBID
    assert update.begin_year == 1994
    assert update.country == "IS"
    assert update.genres == ("rock", "ambient")  # post-rock -> rock, ambient -> ambient


async def test_resolve_artist_handles_no_tags(fixture_http_client: FixtureHttpClient) -> None:
    """An artist with zero MusicBrainz tags resolves with an empty genres tuple, not an error."""
    update = await resolve_artist("Nick Drake", client=fixture_http_client)
    assert update is not None
    assert update.genres == ()


async def test_resolve_artist_handles_unmapped_tags(fixture_http_client: FixtureHttpClient) -> None:
    """Tags that match no genre_mapping.json alias produce an empty genres tuple."""
    update = await resolve_artist("Kasabian", client=fixture_http_client)
    assert update is not None
    assert update.mbid == _KASABIAN_MBID
    assert update.genres == ()


async def test_resolve_artist_returns_none_when_not_found(
    fixture_http_client: FixtureHttpClient,
) -> None:
    """An artist name with no fixture (and hence no confident match) resolves to None."""
    update = await resolve_artist("Totally Unknown Act", client=fixture_http_client)
    assert update is None


async def test_enrich_pending_artists_writes_ok_and_not_found_states(
    tmp_path: Path, fixture_http_client: FixtureHttpClient
) -> None:
    """A mixed batch of resolvable and unresolvable artists gets the right resolve_state each."""
    store = await _new_store(tmp_path)
    try:
        await store._ensure_artist_meta_stub("sigurros", "Sigur Rós")
        await store._ensure_artist_meta_stub("unknown", "Totally Unknown Act")
        resolved = await enrich_pending_artists(store, client=fixture_http_client)
        assert resolved == 1
        assert await store.pending_artist_keys() == []
        meta = await store.get_artist_meta(["sigurros"])
        assert meta["sigurros"].mbid == _SIGUR_ROS_MBID
    finally:
        await store.close()


async def test_artist_popularity_maps_and_omits_missing(
    fixture_http_client: FixtureHttpClient,
) -> None:
    """A requested mbid absent from the response is simply missing, not an error."""
    result = await artist_popularity(
        [_SIGUR_ROS_MBID, _KASABIAN_MBID, "00000000-missing-mbid"], client=fixture_http_client
    )
    assert result[_SIGUR_ROS_MBID].listeners == 118422
    assert result[_SIGUR_ROS_MBID].listen_count == 4821334
    assert result[_KASABIAN_MBID].listeners == 61
    assert "00000000-missing-mbid" not in result


async def test_artist_popularity_batches_large_requests(
    fixture_http_client: FixtureHttpClient,
) -> None:
    """More than one batch worth of mbids results in more than one POST call."""
    mbids = [f"artist-{i}" for i in range(120)]
    await artist_popularity(mbids, client=fixture_http_client)
    post_calls = [call for call in fixture_http_client.calls if call[0] == "POST"]
    assert len(post_calls) == 3  # 120 mbids / 50 per batch, rounded up


async def test_musicbrainz_lookups_go_to_musicbrainz_org_not_the_ma_mirror() -> None:
    """
    Every MusicBrainz request must go to musicbrainz.org itself.

    The fork preferred Music Assistant's own provider and fell back to MA's mirror,
    musicbrainz-mirror.music-assistant.io. Removing the provider path during the port made
    that fallback the ONLY path, while a comment claimed requests went to musicbrainz.org.
    The mirror answers 403 to anything not identifying as Music Assistant, so every lookup on
    a real install would have failed and marked the artist failed. No test caught it, because
    the fixture client matched request paths and never looked at the host.

    This one looks at the host of the request actually made, not at a constant.
    """
    from urllib.parse import urlsplit

    seen: list[str] = []

    class _Recorder:
        async def get_json(self, url: str, *, params=None, headers=None):
            seen.append(url)
            return {"artists": []}

        async def post_json(self, url: str, *, json=None, headers=None):
            seen.append(url)
            return []

    assert await resolve_artist("Portishead", client=_Recorder()) is None
    assert seen, "no MusicBrainz request was made at all"
    hosts = {urlsplit(url).hostname for url in seen}
    assert hosts == {"musicbrainz.org"}, f"MusicBrainz requests went to {hosts}"


class _MusicBrainzDown:
    """MusicBrainz answering 503 to everything."""

    async def get_json(self, url: str, *, params: Any = None, headers: Any = None) -> Any:
        err = Exception("503 Service Unavailable")
        err.status = 503  # type: ignore[attr-defined]
        raise err

    async def post_json(self, url: str, *, json: Any, headers: Any = None) -> Any:
        raise AssertionError("not used")


async def test_a_recheck_during_an_outage_keeps_what_was_known(tmp_path: Path) -> None:
    """
    An ``ok`` artist due for its periodic re-check keeps its metadata when MusicBrainz fails.

    Regression: the pass wrote the error as a whole row of NULLs - mbid, genres, begin year
    and ListenBrainz popularity gone until a later re-check happened to succeed.
    """
    store = await _new_store(tmp_path)
    try:
        await store.add_listens(
            [
                Listen(
                    played_at=1_700_000_000,
                    artist_key="sigur ros",
                    artist_name="Sigur Ros",
                    track_key="t",
                    track_name="T",
                    album_name=None,
                    source="lastfm",
                    player_id=None,
                    duration_ms=None,
                    played_ms=None,
                    fully_played=True,
                    confidence=1.0,
                )
            ],
            listener="household",
        )
        known = ArtistMeta(
            artist_key="sigur ros",
            artist_name="Sigur Ros",
            mbid="abc",
            genres=("rock", "ambient"),
            first_release_year=1997,
            begin_year=1994,
            lb_listeners=900_000,
            lb_listen_count=5,
        )
        await store.upsert_artist_meta([known], state=RESOLVE_STATE_OK)
        assert store.database is not None
        due = int(time.time()) - (RESOLVE_OK_COOLDOWN_DAYS + 1) * 86400
        await store.database.execute("UPDATE genome_artist_meta SET resolved_at = :t", {"t": due})
        await store.database.commit()

        report = await run_musicbrainz_pass(store, client=_MusicBrainzDown(), limit=10)
        assert report.failed == 1
        assert (await store.get_artist_meta(["sigur ros"]))["sigur ros"] == known
        assert await store.artist_resolution_counts() == {RESOLVE_STATE_ERROR: 1}
    finally:
        await store.close()
