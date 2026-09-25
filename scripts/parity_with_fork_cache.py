"""
Parity check: rebuild a real genome.db with ``GenomeService`` and compare with the fork's cache.

Usage::

    python scripts/parity_with_fork_cache.py <path-to-genome.db> [--tz America/Chicago]

The Music Assistant fork left its last computed household genome in ``genome_cache``. This
script reproduces that computation's inputs as exactly as they can be reproduced, and diffs
every field of the two results:

* the database is copied to a temp directory first; the original is opened read-only once, to
  be copied, and never written;
* ``now`` is the cache's ``generated_at``;
* ``half_life_days`` and the obscurity percentile come from the cache itself (it records both);
* ``min_seconds_played`` is not recorded in the cache, so the fork's default is used, and the
  report says so;
* listens with ``played_at > generated_at`` are deleted from the temp copy before rebuilding;
* the timezone offset is the one the fork's ``_tz_offset_seconds`` would have returned in the
  given zone at ``generated_at``;
* player display names (which the fork resolved through MA's player registry) are taken from
  the cached ``players`` list.

Tolerance: every float in a genome is already rounded by the engine (4 decimal places), so two
results from identical inputs must agree to the digit. A numeric difference counts as a
mismatch when ``abs(a - b) > 1e-9`` - float representation noise only, not rounding slack.
Every other value must be equal. Exit status is 1 on any mismatch, 0 otherwise.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "custom_components"))

from listening_genome.baseline import load_baseline
from listening_genome.core.constants import (
    DB_TABLE_GENOME_CACHE,
    DB_TABLE_GENOME_LISTENS,
    DEFAULT_MIN_SECONDS_PLAYED,
    ENGINE_VERSION,
    LISTENER_HOUSEHOLD,
)
from listening_genome.core.service import GenomeService, GenomeServiceSettings
from listening_genome.core.store import GenomeStore

TOLERANCE = 1e-9
CACHE_KEY = f"genome:{LISTENER_HOUSEHOLD}:{ENGINE_VERSION}"

# the fields the parity brief names, reported one section at a time; everything else in the
# result is still diffed, under "other fields"
SECTIONS: list[tuple[str, Any]] = [
    ("divergence", lambda g: g["divergence"]),
    ("obscurity", lambda g: g["obscurity"]),
    ("stats", lambda g: g["stats"]),
    ("top 10 artists", lambda g: g["top_artists"][:10]),
    ("top tracks", lambda g: g["top_tracks"]),
    ("genre shares", lambda g: g["genres"]),
    ("rhythm", lambda g: g["rhythm"]),
]
NAMED_KEYS = {"divergence", "obscurity", "stats", "top_artists", "top_tracks", "genres", "rhythm"}


def diff(fork: Any, port: Any, path: str, out: list[tuple[str, Any, Any]]) -> int:
    """Append every leaf-level difference to ``out``; return the number of leaves compared."""
    if isinstance(fork, dict) and isinstance(port, dict):
        count = 0
        for key in sorted(set(fork) | set(port), key=str):
            sub = f"{path}.{key}" if path else str(key)
            if key not in fork or key not in port:
                out.append((sub, fork.get(key, "<missing>"), port.get(key, "<missing>")))
                count += 1
            else:
                count += diff(fork[key], port[key], sub, out)
        return count
    if isinstance(fork, list) and isinstance(port, list):
        count = 0
        if len(fork) != len(port):
            out.append((f"{path}.len", len(fork), len(port)))
            count += 1
        for idx, (a, b) in enumerate(zip(fork, port, strict=False)):
            count += diff(a, b, f"{path}[{idx}]", out)
        return count
    numeric = (int, float)
    if (
        isinstance(fork, numeric)
        and isinstance(port, numeric)
        and not isinstance(fork, bool)
        and not isinstance(port, bool)
    ):
        if abs(fork - port) > TOLERANCE:
            out.append((path, fork, port))
        return 1
    if fork != port:
        out.append((path, fork, port))
    return 1


def read_fork_cache(db_path: str) -> dict[str, Any]:
    """Read the fork's cached household genome."""
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            f"SELECT value FROM {DB_TABLE_GENOME_CACHE} WHERE key = ?", (CACHE_KEY,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise SystemExit(f"no {CACHE_KEY!r} row in {DB_TABLE_GENOME_CACHE}")
    return json.loads(row[0])


def drop_later_listens(db_path: str, generated_at: int) -> tuple[int, int]:
    """Delete listens played after the cache was written; return (deleted, remaining)."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            f"DELETE FROM {DB_TABLE_GENOME_LISTENS} WHERE played_at > ?", (generated_at,)
        )
        deleted = cur.rowcount
        conn.commit()
        remaining = conn.execute(f"SELECT COUNT(*) FROM {DB_TABLE_GENOME_LISTENS}").fetchone()[0]
    finally:
        conn.close()
    return deleted, remaining


async def run(source: str, tz_name: str) -> int:
    """Do the comparison; return the process exit status."""
    with tempfile.TemporaryDirectory(prefix="genome-parity-") as tmp:
        work_db = os.path.join(tmp, "genome.db")
        # read-only URI open: the source is only ever read, never locked for writing
        src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
        dst = sqlite3.connect(work_db)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()

        fork = read_fork_cache(work_db)
        generated_at = int(fork["generated_at"])
        deleted, remaining = drop_later_listens(work_db, generated_at)

        tz_offset = int(
            datetime.fromtimestamp(generated_at, ZoneInfo(tz_name)).utcoffset().total_seconds()  # type: ignore[union-attr]
        )
        player_names = {p["player_id"]: p["name"] for p in fork.get("players", [])}
        settings = GenomeServiceSettings(
            half_life_days=int(fork["half_life_days"]),
            obscurity_percentile=int(fork["obscurity"]["percentile"]),
            min_seconds_played=DEFAULT_MIN_SECONDS_PLAYED,
        )

        store = GenomeStore(tmp, player_name_resolver=player_names.get)
        await store.setup()
        try:
            service = GenomeService(
                store, await load_baseline(), settings, tz_offset_seconds=lambda: tz_offset
            )
            result = await service.rebuild_with_stats(now=generated_at)
        finally:
            await store.close()
        port = result["genome"]

    print("Parity: GenomeService vs the fork's cached genome")
    print(f"  source db            {source} (copied; original untouched)")
    print(f"  cache key            {CACHE_KEY}")
    print(
        f"  now = generated_at   {generated_at} "
        f"({datetime.fromtimestamp(generated_at, UTC).isoformat()})"
    )
    print(f"  tz                   {tz_name}, offset {tz_offset}s at generated_at")
    print(f"  half_life_days       {settings.half_life_days} (from cache)")
    print(f"  obscurity_percentile {settings.obscurity_percentile} (from cache)")
    print(
        f"  min_seconds_played   {settings.min_seconds_played} (not in cache; the fork's default)"
    )
    print(f"  listens after cache  {deleted} deleted; {remaining} rows fed to the store")
    print(
        f"  rebuild              {result['listens_scanned']} listens scanned "
        f"in {result['duration_ms']} ms"
    )
    print(f"  tolerance            abs diff <= {TOLERANCE:g} on numbers; exact otherwise")
    print()

    total_diffs = 0
    for label, pick in SECTIONS:
        out: list[tuple[str, Any, Any]] = []
        leaves = diff(pick(fork), pick(port), label.replace(" ", "_"), out)
        total_diffs += len(out)
        status = "MATCH" if not out else f"DIFFER ({len(out)} of {leaves})"
        print(f"[{status:>20}] {label}: {leaves} values compared")
        for path, a, b in out:
            print(f"      {path}: fork={a!r} port={b!r}")

    fork_rest = {k: v for k, v in fork.items() if k not in NAMED_KEYS}
    port_rest = {k: v for k, v in port.items() if k not in NAMED_KEYS}
    out = []
    leaves = diff(fork_rest, port_rest, "", out)
    total_diffs += len(out)
    status = "MATCH" if not out else f"DIFFER ({len(out)} of {leaves})"
    print(f"[{status:>20}] other fields ({', '.join(sorted(fork_rest))}): {leaves} values")
    for path, a, b in out:
        print(f"      {path}: fork={a!r} port={b!r}")

    print()
    print("Headline values")
    for label, pick in [
        ("divergence.score", lambda g: g["divergence"]["score"]),
        ("divergence.percent", lambda g: g["divergence"]["percent"]),
        ("obscurity.index", lambda g: g["obscurity"]["index"]),
        ("obscurity.threshold_listeners", lambda g: g["obscurity"]["threshold_listeners"]),
        ("stats.total_listens", lambda g: g["stats"]["total_listens"]),
        ("top_artists[0].name", lambda g: g["top_artists"][0]["name"]),
    ]:
        print(f"  {label:<30} fork={pick(fork)!r:<22} port={pick(port)!r}")
    print()
    if total_diffs:
        print(f"FAIL: {total_diffs} value(s) differ")
        return 1
    print("PASS: every compared value matches")
    return 0


def main() -> None:
    """Parse arguments and run."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("db", help="path to an exported genome.db (never modified)")
    parser.add_argument("--tz", default="America/Chicago", help="the fork server's time zone")
    args = parser.parse_args()
    if not os.path.isfile(args.db):
        raise SystemExit(f"not a file: {args.db}")
    sys.exit(asyncio.run(run(os.path.abspath(args.db), args.tz)))


if __name__ == "__main__":
    main()
