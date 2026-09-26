# Listening Genome

A listening-taste profile for Home Assistant, built from Music Assistant history, Last.fm and an
Apple Music export.

> **Status: phase 3 of 4.** The integration installs through HACS, keeps its history current,
> publishes sensors, and adds a **Listening Genome** page to the sidebar.

## What it does

- **Live capture.** Opens its own session to the Music Assistant server the MA integration points
  at, and records every track played — one listen per play, with the room it played in. The
  *Music Assistant connection* diagnostic sensor says whether it is connected and what it last
  recorded.
- **Last.fm.** With a username and API key in the settings, imports the whole scrobble history
  once, then fetches new scrobbles every hour (configurable).
- **Apple Music.** Imports *Apple Music - Play History Daily Tracks.csv* from an Apple data export
  (action `listening_genome.import_apple_csv`, or an upload over the websocket API).
- **No double counting.** A Last.fm scrobble of a play Apple's export or Music Assistant already
  recorded is removed — once over the whole history, then after every import.
- **Music discovery.** Once a day, artists worth trying: Last.fm's similar artists for the
  genres where your taste stands out, and barely played artists already in your library — each
  with one song. The websocket API plays that one song on a Music Assistant speaker you pick
  (the panel's play button, in phase 3).
- **Keeps itself current.** Rebuilds daily at 04:00, looks new artists up on MusicBrainz and
  ListenBrainz hourly, and has a *Rebuild now* button.
- **Sensors:** obscurity index, divergence, top artist, listens stored, last rebuild.

## What is here

| Path | What it is |
|---|---|
| `custom_components/listening_genome/core/` | Models, the scoring engine, constants, the store protocol, HTTP client |
| `custom_components/listening_genome/importers/` | Last.fm, Apple Play Activity, Apple Play History Daily Tracks |
| `custom_components/listening_genome/enrich/` | MusicBrainz, ListenBrainz, Last.fm similar-artists |
| `custom_components/listening_genome/baseline/` | The reference distribution everything is compared against |
| `custom_components/listening_genome/compat.py` | Helpers vendored from Music Assistant — see below |
| `scripts/build_genome_baseline.py` | Rebuilds the baseline from ListenBrainz |
| `custom_components/listening_genome/*.py` | The Home Assistant side: setup, schedules, live capture, settings, sensors, actions, websocket API |
| `tests/` | 340+ tests; `tests/ha/` runs the integration inside a real Home Assistant core |

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

The sidebar panel is Lit + TypeScript in `frontend/`, bundled into
`custom_components/listening_genome/frontend/listening-genome-panel.js`. HACS installs the
repository as it is and never builds, so **the built file is committed**: after changing
anything in `frontend/src`, run `npm run build` there and commit the result.

```sh
cd frontend && npm install && npm run build && npx vitest run
node dev/shoot.mjs /tmp/page.png "" 1400 1000 1   # screenshot the dev harness
```

```sh
python -m pytest tests/ -q
python -m ruff check .
```

The test suite expects the Music Assistant fork checked out as a sibling directory (`../server`),
since `test_compat.py` compares against the real implementations.
