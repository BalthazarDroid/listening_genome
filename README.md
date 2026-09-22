# Listening Genome

A listening-taste profile for Home Assistant, built from Music Assistant history, Last.fm and an
Apple Music export.

> **Status: phase 1 of 4.** The analysis core is here and tested. The Home Assistant integration
> itself — config flow, websocket API, sidebar panel, sensors — is not written yet, so installing
> this in HA does nothing useful so far.

## What is here

| Path | What it is |
|---|---|
| `custom_components/listening_genome/core/` | Models, the scoring engine, constants, the store protocol, HTTP client |
| `custom_components/listening_genome/importers/` | Last.fm, Apple Play Activity, Apple Play History Daily Tracks |
| `custom_components/listening_genome/enrich/` | MusicBrainz, ListenBrainz, Last.fm similar-artists |
| `custom_components/listening_genome/baseline/` | The reference distribution everything is compared against |
| `custom_components/listening_genome/compat.py` | Helpers vendored from Music Assistant — see below |
| `scripts/build_genome_baseline.py` | Rebuilds the baseline from ListenBrainz |
| `tests/` | 180 tests |

## About `compat.py`

Six helpers are copied verbatim from Music Assistant (Apache-2.0): `create_safe_string`,
`parse_title_and_version`, `json_loads`/`json_dumps`, `load_json_dict`, `Throttler` and
`DEFAULT_GENRE_MAPPING`.

They are copied rather than reimplemented on purpose. The first two derive every `artist_key` and
`track_key` in the database; a behavioural difference of any size would silently orphan every row
in an existing `genome.db` and there would be no way to tell from the outside. `tests/test_compat.py`
is a **differential** test — it runs the vendored and the real Music Assistant implementations over
the same adversarial corpus and asserts identical output, so drift fails the build rather than the
data.

## Requirements

Home Assistant **2026.3 or newer**. Two modules use PEP 758 (`except TypeError, ValueError:`),
which is Python 3.14 syntax; HA has shipped on 3.14 since 2026.3, and on an older core these files
would not parse.

## Development

```sh
python -m pytest tests/ -q
python -m ruff check .
```

The test suite expects the Music Assistant fork checked out as a sibling directory (`../server`),
since `test_compat.py` compares against the real implementations.
