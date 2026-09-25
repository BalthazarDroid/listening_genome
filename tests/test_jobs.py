"""Tests for the job tracker ported from the fork (``core/jobs.py``)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from listening_genome.core.jobs import (
    INTERRUPTED_MESSAGE,
    JOB_ENRICHMENT,
    JOB_REBUILD,
    JobTracker,
)
from listening_genome.core.store import GenomeStore

if TYPE_CHECKING:
    from pathlib import Path


class _CountingStore:
    """A ``get_jobs``/``set_jobs`` store that counts its writes."""

    def __init__(self, stored: dict[str, Any] | None = None) -> None:
        self.stored = stored or {}
        self.writes = 0

    async def get_jobs(self) -> dict[str, Any]:
        return self.stored

    async def set_jobs(self, data: dict[str, Any]) -> None:
        self.writes += 1
        self.stored = data


def _clock() -> float:
    return 1_790_000_000.0


async def test_every_job_starts_idle() -> None:
    tracker = JobTracker(_CountingStore(), clock=_clock)
    jobs = tracker.get_all()
    assert set(jobs) == {JOB_REBUILD, JOB_ENRICHMENT}
    assert all(job["state"] == "idle" for job in jobs.values())


async def test_start_finish_fail_persist_through_the_real_store(tmp_path: Path) -> None:
    store = GenomeStore(str(tmp_path))
    await store.setup()
    try:
        tracker = JobTracker(store, clock=_clock)
        await tracker.start(JOB_REBUILD, "Rebuilding")
        assert (await store.get_jobs())[JOB_REBUILD]["state"] == "running"
        await tracker.finish(JOB_REBUILD, "Rebuilt from 4 listens")
        await tracker.start(JOB_ENRICHMENT, "Looking up")
        await tracker.fail(JOB_ENRICHMENT, "HTTP 503")

        reloaded = JobTracker(store, clock=_clock)
        await reloaded.load()
    finally:
        await store.close()
    rebuild = reloaded.get(JOB_REBUILD)
    assert rebuild["state"] == "ok"
    assert rebuild["message"] == "Rebuilt from 4 listens"
    assert rebuild["progress"] == 100
    assert rebuild["finished_at"] == 1_790_000_000
    assert reloaded.get(JOB_ENRICHMENT)["state"] == "error"


async def test_a_job_left_running_is_interrupted_on_load() -> None:
    store = _CountingStore(
        {JOB_ENRICHMENT: {"job": JOB_ENRICHMENT, "state": "running", "started_at": 5}}
    )
    tracker = JobTracker(store, clock=_clock)
    await tracker.load()
    job = tracker.get(JOB_ENRICHMENT)
    assert job["state"] == "interrupted"
    assert job["message"] == INTERRUPTED_MESSAGE
    assert job["started_at"] == 5
    assert job["finished_at"] == 1_790_000_000
    # and written back, so the next load does not warn about it again
    assert store.writes == 1
    assert store.stored[JOB_ENRICHMENT]["state"] == "interrupted"


async def test_the_forks_export_job_is_dropped_on_load() -> None:
    """
    The fork's export recorded itself ``running`` inside the snapshot it was writing, so every
    exported database carries a "running" export_db that in fact finished. It must not come
    back as an "interrupted" job this integration never runs.
    """
    store = _CountingStore(
        {
            "export_db": {"job": "export_db", "state": "running"},
            "lastfm_import": {"job": "lastfm_import", "state": "idle"},
        }
    )
    tracker = JobTracker(store, clock=_clock)
    await tracker.load()
    jobs = tracker.get_all()
    assert "export_db" not in jobs
    assert jobs["lastfm_import"]["state"] == "idle"
    assert "export_db" not in store.stored


async def test_progress_updates_never_write_the_database() -> None:
    """A per-second progress write into genome.db is the fork's two-day bug; never again."""
    store = _CountingStore()
    tracker = JobTracker(store, clock=_clock)
    await tracker.start(JOB_ENRICHMENT, "Looking up")
    writes_after_start = store.writes
    for done in range(1, 501):
        tracker.update(JOB_ENRICHMENT, message=f"{done} of 500", progress=done * 100 // 500)
    assert store.writes == writes_after_start
    assert tracker.get(JOB_ENRICHMENT)["progress"] == 100
    assert tracker.get(JOB_ENRICHMENT)["message"] == "500 of 500"
    await tracker.finish(JOB_ENRICHMENT, "done")
    assert store.writes == writes_after_start + 1


async def test_interrupt_running_marks_only_running_jobs() -> None:
    store = _CountingStore()
    tracker = JobTracker(store, clock=_clock)
    await tracker.start(JOB_ENRICHMENT, "Looking up")
    await tracker.start(JOB_REBUILD, "Rebuilding")
    await tracker.finish(JOB_REBUILD, "done")
    assert await tracker.interrupt_running() == [JOB_ENRICHMENT]
    assert tracker.get(JOB_ENRICHMENT)["state"] == "interrupted"
    assert tracker.get(JOB_REBUILD)["state"] == "ok"
    assert store.stored[JOB_ENRICHMENT]["state"] == "interrupted"
    assert await tracker.interrupt_running() == []
