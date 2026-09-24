"""
Differential test: :class:`GenomeDatabase` against Music Assistant's real ``DatabaseConnection``.

One scripted sequence of operations runs through each implementation on its own temp file. Every
return value, the transaction state after every step, and the final contents of every table
must be identical. The stand-in exists to be indistinguishable from MA for the eleven methods
the store calls, so any divergence here is a bug in the stand-in, not in this test.
"""

from __future__ import annotations

import inspect
import sqlite3
from typing import TYPE_CHECKING, Any

import pytest
from listening_genome.core.database import UNSET as GENOME_UNSET
from listening_genome.core.database import GenomeDatabase
from music_assistant.helpers.database import UNSET as MA_UNSET
from music_assistant.helpers.database import DatabaseConnection

if TYPE_CHECKING:
    from pathlib import Path

# comfortably past get_rows_from_query's default cap of 500, so the default is observable
_BIG_TABLE_ROWS = 620

_TABLES = ("items", "kv", "scratch")


def _norm(value: Any) -> Any:
    """Turn rows into plain, comparable data while keeping their type visible."""
    if isinstance(value, sqlite3.Row):
        return ("Row", tuple(value.keys()), tuple(value))
    if isinstance(value, list):
        return ("list", [_norm(v) for v in value])
    return value


async def _script(db: Any, unset: Any) -> list[tuple[str, Any]]:
    """Run the full operation sequence against ``db`` and record every observable result."""
    log: list[tuple[str, Any]] = []

    def record(step: str, value: Any) -> None:
        log.append((step, _norm(value)))
        log.append((f"{step}:in_transaction", db._db.in_transaction))

    await db.execute(
        "CREATE TABLE items([id] INTEGER PRIMARY KEY AUTOINCREMENT, [name] TEXT NOT NULL, "
        "[grp] TEXT NOT NULL, [score] INTEGER, [note] TEXT NOT NULL DEFAULT 'none')"
    )
    await db.execute(
        "CREATE TABLE kv([key] TEXT PRIMARY KEY, [value] TEXT, "
        "[kind] TEXT NOT NULL DEFAULT 'str', [n] INTEGER NOT NULL DEFAULT 7)"
    )
    await db.execute("CREATE TABLE scratch([id] INTEGER PRIMARY KEY, [tag] TEXT)")
    record("create:commit", await db.commit())

    # --- insert_or_replace: return value is the rowid, and it commits ---------------------
    ids = [
        await db.insert_or_replace(
            "items", {"name": f"item-{i:04d}", "grp": f"g{i % 3}", "score": i * 7 % 101}
        )
        for i in range(_BIG_TABLE_ROWS)
    ]
    record("items:rowids", ids)
    record("kv:insert_a", await db.insert_or_replace("kv", {"key": "a", "value": "1"}))
    record("kv:insert_b", await db.insert_or_replace("kv", {"key": "b", "value": "2", "n": 3}))
    # replacing an existing TEXT key deletes and reinserts, so the returned rowid moves on
    record(
        "kv:replace_a", await db.insert_or_replace("kv", {"key": "a", "value": "1b", "kind": "j"})
    )
    # UNSET drops the column: the default applies instead of NULL or the previous value
    record(
        "kv:replace_b_unset",
        await db.insert_or_replace("kv", {"key": "b", "value": "2b", "n": unset, "kind": unset}),
    )
    record(
        "items:replace_existing_id",
        await db.insert_or_replace(
            "items", {"id": 5, "name": "replaced", "grp": "g9", "score": None}
        ),
    )

    # --- upsert ---------------------------------------------------------------------------
    record("kv:upsert_new", await db.upsert("kv", {"key": "c", "value": "3", "n": 30}))
    record("kv:upsert_existing", await db.upsert("kv", {"key": "c", "value": "3b", "n": 31}))
    # UNSET on conflict keeps the existing column value rather than clobbering it
    record("kv:upsert_unset_keeps", await db.upsert("kv", {"key": "c", "value": "3c", "n": unset}))
    record("kv:upsert_unset_new", await db.upsert("kv", {"key": "d", "value": None, "n": unset}))
    record("kv:upsert_none_clobbers", await db.upsert("kv", {"key": "c", "kind": "x", "n": 1}))

    # --- get_row --------------------------------------------------------------------------
    record("get_row:hit", await db.get_row("kv", {"key": "c"}))
    record("get_row:multi", await db.get_row("items", {"grp": "g1", "score": 7 * 7 % 101}))
    record("get_row:miss", await db.get_row("kv", {"key": "nope"}))

    # --- get_rows_from_query --------------------------------------------------------------
    base = "SELECT * FROM items ORDER BY id"
    default_rows = await db.get_rows_from_query(base)
    record("rows:default_limit_len", len(default_rows))
    record("rows:default_limit", default_rows)
    record("rows:limit0", await db.get_rows_from_query(base, limit=0))
    record("rows:limit_offset", await db.get_rows_from_query(base, limit=40, offset=575))
    record("rows:offset_without_limit", await db.get_rows_from_query(base, limit=0, offset=10))
    record("rows:offset_default_limit", await db.get_rows_from_query(base, offset=300))
    record(
        "rows:params",
        await db.get_rows_from_query(
            "SELECT id, name FROM items WHERE grp = :grp ORDER BY id", {"grp": "g2"}
        ),
    )
    record(
        "rows:list_param",
        await db.get_rows_from_query(
            "SELECT * FROM items WHERE id IN (:ids) AND grp = :grp ORDER BY id",
            {"ids": [1, 2, 3, 4, 5, 6, 999], "grp": "g0"},
            limit=0,
        ),
    )
    record(
        "rows:tuple_param_bare",
        await db.get_rows_from_query(
            "SELECT key FROM kv WHERE key IN :keys ORDER BY key", {"keys": ("a", "c")}
        ),
    )
    record(
        "rows:aggregate",
        await db.get_rows_from_query(
            "SELECT grp, COUNT(*) AS n FROM items GROUP BY grp ORDER BY grp", limit=0
        ),
    )

    # --- iter_rows_from_query -------------------------------------------------------------
    record("iter:all", [row async for row in db.iter_rows_from_query(base)])
    record(
        "iter:list_param",
        [
            row
            async for row in db.iter_rows_from_query(
                "SELECT * FROM items WHERE id IN (:ids) ORDER BY id", {"ids": [10, 20, 30]}
            )
        ],
    )

    # --- get_count_from_query -------------------------------------------------------------
    record("count:all", await db.get_count_from_query("SELECT 1 FROM items"))
    record(
        "count:params",
        await db.get_count_from_query("SELECT 1 FROM items WHERE grp = :grp", {"grp": "g1"}),
    )
    record(
        "count:list_param",
        await db.get_count_from_query(
            "SELECT 1 FROM items WHERE id IN (:ids)", {"ids": list(range(1, 101))}
        ),
    )
    record("count:empty", await db.get_count_from_query("SELECT 1 FROM kv WHERE key = 'zz'"))

    # --- execute: returns a cursor, does not commit ---------------------------------------
    cursor = await db.execute(
        "UPDATE items SET note = :note WHERE grp = :grp", {"note": "touched", "grp": "g2"}
    )
    record("execute:update_rowcount", cursor.rowcount)
    cursor = await db.execute("INSERT OR IGNORE INTO kv(key, value) VALUES ('a', 'dup')")
    record("execute:ignored_rowcount", cursor.rowcount)
    cursor = await db.execute("INSERT INTO scratch(tag) VALUES ('s1')")
    record("execute:lastrowid", cursor.lastrowid)
    record("execute:commit", await db.commit())

    # --- delete ---------------------------------------------------------------------------
    for i in range(6):
        await db.execute("INSERT INTO scratch(tag) VALUES (:t)", {"t": f"t{i % 2}"})
    record("delete:match", await db.delete("items", {"grp": "g1"}))
    record("delete:match_multi", await db.delete("items", {"grp": "g0", "note": "none"}))
    record("delete:query_no_where", await db.delete("items", query="score > 90"))
    record("delete:query_with_where", await db.delete("scratch", query="WHERE tag = 't0'"))
    record("delete:count_after", await db.get_count_from_query("SELECT 1 FROM items"))
    try:
        await db.delete("kv", {"key": "a"}, query="key = 'a'")
    except AssertionError as err:
        record("delete:both_raises", str(err))
    else:
        record("delete:both_raises", "did not raise")
    record("delete:everything", await db.delete("scratch"))

    return log


async def _dump(path: str) -> dict[str, list[tuple[Any, ...]]]:
    """Read every table (including the AUTOINCREMENT bookkeeping) with a plain connection."""
    con = sqlite3.connect(path)
    try:
        return {
            table: con.execute(f"SELECT rowid, * FROM {table} ORDER BY rowid").fetchall()
            for table in (*_TABLES, "sqlite_sequence")
        }
    finally:
        con.close()


async def test_genome_database_matches_music_assistant(tmp_path: Path) -> None:
    """Every return value and the final contents of every table match MA's implementation."""
    ma_path = str(tmp_path / "ma.db")
    genome_path = str(tmp_path / "genome.db")

    ma = DatabaseConnection(ma_path)
    await ma.setup()
    try:
        ma_log = await _script(ma, MA_UNSET)
    finally:
        await ma.close()

    genome = GenomeDatabase(genome_path)
    await genome.setup()
    try:
        genome_log = await _script(genome, GENOME_UNSET)
    finally:
        await genome.close()

    # the >500-row default cap really was exercised
    assert dict(ma_log)["rows:default_limit_len"] == 500

    assert [step for step, _ in genome_log] == [step for step, _ in ma_log]
    for (step, ma_value), (_, genome_value) in zip(ma_log, genome_log, strict=True):
        assert genome_value == ma_value, f"step {step!r} differs"

    ma_tables = await _dump(ma_path)
    genome_tables = await _dump(genome_path)
    for table in ma_tables:
        assert genome_tables[table] == ma_tables[table], f"table {table!r} differs"
    assert len(ma_tables["items"]) > 0


def test_unset_is_a_falsy_singleton_like_music_assistant() -> None:
    """UNSET keeps MA's sentinel semantics: one instance, falsy, ``repr`` of ``UNSET``."""
    assert type(GENOME_UNSET)() is GENOME_UNSET
    assert not GENOME_UNSET
    assert repr(GENOME_UNSET) == repr(MA_UNSET) == "UNSET"
    assert bool(GENOME_UNSET) is bool(MA_UNSET)


_STORE_METHODS = (
    "setup",
    "close",
    "commit",
    "execute",
    "get_row",
    "get_rows_from_query",
    "iter_rows_from_query",
    "get_count_from_query",
    "insert_or_replace",
    "delete",
    "upsert",
)


@pytest.mark.parametrize("method", _STORE_METHODS)
def test_signature_matches_music_assistant(method: str) -> None:
    """Names, parameters, defaults and annotations of every method the store calls match MA's."""
    ma_sig = inspect.signature(getattr(DatabaseConnection, method))
    genome_sig = inspect.signature(getattr(GenomeDatabase, method))
    assert str(genome_sig) == str(ma_sig)
