"""
Discovery: artists worth trying, each with ONE song to play (slice 2d).

Ported from the fork's ``discovery.py`` and ``GenomeController._run_discovery_pass``, with two
changes of substance:

* **A song per artist.** Every suggestion now carries one track, because the panel plays it
  on a click (Bob, 2026-09-25: "just the one song", on a speaker picked each time). For a
  Last.fm suggestion it is the artist's most popular track on Last.fm; for a cold corner (an
  artist already in the library) it is one of their tracks IN the library, so it always plays.
  Either way, a track the household has already played more than
  :data:`GENOME_DISCOVERY_SONG_MAX_PLAYS` times is passed over for the next one - a
  "discovery" that is your own favourite is not one.
* **Both halves are computed by the background pass and stored.** The fork ranked cold
  corners at read time from MA's own database; here the library lives behind Music
  Assistant's API, and choosing a song needs a request per artist, so the read path serves
  what the pass stored and stays free of any network - the rule D-16 was written for (a read
  that fell through to network work once hung the page for an hour).

No Home Assistant imports. The Music Assistant library arrives through :class:`LibrarySource`,
which the Home Assistant side implements over the MA client.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Protocol

from ..compat import create_safe_string, parse_title_and_version
from ..enrich.lastfm_similar import fetch_similar_artists, fetch_top_tracks
from .constants import (
    DISCOVERY_STATE_PENDING,
    DISCOVERY_STATE_READY,
    DISCOVERY_STATE_UNAVAILABLE,
    GENOME_DISCOVERY_COLD_LIMIT,
    GENOME_DISCOVERY_COLD_MAX_PLAYS,
    GENOME_DISCOVERY_LASTFM_MIN_INTERVAL_SECONDS,
    GENOME_DISCOVERY_SEED_ERROR_COOLDOWN_HOURS,
    GENOME_DISCOVERY_SEED_LIMIT,
    GENOME_DISCOVERY_SIMILAR_PER_SEED,
    GENOME_DISCOVERY_SONG_MAX_PLAYS,
    GENOME_DISCOVERY_SUGGESTED_LIMIT,
    GENOME_DISCOVERY_TOP_TRACKS,
    LISTENER_HOUSEHOLD,
    LOGGER,
)
from .models import ColdArtist, DiscoveryResult, SuggestedArtist

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping, Sequence

    from .http import HttpClient
    from .models import GenomeResult
    from .store import GenomeStore


@dataclass(slots=True, frozen=True)
class LibraryArtist:
    """One artist in the Music Assistant library, with the genres the library holds for it."""

    artist_key: str
    artist_name: str
    genres: tuple[str, ...]
    #: MA's own reference, to ask for this artist's tracks (opaque to this module)
    ref: Any = None


class LibrarySource(Protocol):
    """The Music Assistant library, as discovery needs it."""

    async def artists(self) -> list[LibraryArtist]:
        """Every artist in the library."""

    async def track_names(self, artist: LibraryArtist) -> list[str]:
        """Titles of the artist's tracks in the library, best first."""


@dataclass(slots=True, frozen=True)
class DivergentGenre:
    """One genre the household over-expresses relative to the baseline, and by how much."""

    key: str
    label: str
    contribution: float


@dataclass(slots=True, frozen=True)
class DiscoverySeed:
    """One of the household's own artists, chosen to seed a Last.fm similar-artist lookup."""

    artist_key: str
    artist_name: str
    genre: DivergentGenre


@dataclass(slots=True)
class DiscoveryReport:
    """What one discovery pass did, for the job message."""

    seeds_queried: int = 0
    seeds_failing: int = 0
    suggested: int = 0
    suggested_with_song: int = 0
    in_library: int | None = None  # None: the library could not be read this pass
    in_library_with_song: int = 0
    lastfm: bool = True
    #: artists Music Assistant's library holds, and how many of them have genres to match on
    library_artists: int = 0
    library_with_genres: int = 0
    #: barely played library artists with no genres anywhere, newly queued for a lookup
    lookups_queued: int = 0

    def summary(self) -> str:
        parts = []
        if self.lastfm:
            parts.append(
                f"{self.suggested} artists suggested from {self.seeds_queried} of your "
                f"favourites ({self.suggested_with_song} with a song)"
            )
            if self.seeds_failing:
                parts.append(f"{self.seeds_failing} favourites Last.fm could not answer for")
        else:
            parts.append("no Last.fm account, so no suggestions from outside the library")
        if self.in_library is None:
            parts.append("Music Assistant's library could not be read; kept the last list")
        else:
            parts.append(
                f"{self.in_library} barely played artists in the library "
                f"({self.in_library_with_song} with a song), from {self.library_artists} "
                f"library artists ({self.library_with_genres} with genres)"
            )
            if self.lookups_queued:
                parts.append(
                    f"{self.lookups_queued} library artists queued for a genre lookup; "
                    "they join after the next enrichment passes"
                )
        return "; ".join(parts)


def divergent_genres(genome: GenomeResult | None, *, limit: int = 5) -> list[DivergentGenre]:
    """
    Return the genres the household over-expresses most, strongest first (unchanged port).

    Ranked from ``genres`` rather than ``divergence.top_over``, which drops genres the baseline
    cannot speak to - exactly the least mainstream ones discovery exists to surface.
    """
    if not genome:
        return []
    over = [
        share
        for share in genome.get("genres") or []
        if share.get("key")
        and float(share.get("share") or 0.0) > float(share.get("baseline_share") or 0.0)
    ]
    over.sort(key=lambda share: float(share.get("contribution") or 0.0), reverse=True)
    return [
        DivergentGenre(
            key=str(share["key"]),
            label=str(share.get("label") or share["key"]),
            contribution=float(share.get("contribution") or 0.0),
        )
        for share in over[:limit]
    ]


def rank_cold_corners(
    library_artists: Sequence[LibraryArtist],
    genres: Sequence[DivergentGenre],
    *,
    plays: Mapping[str, int],
    max_plays: int = GENOME_DISCOVERY_COLD_MAX_PLAYS,
    limit: int = GENOME_DISCOVERY_COLD_LIMIT,
) -> list[tuple[LibraryArtist, ColdArtist]]:
    """
    Rank barely played library artists by how well they fit the household's divergent genres.

    ``plays`` is the stored listen count per artist key - the whole imported history, which is
    a better measure than the library's own counter (zero for anything played before MA).
    """
    if not genres:
        return []
    by_key = {genre.key: genre for genre in genres}
    matched: list[tuple[float, int, str, LibraryArtist, ColdArtist]] = []
    for artist in library_artists:
        count = plays.get(artist.artist_key, 0)
        if count > max_plays:
            continue
        best = max(
            (by_key[key] for key in artist.genres if key in by_key),
            key=lambda genre: genre.contribution,
            default=None,
        )
        if best is None:
            continue
        matched.append(
            (
                -best.contribution,
                count,
                artist.artist_name.casefold(),
                artist,
                ColdArtist(
                    artist_key=artist.artist_key,
                    artist_name=artist.artist_name,
                    plays=count,
                    genre_key=best.key,
                    genre_label=best.label,
                ),
            )
        )
    matched.sort(key=lambda row: row[:3])
    return [(row[3], row[4]) for row in matched[:limit]]


def select_seeds(
    genome: GenomeResult | None, genres: Sequence[DivergentGenre], *, limit: int
) -> list[DiscoverySeed]:
    """The household's own top artists in a divergent genre, strongest first (unchanged port)."""
    if not genome or not genres:
        return []
    by_key = {genre.key: genre for genre in genres}
    seeds: list[DiscoverySeed] = []
    for artist in genome.get("top_artists") or []:
        best = max(
            (by_key[key] for key in (artist.get("genres") or []) if key in by_key),
            key=lambda genre: genre.contribution,
            default=None,
        )
        if best is None:
            continue
        seeds.append(
            DiscoverySeed(
                artist_key=str(artist["artist_key"]),
                artist_name=str(artist["name"]),
                genre=best,
            )
        )
        if len(seeds) >= limit:
            break
    return seeds


def pick_song(candidates: Sequence[str], played: Mapping[str, int]) -> str | None:
    """
    The first candidate the household has not already played much, else the first at all.

    Candidates are keyed the way every importer keys a track (title without its version,
    safe-string), so "Song (Remastered)" counts plays of "Song".
    """
    fallback: str | None = None
    for name in candidates:
        title, _version = parse_title_and_version(name, strip_for_search=True)
        key = create_safe_string(title)
        if not key:
            continue
        if fallback is None:
            fallback = name
        if played.get(key, 0) <= GENOME_DISCOVERY_SONG_MAX_PLAYS:
            return name
    return fallback


class DiscoveryRunner:
    """Compute and store discovery: the background pass, and the read of what it stored."""

    def __init__(
        self,
        store: GenomeStore,
        *,
        lastfm_client: HttpClient,
        sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """
        Initialize the runner.

        :param store: Where the result is cached and the history is read from.
        :param lastfm_client: Identified client for ws.audioscrobbler.com.
        :param sleep: Pacing between Last.fm calls (tests pass a no-op).
        :param clock: Wall clock, for the seed-failure cooldown and ``generated_at``.
        """
        self.store = store
        self.lastfm_client = lastfm_client
        self._sleep = sleep
        self._clock = clock

    async def read(self, *, lastfm_configured: bool) -> DiscoveryResult:
        """What the last pass stored (database only; no network, ever - see module docstring)."""
        cached = await self.store.get_cached_discovery(LISTENER_HOUSEHOLD) or {}
        generated_at = cached.get("generated_at")
        if not lastfm_configured:
            state = DISCOVERY_STATE_UNAVAILABLE
        elif not cached.get("lastfm_generated_at"):
            state = DISCOVERY_STATE_PENDING
        else:
            state = DISCOVERY_STATE_READY
        return DiscoveryResult(
            in_library=_rows(ColdArtist, cached.get("in_library")),
            suggested=_rows(SuggestedArtist, cached.get("suggested")) if lastfm_configured else [],
            suggested_state=state,
            generated_at=float(generated_at) if generated_at else None,
        )

    async def run(
        self, genome: GenomeResult | None, library: LibrarySource | None, api_key: str | None
    ) -> DiscoveryReport:
        """
        One pass: cold corners from the library, suggestions from Last.fm, a song for each.

        :param genome: The current genome (its divergent genres and top artists steer both).
        :param library: The MA library, or ``None`` when Music Assistant is not connected - the
            previous cold-corner list is then kept rather than emptied.
        :param api_key: The Last.fm key, or ``None``/empty for no Last.fm half.
        """
        report = DiscoveryReport(lastfm=bool(api_key))
        cached = await self.store.get_cached_discovery(LISTENER_HOUSEHOLD) or {}
        genres = divergent_genres(genome)
        plays = await self.store.artist_play_counts(LISTENER_HOUSEHOLD)
        library_artists: list[LibraryArtist] | None = None
        if library is not None:
            try:
                library_artists = await library.artists()
            except Exception:
                LOGGER.warning(
                    "Discovery: could not read the Music Assistant library", exc_info=True
                )

        blob: dict[str, Any] = {
            "generated_at": self._clock(),
            "in_library": cached.get("in_library") or [],
            "suggested": cached.get("suggested") or [],
            "seed_failures": cached.get("seed_failures") or {},
            "lastfm_generated_at": cached.get("lastfm_generated_at"),
        }

        if library is not None and library_artists is not None:
            library_artists = await self._with_stored_genres(library_artists, plays, report)
            cold = await self._cold_corners(library, library_artists, genres, plays)
            blob["in_library"] = [row.to_dict() for row in cold]
            report.in_library = len(cold)
            report.in_library_with_song = sum(1 for row in cold if row.song)
        if api_key:
            known = set(plays)
            if library_artists is not None:
                known.update(artist.artist_key for artist in library_artists)
            else:
                # without the library, suggestions could name artists Bob already owns: keep
                # the last list instead of storing an unfiltered one
                LOGGER.info("Discovery: library unavailable, Last.fm suggestions not refreshed")
                api_key = None
        if api_key:
            suggested, failures, queried = await self._suggestions(
                genome, genres, known, api_key, blob["seed_failures"]
            )
            blob["suggested"] = [row.to_dict() for row in suggested]
            blob["seed_failures"] = failures
            blob["lastfm_generated_at"] = self._clock()
            report.seeds_queried = queried
            report.seeds_failing = len(failures)
            report.suggested = len(suggested)
            report.suggested_with_song = sum(1 for row in suggested if row.song)
        await self.store.set_cached_discovery(LISTENER_HOUSEHOLD, blob)
        return report

    async def _with_stored_genres(
        self,
        library_artists: list[LibraryArtist],
        plays: Mapping[str, int],
        report: DiscoveryReport,
    ) -> list[LibraryArtist]:
        """
        Give library artists without genres the ones Genome looked up itself.

        Music Assistant's library artists often carry no genres at all (whether they do depends
        on which providers filled in their metadata), and without genres nothing can match a
        divergent genre. Genome's own MusicBrainz genres cover every artist in the listening
        history; barely played artists with none anywhere are queued for the same lookup.
        """
        missing = [artist.artist_key for artist in library_artists if not artist.genres]
        stored = await self.store.artist_genres(missing) if missing else {}
        filled: list[LibraryArtist] = []
        to_look_up: list[tuple[str, str]] = []
        for artist in library_artists:
            if not artist.genres and artist.artist_key in stored:
                artist = replace(artist, genres=stored[artist.artist_key])
            elif not artist.genres and plays.get(artist.artist_key, 0) <= (
                GENOME_DISCOVERY_COLD_MAX_PLAYS
            ):
                to_look_up.append((artist.artist_key, artist.artist_name))
            filled.append(artist)
        report.library_artists = len(filled)
        report.library_with_genres = sum(1 for artist in filled if artist.genres)
        if to_look_up:
            try:
                report.lookups_queued = await self.store.queue_artist_lookups(to_look_up)
            except Exception:
                LOGGER.warning("Discovery: could not queue genre lookups", exc_info=True)
        return filled

    async def _cold_corners(
        self,
        library: LibrarySource,
        library_artists: Sequence[LibraryArtist],
        genres: Sequence[DivergentGenre],
        plays: Mapping[str, int],
    ) -> list[ColdArtist]:
        ranked = rank_cold_corners(library_artists, genres, plays=plays)
        rows: list[ColdArtist] = []
        for artist, row in ranked:
            song: str | None = None
            try:
                names = await library.track_names(artist)
                song = pick_song(
                    names, await self.store.track_play_counts(LISTENER_HOUSEHOLD, artist.artist_key)
                )
            except Exception:
                LOGGER.debug(
                    "Discovery: no library tracks for %s", artist.artist_name, exc_info=True
                )
            rows.append(
                ColdArtist(
                    artist_key=row.artist_key,
                    artist_name=row.artist_name,
                    plays=row.plays,
                    genre_key=row.genre_key,
                    genre_label=row.genre_label,
                    song=song,
                )
            )
        return rows

    async def _suggestions(
        self,
        genome: GenomeResult | None,
        genres: Sequence[DivergentGenre],
        known: set[str],
        api_key: str,
        previous_failures: Mapping[str, float],
    ) -> tuple[list[SuggestedArtist], dict[str, float], int]:
        """The fork's Last.fm walk (paced, with a failure cooldown per seed), plus a song each."""
        seeds = select_seeds(genome, genres, limit=GENOME_DISCOVERY_SEED_LIMIT)
        failures = {k: float(v) for k, v in previous_failures.items()}
        now = self._clock()
        cooldown = GENOME_DISCOVERY_SEED_ERROR_COOLDOWN_HOURS * 3600
        best: dict[str, SuggestedArtist] = {}
        queried = 0
        for seed in seeds:
            if now - failures.get(seed.artist_key, 0.0) < cooldown:
                continue
            if queried:
                await self._sleep(GENOME_DISCOVERY_LASTFM_MIN_INTERVAL_SECONDS)
            queried += 1
            try:
                similar = await fetch_similar_artists(
                    seed.artist_name,
                    client=self.lastfm_client,
                    api_key=api_key,
                    limit=GENOME_DISCOVERY_SIMILAR_PER_SEED,
                )
            except Exception as err:  # the message never holds the key (describe_fetch_error)
                LOGGER.info("Discovery: seed %r failed: %s", seed.artist_name, err)
                failures[seed.artist_key] = now
                continue
            failures.pop(seed.artist_key, None)
            for entry in similar:
                key = create_safe_string(entry.name)
                if not key or key in known:
                    continue
                existing = best.get(key)
                if existing is not None and existing.match >= entry.match:
                    continue
                best[key] = SuggestedArtist(
                    artist_name=entry.name,
                    mbid=entry.mbid,
                    seed_artist=seed.artist_name,
                    genre_key=seed.genre.key,
                    genre_label=seed.genre.label,
                    match=entry.match,
                )
        ranked = sorted(best.values(), key=lambda row: (-row.match, row.artist_name.casefold()))
        ranked = ranked[:GENOME_DISCOVERY_SUGGESTED_LIMIT]
        with_songs: list[SuggestedArtist] = []
        for row in ranked:
            await self._sleep(GENOME_DISCOVERY_LASTFM_MIN_INTERVAL_SECONDS)
            song: str | None = None
            try:
                tracks = await fetch_top_tracks(
                    row.artist_name,
                    client=self.lastfm_client,
                    api_key=api_key,
                    limit=GENOME_DISCOVERY_TOP_TRACKS,
                )
                song = pick_song(
                    tracks,
                    await self.store.track_play_counts(
                        LISTENER_HOUSEHOLD, create_safe_string(row.artist_name)
                    ),
                )
            except Exception as err:
                LOGGER.info("Discovery: no top tracks for %r: %s", row.artist_name, err)
            with_songs.append(
                SuggestedArtist(
                    artist_name=row.artist_name,
                    mbid=row.mbid,
                    seed_artist=row.seed_artist,
                    genre_key=row.genre_key,
                    genre_label=row.genre_label,
                    match=row.match,
                    song=song,
                )
            )
        seed_keys = {seed.artist_key for seed in seeds}
        return with_songs, {k: v for k, v in failures.items() if k in seed_keys}, queried


def _rows(cls: Any, raw: Any) -> list[Any]:
    """Rebuild stored rows, skipping any that no longer parse (a hand-edited or odd blob)."""
    rows = []
    for row in raw or []:
        try:
            rows.append(cls.from_dict(row))
        except Exception:  # one bad row must not blank the whole card
            LOGGER.debug("Skipping an unreadable stored discovery row: %r", row)
    return rows


__all__ = [
    "DiscoveryReport",
    "DiscoveryRunner",
    "DivergentGenre",
    "LibraryArtist",
    "LibrarySource",
    "divergent_genres",
    "pick_song",
    "rank_cold_corners",
    "select_seeds",
]
