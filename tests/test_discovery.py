"""Tests for discovery (slice 2d): suggestions and cold corners, each with one song to play."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from listening_genome.core.constants import GENOME_DISCOVERY_SEED_ERROR_COOLDOWN_HOURS
from listening_genome.core.discovery import (
    DiscoveryRunner,
    LibraryArtist,
    pick_song,
)
from listening_genome.core.models import Listen
from listening_genome.core.store import GenomeStore

if TYPE_CHECKING:
    from pathlib import Path

KEY = "0123456789abcdef0123456789abcdef"
NOW = 1_790_000_000.0

# a genome whose divergent genre is "psychedelic", with one favourite artist in it
GENOME: dict[str, Any] = {
    "genres": [
        {
            "key": "psychedelic",
            "label": "psychedelic",
            "share": 0.12,
            "baseline_share": 0.02,
            "contribution": 0.18,
        },
        {"key": "pop", "label": "pop", "share": 0.1, "baseline_share": 0.2, "contribution": 0.05},
    ],
    "top_artists": [
        {"artist_key": "the dandy warhols", "name": "The Dandy Warhols", "genres": ["psychedelic"]},
        {"artist_key": "abba", "name": "ABBA", "genres": ["pop"]},
    ],
}


def _listen(artist: str, track: str, n: int = 0) -> Listen:
    return Listen(
        played_at=1_700_000_000 + 60 * n,
        artist_key=artist.lower(),
        artist_name=artist,
        track_key=track.lower(),
        track_name=track,
        album_name=None,
        source="lastfm",
        player_id=None,
        duration_ms=None,
        played_ms=None,
        fully_played=None,
        confidence=1.0,
    )


class FakeLastfm:
    """``artist.getSimilar`` and ``artist.getTopTracks`` from tables; records every request."""

    def __init__(
        self,
        similar: dict[str, list[tuple[str, float]]],
        top: dict[str, list[str]],
        failing: frozenset[str] = frozenset(),
    ) -> None:
        self.similar = similar
        self.top = top
        self.failing = failing
        self.calls: list[dict[str, str]] = []

    async def get_json(self, url: str, *, params: Any = None, headers: Any = None) -> Any:
        self.calls.append(dict(params))
        artist = params["artist"]
        if artist in self.failing:
            return {"error": 6, "message": "The artist you supplied could not be found"}
        if params["method"] == "artist.getSimilar":
            return {
                "similarartists": {
                    "artist": [
                        {"name": name, "mbid": "", "match": str(match)}
                        for name, match in self.similar.get(artist, [])
                    ]
                }
            }
        return {"toptracks": {"track": [{"name": name} for name in self.top.get(artist, [])]}}

    async def post_json(self, url: str, *, json: Any, headers: Any = None) -> Any:
        raise AssertionError("not used")


class FakeLibrary:
    def __init__(self, artists: list[LibraryArtist], tracks: dict[str, list[str]]) -> None:
        self._artists = artists
        self._tracks = tracks
        self.fail = False

    async def artists(self) -> list[LibraryArtist]:
        if self.fail:
            raise ConnectionError("Music Assistant went away")
        return self._artists

    async def track_names(self, artist: LibraryArtist) -> list[str]:
        return self._tracks.get(artist.artist_name, [])


async def _nosleep(_seconds: float) -> None:
    return None


async def _store(tmp_path: Path) -> GenomeStore:
    """A store in which the household's favourite has plenty of plays (so it is no cold corner)."""
    store = GenomeStore(str(tmp_path))
    await store.setup()
    await store.add_listens(
        [_listen("The Dandy Warhols", "Godless", n) for n in range(5)], listener="household"
    )
    return store


def _runner(store: GenomeStore, lastfm: FakeLastfm, now: float = NOW) -> DiscoveryRunner:
    return DiscoveryRunner(store, lastfm_client=lastfm, sleep=_nosleep, clock=lambda: now)


LIBRARY = [
    LibraryArtist("the dandy warhols", "The Dandy Warhols", ("psychedelic",), ref=1),
    LibraryArtist("tame impala", "Tame Impala", ("psychedelic",), ref=2),
    LibraryArtist("abba", "ABBA", ("pop",), ref=3),
]
LIBRARY_TRACKS = {"Tame Impala": ["Let It Happen", "Elephant"]}


def test_pick_song_skips_what_the_household_already_plays() -> None:
    played = {"desire lines": 5, "helicopter": 1}
    assert (
        pick_song(["Desire Lines", "Helicopter", "Nothing Ever Happened"], played) == "Helicopter"
    )
    # a version suffix is the same song
    assert pick_song(["Desire Lines (Remastered)", "Agoraphobia"], played) == "Agoraphobia"
    # everything played a lot: still suggest the most popular rather than nothing
    assert pick_song(["Desire Lines"], played) == "Desire Lines"
    assert pick_song([], played) is None


async def test_a_pass_stores_suggestions_and_cold_corners_each_with_a_song(tmp_path: Path) -> None:
    store = await _store(tmp_path)
    try:
        lastfm = FakeLastfm(
            similar={
                "The Dandy Warhols": [
                    ("Deerhunter", 0.9),
                    ("Tame Impala", 0.8),  # already in the library: not suggested
                    ("The Dandy Warhols", 0.7),  # yourself, never
                ]
            },
            top={"Deerhunter": ["Desire Lines", "Helicopter"]},
        )
        report = await _runner(store, lastfm).run(GENOME, FakeLibrary(LIBRARY, LIBRARY_TRACKS), KEY)
        assert report.suggested == 1
        assert report.suggested_with_song == 1
        assert report.in_library == 1
        result = await _runner(store, lastfm).read(lastfm_configured=True)
        assert result.suggested_state == "ready"
        [suggested] = result.suggested
        assert (suggested.artist_name, suggested.song, suggested.seed_artist) == (
            "Deerhunter",
            "Desire Lines",
            "The Dandy Warhols",
        )
        # Tame Impala is in the library, in the divergent genre, never played: a cold corner,
        # with one of its LIBRARY tracks (so it always plays)
        [cold] = result.in_library
        assert (cold.artist_name, cold.song, cold.plays) == ("Tame Impala", "Let It Happen", 0)
        # the key only ever went to Last.fm as a parameter, and every request carried it
        assert all(call["api_key"] == KEY for call in lastfm.calls)
    finally:
        await store.close()


async def test_reading_never_touches_the_network(tmp_path: Path) -> None:
    store = await _store(tmp_path)
    try:
        lastfm = FakeLastfm(similar={}, top={})
        result = await _runner(store, lastfm).read(lastfm_configured=True)
        assert result.suggested_state == "pending"
        assert result.suggested == []
        assert lastfm.calls == []
    finally:
        await store.close()


async def test_without_lastfm_only_the_library_half_runs(tmp_path: Path) -> None:
    store = await _store(tmp_path)
    try:
        lastfm = FakeLastfm(similar={}, top={})
        report = await _runner(store, lastfm).run(
            GENOME, FakeLibrary(LIBRARY, LIBRARY_TRACKS), None
        )
        assert lastfm.calls == []
        assert report.in_library == 1
        result = await _runner(store, lastfm).read(lastfm_configured=False)
        assert result.suggested_state == "unavailable"
        assert [row.artist_name for row in result.in_library] == ["Tame Impala"]
    finally:
        await store.close()


async def test_music_assistant_down_keeps_the_last_lists(tmp_path: Path) -> None:
    """No library: the cold corners stay, and suggestions are not refreshed unfiltered."""
    store = await _store(tmp_path)
    try:
        lastfm = FakeLastfm(
            similar={"The Dandy Warhols": [("Deerhunter", 0.9)]},
            top={"Deerhunter": ["Desire Lines"]},
        )
        library = FakeLibrary(LIBRARY, LIBRARY_TRACKS)
        await _runner(store, lastfm).run(GENOME, library, KEY)
        calls_before = len(lastfm.calls)
        library.fail = True
        report = await _runner(store, lastfm, now=NOW + 86400).run(GENOME, library, KEY)
        assert report.in_library is None
        assert len(lastfm.calls) == calls_before  # not asked again without the library
        result = await _runner(store, lastfm).read(lastfm_configured=True)
        assert [row.artist_name for row in result.in_library] == ["Tame Impala"]
        assert [row.artist_name for row in result.suggested] == ["Deerhunter"]
        # and with no connection at all, the same
        report = await _runner(store, lastfm).run(GENOME, None, KEY)
        assert report.in_library is None
        assert [
            row.artist_name
            for row in (await _runner(store, lastfm).read(lastfm_configured=True)).in_library
        ] == ["Tame Impala"]
    finally:
        await store.close()


async def test_a_failing_seed_cools_down_and_the_error_never_holds_the_key(tmp_path: Path) -> None:
    store = await _store(tmp_path)
    try:
        lastfm = FakeLastfm(similar={}, top={}, failing=frozenset({"The Dandy Warhols"}))
        report = await _runner(store, lastfm).run(GENOME, FakeLibrary(LIBRARY, {}), KEY)
        assert report.seeds_failing == 1
        assert KEY not in report.summary()
        asked = len(lastfm.calls)
        # an hour later: still cooling down, not asked again
        await _runner(store, lastfm, now=NOW + 3600).run(GENOME, FakeLibrary(LIBRARY, {}), KEY)
        assert len(lastfm.calls) == asked
        # after the cooldown: asked again
        later = NOW + GENOME_DISCOVERY_SEED_ERROR_COOLDOWN_HOURS * 3600 + 1
        await _runner(store, lastfm, now=later).run(GENOME, FakeLibrary(LIBRARY, {}), KEY)
        assert len(lastfm.calls) == asked + 1
    finally:
        await store.close()


async def test_an_artist_without_top_tracks_is_still_suggested_without_a_song(
    tmp_path: Path,
) -> None:
    store = await _store(tmp_path)
    try:
        lastfm = FakeLastfm(similar={"The Dandy Warhols": [("Obscure Band", 0.5)]}, top={})
        await _runner(store, lastfm).run(GENOME, FakeLibrary(LIBRARY, {}), KEY)
        [row] = (await _runner(store, lastfm).read(lastfm_configured=True)).suggested
        assert (row.artist_name, row.song) == ("Obscure Band", None)
    finally:
        await store.close()
