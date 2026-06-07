"""JobRepository ABC and JsonFileJobRepository implementation."""

from __future__ import annotations

import base64
import json
import time
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from voiceconv.inference.engine import ConvertParams, ProfileArtifacts
from voiceconv.services.job import ConversionRequest, Job, JobStatus


class JobRepository(ABC):
    @abstractmethod
    def save(self, job: Job) -> None: ...

    @abstractmethod
    def load_all(self) -> list[Job]: ...

    @abstractmethod
    def delete(self, job_id: str) -> None: ...


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _job_to_dict(job: Job) -> dict[str, Any]:
    req = job.request
    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "attempt": job.attempt,
        "progress": job.progress,
        "error": job.error,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "request": {
            "source_path": req.source_path,
            "output_path": req.output_path,
            "profile": {
                "engine_id": req.profile.engine_id,
                "engine_version": req.profile.engine_version,
                "data_b64": base64.b64encode(req.profile.data).decode(),
                "metadata": req.profile.metadata,
            },
            "params": {
                "target_sample_rate": req.params.target_sample_rate,
                "device": req.params.device,
                "extra": req.params.extra,
            },
        },
    }


def _dict_to_job(d: dict[str, Any]) -> Job:
    r = d["request"]
    profile = ProfileArtifacts(
        engine_id=r["profile"]["engine_id"],
        engine_version=r["profile"]["engine_version"],
        data=base64.b64decode(r["profile"]["data_b64"]),
        metadata=r["profile"].get("metadata", {}),
    )
    params = ConvertParams(
        target_sample_rate=r["params"]["target_sample_rate"],
        device=r["params"].get("device", "auto"),
        extra=r["params"].get("extra", {}),
    )
    request = ConversionRequest(
        source_path=r["source_path"],
        profile=profile,
        params=params,
        output_path=r["output_path"],
    )
    raw_status = d["status"]
    # Jobs that were RUNNING at crash time re-enter as QUEUED.
    status = (
        JobStatus.QUEUED
        if raw_status == JobStatus.RUNNING.value
        else JobStatus(raw_status)
    )
    return Job(
        job_id=d["job_id"],
        request=request,
        status=status,
        attempt=d.get("attempt", 0),
        progress=0.0 if status == JobStatus.QUEUED else d.get("progress", 0.0),
        error=d.get("error"),
        created_at=d.get("created_at", time.time()),
        started_at=d.get("started_at"),
        finished_at=None if status == JobStatus.QUEUED else d.get("finished_at"),
    )


# ---------------------------------------------------------------------------
# JSON file implementation
# ---------------------------------------------------------------------------


class JsonFileJobRepository(JobRepository):
    """Persists each job as a separate JSON file in a directory.

    Writes are atomic: data is written to a temp file, then renamed into
    place so a crash mid-write never leaves a corrupt record.
    """

    def __init__(self, directory: Path) -> None:
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, job_id: str) -> Path:
        return self._dir / f"{job_id}.json"

    def save(self, job: Job) -> None:
        tmp = self._dir / f".{uuid.uuid4().hex}.tmp"
        tmp.write_bytes(json.dumps(_job_to_dict(job), indent=2).encode())
        tmp.replace(self._path(job.job_id))

    def load_all(self) -> list[Job]:
        jobs: list[Job] = []
        for p in sorted(self._dir.glob("*.json")):
            try:
                jobs.append(_dict_to_job(json.loads(p.read_text())))
            except Exception:
                pass  # corrupt file; skip silently
        return jobs

    def delete(self, job_id: str) -> None:
        try:
            self._path(job_id).unlink()
        except FileNotFoundError:
            pass
