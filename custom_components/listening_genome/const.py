"""Constants for the Listening Genome Home Assistant integration (not the HA-free core)."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

from homeassistant.const import Platform

from .core.constants import GENOME_ENRICHMENT_INTERVAL_SECONDS

DOMAIN: Final = "listening_genome"

# the Music Assistant integration whose entry this one is linked to
MA_DOMAIN: Final = "music_assistant"

# config entry data: ONLY the linked Music Assistant entry's id. Its URL and token stay in that
# entry and are read from it at runtime, so they are never duplicated here.
CONF_MA_ENTRY_ID: Final = "ma_entry_id"

# genome.db and anything else the integration persists live in <config>/listening_genome
STORAGE_DIRNAME: Final = "listening_genome"

DEVICE_NAME: Final = "Listening Genome"

# The coordinator no longer polls: it holds the genome, read once at setup and replaced by every
# rebuild (daily at the configured local hour, the button, or the websocket command).

# how often the background enrichment pass runs (the fork's hourly scheduled task)
ENRICHMENT_INTERVAL: Final = timedelta(seconds=GENOME_ENRICHMENT_INTERVAL_SECONDS)

# the first Last.fm poll after start-up: soon enough to catch up on what was scrobbled while
# Home Assistant was down, late enough not to add to start-up's own load
LASTFM_STARTUP_POLL_DELAY: Final = timedelta(minutes=2)

PLATFORMS: Final[list[Platform]] = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR]

WS_TYPE_GET: Final = f"{DOMAIN}/get"
WS_TYPE_REBUILD: Final = f"{DOMAIN}/rebuild"
WS_TYPE_JOBS: Final = f"{DOMAIN}/jobs"
WS_TYPE_UNRESOLVED_ARTISTS: Final = f"{DOMAIN}/unresolved_artists"
WS_TYPE_RETRY_ARTISTS: Final = f"{DOMAIN}/retry_artists"
WS_TYPE_DISMISS_UNRESOLVED: Final = f"{DOMAIN}/dismiss_unresolved"
WS_TYPE_IMPORT_LASTFM: Final = f"{DOMAIN}/import_lastfm"
WS_TYPE_IMPORT_APPLE: Final = f"{DOMAIN}/import_apple"
WS_TYPE_LIVE: Final = f"{DOMAIN}/live"

# actions
SERVICE_IMPORT_LASTFM: Final = "import_lastfm"
SERVICE_IMPORT_APPLE_CSV: Final = "import_apple_csv"
ATTR_PATH: Final = "path"
ATTR_MAX_PAGES: Final = "max_pages"

# where an uploaded Apple export is copied while it is imported (inside STORAGE_DIRNAME)
UPLOADS_DIRNAME: Final = "uploads"
