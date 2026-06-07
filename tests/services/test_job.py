"""Unit tests for the Job state machine."""

import pytest

from voiceconv.inference.engine import ConvertParams, ProfileArtifacts
from voiceconv.services.job import ConversionRequest, Job, JobStatus


def _request() -> ConversionRequest:
    return ConversionRequest(
        source_path="source.wav",
        profile=ProfileArtifacts("mock", "0.1", b"embedding", {}),
        params=ConvertParams(target_sample_rate=22050),
        output_path="output.wav",
    )


def test_create_job_defaults():
    job = Job.create(_request())
    assert job.status == JobStatus.QUEUED
    assert job.attempt == 0
    assert job.progress == 0.0
    assert job.error is None
    assert job.started_at is None
    assert job.finished_at is None
    assert len(job.job_id) == 32  # uuid4 hex


def test_create_jobs_have_unique_ids():
    j1 = Job.create(_request())
    j2 = Job.create(_request())
    assert j1.job_id != j2.job_id


def test_transition_queued_to_running():
    job = Job.create(_request())
    job.transition(JobStatus.RUNNING)
    assert job.status == JobStatus.RUNNING


def test_transition_queued_to_cancelled():
    job = Job.create(_request())
    job.transition(JobStatus.CANCELLED)
    assert job.status == JobStatus.CANCELLED


def test_transition_running_to_done():
    job = Job.create(_request())
    job.transition(JobStatus.RUNNING)
    job.transition(JobStatus.DONE)
    assert job.status == JobStatus.DONE


def test_transition_running_to_failed():
    job = Job.create(_request())
    job.transition(JobStatus.RUNNING)
    job.transition(JobStatus.FAILED)
    assert job.status == JobStatus.FAILED


def test_transition_running_to_cancelled():
    job = Job.create(_request())
    job.transition(JobStatus.RUNNING)
    job.transition(JobStatus.CANCELLED)
    assert job.status == JobStatus.CANCELLED


def test_retry_from_failed():
    job = Job.create(_request())
    job.transition(JobStatus.RUNNING)
    job.transition(JobStatus.FAILED)
    job.attempt += 1
    job.transition(JobStatus.QUEUED)
    assert job.status == JobStatus.QUEUED
    assert job.attempt == 1


def test_retry_from_cancelled():
    job = Job.create(_request())
    job.transition(JobStatus.CANCELLED)
    job.attempt += 1
    job.transition(JobStatus.QUEUED)
    assert job.status == JobStatus.QUEUED
    assert job.attempt == 1


def test_invalid_transition_queued_to_done_raises():
    job = Job.create(_request())
    with pytest.raises(ValueError, match="invalid transition"):
        job.transition(JobStatus.DONE)


def test_invalid_transition_queued_to_failed_raises():
    job = Job.create(_request())
    with pytest.raises(ValueError, match="invalid transition"):
        job.transition(JobStatus.FAILED)


def test_done_is_terminal():
    job = Job.create(_request())
    job.transition(JobStatus.RUNNING)
    job.transition(JobStatus.DONE)
    with pytest.raises(ValueError):
        job.transition(JobStatus.QUEUED)
