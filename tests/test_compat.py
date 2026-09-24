"""
Differential tests for the vendored Music Assistant helpers in ``compat.py``.

These compare the vendored implementations against the real Music Assistant
implementations (imported from the sibling ``server`` checkout, see conftest.py) over
an adversarial corpus of inputs, and assert byte-for-byte identical outputs. Any
divergence here means an existing genome.db's artist_key/track_key values would
silently change, which is unrecoverable, so these tests must never be "fixed" by
relaxing the assertion.
"""

import itertools

from conftest import ma_source
from listening_genome import compat

ma_source()

import music_assistant_models.helpers as real_helpers  # noqa: E402
from music_assistant import constants as real_constants  # noqa: E402
from music_assistant.helpers import util as real_util  # noqa: E402

# ---------------------------------------------------------------------------
# create_safe_string
# ---------------------------------------------------------------------------

SAFE_STRING_INPUTS = [
    # special cases handled explicitly in the function
    "P!nk",
    "p!nk",
    "Wh♂",
    "wh♂",
    "KoЯn",
    "koЯn",
    "$hort",
    # accented / diacritic names
    "Björk",
    "Sigur Rós",
    "Beyoncé",
    "Mötley Crüe",
    "Café Tacvba",
    # non-latin scripts
    "Япония",
    "東京事変",
    "קרן",
    "北京",
    "Тату",
    # symbols
    "AC/DC",
    "†††",
    "¡Forward!",
    "Nine Inch Nails ™",
    "Panic! At The Disco",
    "Bloc Party & Friends",
    "50 Cent",
    "*NSYNC",
    "Ke$ha",
    # empty / whitespace only
    "",
    "   ",
    "\t\n",
    # emoji
    "🎵 Music 🎶",
    "Drake 🦉",
    "😀😃😄",
    # mixed
    "  Multiple   Spaces  ",
    "UPPERCASE lowercase MiXeD",
    "Numbers123AndText456",
    "Special-Chars_Here.Too,Right?",
    "a" * 500,
]


def test_create_safe_string_matches_upstream():
    """create_safe_string output must be byte-identical to the real MA function."""
    mismatches = []
    for value, lowercase, replace_space in itertools.product(
        SAFE_STRING_INPUTS, (True, False), (True, False)
    ):
        vendored = compat.create_safe_string(
            value, lowercase=lowercase, replace_space=replace_space
        )
        real = real_helpers.create_safe_string(
            value, lowercase=lowercase, replace_space=replace_space
        )
        if vendored != real:
            mismatches.append((value, lowercase, replace_space, vendored, real))
    assert not mismatches, mismatches


# ---------------------------------------------------------------------------
# parse_title_and_version
# ---------------------------------------------------------------------------

TITLE_INPUTS = [
    "Plain Title",
    "Song (Remastered 2019)",
    "Song - Remastered",
    "Song - Remastered 2019",
    "Track [Live]",
    "Track (Live)",
    "Song feat. Someone Else",
    "Song (feat. Someone Else)",
    "Song ft. X",
    "Song featuring X",
    "Song with You",
    "Song (with You)",
    "Song - with Drake",
    "Song (Official Video)",
    "Song (Official Music Video)",
    "Song [Official Lyric Video]",
    "Nested (Bracket (Inside) Group)",
    "Unbalanced (Bracket",
    "Unbalanced Bracket)",
    "(Only A Bracket Group)",
    "[Only A Bracket Group]",
    "",
    "   ",
    "Song (Deluxe Edition)",
    "Song (Deluxe Edition) [Explicit]",
    "Song (Acoustic Version)",
    "Song - 2019 Remaster",
    "Song (Karaoke Version) (Live)",
    "Song (Extended Mix) - Radio Edit",
    "Multiple (Groups) (Here) (Together)",
    "Song (with someone)",
    "Song (with the band)",
    "Title - with Someone Cool",
    "Weird ((Double Parens))",
    "Mismatched [Brackets)",
    "Song (Explicit)",
    "Song feat X (Remastered 2019)",
    "Artist Name - Song Title - Remastered",
    "Track (Anniversary Edition) [Deluxe]",
    "Song (2019 Version)",
]


def test_parse_title_and_version_matches_upstream():
    """parse_title_and_version output must be byte-identical to the real MA function."""
    mismatches = []
    kw_combos = list(itertools.product((False, True), (False, True)))
    for title, (strip_for_search, strip_for_display) in itertools.product(TITLE_INPUTS, kw_combos):
        vendored = compat.parse_title_and_version(
            title, strip_for_search=strip_for_search, strip_for_display=strip_for_display
        )
        real = real_util.parse_title_and_version(
            title, strip_for_search=strip_for_search, strip_for_display=strip_for_display
        )
        if vendored != real:
            mismatches.append((title, strip_for_search, strip_for_display, vendored, real))
    assert not mismatches, mismatches


def test_parse_title_and_version_with_track_version_matches_upstream():
    """Also check the track_version argument is threaded through identically."""
    mismatches = []
    for title in TITLE_INPUTS:
        for track_version in (None, "Remix", "Live Version"):
            vendored = compat.parse_title_and_version(title, track_version=track_version)
            real = real_util.parse_title_and_version(title, track_version=track_version)
            if vendored != real:
                mismatches.append((title, track_version, vendored, real))
    assert not mismatches, mismatches


# ---------------------------------------------------------------------------
# DEFAULT_GENRE_MAPPING
# ---------------------------------------------------------------------------


def test_default_genre_mapping_matches_upstream():
    """The vendored genre mapping data must be identical to MA's own constant."""
    assert compat.DEFAULT_GENRE_MAPPING == real_constants.DEFAULT_GENRE_MAPPING
