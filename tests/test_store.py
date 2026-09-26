"""Tests for :class:`GenomeStore` (§3.1)."""

from __future__ import annotations

import asyncio
import sqlite3
import time
from typing import TYPE_CHECKING

from listening_genome.core.constants import (
    DB_TABLE_GENOME_ARTIST_META,
    GENOME_RESULT_SCHEMA_VERSION,
    RESOLVE_ERROR_COOLDOWN_HOURS,
    RESOLVE_STATE_ERROR,
)
from listening_genome.core.models import Listen
from listening_genome.core.store import ArtistMetaWrite, GenomeStore

if TYPE_CHECKING:
    from pathlib import Path


def _listen(**overrides: object) -> Listen:
    defaults: dict[str, object] = {
        "played_at": 1_700_000_000,
        "artist_key": "sigurros",
        "artist_name": "Sigur Rós",
        "track_key": "svefngenglar",
        "track_name": "Svefn-g-englar",
        "album_name": "Ágætis byrjun",
        "source": "apple_export",
        "player_id": None,
        "duration_ms": 600_000,
        "played_ms": 600_000,
        "fully_played": True,
        "confidence": 1.0,
    }
    defaults.update(overrides)
    return Listen(**defaults)  # type: ignore[arg-type]


async def _add_history(store: GenomeStore, *artist_keys: str) -> None:
    """
    Give each artist one listen, so its meta row counts as part of the listening history.

    Resolution counts and failure lists only cover artists with at least one listen; call this
    before any meta upsert, since `add_listens` inserts a `pending` stub the upsert overwrites.
    """
    await store.add_listens(
        [
            _listen(
                played_at=1_700_000_000 + i * 600,
                artist_key=key,
                artist_name=key,
                track_key=f"{key}-track",
                track_name=f"{key} track",
            )
            for i, key in enumerate(artist_keys)
        ],
        listener="household",
    )


async def _new_store(tmp_path: Path) -> GenomeStore:
    store = GenomeStore(str(tmp_path))
    await store.setup()
    return store


async def test_setup_is_idempotent(tmp_path: Path) -> None:
    """Calling setup twice against the same directory must not raise or duplicate schema."""
    store = await _new_store(tmp_path)
    await store.close()
    store2 = await _new_store(tmp_path)
    assert await store2.count_listens("household") == 0
    await store2.close()


async def test_add_listens_dedupes_within_same_minute(tmp_path: Path) -> None:
    """Two listens with the same dedupe_key must collapse to one stored row."""
    store = await _new_store(tmp_path)
    try:
        listens = [_listen(played_at=1_700_000_000), _listen(played_at=1_700_000_030)]
        result = await store.add_listens(listens, listener="household")
        assert result["rows_imported"] == 1
        assert result["rows_duplicate"] == 1
        assert await store.count_listens("household") == 1
    finally:
        await store.close()


async def test_add_listens_creates_pending_artist_stub(tmp_path: Path) -> None:
    """A newly-seen artist must appear in pending_artist_keys."""
    store = await _new_store(tmp_path)
    try:
        await store.add_listens([_listen()], listener="household")
        pending = await store.pending_artist_keys()
        assert pending == [("sigurros", "Sigur Rós")]
    finally:
        await store.close()


async def test_upsert_artist_meta_full_clears_pending_state(tmp_path: Path) -> None:
    """Resolving an artist must remove it from the pending queue and be readable back."""
    store = await _new_store(tmp_path)
    try:
        await store.add_listens([_listen()], listener="household")
        row: ArtistMetaWrite = {
            "artist_key": "sigurros",
            "artist_name": "Sigur Rós",
            "mbid": "f6f2326f-6b25-4170-b89d-e235b25508e8",
            "mb_tags": [{"name": "post-rock", "count": 8}],
            "genres": ["rock", "ambient"],
            "begin_year": 1994,
            "first_release_year": 1997,
            "country": "IS",
            "lb_listeners": 118422,
            "lb_listen_count": 4821334,
        }
        await store.upsert_artist_meta_full([row], state="ok")
        assert await store.pending_artist_keys() == []
        meta = await store.get_artist_meta(["sigurros"])
        assert meta["sigurros"].genres == ("rock", "ambient")
        assert meta["sigurros"].lb_listeners == 118422
    finally:
        await store.close()


async def test_source_counts_and_clear(tmp_path: Path) -> None:
    """source_counts groups by source; clear(listener=...) only drops that listener's rows."""
    store = await _new_store(tmp_path)
    try:
        await store.add_listens([_listen(source="apple_export")], listener="household")
        await store.add_listens(
            [
                _listen(
                    artist_key="acdc",
                    artist_name="AC/DC",
                    track_key="backinblack",
                    track_name="Back In Black",
                    played_at=1_700_100_000,
                    source="lastfm",
                )
            ],
            listener="household",
        )
        counts = await store.source_counts("household")
        assert counts == {"apple_export": 1, "lastfm": 1}

        await store.clear(listener="household")
        assert await store.count_listens("household") == 0
        # artist metadata (shared across listeners) is not cleared by a listener-scoped clear
        assert await store.pending_artist_keys(limit=10)
    finally:
        await store.close()


async def test_clear_all_drops_artist_meta_too(tmp_path: Path) -> None:
    """clear(listener=None) is a full reset, including artist metadata."""
    store = await _new_store(tmp_path)
    try:
        await store.add_listens([_listen()], listener="household")
        await store.clear()
        assert await store.count_listens("household") == 0
        assert await store.pending_artist_keys() == []
    finally:
        await store.close()


async def test_cached_genome_roundtrip(tmp_path: Path) -> None:
    """set_cached_genome/get_cached_genome round-trip an arbitrary JSON-shaped payload."""
    store = await _new_store(tmp_path)
    try:
        assert await store.get_cached_genome("household") is None
        payload = {
            "schema_version": GENOME_RESULT_SCHEMA_VERSION,
            "stats": {"total_listens": 0},
        }
        await store.set_cached_genome("household", payload)  # type: ignore[arg-type]
        assert await store.get_cached_genome("household") == payload
    finally:
        await store.close()


async def test_cached_genome_from_older_result_schema_is_discarded(tmp_path: Path) -> None:
    """
    A cached blob from an older result shape is dropped, not served.

    Regression: `bases`/`base_mix` were added to GenomeResult without the cache key
    changing, so `genome/get` kept serving pre-`bases` blobs. The frontend reads those
    fields unconditionally, and the missing key took the whole molecule card down with
    no server-side error to show for it.
    """
    store = await _new_store(tmp_path)
    try:
        stale = {
            "schema_version": GENOME_RESULT_SCHEMA_VERSION - 1,
            "stats": {"total_listens": 5},
        }
        await store.set_cached_genome("household", stale)  # type: ignore[arg-type]
        assert await store.get_cached_genome("household") is None
    finally:
        await store.close()


async def test_cached_genome_without_schema_version_is_discarded(tmp_path: Path) -> None:
    """A cache entry predating result versioning has no recorded shape, so it is dropped."""
    store = await _new_store(tmp_path)
    try:
        await store.set_cached_genome("household", {"stats": {}})  # type: ignore[arg-type]
        assert await store.get_cached_genome("household") is None
    finally:
        await store.close()


async def test_dedupe_window_drops_cross_source_duplicate(tmp_path: Path) -> None:
    """A Last.fm listen within 90s of an MA-sourced listen for the same track is dropped."""
    store = await _new_store(tmp_path)
    try:
        await store.add_listens(
            [_listen(source="ma_playlog", played_at=1_700_000_000)], listener="household"
        )
        await store.add_listens(
            [_listen(source="lastfm", played_at=1_700_000_050)], listener="household"
        )
        assert await store.count_listens("household") == 2
        deleted = await store.dedupe_window()
        assert deleted == 1
        assert await store.count_listens("household") == 1
    finally:
        await store.close()


async def test_iter_listens_respects_since(tmp_path: Path) -> None:
    """iter_listens only yields rows strictly newer than `since`."""
    store = await _new_store(tmp_path)
    try:
        await store.add_listens(
            [_listen(played_at=1_700_000_000), _listen(played_at=1_800_000_000, source="lastfm")],
            listener="household",
        )
        collected = [
            listen async for listen in store.iter_listens("household", since=1_750_000_000)
        ]
        assert len(collected) == 1
        assert collected[0].played_at == 1_800_000_000
    finally:
        await store.close()


async def test_lastfm_backfill_done_defaults_false_and_persists(tmp_path: Path) -> None:
    """The one-time Last.fm sweep flag (§3.1 `settings` table, P1) starts false and sticks."""
    store = await _new_store(tmp_path)
    try:
        assert await store.lastfm_backfill_done() is False
        await store.mark_lastfm_backfill_done()
        assert await store.lastfm_backfill_done() is True
        # independent of the (also settings-table-backed) MA playlog backfill flag
        assert await store.backfill_done() is False
    finally:
        await store.close()


async def test_artist_resolution_counts_groups_by_state(tmp_path: Path) -> None:
    """artist_resolution_counts (P3) reports a count per resolve_state across all artists."""
    store = await _new_store(tmp_path)
    try:
        assert await store.artist_resolution_counts() == {}
        await store.add_listens([_listen()], listener="household")  # -> one pending stub
        await _add_history(store, "resolved-artist", "missing-artist")
        await store.upsert_artist_meta_full(
            [{"artist_key": "resolved-artist", "artist_name": "Resolved Artist"}], state="ok"
        )
        await store.upsert_artist_meta_full(
            [{"artist_key": "missing-artist", "artist_name": "Missing Artist"}],
            state="not_found",
        )
        counts = await store.artist_resolution_counts()
        assert counts == {"pending": 1, "ok": 1, "not_found": 1}
    finally:
        await store.close()


async def test_pending_popularity_keys_finds_resolved_artists_missing_listeners(
    tmp_path: Path,
) -> None:
    """An artist with an mbid but no lb_listeners is the popularity backlog, regardless of age."""
    store = await _new_store(tmp_path)
    try:
        await store.upsert_artist_meta_full(
            [
                {
                    "artist_key": "sigurros",
                    "artist_name": "Sigur Rós",
                    "mbid": "f6f2326f-6b25-4170-b89d-e235b25508e8",
                }
            ],
            state="ok",
        )
        assert await store.pending_popularity_keys() == [
            ("sigurros", "f6f2326f-6b25-4170-b89d-e235b25508e8")
        ]
    finally:
        await store.close()


async def test_pending_popularity_keys_excludes_unresolved_and_already_populated(
    tmp_path: Path,
) -> None:
    """No mbid (still pending) and an already-known lb_listeners must both be excluded."""
    store = await _new_store(tmp_path)
    try:
        await store.add_listens([_listen()], listener="household")  # pending, no mbid yet
        await store.upsert_artist_meta_full(
            [
                {
                    "artist_key": "known-popularity",
                    "artist_name": "Known Popularity",
                    "mbid": "c3ae7ee4-8b02-4c33-8ae9-3d15fcb9d4d0",
                    "lb_listeners": 61,
                    "lb_listen_count": 900,
                }
            ],
            state="ok",
        )
        assert await store.pending_popularity_keys() == []
    finally:
        await store.close()


async def test_pending_popularity_keys_respects_limit(tmp_path: Path) -> None:
    """The limit argument caps how many backlog rows come back in one pass."""
    store = await _new_store(tmp_path)
    try:
        for i in range(3):
            await store.upsert_artist_meta_full(
                [{"artist_key": f"artist-{i}", "artist_name": f"Artist {i}", "mbid": f"mbid-{i}"}],
                state="ok",
            )
        assert len(await store.pending_popularity_keys(limit=2)) == 2
    finally:
        await store.close()


async def test_mark_popularity_attempted_rotates_backlog_order(tmp_path: Path) -> None:
    """Marking a backlog artist as attempted moves it behind others in resolved_at order."""
    store = await _new_store(tmp_path)
    try:
        await store.upsert_artist_meta_full(
            [{"artist_key": "always-unknown", "artist_name": "Always Unknown", "mbid": "mbid-a"}],
            state="ok",
        )
        await store.upsert_artist_meta_full(
            [{"artist_key": "next-in-line", "artist_name": "Next In Line", "mbid": "mbid-b"}],
            state="ok",
        )
        # both rows land with the same real-clock resolved_at (same second) - pin them apart
        # explicitly so this test's ordering assertions don't depend on sqlite's tie-break.
        assert store.database is not None
        await store.database.execute(
            "UPDATE genome_artist_meta SET resolved_at = :t WHERE artist_key = :k",
            {"t": 1_000, "k": "always-unknown"},
        )
        await store.database.execute(
            "UPDATE genome_artist_meta SET resolved_at = :t WHERE artist_key = :k",
            {"t": 2_000, "k": "next-in-line"},
        )
        await store.database.commit()

        backlog = await store.pending_popularity_keys(limit=1)
        assert backlog == [("always-unknown", "mbid-a")]

        await store.mark_popularity_attempted(["always-unknown"])
        backlog = await store.pending_popularity_keys(limit=1)
        assert backlog == [("next-in-line", "mbid-b")]
    finally:
        await store.close()


async def test_mark_popularity_attempted_noop_on_empty_list(tmp_path: Path) -> None:
    """Calling with no keys must not raise or touch anything."""
    store = await _new_store(tmp_path)
    try:
        await store.mark_popularity_attempted([])
    finally:
        await store.close()


async def test_pending_artist_keys_holds_off_a_repeatedly_failing_artist(tmp_path: Path) -> None:
    """
    An artist whose lookup raised is not eligible again until its cooldown expires.

    Regression: `error` was always eligible, so three artists that failed every time were
    retried on every pass and sat in "still resolving" for days - a progress notice that
    could never finish.
    """
    store = await _new_store(tmp_path)
    try:
        await store.upsert_artist_meta_full(
            [{"artist_key": "a", "artist_name": "Broken"}], state=RESOLVE_STATE_ERROR
        )
        assert await store.pending_artist_keys() == []
    finally:
        await store.close()


async def test_failed_artist_keys_returns_newest_attempt_first(tmp_path: Path) -> None:
    """`failed_artist_keys` lists `error`-state artists, most recently attempted first."""
    store = await _new_store(tmp_path)
    try:
        await _add_history(store, "a", "b")
        await store.upsert_artist_meta_full(
            [{"artist_key": "a", "artist_name": "Artist A"}], state=RESOLVE_STATE_ERROR
        )
        await store.upsert_artist_meta_full(
            [{"artist_key": "b", "artist_name": "Artist B"}], state=RESOLVE_STATE_ERROR
        )
        assert store.database is not None
        # force distinct resolved_at values so ordering is unambiguous
        await store.database.execute(
            f"UPDATE {DB_TABLE_GENOME_ARTIST_META} SET resolved_at = 100 WHERE artist_key = 'a'"
        )
        await store.database.execute(
            f"UPDATE {DB_TABLE_GENOME_ARTIST_META} SET resolved_at = 200 WHERE artist_key = 'b'"
        )
        failed = await store.failed_artist_keys()
        assert [row["artist_key"] for row in failed] == ["b", "a"]
        assert failed[0]["artist_name"] == "Artist B"
        assert failed[0]["resolved_at"] == 200
    finally:
        await store.close()


async def test_failed_artist_keys_excludes_other_states(tmp_path: Path) -> None:
    """Only `error`-state rows are unresolved failures - pending/ok/not_found are not."""
    store = await _new_store(tmp_path)
    try:
        await store.add_listens([_listen()], listener="household")  # pending
        await store.upsert_artist_meta_full(
            [{"artist_key": "resolved-artist", "artist_name": "Resolved Artist"}], state="ok"
        )
        assert await store.failed_artist_keys() == []
    finally:
        await store.close()


async def test_failed_artist_keys_respects_limit(tmp_path: Path) -> None:
    """`limit` caps the number of rows returned."""
    store = await _new_store(tmp_path)
    try:
        await _add_history(store, *(f"artist-{i}" for i in range(3)))
        for i in range(3):
            await store.upsert_artist_meta_full(
                [{"artist_key": f"artist-{i}", "artist_name": f"Artist {i}"}],
                state=RESOLVE_STATE_ERROR,
            )
        assert len(await store.failed_artist_keys(limit=2)) == 2
    finally:
        await store.close()


async def test_pending_artist_keys_retries_a_failure_once_cooled_off(tmp_path: Path) -> None:
    """A cooldown is a delay, not a grave: the artist comes back round eventually."""
    store = await _new_store(tmp_path)
    try:
        await store.upsert_artist_meta_full(
            [{"artist_key": "a", "artist_name": "Broken"}], state=RESOLVE_STATE_ERROR
        )
        stale = int(time.time()) - (RESOLVE_ERROR_COOLDOWN_HOURS + 1) * 3600
        assert store.database is not None
        await store.database.execute(
            f"UPDATE {DB_TABLE_GENOME_ARTIST_META} SET resolved_at = :t WHERE artist_key = 'a'",
            {"t": stale},
        )
        assert [key for key, _name in await store.pending_artist_keys()] == ["a"]
    finally:
        await store.close()


async def test_retry_failed_artists_moves_error_rows_back_to_pending(tmp_path: Path) -> None:
    """`retry_failed_artists` puts `error` rows back in the eligible-now `pending` queue."""
    store = await _new_store(tmp_path)
    try:
        await store.upsert_artist_meta_full(
            [{"artist_key": "a", "artist_name": "Broken"}], state=RESOLVE_STATE_ERROR
        )
        assert await store.pending_artist_keys() == []  # still in error cooldown
        reset = await store.retry_failed_artists()
        assert reset == 1
        assert [key for key, _name in await store.pending_artist_keys()] == ["a"]
        assert await store.failed_artist_keys() == []
    finally:
        await store.close()


async def test_retry_failed_artists_with_keys_only_resets_those(tmp_path: Path) -> None:
    """Passing explicit keys leaves other `error` rows untouched."""
    store = await _new_store(tmp_path)
    try:
        await _add_history(store, "a", "b")
        for key in ("a", "b"):
            await store.upsert_artist_meta_full(
                [{"artist_key": key, "artist_name": key}], state=RESOLVE_STATE_ERROR
            )
        reset = await store.retry_failed_artists(["a"])
        assert reset == 1
        assert {row["artist_key"] for row in await store.failed_artist_keys()} == {"b"}
    finally:
        await store.close()


async def test_retry_failed_artists_returns_zero_for_unknown_keys(tmp_path: Path) -> None:
    """A key that is not currently `error` (or does not exist) resets nothing."""
    store = await _new_store(tmp_path)
    try:
        assert await store.retry_failed_artists(["nope"]) == 0
        assert await store.retry_failed_artists([]) == 0
        assert await store.retry_failed_artists() == 0
    finally:
        await store.close()


async def test_retry_failed_artists_preserves_resolved_metadata_never_written(
    tmp_path: Path,
) -> None:
    """
    Reusing `upsert_artist_meta_full` is safe because `error` rows never carry real metadata.

    An `error` row is always written with only `artist_key`/`artist_name` (see
    `enrich/musicbrainz.py`), so resetting it the same way clobbers nothing.
    """
    store = await _new_store(tmp_path)
    try:
        await store.upsert_artist_meta_full(
            [{"artist_key": "a", "artist_name": "Broken"}], state=RESOLVE_STATE_ERROR
        )
        await store.retry_failed_artists(["a"])
        meta = await store.get_artist_meta(["a"])
        assert meta["a"].mbid is None
        assert meta["a"].genres == ()
    finally:
        await store.close()


async def test_all_failed_artist_keys_is_unlimited(tmp_path: Path) -> None:
    """Unlike `failed_artist_keys`, this reports every `error` artist regardless of count."""
    store = await _new_store(tmp_path)
    try:
        await _add_history(store, *(f"artist-{i}" for i in range(5)))
        for i in range(5):
            await store.upsert_artist_meta_full(
                [{"artist_key": f"artist-{i}", "artist_name": f"Artist {i}"}],
                state=RESOLVE_STATE_ERROR,
            )
        assert await store.all_failed_artist_keys() == {f"artist-{i}" for i in range(5)}
    finally:
        await store.close()


async def test_library_only_artists_are_queued_but_not_counted(tmp_path: Path) -> None:
    """
    A meta row with no listens is resolved last and never counts toward the genome's figures.

    Discovery queues MusicBrainz lookups for library artists that were never played; those
    must not inflate "still resolving" / "could not be identified", and must not jump the
    enrichment queue ahead of artists from the listening history.
    """
    store = await _new_store(tmp_path)
    try:
        assert await store.queue_artist_lookups([("pond", "Pond")]) == 1
        await store.add_listens([_listen()], listener="household")  # history artist, pending
        # queued first with the same resolved_at, yet the history artist still comes first
        assert await store.pending_artist_keys() == [
            ("sigurros", "Sigur Rós"),
            ("pond", "Pond"),
        ]
        assert await store.artist_resolution_counts() == {"pending": 1}

        await store.upsert_artist_meta_full(
            [{"artist_key": "pond", "artist_name": "Pond"}], state=RESOLVE_STATE_ERROR
        )
        assert await store.artist_resolution_counts() == {"pending": 1}
        assert await store.all_failed_artist_keys() == set()
        assert await store.failed_artist_keys() == []

        # once its error cooldown lapses it is retried - still behind the history artist
        stale = int(time.time()) - (RESOLVE_ERROR_COOLDOWN_HOURS + 1) * 3600
        assert store.database is not None
        await store.database.execute(
            f"UPDATE {DB_TABLE_GENOME_ARTIST_META} SET resolved_at = :t WHERE artist_key = 'pond'",
            {"t": stale},
        )
        assert [key for key, _name in await store.pending_artist_keys()] == ["sigurros", "pond"]
    finally:
        await store.close()


async def test_dismiss_unresolved_round_trips(tmp_path: Path) -> None:
    """The dismissed fingerprint survives a write/read round trip."""
    store = await _new_store(tmp_path)
    try:
        assert await store.unresolved_dismissed_keys() is None
        await store.dismiss_unresolved(["b", "a", "a"])
        assert await store.unresolved_dismissed_keys() == frozenset({"a", "b"})
    finally:
        await store.close()


async def test_dismiss_unresolved_overwrites_previous_fingerprint(tmp_path: Path) -> None:
    """Dismissing again replaces the old fingerprint rather than merging into it."""
    store = await _new_store(tmp_path)
    try:
        await store.dismiss_unresolved(["a"])
        await store.dismiss_unresolved(["b"])
        assert await store.unresolved_dismissed_keys() == frozenset({"b"})
    finally:
        await store.close()


async def test_a_second_connection_can_read_while_the_store_is_open(tmp_path: Path) -> None:
    """
    genome.db must stay readable by other connections while the store holds it open.

    Replaces the fork's ``test_snapshot_works_while_the_store_holds_its_exclusive_lock``, whose
    premise was that MA's ``PRAGMA locking_mode=exclusive`` locked every second connection out.
    That lock cost two days of an export hanging forever, and inside Home Assistant it would
    also block HA's backups and any external tool from reading the file, so ``GenomeDatabase``
    drops it on purpose. This asserts the opposite premise - a second reader works - because
    that is now a requirement - and that the snapshot still works alongside it.
    """
    store = await _new_store(tmp_path)
    try:
        await store.add_listens(
            [_listen(played_at=1_700_000_000 + i, track_key=f"t{i}") for i in range(500)],
            listener="household",
        )
        readable = await asyncio.to_thread(_second_connection_can_read, store.db_path)
        assert readable, "a second connection could not read genome.db while the store was open"
        assert await asyncio.to_thread(_second_connection_count, store.db_path) == 500

        target = str(tmp_path / "export.db")
        await asyncio.wait_for(store.snapshot_to(target), timeout=10)

        copy = sqlite3.connect(target)
        try:
            assert copy.execute("SELECT COUNT(*) FROM genome_listens").fetchone()[0] == 500
        finally:
            copy.close()
    finally:
        await store.close()


async def test_snapshot_is_consistent_while_listens_keep_arriving(tmp_path: Path) -> None:
    """
    A snapshot taken while listens are still arriving must be a real database.

    The database is always being written to during an export - live playlog capture alone
    sees to that - so a torn copy that only looks like a database is the failure to rule out.
    """
    store = await _new_store(tmp_path)
    try:
        await store.add_listens(
            [_listen(played_at=1_700_000_000 + i, track_key=f"t{i}") for i in range(300)],
            listener="household",
        )

        async def keep_writing() -> None:
            for i in range(300, 600):
                await store.add_listens(
                    [_listen(played_at=1_700_000_000 + i, track_key=f"t{i}")], listener="household"
                )

        target = str(tmp_path / "export.db")
        await asyncio.gather(keep_writing(), store.snapshot_to(target))

        copy = sqlite3.connect(target)
        try:
            assert copy.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            count = copy.execute("SELECT COUNT(*) FROM genome_listens").fetchone()[0]
            assert 300 <= count <= 600
        finally:
            copy.close()
    finally:
        await store.close()


def _second_connection_can_read(path: str) -> bool:
    """Whether an independent connection can read ``path`` within a couple of seconds."""
    try:
        other = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2.0)
        try:
            other.execute("SELECT COUNT(*) FROM genome_listens").fetchone()
        finally:
            other.close()
    except sqlite3.OperationalError:
        return False
    return True


def _second_connection_count(path: str) -> int:
    """Count ``genome_listens`` rows through an independent read-only connection."""
    other = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2.0)
    try:
        return int(other.execute("SELECT COUNT(*) FROM genome_listens").fetchone()[0])
    finally:
        other.close()


async def test_player_names_uses_the_injected_resolver(tmp_path: Path) -> None:
    """The name seam replacing ``mass.players``: resolved names win, unknown ids fall back."""
    store = GenomeStore(str(tmp_path), player_name_resolver={"kitchen_id": "Kitchen"}.get)
    await store.setup()
    try:
        await store.add_listens(
            [
                _listen(player_id="kitchen_id", played_at=1_700_000_000),
                _listen(player_id="garage_id", played_at=1_700_001_000),
            ],
            listener="household",
        )
        assert await store.player_names() == {"kitchen_id": "Kitchen", "garage_id": "garage_id"}
        store.player_name_resolver = None
        assert await store.player_names() == {"kitchen_id": "kitchen_id", "garage_id": "garage_id"}
    finally:
        await store.close()


# --- 2c: duplicate removal ------------------------------------------------------------------

_DAY = 86400
_NOON = 1_700_049_600  # 2023-11-15 12:00 UTC


async def _sources(store: GenomeStore) -> dict[str, int]:
    return await store.source_counts("household")


async def test_apple_same_day_removes_every_lastfm_copy_that_day(tmp_path: Path) -> None:
    """Apple saw the track that day: all Last.fm rows for it that day go, Apple's stay."""
    store = await _new_store(tmp_path)
    try:
        day_start = (_NOON // _DAY) * _DAY
        await store.add_listens(
            [_listen(played_at=day_start + 3600), _listen(played_at=day_start + 7200)],
            listener="household",
        )
        await store.add_listens(
            [
                _listen(source="lastfm", played_at=day_start + 3700),
                _listen(source="lastfm", played_at=day_start + 7300),
                _listen(source="lastfm", played_at=day_start + 20000),
            ],
            listener="household",
        )
        removed = await store.remove_duplicate_listens("household")
        assert (removed.apple, removed.music_assistant) == (3, 0)
        assert await _sources(store) == {"apple_export": 2}
    finally:
        await store.close()


async def test_apple_rule_keeps_other_days_and_other_tracks(tmp_path: Path) -> None:
    """A Last.fm play on another UTC day, or of another track, is not a duplicate."""
    store = await _new_store(tmp_path)
    try:
        day_start = (_NOON // _DAY) * _DAY
        await store.add_listens([_listen(played_at=day_start + 60)], listener="household")
        await store.add_listens(
            [
                # same track, the previous UTC day (one minute before midnight)
                _listen(source="lastfm", played_at=day_start - 60),
                # same day, different track
                _listen(source="lastfm", played_at=day_start + 600, track_key="viðrarvelti"),
                # same day, same title, different artist
                _listen(source="lastfm", played_at=day_start + 1200, artist_key="someoneelse"),
            ],
            listener="household",
        )
        removed = await store.remove_duplicate_listens("household")
        assert removed.total == 0
        assert await _sources(store) == {"apple_export": 1, "lastfm": 3}
    finally:
        await store.close()


async def test_duplicate_removal_is_idempotent(tmp_path: Path) -> None:
    """
    A second pass over the same history removes nothing.

    It runs after every import. A count-based rule ("drop as many as Apple counted") failed
    this on the real history: the second pass ate another 361 rows.
    """
    store = await _new_store(tmp_path)
    try:
        day_start = (_NOON // _DAY) * _DAY
        await store.add_listens([_listen(played_at=day_start + 60)], listener="household")
        await store.add_listens(
            [_listen(source="lastfm", played_at=day_start + 60 * k) for k in (2, 5, 9)],
            listener="household",
        )
        first = await store.remove_duplicate_listens("household")
        second = await store.remove_duplicate_listens("household")
        assert first.total == 3
        assert second.total == 0
    finally:
        await store.close()


async def test_duplicate_removal_respects_its_time_range(tmp_path: Path) -> None:
    """A scoped pass (after an import) leaves duplicates outside its days alone."""
    store = await _new_store(tmp_path)
    try:
        day_a = (_NOON // _DAY) * _DAY
        day_b = day_a + 10 * _DAY
        for day in (day_a, day_b):
            await store.add_listens([_listen(played_at=day + 60)], listener="household")
            await store.add_listens(
                [_listen(source="lastfm", played_at=day + 120)], listener="household"
            )
        removed = await store.remove_duplicate_listens(
            "household", since=day_b + 5000, until=day_b + 6000
        )
        # whole UTC days: the range sits inside day_b, and day_b's pair is still found
        assert removed.apple == 1
        assert await _sources(store) == {"apple_export": 2, "lastfm": 1}
    finally:
        await store.close()


async def test_ma_scrobble_removed_one_track_length_after_the_live_row(tmp_path: Path) -> None:
    """
    MA scrobbles at the END of a play; the live row is stamped at the START.

    The Last.fm copy lands ~duration later, so a fixed +-90 s window (the old ``dedupe_window``)
    would never match it.
    """
    store = await _new_store(tmp_path)
    try:
        start = _NOON
        await store.add_listens(
            [_listen(source="ma_playlog", played_at=start, duration_ms=240_000)],
            listener="household",
        )
        await store.add_listens(
            [_listen(source="lastfm", played_at=start + 245)], listener="household"
        )
        removed = await store.remove_duplicate_listens("household")
        assert (removed.apple, removed.music_assistant) == (0, 1)
        assert await _sources(store) == {"ma_playlog": 1}
    finally:
        await store.close()


async def test_ma_rule_matches_multi_artist_credit_and_only_once(tmp_path: Path) -> None:
    """
    "Artist, Guest" on Last.fm matches the MA row for "Artist"; each MA row cancels one copy.

    A second Last.fm play of the same track inside the window is a genuine second play (a
    repeat that MA would have captured as its own row) and stays.
    """
    store = await _new_store(tmp_path)
    try:
        start = _NOON
        await store.add_listens(
            [_listen(source="ma_playlog", played_at=start, duration_ms=200_000)],
            listener="household",
        )
        await store.add_listens(
            [
                _listen(source="lastfm", played_at=start + 205, artist_key="sigurros, jonsi"),
                _listen(source="lastfm", played_at=start + 410),
            ],
            listener="household",
        )
        removed = await store.remove_duplicate_listens("household")
        assert removed.music_assistant == 1
        assert await _sources(store) == {"ma_playlog": 1, "lastfm": 1}
    finally:
        await store.close()


async def test_ma_rule_ignores_lastfm_plays_outside_the_window(tmp_path: Path) -> None:
    """Before the start (beyond clock skew) or well after the end is a different play."""
    store = await _new_store(tmp_path)
    try:
        start = _NOON
        await store.add_listens(
            [_listen(source="ma_playlog", played_at=start, duration_ms=200_000)],
            listener="household",
        )
        await store.add_listens(
            [
                _listen(source="lastfm", played_at=start - 600),
                # beyond the track's length plus the hour a pause may add
                _listen(source="lastfm", played_at=start + 200 + 3600 + 60),
            ],
            listener="household",
        )
        removed = await store.remove_duplicate_listens("household")
        assert removed.total == 0
    finally:
        await store.close()


async def test_ma_rule_does_not_match_a_longer_different_artist(tmp_path: Path) -> None:
    """A whole-word prefix only: "queens of the stone age" is not a credit of "queen"."""
    store = await _new_store(tmp_path)
    try:
        await store.add_listens(
            [_listen(source="ma_playlog", played_at=_NOON, artist_key="queen", track_key="go")],
            listener="household",
        )
        await store.add_listens(
            [
                _listen(
                    source="lastfm",
                    played_at=_NOON + 200,
                    artist_key="queens of the stone age",
                    track_key="go",
                )
            ],
            listener="household",
        )
        assert (await store.remove_duplicate_listens("household")).total == 0
    finally:
        await store.close()


async def test_lastfm_resume_mark_never_moves_backwards(tmp_path: Path) -> None:
    """The mark only advances; a stale or smaller value is ignored."""
    store = await _new_store(tmp_path)
    try:
        assert await store.lastfm_resume_after() == 0
        await store.set_lastfm_resume_after(2_000)
        await store.set_lastfm_resume_after(1_000)
        assert await store.lastfm_resume_after() == 2_000
    finally:
        await store.close()


async def test_latest_played_at_is_per_source(tmp_path: Path) -> None:
    """The newest row of one source, not of the whole table."""
    store = await _new_store(tmp_path)
    try:
        await store.add_listens([_listen(played_at=5_000)], listener="household")
        await store.add_listens(
            [_listen(source="lastfm", played_at=3_000, track_key="x")], listener="household"
        )
        assert await store.latest_played_at("household", "lastfm") == 3_000
        assert await store.latest_played_at("household", "ma_playlog") == 0
    finally:
        await store.close()


async def test_ma_scrobble_delayed_by_a_pause_is_still_removed(tmp_path: Path) -> None:
    """A 4-minute track paused 10 minutes: MA scrobbles at start + 14 min."""
    store = await _new_store(tmp_path)
    try:
        await store.add_listens(
            [_listen(source="ma_playlog", played_at=_NOON, duration_ms=240_000)],
            listener="household",
        )
        await store.add_listens(
            [_listen(source="lastfm", played_at=_NOON + 240 + 600)], listener="household"
        )
        assert (await store.remove_duplicate_listens("household")).music_assistant == 1
    finally:
        await store.close()


async def test_ma_rule_pairs_each_pair_once_when_scoped_to_new_rows(tmp_path: Path) -> None:
    """
    Re-running over the same day must not eat a genuine second Last.fm play.

    One MA play, its own scrobble, and a genuine second play of the track from a phone in the
    window. The pass that adds the scrobble removes it; later passes (after each captured
    track, over the whole day) consider only pairs with a NEW row, so the phone play stays.
    """
    store = await _new_store(tmp_path)
    try:
        await store.add_listens(
            [_listen(source="ma_playlog", played_at=_NOON, duration_ms=200_000)],
            listener="household",
        )
        mark = await store.max_listen_id()
        await store.add_listens(
            [
                _listen(source="lastfm", played_at=_NOON + 205),
                _listen(source="lastfm", played_at=_NOON + 1500),
            ],
            listener="household",
        )
        first = await store.remove_duplicate_listens(
            "household", since=_NOON, until=_NOON, added_after_id=mark
        )
        assert first.music_assistant == 1
        for _ in range(3):
            again = await store.remove_duplicate_listens(
                "household", since=_NOON, until=_NOON, added_after_id=await store.max_listen_id()
            )
            assert again.total == 0
        assert (await _sources(store))["lastfm"] == 1
    finally:
        await store.close()


async def test_changing_lastfm_account_forgets_the_old_accounts_progress(tmp_path: Path) -> None:
    """A new account is swept from its own beginning, not resumed from the old account's."""
    store = await _new_store(tmp_path)
    try:
        # a database from before 2c: progress, but no account recorded - it is kept
        await store.mark_lastfm_backfill_done()
        await store.set_lastfm_resume_after(5_000)
        assert await store.use_lastfm_account("Bob_Baird") is False
        assert await store.lastfm_backfill_done() is True
        # the same account, however it is capitalised
        assert await store.use_lastfm_account("bob_baird") is False
        # another account
        assert await store.use_lastfm_account("someone_else") is True
        assert await store.lastfm_backfill_done() is False
        assert await store.lastfm_resume_after() == 0
        assert await store.lastfm_account() == "someone_else"
    finally:
        await store.close()
