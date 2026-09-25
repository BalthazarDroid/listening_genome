"""
MusicBrainz artist enrichment (§1.9, §3.8, D-08).

Resolves an artist name to a MusicBrainz ID, tags, life-span begin year and country, through
the injected :class:`~listening_genome.core.http.HttpClient` - the seam tests use, since
MusicBrainz is unreachable from this workspace.

The fork preferred Music Assistant's loaded ``musicbrainz`` provider, which went to MA's own
mirror with MA's identity. That path left with the process. Requests now go to musicbrainz.org
itself, identified by the integration's own User-Agent (``core/http.py::user_agent``).
"""

from __future__ import annotations

import asyncio
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..compat import DEFAULT_GENRE_MAPPING, create_safe_string
from ..core.constants import (
    LOGGER,
    MUSICBRAINZ_BASE_URL,
    RESOLVE_STATE_ERROR,
    RESOLVE_STATE_NOT_FOUND,
    RESOLVE_STATE_OK,
)
from ..core.http import describe_http_error

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from ..core.http import HttpClient
    from ..core.protocols import GenomeStoreProtocol

# musicbrainz.org itself. This used to be MA's mirror (musicbrainz-mirror.music-assistant.io),
# carried over from the fork - but that mirror answers 403 to anything not identifying itself as
# Music Assistant, which this integration no longer is and does not pretend to be.
_MB_BASE_URL = MUSICBRAINZ_BASE_URL

# from the fork's providers/musicbrainz/constants.py::LUCENE_SPECIAL
_LUCENE_SPECIAL = r'([+\-&|!(){}\[\]\^"~*?:\\\/])'

_MIN_MATCH_SCORE = 85
_MAX_GENRES_PER_ARTIST = 3


@dataclass(slots=True, frozen=True)
class ArtistMetaUpdate:
    """The MusicBrainz-derived fields for one artist, ready to hand to ``GenomeStore``."""

    mbid: str | None
    mb_tags: tuple[tuple[str, int], ...]
    genres: tuple[str, ...]
    begin_year: int | None
    country: str | None


@dataclass(slots=True)
class MusicBrainzPassReport:
    """What one MusicBrainz pass did, for the log and for the enrichment job's message."""

    attempted: int = 0
    resolved: int = 0
    not_found: int = 0
    failed: int = 0
    #: ``(artist name, reason)`` for every lookup that raised, in order
    failures: list[tuple[str, str]] = field(default_factory=list)

    def failure_reasons(self) -> dict[str, int]:
        """Return how many failures each distinct reason accounts for, most common first."""
        return dict(Counter(reason for _name, reason in self.failures).most_common())


def _normalize_for_match(value: str) -> str:
    """Fold a genre/tag name for alias matching: lowercase, ``&``/``_``/``-`` normalized."""
    value = value.lower().strip().replace("&", "and")
    value = re.sub(r"[-_]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _build_alias_lookup() -> dict[str, str]:
    """Build the normalized-alias -> ``translation_key`` lookup from ``genre_mapping.json``."""
    lookup: dict[str, str] = {}
    for entry in DEFAULT_GENRE_MAPPING:
        translation_key = entry["translation_key"]
        for alias in (*entry.get("aliases", ()), entry["genre"]):
            lookup.setdefault(_normalize_for_match(alias), translation_key)
    return lookup


_ALIAS_LOOKUP = _build_alias_lookup()


async def resolve_artist(
    name: str,
    *,
    client: HttpClient,
) -> ArtistMetaUpdate | None:
    """
    Resolve an artist name to MusicBrainz metadata, or ``None`` if no confident match exists.

    A transport failure or an unexpected response shape propagates as an exception rather than
    being swallowed here, so :func:`enrich_pending_artists` can tell "not found" (``None``, cheap
    30-day recheck) apart from "MusicBrainz did not answer" (exception, ``resolve_state="error"``,
    short cooldown — see §3.8). Callers that do not go through :func:`enrich_pending_artists` must
    apply the same distinction themselves; a rebuild must never fail outright because MusicBrainz
    is briefly unreachable.

    :param name: The artist name as reported by a listen.
    :param client: The :class:`HttpClient` to issue the MusicBrainz requests through.
    """
    mbid = await _search_artist(name, client=client)
    if mbid is None:
        return None
    return await _lookup_artist(mbid, client=client)


async def enrich_pending_artists(
    store: GenomeStoreProtocol,
    *,
    client: HttpClient,
    limit: int = 200,
    min_interval_seconds: float = 0.0,
) -> int:
    """
    Resolve and store MusicBrainz metadata for pending artists; return how many resolved.

    The fork's signature and return value, kept for its callers and tests; the pass itself is
    :func:`run_musicbrainz_pass`, which also reports what failed and why.
    """
    report = await run_musicbrainz_pass(
        store, client=client, limit=limit, min_interval_seconds=min_interval_seconds
    )
    return report.resolved


async def run_musicbrainz_pass(
    store: GenomeStoreProtocol,
    *,
    client: HttpClient,
    limit: int = 200,
    min_interval_seconds: float = 0.0,
    on_progress: Callable[[int, int, MusicBrainzPassReport], None] | None = None,
) -> MusicBrainzPassReport:
    """
    Resolve and store MusicBrainz metadata for pending artists, one at a time.

    Every artist :meth:`GenomeStore.pending_artist_keys` returns is resolved independently,
    never letting a single failure abort the batch, and each result is written as soon as it is
    known, so a restart mid-pass loses at most the artist in flight. As in the fork:

    * a confident match is stored with ``resolve_state="ok"``;
    * no confident match is ``not_found`` (rechecked after a 30-day cooldown);
    * a lookup that RAISED (HTTP error, timeout, unexpected shape) is ``error``, retried after
      the short error cooldown, and listed by ``listening_genome/unresolved_artists``.

    :param store: The ``GenomeStore``-shaped object to read pending artists from and write to.
    :param client: The :class:`HttpClient` to issue MusicBrainz requests through.
    :param limit: The maximum number of artists to resolve in this pass.
    :param min_interval_seconds: Minimum wall-clock spacing between artists' lookups (§3.8,
        P3); ``0`` relies on the client's own throttling alone.
    :param on_progress: Called after each artist with ``(done, total, report)``. Must be cheap
        and must not write the database (see ``core/jobs.py``).
    """
    report = MusicBrainzPassReport()
    pending = await store.pending_artist_keys(limit=limit)
    if not pending:
        LOGGER.debug("MusicBrainz enrichment: no artists are due for resolution")
        return report
    LOGGER.info("MusicBrainz enrichment pass starting: %d artists due", len(pending))
    last_call = 0.0
    for artist_key, artist_name in pending:
        if min_interval_seconds > 0:
            wait = min_interval_seconds - (time.monotonic() - last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            last_call = time.monotonic()
        report.attempted += 1
        try:
            update = await resolve_artist(artist_name, client=client)
        except Exception as err:
            reason = describe_http_error(err)
            LOGGER.debug("MusicBrainz lookup failed for %r: %s (%s)", artist_name, reason, err)
            report.failed += 1
            report.failures.append((artist_name, reason))
            await store.upsert_artist_meta_full(
                [{"artist_key": artist_key, "artist_name": artist_name}], state=RESOLVE_STATE_ERROR
            )
        else:
            if update is None:
                report.not_found += 1
                await store.upsert_artist_meta_full(
                    [{"artist_key": artist_key, "artist_name": artist_name}],
                    state=RESOLVE_STATE_NOT_FOUND,
                )
            else:
                await store.upsert_artist_meta_full(
                    [
                        {
                            "artist_key": artist_key,
                            "artist_name": artist_name,
                            "mbid": update.mbid,
                            "mb_tags": [
                                {"name": name, "count": count} for name, count in update.mb_tags
                            ],
                            "genres": list(update.genres),
                            "begin_year": update.begin_year,
                            "country": update.country,
                        }
                    ],
                    state=RESOLVE_STATE_OK,
                )
                report.resolved += 1
        if on_progress is not None:
            on_progress(report.attempted, len(pending), report)
    if report.failures:
        # Named, at INFO, with the reason: a handful of artists that fail every pass is the
        # difference between "still working" and "stuck", and nobody reads debug logs on a
        # live box. The reason tally is what tells a 503 (rate limited) from a 403 (refused).
        LOGGER.info(
            "MusicBrainz lookup failed for %d artist(s) this pass (%s): %s",
            report.failed,
            ", ".join(f"{reason} x{count}" for reason, count in report.failure_reasons().items()),
            ", ".join(f"{name!r} ({reason})" for name, reason in report.failures[:8]),
        )
    LOGGER.info(
        "MusicBrainz enrichment pass finished: %d of %d resolved, %d not found, %d failed",
        report.resolved,
        len(pending),
        report.not_found,
        report.failed,
    )
    return report


async def _search_artist(name: str, *, client: HttpClient) -> str | None:
    """Search by artist name and return the best matching MBID, or ``None``."""
    escaped = re.sub(_LUCENE_SPECIAL, r"\\\1", name)
    query = f'artist:"{escaped}"'
    data = await _get("artist", {"query": query, "limit": "5"}, client=client)
    candidates = data.get("artists", []) if isinstance(data, dict) else []
    safe_name = create_safe_string(name)
    for candidate in candidates:
        score = candidate.get("score", 0) or 0
        if score >= _MIN_MATCH_SCORE and create_safe_string(candidate.get("name", "")) == safe_name:
            mbid: str = candidate["id"]
            return mbid
    return None


async def _lookup_artist(mbid: str, *, client: HttpClient) -> ArtistMetaUpdate:
    """Fetch full artist details for a known MBID and build an :class:`ArtistMetaUpdate`."""
    data = await _get(f"artist/{mbid}", {"inc": "tags+genres"}, client=client)
    tags = sorted((data.get("tags") or []), key=lambda tag: tag.get("count", 0), reverse=True)
    mb_tags = tuple((tag["name"], int(tag.get("count", 0))) for tag in tags if tag.get("name"))
    genres = _map_tags_to_genres(name for name, _count in mb_tags)
    life_span = data.get("life-span") or {}
    return ArtistMetaUpdate(
        mbid=mbid,
        mb_tags=mb_tags,
        genres=genres,
        begin_year=_parse_year(life_span.get("begin")),
        country=data.get("country"),
    )


async def _get(endpoint: str, params: dict[str, str], *, client: HttpClient) -> Any:
    """Issue one MusicBrainz GET to musicbrainz.org, throttled and identified by ``client``."""
    url = f"{_MB_BASE_URL}/{endpoint}"
    return await client.get_json(url, params={**params, "fmt": "json"})


def _map_tags_to_genres(tag_names: Any) -> tuple[str, ...]:
    """Map tag names (most-confident first) to up to 3 distinct ``genre_mapping.json`` keys."""
    genres: list[str] = []
    for tag_name in tag_names:
        translation_key = _ALIAS_LOOKUP.get(_normalize_for_match(tag_name))
        if translation_key and translation_key not in genres:
            genres.append(translation_key)
        if len(genres) >= _MAX_GENRES_PER_ARTIST:
            break
    return tuple(genres)


def map_genre_names(names: Iterable[str]) -> tuple[str, ...]:
    """
    Map free-form genre/tag names to ``genre_mapping.json`` translation keys (D-07).

    The public entry point onto the same alias table the MusicBrainz tag mapping uses, so a
    genre string that arrives from somewhere else entirely (an MA library artist's own
    metadata, for the discovery feature) lands in exactly the same 59-key vocabulary the
    divergence maths is expressed in.

    :param names: Genre/tag names, most confident first.
    """
    return _map_tags_to_genres(names)


def _parse_year(value: Any) -> int | None:
    """Parse a MusicBrainz ``life-span.begin`` value (``"1994"`` or ``"1994-03-01"``) to a year."""
    if not value or not isinstance(value, str):
        return None
    try:
        return int(value[:4])
    except ValueError:
        return None


__all__ = [
    "ArtistMetaUpdate",
    "MusicBrainzPassReport",
    "enrich_pending_artists",
    "map_genre_names",
    "resolve_artist",
    "run_musicbrainz_pass",
]
