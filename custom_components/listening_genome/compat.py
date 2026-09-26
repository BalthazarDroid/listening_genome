"""
Vendored helpers from Music Assistant (Apache-2.0 licensed).

Listening Genome derives stable identity keys (``artist_key``, ``track_key``) from
``create_safe_string`` and ``parse_title_and_version``. Those keys are persisted in
``genome.db`` and are effectively unrecoverable if the string-normalisation behaviour
that produced them ever changes. The functions below are therefore copied verbatim
from the upstream Music Assistant server, not reimplemented, so that this integration
never silently drifts from the exact behaviour that generated an existing genome.db.

Source files (Music Assistant, Apache License 2.0, https://github.com/music-assistant):

- ``create_safe_string``:
  ``music_assistant_models/helpers.py`` (from the ``music-assistant-models`` package)
- ``parse_title_and_version`` and its private dependencies
  (``VERSION_PARTS``, ``IGNORE_TITLE_PARTS``, ``WITH_TITLE_WORDS``, the
  ``_TITLE_*``/``_SEARCH_*``/``_DISPLAY_*`` compiled regexes, ``_is_with_artist_credit``,
  ``_balanced_bracket_groups``, ``_strip_outer_markers``):
  ``music_assistant/helpers/util.py``
- ``json_loads``, ``json_dumps``, ``load_json_dict`` and their private dependencies
  (``get_serializable_value``, ``DO_NOT_SERIALIZE_TYPES``, ``_json_default``):
  ``music_assistant/helpers/json.py``
- ``Throttler``:
  ``music_assistant/helpers/throttle_retry.py``
- ``DEFAULT_GENRE_MAPPING``:
  ``music_assistant/constants.py`` (loaded, in upstream, from
  ``music_assistant/helpers/resources/genres/genre_mapping.json``; that same JSON file
  is vendored alongside this module as ``genre_mapping.json`` and loaded below)

Third-party requirements this module needs at runtime:

- ``anyascii`` (used by ``create_safe_string``)
- ``orjson`` (used by ``json_loads``/``json_dumps``/``load_json_dict``)
- ``aiofiles`` (used by ``load_json_dict``)

Note on ``Throttler``: in the upstream file, the ``Throttler`` class itself does not
raise any Music Assistant exception type (only the separate, non-vendored
``ThrottlerManager``/``throttle_with_retries`` helpers in that file do, via
``RetriesExhausted``/``RateLimited``/``ResourceTemporarilyUnavailable`` from
``music_assistant_models.errors``). Since those are not part of the vendored surface,
no substitution was needed for the code copied here. A local ``ThrottleError``
exception is still defined below, for callers of this module that want a stable,
dependency-free exception type to catch instead of importing Music Assistant's own
error classes.
"""

from __future__ import annotations

import asyncio
import base64
import functools
import importlib.resources
import json as _stdlib_json
import re
import time
from _collections_abc import dict_keys, dict_values
from collections import deque
from pathlib import Path
from types import MethodType
from typing import Any

import aiofiles
import orjson
from anyascii import anyascii

# ---------------------------------------------------------------------------
# Local substitute for Music Assistant's own exception hierarchy.
#
# Nothing in the vendored code below actually raises an MA exception type (see the
# module docstring), but this is provided so that code depending on this compat
# module has a stable exception type of its own to catch, without importing
# music_assistant_models.errors.
# ---------------------------------------------------------------------------


class ThrottleError(Exception):
    """Local stand-in for Music Assistant's throttle/retry related exceptions."""


# =============================================================================
# Vendored from music_assistant_models/helpers.py
# =============================================================================


#: the anyascii package holding its lookup tables, one file per 256-codepoint block, each named
#: by its block number in three hex digits (``000`` .. ``e00`` in anyascii 0.3)
_TRANSLITERATION_DATA_PACKAGE = "anyascii._data"


def preload_transliteration() -> None:
    """
    Read EVERY transliteration table now (blocking - call it in an executor).

    anyascii reads a block's table from disk the first time a character from that block is
    transliterated. Artist and track keys are built on Home Assistant's event loop, so a name
    in any script not loaded yet - CJK, Hangul, Thai, emoji - would read a file on the loop.
    Preloading only a handful of common blocks left all of those. Every table file in the
    package is loaded, through anyascii's own code path (one character from each block), so
    nothing depends on how anyascii caches them. Measured on anyascii 0.3.3 (640 tables,
    2.6 MB on disk): about 55 ms, and 6.4 MB of Python objects (+4.4 MB RSS), once per start.

    Only a codepoint in a block anyascii has NO table for still makes it look on disk (once;
    it then caches the empty block) - those characters have no transliteration anyway.
    """
    blocks = [
        int(resource.name, 16)
        for resource in importlib.resources.files(_TRANSLITERATION_DATA_PACKAGE).iterdir()
        if _is_block_name(resource.name)
    ]
    anyascii("".join(chr((block << 8) | 0x80) for block in sorted(blocks)))


def _is_block_name(name: str) -> bool:
    """Whether a resource in anyascii's data package is a block table (``"0a3"``)."""
    return len(name) == 3 and all(char in "0123456789abcdef" for char in name)


def create_safe_string(input_str: str, lowercase: bool = True, replace_space: bool = False) -> str:
    """Return clean lowered string for compare actions."""
    # handle some special cases
    if input_str in ("P!nk", "p!nk"):
        input_str = input_str.replace("!", "i")
    if input_str in ("Wh♂", "wh♂"):
        input_str = input_str.replace("♂", "o")
    if input_str in ("KoЯn", "koЯn"):
        input_str = input_str.replace("Я", "r")
    if input_str == "$hort":
        input_str = input_str.replace("$hort", "short")
    input_str = input_str.lower().strip() if lowercase else input_str.strip()
    unaccented_string = anyascii(input_str)
    if lowercase:
        # anyascii can emit uppercase for symbols and non-latin scripts (™ -> TM)
        unaccented_string = unaccented_string.lower()
    regex = r"[^a-zA-Z0-9]" if replace_space else r"[^a-zA-Z0-9 ]"
    return re.sub(regex, "", unaccented_string)


# =============================================================================
# Vendored from music_assistant/helpers/util.py
# =============================================================================

VERSION_PARTS = (
    # list of common version strings
    "version",
    "live",
    "edit",
    "remix",
    "mix",
    "acoustic",
    "instrumental",
    "karaoke",
    "remaster",
    "remastered",
    "versie",
    "unplugged",
    "disco",
    "akoestisch",
    "deluxe",
    "video",
    "radio",
    "extended",
    "single",
    "edition",
    "anniversary",
    "stereo",
    "album",
    "bonus",
    "release",
)
IGNORE_TITLE_PARTS = (
    # strings that may be stripped off a title part
    # (most important the featuring parts)
    "feat.",
    "featuring",
    "ft.",
    "with ",
    "explicit",
)
WITH_TITLE_WORDS = (
    # first words after "with" that should stay part of the title, not a credit
    "someone",
    "the",
    "u",
    "you",
    "no",
)
_TITLE_FEATURED_CREDIT_PATTERN = re.compile(
    # require preceding title text so titles starting with "Featuring"/"Ft" stay intact
    r"(?:[(\[]|(?<=\s))\b(?:feat(?:uring)?|ft)(?:(?:\.|:)\s*|\s+)"
    r"(.+?)(?=\s*(?:\(|\[|\)|\]| - |$))",
    re.IGNORECASE,
)
_TITLE_BRACKETED_WITH_CREDIT_PATTERN = re.compile(
    r"(?:\(|\[)with\s+(?P<credit>.+?)(?:\)|\])",
    re.IGNORECASE,
)
_TITLE_HYPHEN_WITH_CREDIT_PATTERN = re.compile(
    r"\s+-\s+with\s+(?P<credit>.+?)(?=\s*(?:\(|\[| - |$))",
    re.IGNORECASE,
)
_TITLE_WITH_CREDIT_PATTERNS = (
    _TITLE_BRACKETED_WITH_CREDIT_PATTERN,
    _TITLE_HYPHEN_WITH_CREDIT_PATTERN,
)

# Keywords for aggressive search cleaning (includes featuring).
_VERSION_PATTERN = "|".join(re.escape(v) for v in VERSION_PARTS)
_FEAT_PATTERN = r"feat(?:uring)?|ft"
_SEARCH_PATTERN = rf"{_VERSION_PATTERN}|{_FEAT_PATTERN}"

_SEARCH_PAREN_PATTERN = re.compile(
    rf"[\(\[][^\)\]]*\b({_SEARCH_PATTERN})\b[^\)\]]*[\)\]]",
    re.IGNORECASE,
)
_SEARCH_HYPHEN_PATTERN = re.compile(
    rf"(\s*-\s*(\d{{4}}|{_SEARCH_PATTERN}).*)$",
    re.IGNORECASE,
)

# Superfluous suffixes to strip for display (video/audio markers, etc.)
_DISPLAY_STRIP_PATTERN = re.compile(
    r"\s*[\(\[]"
    r"(official\s+)?(lyric\s+|music\s+)?(video|audio|visualizer|clip)"
    r"[\)\]]$",
    re.IGNORECASE,
)


def _is_with_artist_credit(value: str) -> bool:
    """Return whether a with-suffix identifies an artist rather than title words."""
    first_word = value.split(maxsplit=1)[0].casefold().strip(".,:;!?") if value else ""
    return bool(first_word) and first_word not in WITH_TITLE_WORDS


@functools.lru_cache(maxsize=2048)
def parse_title_and_version(
    title: str,
    track_version: str | None = None,
    strip_for_search: bool = False,
    strip_for_display: bool = False,
) -> tuple[str, str]:
    """
    Parse version from the title and optionally clean for search or display.

    :param title: The title to parse.
    :param track_version: Optional existing version string.
    :param strip_for_search: Aggressively strip for search matching.
    :param strip_for_display: Strip superfluous suffixes for display.
    """
    version_parts = [track_version] if track_version else []
    version_keys = {track_version.casefold()} if track_version else set()

    # Strip featuring, bracketed version info, and hyphen suffixes (e.g. "- Remastered 2019")
    if strip_for_search:
        with_credit_matches = [
            match for pattern in _TITLE_WITH_CREDIT_PATTERNS for match in pattern.finditer(title)
        ]
        for match in sorted(with_credit_matches, key=lambda item: item.start(), reverse=True):
            if _is_with_artist_credit(match.group("credit")):
                title = f"{title[: match.start()]}{title[match.end() :]}"
        title = _SEARCH_PAREN_PATTERN.sub("", title)
        title = _SEARCH_HYPHEN_PATTERN.sub("", title)
        # Strip bare featuring credits with the same pattern used for extraction.
        if bare_credit_match := _TITLE_FEATURED_CREDIT_PATTERN.search(title):
            title = title[: bare_credit_match.start()]
        # Clean up dangling hyphens and extra spaces
        title = re.sub(r"\s*-\s*$", "", title)
        title = re.sub(r"\s+", " ", title).strip()
        return title, track_version or ""

    # Strip video/audio suffixes like "(Official Video)"
    if strip_for_display:
        title = _DISPLAY_STRIP_PATTERN.sub("", title).strip()
        return title, track_version or ""

    # Standard version parsing
    # each pass extracts from the current title so removals from
    # earlier passes are taken into account
    for extract_parts in (
        lambda t: _balanced_bracket_groups(t, "(", ")"),
        lambda t: _balanced_bracket_groups(t, "[", "]"),
        lambda t: re.findall(r" - .*", t),
    ):
        for title_part in extract_parts(title):
            # skip parts already consumed by an earlier removal in this pass
            if title_part not in title:
                continue
            # Extract the content without brackets/dashes for checking
            clean_part = title_part.translate(str.maketrans("", "", "()[]-")).strip().lower()

            # Check if this should be ignored (featuring/explicit parts)
            should_ignore = False
            for ignore_str in IGNORE_TITLE_PARTS:
                if clean_part.startswith(ignore_str):
                    # Special handling for "with " - check if followed by title words
                    if ignore_str == "with ":  # noqa: SIM102 (verbatim upstream logic)
                        if not _is_with_artist_credit(clean_part[len("with ") :]):
                            # This is part of the title (e.g., "with you"), don't ignore
                            break
                    # Remove this part from the title
                    title = title.replace(title_part, "").strip()
                    should_ignore = True
                    break

            if should_ignore:
                continue

            # Check if this part is a version
            for version_str in VERSION_PARTS:
                if version_str in clean_part:
                    # Preserve original casing (and any nested brackets) for output
                    version_part = _strip_outer_markers(title_part)
                    if version_part.casefold() not in version_keys:
                        version_parts.append(version_part)
                        version_keys.add(version_part.casefold())
                    title = title.replace(title_part, "").strip()
                    break
    title = re.sub(r"\s{2,}", " ", title).strip()
    return title, " ".join(version_parts)


def _balanced_bracket_groups(text: str, open_char: str, close_char: str) -> list[str]:
    """
    Return the top-level balanced bracketed substrings, including the outer brackets.

    :param text: The text to scan.
    :param open_char: The opening bracket character.
    :param close_char: The closing bracket character.
    """
    groups: list[str] = []
    depth = 0
    start = -1
    for idx, char in enumerate(text):
        if char == open_char:
            if depth == 0:
                start = idx
            depth += 1
        elif char == close_char and depth > 0:
            depth -= 1
            if depth == 0:
                groups.append(text[start : idx + 1])
    return groups


def _strip_outer_markers(part: str) -> str:
    """
    Strip the outer brackets or leading hyphen from a parsed title part.

    :param part: The raw title part as matched from the title.
    """
    part = part.strip()
    # only strip a single outer bracket pair so nested brackets stay intact
    if part[:1] in "([" and part[-1:] in ")]":
        return part[1:-1].strip()
    return part.lstrip("- ").strip()


# =============================================================================
# Vendored from music_assistant/helpers/json.py
# =============================================================================

DO_NOT_SERIALIZE_TYPES = (MethodType, asyncio.Task)


def get_serializable_value(obj: Any) -> Any:
    """Parse the value to its serializable equivalent."""
    if getattr(obj, "do_not_serialize", None):
        return None
    if isinstance(obj, list | set | filter | tuple | dict_values | dict_keys) or (
        obj.__class__.__name__ == "dict_valueiterator"
    ):
        return [get_serializable_value(x) for x in obj]
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if isinstance(obj, bytes):
        return base64.b64encode(obj).decode("ascii")
    if isinstance(obj, DO_NOT_SERIALIZE_TYPES):
        return None
    # unhandled values are returned as-is on purpose: serialize_to_json and the
    # recursion above rely on natively serializable values passing through
    return obj


def json_dumps(data: Any, indent: bool = False) -> str:
    """Dump json string."""
    # we use the passthrough dataclass option because we use mashumaro for that
    option = orjson.OPT_OMIT_MICROSECONDS | orjson.OPT_PASSTHROUGH_DATACLASS
    if indent:
        option |= orjson.OPT_INDENT_2
    return orjson.dumps(
        data,
        default=_json_default,
        option=option,
    ).decode("utf-8")


json_loads = orjson.loads


async def load_json_dict(path: str) -> dict[str, Any]:
    """
    Load a plain JSON object from file as a dict.

    For JSON files that are not backed by a dataclass (e.g. translation strings files).

    :param path: Absolute path to the JSON file.
    """
    async with aiofiles.open(path, "rb") as _file:
        content = await _file.read()
    data = orjson.loads(content)
    if not isinstance(data, dict):
        msg = f"Expected a JSON object in {path}, got {type(data).__name__}"
        raise TypeError(msg)
    return data


def _json_default(obj: Any) -> Any:
    """Convert a value for orjson, raising a descriptive error for unhandled types."""
    value = get_serializable_value(obj)
    if value is obj:
        cls = type(obj)
        msg = (
            f"unhandled type for json serialization: {cls.__module__}.{cls.__qualname__}"
            " - pass a dict (e.g. via .to_dict()) instead of the raw object"
        )
        raise TypeError(msg)
    return value


# =============================================================================
# Vendored from music_assistant/helpers/throttle_retry.py
# =============================================================================


class Throttler:
    """
    asyncio_throttle (https://github.com/hallazzang/asyncio-throttle).

    With improvements:
    - Accurate sleep without "busy waiting" (PR #4)
    - Return the delay caused by acquire()
    """

    def __init__(self, rate_limit: int, period: float = 1.0) -> None:
        """Initialize the Throttler."""
        self.rate_limit = rate_limit
        self.period = period
        self._task_logs: deque[float] = deque()

    async def acquire(self) -> float:
        """Acquire a free slot from the Throttler, returns the throttled time."""
        cur_time = time.monotonic()
        start_time = cur_time
        while True:
            self._flush()
            if len(self._task_logs) < self.rate_limit:
                break
            # sleep the exact amount of time until the oldest task can be flushed
            time_to_release = self._task_logs[0] + self.period - cur_time
            await asyncio.sleep(time_to_release)
            cur_time = time.monotonic()

        self._task_logs.append(cur_time)
        return cur_time - start_time  # exactly 0 if not throttled

    async def __aenter__(self) -> float:
        """Wait until the lock is acquired, return the time delay."""
        return await self.acquire()

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> bool | None:
        """Nothing to do on exit."""

    def _flush(self) -> None:
        now = time.monotonic()
        while self._task_logs:
            if now - self._task_logs[0] > self.period:
                self._task_logs.popleft()
            else:
                break


# =============================================================================
# Vendored from music_assistant/constants.py
# =============================================================================
#
# Upstream computes this at import time via
# ``load_genre_mapping(GENRE_MAPPING_FILE)``, which reads and json-parses
# ``music_assistant/helpers/resources/genres/genre_mapping.json``. That same JSON
# file (byte-for-byte) is vendored next to this module as ``genre_mapping.json`` and
# loaded the same way here, so the resulting list of dicts is identical.

_GENRE_MAPPING_FILE = Path(__file__).with_name("genre_mapping.json")
DEFAULT_GENRE_MAPPING: list[dict[str, Any]] = _stdlib_json.loads(
    _GENRE_MAPPING_FILE.read_text(encoding="utf-8")
)
