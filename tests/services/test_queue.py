"""Unit tests for JobQueue and JsonFileJobRepository."""

import threading

import pytest

from voiceconv.inference.engine import ConvertParams, ProfileArtifacts
from voiceconv.services._repository import (
    JsonFileJobRepository,
    _dict_to_job,
    _job_to_dict,
)
from voiceconv.services.job import ConversionRequest, Job, JobStatus
from voiceconv.services.queue import JobQueue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _request(source: str = "source.wav", output: str = "output.wav") -> ConversionRequest:
    return ConversionRequest(
        source_path=source,
        profile=ProfileArtifacts("mock", "0.1", b"embedding", {}),
        params=ConvertParams(target_sample_rate=22050),
        output_path=output,
    )


class _InMemoryRepo:
    """Minimal in-memory JobRepository (no disk I/O) for unit tests."""

    def __init__(self) -> None:
        self._store: dict[str, dict] = {}

    def save(self, job: Job) -> None:
        self._store[job.job_id] = _job_to_dict(job)

    def load_all(self) -> list[Job]:
        return [_dict_to_job(d) for d in self._store.values()]

    def delete(self, job_id: str) -> None:
        self._store.pop(job_id, None)


def _queue() -> JobQueue:
    return JobQueue(_InMemoryRepo())


# ---------------------------------------------------------------------------
# add / list / get
# ---------------------------------------------------------------------------


def test_add_and_list_all():
    q = _queue()
    job = Job.create(_request())
    q.add(job)
    all_jobs = q.list_all()
    assert len(all_jobs) == 1
    assert all_jobs[0].job_id == job.job_id


def test_list_all_returns_snapshot():
    q = _queue()
    q.add(Job.create(_request("a.wav")))
    snapshot = q.list_all()
    q.add(Job.create(_request("b.wav")))
    assert len(snapshot) == 1  # snapshot is frozen


def test_get_returns_job():
    q = _queue()
    job = Job.create(_request())
    q.add(job)
    assert q.get(job.job_id).job_id == job.job_id


def test_get_returns_none_for_unknown():
    q = _queue()
    assert q.get("nonexistent") is None


# ---------------------------------------------------------------------------
# next_queued
# ---------------------------------------------------------------------------


def test_next_queued_returns_first_queued():
    q = _queue()
    j1 = Job.create(_request("a.wav"))
    j2 = Job.create(_request("b.wav"))
    q.add(j1)
    q.add(j2)
    assert q.next_queued().job_id == j1.job_id


def test_next_queued_skips_non_queued():
    q = _queue()
    j1 = Job.create(_request("a.wav"))
    j2 = Job.create(_request("b.wav"))
    q.add(j1)
    q.add(j2)
    j1.transition(JobStatus.RUNNING)
    q.update(j1)
    assert q.next_queued().job_id == j2.job_id


def test_next_queued_returns_none_when_empty():
    q = _queue()
    assert q.next_queued() is None


def test_next_queued_returns_none_when_all_done():
    q = _queue()
    job = Job.create(_request())
    q.add(job)
    job.transition(JobStatus.RUNNING)
    job.transition(JobStatus.DONE)
    q.update(job)
    assert q.next_queued() is None


# ---------------------------------------------------------------------------
# cancel_if_queued
# ---------------------------------------------------------------------------


def test_cancel_if_queued_transitions_and_returns_true():
    q = _queue()
    job = Job.create(_request())
    q.add(job)
    assert q.cancel_if_queued(job.job_id) is True
    assert q.get(job.job_id).status == JobStatus.CANCELLED


def test_cancel_if_queued_returns_false_when_running():
    q = _queue()
    job = Job.create(_request())
    q.add(job)
    job.transition(JobStatus.RUNNING)
    q.update(job)
    assert q.cancel_if_queued(job.job_id) is False
    assert q.get(job.job_id).status == JobStatus.RUNNING


def test_cancel_if_queued_returns_false_for_unknown():
    q = _queue()
    assert q.cancel_if_queued("ghost") is False


# ---------------------------------------------------------------------------
# Persistence: JsonFileJobRepository
# ---------------------------------------------------------------------------


def test_json_repo_save_and_load(tmp_path):
    repo = JsonFileJobRepository(tmp_path)
    job = Job.create(_request())
    repo.save(job)
    loaded = repo.load_all()
    assert len(loaded) == 1
    assert loaded[0].job_id == job.job_id
    assert loaded[0].status == JobStatus.QUEUED


def test_json_repo_running_reloaded_as_queued(tmp_path):
    repo = JsonFileJobRepository(tmp_path)
    job = Job.create(_request())
    job.transition(JobStatus.RUNNING)
    repo.save(job)
    loaded = repo.load_all()[0]
    assert loaded.status == JobStatus.QUEUED
    assert loaded.progress == 0.0
    assert loaded.started_at is None


def test_json_repo_done_job_reloaded_as_done(tmp_path):
    repo = JsonFileJobRepository(tmp_path)
    job = Job.create(_request())
    job.transition(JobStatus.RUNNING)
    job.transition(JobStatus.DONE)
    repo.save(job)
    loaded = repo.load_all()[0]
    assert loaded.status == JobStatus.DONE


def test_queue_restore_reloads_jobs(tmp_path):
    repo = JsonFileJobRepository(tmp_path)
    q1 = JobQueue(repo)
    j1 = Job.create(_request("a.wav"))
    j2 = Job.create(_request("b.wav"))
    q1.add(j1)
    q1.add(j2)

    q2 = JobQueue(repo)
    q2.restore()
    ids = {j.job_id for j in q2.list_all()}
    assert j1.job_id in ids
    assert j2.job_id in ids


def test_queue_restore_running_becomes_queued(tmp_path):
    repo = JsonFileJobRepository(tmp_path)
    q1 = JobQueue(repo)
    job = Job.create(_request())
    q1.add(job)
    job.transition(JobStatus.RUNNING)
    q1.update(job)

    q2 = JobQueue(repo)
    q2.restore()
    reloaded = q2.list_all()[0]
    assert reloaded.status == JobStatus.QUEUED
    assert q2.next_queued() is not None
