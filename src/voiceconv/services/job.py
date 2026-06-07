"""Job state machine and request types for the queue engine."""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from voiceconv.inference.engine import ConvertParams, ProfileArtifacts


class JobStatus(enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    CANCELLED = "cancelled"
    FAILED = "failed"


_VALID_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.QUEUED:    frozenset({JobStatus.RUNNING, JobStatus.CANCELLED}),
    JobStatus.RUNNING:   frozenset({JobStatus.DONE, JobStatus.CANCELLED, JobStatus.FAILED}),
    JobStatus.DONE:      frozenset(),
    JobStatus.CANCELLED: frozenset({JobStatus.QUEUED}),
    JobStatus.FAILED:    frozenset({JobStatus.QUEUED}),
}


@dataclass(frozen=True)
class ConversionRequest:
    """Everything the runner needs to execute one conversion job.

    ``source_path`` and ``output_path`` are persisted to disk.
    PCM loading from ``source_path`` is delegated to the injected ``PcmLoader``.
    """

    source_path: str
    profile: ProfileArtifacts
    params: ConvertParams
    output_path: str


@dataclass
class Job:
    """Mutable runtime record for one conversion job.

    The ``JobQueue`` owns canonical instances; callers receive references.
    Mutate via ``transition()`` to enforce the state machine.
    """

    job_id: str
    request: ConversionRequest
    status: JobStatus = JobStatus.QUEUED
    attempt: int = 0
    progress: float = 0.0
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None

    @classmethod
    def create(cls, request: ConversionRequest) -> "Job":
        return cls(job_id=uuid.uuid4().hex, request=request)

    def transition(self, new_status: JobStatus) -> None:
        """Advance state, raising ValueError on illegal transitions."""
        allowed = _VALID_TRANSITIONS[self.status]
        if new_status not in allowed:
            raise ValueError(
                f"invalid transition: {self.status.value!r} → {new_status.value!r}"
            )
        self.status = new_status
