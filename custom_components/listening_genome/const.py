"""Constants for the Listening Genome Home Assistant integration (not the HA-free core)."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "listening_genome"

# the Music Assistant integration whose entry this one is linked to
MA_DOMAIN: Final = "music_assistant"

# config entry data: ONLY the linked Music Assistant entry's id. Its URL and token stay in that
# entry and are read from it at runtime, so they are never duplicated here.
CONF_MA_ENTRY_ID: Final = "ma_entry_id"

# genome.db and anything else the integration persists live in <config>/listening_genome
STORAGE_DIRNAME: Final = "listening_genome"

DEVICE_NAME: Final = "Listening Genome"

# how often the coordinator re-reads the genome (from cache; a rebuild only when none exists)
UPDATE_INTERVAL: Final = timedelta(hours=1)

PLATFORMS: Final[list[Platform]] = [Platform.SENSOR]

WS_TYPE_GET: Final = f"{DOMAIN}/get"
