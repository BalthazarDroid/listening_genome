"""Artist keys are built on Home Assistant's event loop, so their lookup tables are preloaded."""

from __future__ import annotations

import importlib.resources
from pathlib import Path
from unittest.mock import patch

import anyascii
from listening_genome.compat import create_safe_string, preload_transliteration

_NAMES = (
    "Sigur Rós – Hoppípolla",  # noqa: RUF001 - accents and an en dash
    "坂本龍一",  # CJK
    "방탄소년단",  # Hangul
    "ธงไชย แมคอินไตย์",  # Thai
    "Love ❤ Song 🎸",  # symbols and emoji (astral plane)
    "ﾒﾛﾃﾞｨ",  # halfwidth kana
    "Мумий Тролль",  # Cyrillic
)


def _table_files() -> set[int]:
    return {
        int(resource.name, 16)
        for resource in importlib.resources.files("anyascii._data").iterdir()
        if len(resource.name) == 3
    }


def test_preloading_reads_every_transliteration_table() -> None:
    """
    After the preload, no name in any script makes Home Assistant read a file on its loop.

    Regression: only eleven common blocks were preloaded, so a CJK, Hangul, Thai or emoji
    name still read its table from disk on the event loop the first time it was keyed.
    """
    anyascii._blocks.clear()
    preload_transliteration()
    assert set(anyascii._blocks) == _table_files()
    assert all(anyascii._blocks.values())  # every one really loaded, none empty

    real_read = Path.read_bytes
    reads: list[str] = []

    def spy(self: Path) -> bytes:
        reads.append(self.name)
        return real_read(self)

    with patch.object(Path, "read_bytes", spy):
        keys = [create_safe_string(name) for name in _NAMES]
    assert reads == []
    assert keys[0] == "sigur ros  hoppipolla"
    assert all(keys)
