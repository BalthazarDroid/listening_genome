"""
Opt-in: run the integration over a COPY of a real genome.db, in America/Chicago.

Skipped unless ``LISTENING_GENOME_REAL_DB`` names a database. The file is copied into the
test's temporary config directory and only the copy is ever opened; its sha256 is checked
before and after. Enrichment is switched off so the run makes no network requests; what the
first enrichment pass would pick up is printed instead. Run with ``-s`` to see the report.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.button import SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID

from custom_components.listening_genome.const import STORAGE_DIRNAME
from custom_components.listening_genome.core.constants import CONF_ENRICH_ENABLED

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

REAL_DB = os.environ.get("LISTENING_GENOME_REAL_DB", "")
SENSORS = (
    "sensor.listening_genome_obscurity_index",
    "sensor.listening_genome_divergence",
    "sensor.listening_genome_top_artist",
    "sensor.listening_genome_listens_stored",
    "sensor.listening_genome_last_rebuild",
)

pytestmark = pytest.mark.skipif(
    not REAL_DB, reason="set LISTENING_GENOME_REAL_DB to a genome.db to run against real data"
)


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _report(hass: HomeAssistant, title: str) -> None:
    print(f"\n{title}")
    for entity_id in SENSORS:
        state = hass.states.get(entity_id)
        stale = state.attributes.get("stale")
        print(
            f"  {entity_id} = {state.state}" + (f"  (stale={stale})" if stale is not None else "")
        )


async def test_real_database(
    hass: HomeAssistant, genome_entry: MockConfigEntry, hass_tmp_config_dir: str
) -> None:
    original_sha = await hass.async_add_executor_job(_sha256, REAL_DB)
    storage = Path(hass_tmp_config_dir) / STORAGE_DIRNAME
    await hass.async_add_executor_job(lambda: storage.mkdir(parents=True, exist_ok=True))
    await hass.async_add_executor_job(shutil.copyfile, REAL_DB, str(storage / "genome.db"))
    await hass.config.async_set_time_zone("America/Chicago")

    genome_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(genome_entry, options={CONF_ENRICH_ENABLED: False})
    assert await hass.config_entries.async_setup(genome_entry.entry_id)
    await hass.async_block_till_done()
    runtime = genome_entry.runtime_data
    _report(hass, "After setup (the cached genome):")
    print(f"  jobs after load: { {k: v['state'] for k, v in runtime.jobs.get_all().items()} }")
    raw = await runtime.store.count_listens("household")
    eligible = await runtime.store.count_eligible_listens("household", min_seconds_played=30)
    print(f"  listens stored {raw}, counted by a rebuild {eligible}")

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.listening_genome_rebuild_now"},
        blocking=True,
    )
    await hass.async_block_till_done()
    _report(hass, "After pressing Rebuild now:")
    print(f"  rebuild job: {runtime.jobs.get('rebuild')['message']}")
    due = await runtime.store.pending_artist_keys(limit=100_000)
    backlog = await runtime.store.pending_popularity_keys(limit=100_000)
    counts = await runtime.store.artist_resolution_counts()
    print(f"  artist states: {counts}")
    print(f"  first enrichment pass would look up {len(due)} artists on MusicBrainz")
    print(f"  and {len(backlog)} on ListenBrainz (popularity backlog)")
    assert hass.states.get("sensor.listening_genome_last_rebuild").attributes["stale"] is False

    assert await hass.config_entries.async_unload(genome_entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.async_add_executor_job(_sha256, REAL_DB) == original_sha
