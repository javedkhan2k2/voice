"""Thread-safe ordered job collection."""

from __future__ import annotations

import threading
from typing import Optional

from voiceconv.services._repository import JobRepository
from voiceconv.services.job import Job, JobStatus


class JobQueue:
    """Thread-safe ordered list of Job records backed by a JobRepository.

    The QueueRunner is the only writer during a run; the public API may be
    called from any thread (GUI, tests, CLI).
    """

    def __init__(self, repository: JobRepository) -> None:
        self._repo = repository
        self._jobs: list[Job] = []
        self._lock = threading.Lock()

    def restore(self) -> None:
        """Load persisted jobs from the repository.

        Call once on startup before ``start()``-ing the runner.
        Jobs that were RUNNING at crash time are reloaded as QUEUED.
        """
        with self._lock:
            self._jobs = self._repo.load_all()

    def add(self, job: Job) -> None:
        """Append a new job and persist it."""
        with self._lock:
            self._jobs.append(job)
            self._repo.save(job)

    def get(self, job_id: str) -> Optional[Job]:
        """Return the job with the given id, or None."""
        with self._lock:
            for j in self._jobs:
                if j.job_id == job_id:
                    return j
            return None

    def update(self, job: Job) -> None:
        """Persist the current state of *job*.

        The job must already be present in the queue (added via ``add()``).
        """
        with self._lock:
            self._repo.save(job)

    def next_queued(self) -> Optional[Job]:
        """Return the first QUEUED job without removing it, or None."""
        with self._lock:
            for j in self._jobs:
                if j.status == JobStatus.QUEUED:
                    return j
            return None

    def list_all(self) -> list[Job]:
        """Return a shallow-copy snapshot of all jobs (any status)."""
        with self._lock:
            return list(self._jobs)

    def cancel_if_queued(self, job_id: str) -> bool:
        """Transition a QUEUED job to CANCELLED and persist.

        Returns True if the transition happened, False if the job was not
        found or was not in QUEUED state.
        """
        with self._lock:
            for j in self._jobs:
                if j.job_id == job_id and j.status == JobStatus.QUEUED:
                    j.transition(JobStatus.CANCELLED)
                    self._repo.save(j)
                    return True
            return False
