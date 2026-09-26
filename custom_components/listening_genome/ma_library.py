"""The Music Assistant library, read over the live-capture session, for discovery."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .compat import create_safe_string
from .core.discovery import LibraryArtist
from .enrich.musicbrainz import map_genre_names

if TYPE_CHECKING:
    from music_assistant_client import MusicAssistantClient

#: artists fetched per request when paging through the library
PAGE_SIZE = 500
#: a library bigger than this is read no further (a safety stop, not a real limit)
MAX_ARTISTS = 50_000


class MusicAssistantLibrary:
    """:class:`~.core.discovery.LibrarySource` over a connected ``MusicAssistantClient``."""

    def __init__(self, client: MusicAssistantClient) -> None:
        """Wrap an already connected client (the live capture's)."""
        self._client = client

    async def artists(self) -> list[LibraryArtist]:
        """Every library artist, keyed and genre-mapped exactly as the importers key them."""
        artists: list[LibraryArtist] = []
        offset = 0
        while offset < MAX_ARTISTS:
            page = await self._client.music.get_library_artists(limit=PAGE_SIZE, offset=offset)
            for artist in page:
                name = (artist.name or "").strip()
                key = create_safe_string(name) if name else ""
                if not key:
                    continue
                genres = (artist.metadata.genres if artist.metadata else None) or ()
                artists.append(
                    LibraryArtist(
                        artist_key=key,
                        artist_name=name,
                        genres=map_genre_names(sorted(genres)),
                        ref=(artist.item_id, artist.provider),
                    )
                )
            if len(page) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
        return artists

    async def track_names(self, artist: LibraryArtist) -> list[str]:
        """The artist's tracks that are in the library, in the order MA gives them."""
        item_id, provider = artist.ref
        tracks = await self._client.music.get_artist_tracks(item_id, provider, in_library_only=True)
        return [track.name for track in tracks if track.name]
