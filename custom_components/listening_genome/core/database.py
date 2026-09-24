"""
The ``genome.db`` connection: a small stand-in for Music Assistant's ``DatabaseConnection``.

The store was written against MA's ``helpers/database.py`` and calls exactly eleven of its
methods. This class carries those eleven over with identical names, parameters, defaults and
return shapes - and the same SQL they build - so ``store.py`` could move across unchanged apart
from its imports. ``tests/test_database_parity.py`` runs both implementations side by side and
fails on any difference.

Deliberately left out: MA's deferred-commit scopes, ``execute_write``, the slow-query logging
and event-loop stall tracker, and every helper the store never calls. Without deferred-commit
scopes the per-write commit is unconditional, which is exactly what MA does outside one.
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Any, cast

import aiosqlite

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping


class _UnsetType:
    """Sentinel value to indicate a field should use the database default."""

    _instance: _UnsetType | None = None

    def __new__(cls) -> _UnsetType:  # singleton sentinel always returns the one instance, not Self
        """Create singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        """Return string representation."""
        return "UNSET"

    def __bool__(self) -> bool:
        """Return False for boolean context."""
        return False


# A value of UNSET in the dict passed to insert_or_replace/upsert drops that column from the
# statement entirely, so the database default applies on insert and - for upsert - the existing
# value is kept on conflict. None, by contrast, writes NULL.
UNSET: _UnsetType = _UnsetType()


def query_params(query: str, params: dict[str, Any] | None) -> tuple[str, dict[str, Any]]:
    """Extend query parameters support."""
    if params is None:
        return (query, {})
    count = 0
    result_query = query
    result_params = {}
    for key, value in params.items():
        # add support for a list within the query params
        # recreates the params as (:_param_0, :_param_1) etc
        if isinstance(value, list | tuple):
            subparams = []
            for subval in value:
                subparam_name = f"_param_{count}"
                result_params[subparam_name] = subval
                subparams.append(subparam_name)
                count += 1
            params_str = ",".join(f":{x}" for x in subparams)
            # replace the placeholder with the expanded (:_param_x, ...) list;
            # consume optional parens already around the placeholder and use a
            # word boundary so placeholders sharing the same prefix are untouched
            result_query = re.sub(
                rf"\(\s*:{re.escape(key)}\b\s*\)|:{re.escape(key)}\b",
                f"({params_str})",
                result_query,
            )
        else:
            result_params[key] = value
    return (result_query, result_params)


def get_sqlite_memory_settings() -> tuple[int, int]:
    """
    Return (cache_size_kib, mmap_size_bytes) scaled to available system memory.

    The same tiers as Music Assistant. The page cache is a per-connection ceiling filled
    lazily, so a small database never consumes a large ceiling. Returns the generous defaults
    when memory is unknown, so those hosts fail open to full performance.
    """
    gib = 1024**3
    total_ram_gb = _get_host_memory_gb()
    if total_ram_gb >= 16.0:
        return 1024000, 2 * gib
    if total_ram_gb >= 12.0:
        return 512000, 2 * gib
    if total_ram_gb >= 8.0:
        return 128000, 2 * gib
    if total_ram_gb == 0.0 or total_ram_gb >= 4.0:
        return 64000, 2 * gib
    if total_ram_gb >= 2.0:
        return 32000, gib
    return 16000, 256 * 1024 * 1024


class GenomeDatabase:
    """Holds the connection to ``genome.db`` with the convenience helpers the store uses."""

    _db: aiosqlite.Connection

    def __init__(self, db_path: str) -> None:
        """
        Initialize class.

        :param db_path: Filesystem path of the SQLite database file.
        """
        self.db_path = db_path

    async def setup(
        self,
        cache_size_kib: int | None = None,
        mmap_size_bytes: int | None = None,
    ) -> None:
        """
        Perform async initialization.

        :param cache_size_kib: SQLite page-cache ceiling for this connection, in KiB.
            Defaults to a value scaled to the host's available memory.
        :param mmap_size_bytes: SQLite memory-map ceiling for this connection, in bytes.
            Defaults to a value scaled to the host's available memory.
        """
        default_cache_kib, default_mmap_bytes = get_sqlite_memory_settings()
        # coerce + clamp to non-negative ints so the values are always safe to interpolate
        cache_size_kib = max(
            0, int(default_cache_kib if cache_size_kib is None else cache_size_kib)
        )
        mmap_size_bytes = max(
            0, int(default_mmap_bytes if mmap_size_bytes is None else mmap_size_bytes)
        )
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self.execute("PRAGMA analysis_limit=10000;")
        # Music Assistant also sets `PRAGMA locking_mode=exclusive` here. It is left out on
        # purpose. Exclusive locking over WAL means the connection that takes the lock never
        # releases it and keeps the WAL index in its private memory, so no second connection
        # can ever read the file - not read-only, not to back it up. That cost two days of a
        # database export hanging forever on a lock that could never be granted. Inside Home
        # Assistant it would also block HA's own backups and any external tool from reading
        # genome.db. WAL stays: it is what lets those readers run alongside our writes.
        await self.execute("PRAGMA journal_mode=WAL;")
        await self.execute("PRAGMA journal_size_limit = 6144000;")
        await self.execute("PRAGMA synchronous=normal;")
        await self.execute("PRAGMA temp_store=memory;")
        await self.execute(f"PRAGMA mmap_size = {mmap_size_bytes};")
        await self.execute(f"PRAGMA cache_size = -{cache_size_kib};")
        await self.commit()

    async def close(self) -> None:
        """Close db connection on exit."""
        await self.execute("PRAGMA optimize;")
        await self.commit()
        await self._db.close()

    async def get_rows_from_query(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[Mapping[str, Any]]:
        """
        Get all rows for given custom query.

        :param query: The SELECT statement; list/tuple params expand into ``(...)`` lists.
        :param params: Named parameters for the query.
        :param limit: Maximum number of rows; ``0`` means no limit. Defaults to 500.
        :param offset: Number of rows to skip (only applied together with a limit).
        """
        if limit:
            query += f" LIMIT {limit} OFFSET {offset}"
        _query, _params = query_params(query, params)
        return cast("list[Mapping[str, Any]]", await self._db.execute_fetchall(_query, _params))

    async def iter_rows_from_query(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> AsyncGenerator[Mapping[str, Any]]:
        """Stream rows for a given custom query without materializing the full result."""
        _query, _params = query_params(query, params)
        async with self._db.execute(_query, _params) as cursor:
            async for row in cursor:
                yield cast("Mapping[str, Any]", row)

    async def get_count_from_query(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> int:
        """Get row count for given custom query."""
        query = f"SELECT count() FROM ({query})"
        _query, _params = query_params(query, params)
        async with self._db.execute(_query, _params) as cursor:
            if result := await cursor.fetchone():
                assert isinstance(result[0], int)  # for type checking
                return result[0]
        return 0

    async def get_row(self, table: str, match: dict[str, Any]) -> Mapping[str, Any] | None:
        """Get single row for given table where column matches keys/values."""
        sql_query = f"SELECT * FROM {table} WHERE "
        sql_query += " AND ".join(f"{table}.{x} = :{x}" for x in match)
        async with self._db.execute(sql_query, match) as cursor:
            return cast("Mapping[str, Any] | None", await cursor.fetchone())

    async def insert_or_replace(self, table: str, values: dict[str, Any]) -> int:
        """
        Insert or replace data in given table, and commit.

        :param table: The table to write to.
        :param values: Column -> value; columns set to :data:`UNSET` are omitted.
        :return: The rowid of the written row.
        """
        values = {k: v for k, v in values.items() if v is not UNSET}
        keys = tuple(values.keys())
        sql_query = f"INSERT OR REPLACE INTO {table}({','.join(keys)})"
        sql_query += f" VALUES ({','.join(f':{x}' for x in keys)})"
        row_id = await self._db.execute_insert(sql_query, values)
        await self._db.commit()
        assert row_id is not None  # for type checking
        assert isinstance(row_id[0], int)  # for type checking
        return row_id[0]

    async def upsert(self, table: str, values: dict[str, Any]) -> None:
        """
        Upsert data in given table, and commit.

        :param table: The table to write to.
        :param values: Column -> value; columns set to :data:`UNSET` are omitted, so they take
            the database default on insert and keep their existing value on conflict.
        """
        values = {k: v for k, v in values.items() if v is not UNSET}
        keys = tuple(values.keys())
        sql_query = (
            f"INSERT INTO {table}({','.join(keys)}) VALUES ({','.join(f':{x}' for x in keys)})"
        )
        sql_query += f" ON CONFLICT DO UPDATE SET {','.join(f'{x}=:{x}' for x in keys)}"
        await self._db.execute(sql_query, values)
        await self._db.commit()

    async def delete(
        self, table: str, match: dict[str, Any] | None = None, query: str | None = None
    ) -> None:
        """
        Delete data in given table, and commit.

        :param table: The table to delete from.
        :param match: Column -> value equality filter (mutually exclusive with ``query``).
        :param query: A raw WHERE clause, with or without the ``WHERE`` keyword.
        """
        assert not (match and query), "Cannot use both match and query"
        sql_query = f"DELETE FROM {table} "
        if match:
            sql_query += " WHERE " + " AND ".join(f"{x} = :{x}" for x in match)
        elif query and "where" not in query.lower():
            sql_query += "WHERE " + query
        elif query:
            sql_query += query
        await self.execute(sql_query, match)
        await self._db.commit()

    async def execute(self, query: str, values: dict[str, Any] | None = None) -> Any:
        """Execute command on the database; does not commit."""
        return await self._db.execute(query, values)

    async def commit(self) -> None:
        """Commit the current transaction."""
        return await self._db.commit()


def _get_host_memory_gb() -> float:
    """Return host physical RAM in GB via sysconf, or 0.0 when unavailable."""
    try:
        total_memory_bytes = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        return total_memory_bytes / (1024**3)
    except AttributeError, ValueError, OSError:
        return 0.0


__all__ = ["UNSET", "GenomeDatabase"]
