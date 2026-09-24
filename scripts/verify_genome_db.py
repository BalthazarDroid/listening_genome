"""
Check that a genome.db opens cleanly under this integration's store, without migrating it.

Run it against an export before trusting it, and again at the switchover from the Music
Assistant fork. It works on a COPY and never touches the file you point it at.

    python scripts/verify_genome_db.py path/to/genome-export.db [expected_listens]

It reports the listen count (by COUNT and by walking every row, which must agree), the
per-source split, and whether opening the file changed its schema. Opening it will add
SQLite's own ``sqlite_stat1`` statistics table on close - that is planner metadata, not data,
and is reported separately rather than as a change.
"""

from __future__ import annotations

import asyncio
import hashlib
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "custom_components"))

from listening_genome.core.constants import DB_SCHEMA_VERSION
from listening_genome.core.store import GenomeStore

_INTERNAL_PREFIX = "sqlite_"


def _schema(path: Path) -> tuple[dict[tuple[str, str], str], str | None]:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        objects = {
            (kind, name): sql or ""
            for kind, name, sql in connection.execute("SELECT type, name, sql FROM sqlite_master")
        }
        row = connection.execute("SELECT value FROM settings WHERE key='version'").fetchone()
    finally:
        connection.close()
    return objects, (row[0] if row else None)


def _fingerprint(objects: dict[tuple[str, str], str]) -> str:
    user = sorted((k, v) for k, v in objects.items() if not k[1].startswith(_INTERNAL_PREFIX))
    return hashlib.sha256(repr(user).encode()).hexdigest()[:16]


async def _read(directory: Path) -> tuple[int, int, dict[str, int]]:
    store = GenomeStore(str(directory))
    await store.setup()
    try:
        counted = await store.count_listens("household")
        walked = 0
        async for _ in store.iter_listens("household"):
            walked += 1
        return counted, walked, await store.source_counts("household")
    finally:
        await store.close()


def main() -> int:
    """Verify the file named on the command line; exit non-zero on any failure."""
    if len(sys.argv) not in (2, 3):
        print(__doc__)
        return 2
    source = Path(sys.argv[1])
    expected = int(sys.argv[2]) if len(sys.argv) == 3 else None

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "genome.db"
        shutil.copyfile(source, work)
        before, version_before = _schema(work)
        counted, walked, by_source = asyncio.run(_read(Path(tmp)))
        after, version_after = _schema(work)

    failures: list[str] = []
    print(f"file:            {source} ({source.stat().st_size} bytes)")
    print(
        f"schema version:  {version_before} -> {version_after} (code expects {DB_SCHEMA_VERSION})"
    )
    print(f"listens:         {counted} counted, {walked} walked")
    print(f"by source:       {by_source}")

    if counted != walked:
        failures.append("COUNT and a full walk disagree")
    if expected is not None and counted != expected:
        failures.append(f"expected {expected} listens")
    if version_before != str(DB_SCHEMA_VERSION) or version_after != version_before:
        failures.append("schema version is not the one this code expects, or it changed")
    if _fingerprint(before) != _fingerprint(after):
        failures.append("opening the file changed its schema")
    added_internal = sorted(
        k[1] for k in set(after) - set(before) if k[1].startswith(_INTERNAL_PREFIX)
    )
    if added_internal:
        print(f"sqlite internal: added {added_internal} (planner statistics, not data)")

    for failure in failures:
        print(f"FAIL: {failure}")
    print("OK" if not failures else f"{len(failures)} check(s) failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
