"""
Persisted job tracker for the Listening Genome's long-running operations.

Ported from the fork's ``controllers/genome/jobs.py``. The reason it exists is unchanged: an
operation that runs for seconds or minutes must write its outcome down rather than only return
it, so the result survives the request that started it going away, and survives a restart.
:class:`JobTracker` keeps the last known state of every job, persists it through the store's
``set_jobs``/``get_jobs`` (one json row in the ``settings`` table, same key as the fork, so a
database exported from the fork carries its job history across), and serves reads from memory.

Differences from the fork, each deliberate:

* The jobs are this integration's own: ``rebuild``, ``enrichment``, the fork's
  ``lastfm_import`` and ``apple_import`` (same ids), and ``duplicates``. The fork's
  ``export_db`` is retired: the fork recorded that job as ``running`` *inside the very snapshot
  it was writing*, so every exported database carries an ``export_db`` that looks interrupted
  but in fact finished. Restoring it would greet the user with a false "interrupted" warning.
* A job found ``running`` at startup becomes ``interrupted`` (its own state), rather than the
  fork's generic ``error``: nothing failed, the process simply stopped, and the panel can say so.
* :meth:`JobTracker.update` (progress) changes memory only and never writes the database. In
  the fork, a per-second progress write into ``genome.db`` while the same database was being
  copied is what turned a one-second export into a two-day bug. Only start, finish, fail and
  interrupt are persisted, which is at most a handful of writes per run.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from .constants import LOGGER

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

# job ids: the keys of the `listening_genome/jobs` payload, part of the panel's contract
JOB_REBUILD = "rebuild"
JOB_ENRICHMENT = "enrichment"
# the fork's import jobs (same ids, so a fork database's last results carry across)
JOB_LASTFM_IMPORT = "lastfm_import"
JOB_APPLE_IMPORT = "apple_import"
# 2c's duplicate removal: once over the whole history, then after every import
JOB_DUPLICATES = "duplicates"
# 2d's discovery pass (daily, or on request)
JOB_DISCOVERY = "discovery"

#: the jobs this integration runs, in the order a UI shows them; each always has a state
ALL_JOBS: tuple[str, ...] = (
    JOB_REBUILD,
    JOB_ENRICHMENT,
    JOB_LASTFM_IMPORT,
    JOB_APPLE_IMPORT,
    JOB_DUPLICATES,
    JOB_DISCOVERY,
)

#: every job id :meth:`JobTracker.load` restores; anything else in the stored map is dropped
KNOWN_JOBS: frozenset[str] = frozenset(ALL_JOBS)

JOB_STATE_IDLE = "idle"
JOB_STATE_RUNNING = "running"
JOB_STATE_OK = "ok"
JOB_STATE_ERROR = "error"
JOB_STATE_INTERRUPTED = "interrupted"

_VALID_STATES = frozenset(
    {
        JOB_STATE_IDLE,
        JOB_STATE_RUNNING,
        JOB_STATE_OK,
        JOB_STATE_ERROR,
        JOB_STATE_INTERRUPTED,
    }
)

# what a job left `running` by a process that went away is told when this process loads it
INTERRUPTED_MESSAGE = (
    "Interrupted: Home Assistant stopped or the integration reloaded while this was running, "
    "so it never finished. It runs again on its next schedule, or start it now."
)


@dataclass(frozen=True)
class JobState:
    """
    The last known state of one long-running operation (unchanged from the fork).

    :param job: The job id.
    :param state: One of ``idle``, ``running``, ``ok``, ``error``, ``interrupted``.
    :param message: The human-readable outcome - the whole answer, not "done".
    :param started_at: Unix timestamp of the last start, or ``None`` if never started.
    :param finished_at: Unix timestamp of the last finish, or ``None`` while running/never run.
    :param progress: Percentage 0-100, or ``None`` meaning "indeterminate".
    """

    job: str
    state: str = JOB_STATE_IDLE
    message: str = ""
    started_at: int | None = None
    finished_at: int | None = None
    progress: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe wire form served by ``listening_genome/jobs`` and stored."""
        return {
            "job": self.job,
            "state": self.state,
            "message": self.message,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "progress": self.progress,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> JobState:
        """Rebuild a :class:`JobState` from its stored form; anything unreadable degrades to idle."""
        state = str(data.get("state") or JOB_STATE_IDLE)
        if state not in _VALID_STATES:
            state = JOB_STATE_IDLE
        return cls(
            job=str(data.get("job") or ""),
            state=state,
            message=str(data.get("message") or ""),
            started_at=_int_or_none(data.get("started_at")),
            finished_at=_int_or_none(data.get("finished_at")),
            progress=_int_or_none(data.get("progress")),
        )


def _int_or_none(value: Any) -> int | None:
    """Coerce a stored value to ``int``, or ``None`` when it is absent or not a number."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except TypeError, ValueError:  # pragma: no cover - defensive, malformed settings row
        return None


class JobTracker:
    """
    Remembers what the long-running operations did, across page loads and restarts.

    Reads come from memory and never touch the database; persisted transitions update memory
    first and then write the whole (small) map through the store.
    """

    def __init__(self, store: Any, *, clock: Callable[[], float] | None = None) -> None:
        """
        Initialize the tracker with every job in :data:`ALL_JOBS` idle.

        :param store: A ``GenomeStore``-shaped object exposing ``get_jobs``/``set_jobs``.
        :param clock: Wall clock (unix seconds); defaults to :func:`time.time`.
        """
        self._store = store
        self._clock = clock or time.time
        self._jobs: dict[str, JobState] = {job: JobState(job=job) for job in ALL_JOBS}

    def get_all(self) -> dict[str, dict[str, Any]]:
        """Return every job's state in wire form. Pure and instant: never touches the database."""
        return {job: state.to_dict() for job, state in self._jobs.items()}

    def get(self, job: str) -> dict[str, Any]:
        """Return one job's state in wire form, creating an idle entry for an unknown id."""
        return self._jobs.setdefault(job, JobState(job=job)).to_dict()

    def is_running(self, job: str) -> bool:
        """Return whether ``job`` is currently marked running."""
        state = self._jobs.get(job)
        return state is not None and state.state == JOB_STATE_RUNNING

    async def load(self) -> None:
        """
        Restore persisted job state, turning anything a gone process left ``running`` into
        ``interrupted``. Must run after the store is set up and before any job starts.
        """
        try:
            stored = await self._store.get_jobs()
        except Exception:  # pragma: no cover - defensive, a broken store must not block setup
            LOGGER.warning(
                "Could not load Listening Genome job state; starting idle", exc_info=True
            )
            return
        if not isinstance(stored, dict):  # pragma: no cover - defensive, malformed settings row
            return
        interrupted: list[str] = []
        dropped: list[str] = []
        for job, raw in stored.items():
            if job not in KNOWN_JOBS:
                dropped.append(job)
                continue
            if not isinstance(raw, dict):  # pragma: no cover - defensive
                continue
            state = JobState.from_dict({**raw, "job": job})
            if state.state == JOB_STATE_RUNNING:
                state = replace(
                    state,
                    state=JOB_STATE_INTERRUPTED,
                    message=INTERRUPTED_MESSAGE,
                    finished_at=int(self._clock()),
                    progress=None,
                )
                interrupted.append(job)
            self._jobs[job] = state
        if dropped:
            LOGGER.debug(
                "Ignoring stored state for job(s) this integration does not run: %s", dropped
            )
        for job in interrupted:
            LOGGER.warning("Listening Genome job %r was still running when it last stopped", job)
        if interrupted or dropped:
            await self._persist()

    async def start(self, job: str, message: str = "") -> dict[str, Any]:
        """Mark ``job`` running now, clearing the previous run's outcome (persisted)."""
        self._jobs[job] = JobState(
            job=job, state=JOB_STATE_RUNNING, message=message, started_at=int(self._clock())
        )
        await self._persist()
        return self._jobs[job].to_dict()

    def update(
        self, job: str, *, message: str | None = None, progress: int | None = None
    ) -> dict[str, Any]:
        """
        Amend a running job's message and/or progress. MEMORY ONLY - never writes the database.

        Safe to call as often as a loop likes; see the module docstring for why this is not
        persisted. A restart loses only the progress of a run that is then ``interrupted``.
        """
        current = self._jobs.setdefault(job, JobState(job=job))
        self._jobs[job] = replace(
            current,
            message=current.message if message is None else message,
            progress=current.progress if progress is None else max(0, min(100, int(progress))),
        )
        return self._jobs[job].to_dict()

    async def finish(self, job: str, message: str) -> dict[str, Any]:
        """Record ``job`` as succeeded, with the outcome a person needs to read (persisted)."""
        return await self._settle(job, JOB_STATE_OK, message)

    async def fail(self, job: str, message: str) -> dict[str, Any]:
        """Record ``job`` as failed, with the actual reason (persisted)."""
        return await self._settle(job, JOB_STATE_ERROR, message)

    async def interrupt_running(self) -> list[str]:
        """
        Mark every running job ``interrupted`` (persisted); return their ids.

        Called on unload, after this process's own tasks are cancelled and before the store
        closes, so a reload records the truth instead of leaving it for the next load to infer.
        """
        running = [job for job, state in self._jobs.items() if state.state == JOB_STATE_RUNNING]
        for job in running:
            self._jobs[job] = replace(
                self._jobs[job],
                state=JOB_STATE_INTERRUPTED,
                message=INTERRUPTED_MESSAGE,
                finished_at=int(self._clock()),
                progress=None,
            )
        if running:
            await self._persist()
        return running

    async def _settle(self, job: str, state: str, message: str) -> dict[str, Any]:
        """Apply a terminal state to ``job`` and persist it."""
        current = self._jobs.setdefault(job, JobState(job=job))
        self._jobs[job] = replace(
            current,
            state=state,
            message=message,
            finished_at=int(self._clock()),
            progress=100 if state == JOB_STATE_OK else None,
        )
        await self._persist()
        return self._jobs[job].to_dict()

    async def _persist(self) -> None:
        """Write the whole job map; failures are logged, never raised into the job itself."""
        try:
            await self._store.set_jobs(self.get_all())
        except Exception:  # pragma: no cover - defensive, a broken store must not fail the job
            LOGGER.warning("Could not persist Listening Genome job state", exc_info=True)


__all__ = [
    "ALL_JOBS",
    "INTERRUPTED_MESSAGE",
    "JOB_ENRICHMENT",
    "JOB_REBUILD",
    "JOB_STATE_ERROR",
    "JOB_STATE_IDLE",
    "JOB_STATE_INTERRUPTED",
    "JOB_STATE_OK",
    "JOB_STATE_RUNNING",
    "JobState",
    "JobTracker",
]
