"""Integration tests for QueueRunner.

All conversion tests use WorkerAdapter("mock") — real subprocess, no GPU.
A MockPcmLoader is injected instead of StdlibWavLoader to avoid file I/O.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

import numpy as np
import pytest

from voiceconv.inference.engine import ConvertParams, ProfileArtifacts
from voiceconv.inference.worker_adapter import WorkerAdapter
from voiceconv.services._repository import JsonFileJobRepository, _job_to_dict
from voiceconv.services.job import ConversionRequest, Job, JobStatus
from voiceconv.services.queue import JobQueue
from voiceconv.services.runner import QueueRunner


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class _MockPcmLoader:
    """Returns a short noise clip for any path; avoids file I/O in tests."""

    def __init__(
        self,
        pcm: Optional[np.ndarray] = None,
        sample_rate: int = 22050,
    ) -> None:
        if pcm is None:
            rng = np.random.default_rng(42)
            # ~0.1 s of noise — enough for a few mock-engine chunks
            pcm = rng.uniform(-0.1, 0.1, 2205).astype(np.float32)
        self._pcm = pcm
        self._sr = sample_rate

    def load(self, path: str) -> tuple[np.ndarray, int]:
        return self._pcm.copy(), self._sr


class _FailOncePcmLoader:
    """Raises IOError on the first call, succeeds on subsequent calls."""

    def __init__(self) -> None:
        self._calls = 0
        rng = np.random.default_rng(0)
        self._pcm = rng.uniform(-0.05, 0.05, 2205).astype(np.float32)

    def load(self, path: str) -> tuple[np.ndarray, int]:
        self._calls += 1
        if self._calls == 1:
            raise IOError("simulated load failure")
        return self._pcm.copy(), 22050


class _Collector:
    """Thread-safe collector for on_status / on_progress callbacks."""

    def __init__(self) -> None:
        self.statuses: list[tuple[str, JobStatus]] = []
        self.progresses: list[tuple[str, float]] = []
        self._events: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def on_status(self, job_id: str, status: JobStatus) -> None:
        with self._lock:
            self.statuses.append((job_id, status))
            if status in (JobStatus.DONE, JobStatus.CANCELLED, JobStatus.FAILED):
                ev = self._events.get(job_id)
                if ev:
                    ev.set()

    def on_progress(self, job_id: str, fraction: float) -> None:
        with self._lock:
            self.progresses.append((job_id, fraction))

    def wait_terminal(
        self, job_id: str, timeout: float = 15.0, after: int = 0
    ) -> JobStatus:
        """Block until *job_id* reaches a terminal status at index >= *after*.

        Pass ``after=len(collector.statuses)`` before calling retry/cancel to
        ensure you wait for the *next* terminal transition rather than a prior one.
        """
        _TERMINAL = (JobStatus.DONE, JobStatus.CANCELLED, JobStatus.FAILED)
        ev = threading.Event()
        with self._lock:
            for i, (jid, status) in enumerate(self.statuses):
                if i < after:
                    continue
                if jid == job_id and status in _TERMINAL:
                    return status
            self._events[job_id] = ev

        if not ev.wait(timeout=timeout):
            raise TimeoutError(f"job {job_id!r} did not reach terminal state in {timeout}s")

        with self._lock:
            for jid, status in reversed(self.statuses):
                if jid == job_id and status in _TERMINAL:
                    return status
        raise RuntimeError("wait_terminal: no status found after event set")

    def statuses_for(self, job_id: str) -> list[JobStatus]:
        with self._lock:
            return [s for jid, s in self.statuses if jid == job_id]

    def progresses_for(self, job_id: str) -> list[float]:
        with self._lock:
            return [f for jid, f in self.progresses if jid == job_id]


def _request(source: str = "src.wav", output_dir=None, *, tmp_path) -> ConversionRequest:
    out = str(tmp_path / "output" / f"{source}.wav")
    return ConversionRequest(
        source_path=source,
        profile=ProfileArtifacts("mock", "0.1", b"emb", {}),
        params=ConvertParams(target_sample_rate=22050),
        output_path=out,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine():
    e = WorkerAdapter("mock")
    e.warmup("cpu")
    yield e
    e.terminate()


@pytest.fixture
def collector():
    return _Collector()


def _make_runner(engine, tmp_path, collector, pcm_loader=None):
    if pcm_loader is None:
        pcm_loader = _MockPcmLoader()
    repo = JsonFileJobRepository(tmp_path / "jobs")
    queue = JobQueue(repo)
    runner = QueueRunner(
        engine,
        queue,
        pcm_loader,
        on_status=collector.on_status,
        on_progress=collector.on_progress,
    )
    runner.start()
    return runner, queue, repo


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_single_job_runs_to_done(engine, collector, tmp_path):
    runner, _, _ = _make_runner(engine, tmp_path, collector)
    try:
        req = _request(tmp_path=tmp_path)
        jid = runner.submit(req)
        status = collector.wait_terminal(jid)
        assert status == JobStatus.DONE
        assert runner.get_job(jid).status == JobStatus.DONE
    finally:
        runner.stop()


def test_output_file_written(engine, collector, tmp_path):
    import os

    runner, _, _ = _make_runner(engine, tmp_path, collector)
    try:
        req = _request(tmp_path=tmp_path)
        jid = runner.submit(req)
        collector.wait_terminal(jid)
        assert os.path.exists(req.output_path)
    finally:
        runner.stop()


def test_two_jobs_run_sequentially(engine, collector, tmp_path):
    runner, _, _ = _make_runner(engine, tmp_path, collector)
    try:
        jid1 = runner.submit(_request("a.wav", tmp_path=tmp_path))
        jid2 = runner.submit(_request("b.wav", tmp_path=tmp_path))
        collector.wait_terminal(jid1)
        collector.wait_terminal(jid2)
        # Both done; second job should not have RUNNING before first was DONE.
        s1 = collector.statuses_for(jid1)
        s2 = collector.statuses_for(jid2)
        assert JobStatus.DONE in s1
        assert JobStatus.DONE in s2
    finally:
        runner.stop()


def test_cancel_queued_job(engine, collector, tmp_path):
    runner, _, _ = _make_runner(engine, tmp_path, collector)
    try:
        jid1 = runner.submit(_request("a.wav", tmp_path=tmp_path))
        jid2 = runner.submit(_request("b.wav", tmp_path=tmp_path))
        # Cancel job2 while job1 is (potentially) running.
        runner.cancel(jid2)
        collector.wait_terminal(jid1)
        status2 = collector.wait_terminal(jid2)
        assert status2 == JobStatus.CANCELLED
        assert runner.get_job(jid2).status == JobStatus.CANCELLED
    finally:
        runner.stop()


def test_cancel_running_job(engine, collector, tmp_path):
    # 20 s clip → ~220 chunks × 2 ms/chunk = ~440 ms; plenty of time to cancel.
    rng = np.random.default_rng(1)
    long_pcm = rng.uniform(-0.1, 0.1, 22050 * 20).astype(np.float32)
    loader = _MockPcmLoader(pcm=long_pcm)

    runner, _, _ = _make_runner(engine, tmp_path, collector, pcm_loader=loader)
    try:
        jid = runner.submit(_request(tmp_path=tmp_path))

        # Wait until RUNNING before cancelling.
        deadline = time.time() + 10.0
        while JobStatus.RUNNING not in collector.statuses_for(jid):
            if time.time() > deadline:
                raise TimeoutError("job never reached RUNNING")
            time.sleep(0.01)

        runner.cancel(jid)
        status = collector.wait_terminal(jid)
        assert status == JobStatus.CANCELLED
    finally:
        runner.stop()


def test_cancel_does_not_abort_next_job(engine, collector, tmp_path):
    rng = np.random.default_rng(2)
    long_pcm = rng.uniform(-0.1, 0.1, 22050 * 20).astype(np.float32)
    loader = _MockPcmLoader(pcm=long_pcm)

    runner, _, _ = _make_runner(engine, tmp_path, collector, pcm_loader=loader)
    try:
        jid1 = runner.submit(_request("a.wav", tmp_path=tmp_path))

        deadline = time.time() + 10.0
        while JobStatus.RUNNING not in collector.statuses_for(jid1):
            if time.time() > deadline:
                raise TimeoutError("job1 never reached RUNNING")
            time.sleep(0.01)

        runner.cancel(jid1)
        collector.wait_terminal(jid1)

        jid2 = runner.submit(_request("b.wav", tmp_path=tmp_path))
        status2 = collector.wait_terminal(jid2)
        assert status2 == JobStatus.DONE
    finally:
        runner.stop()


def test_retry_failed_job(engine, collector, tmp_path):
    loader = _FailOncePcmLoader()
    runner, _, _ = _make_runner(engine, tmp_path, collector, pcm_loader=loader)
    try:
        jid = runner.submit(_request(tmp_path=tmp_path))
        status = collector.wait_terminal(jid)
        assert status == JobStatus.FAILED
        assert runner.get_job(jid).attempt == 0

        after = len(collector.statuses)
        runner.retry(jid)
        status = collector.wait_terminal(jid, after=after)
        assert status == JobStatus.DONE
        assert runner.get_job(jid).attempt == 1
    finally:
        runner.stop()


def test_retry_cancelled_job(engine, collector, tmp_path):
    runner, _, _ = _make_runner(engine, tmp_path, collector)
    try:
        jid1 = runner.submit(_request("a.wav", tmp_path=tmp_path))
        jid2 = runner.submit(_request("b.wav", tmp_path=tmp_path))
        runner.cancel(jid2)
        collector.wait_terminal(jid1)
        collector.wait_terminal(jid2)

        after = len(collector.statuses)
        runner.retry(jid2)
        status = collector.wait_terminal(jid2, after=after)
        assert status == JobStatus.DONE
        assert runner.get_job(jid2).attempt == 1
    finally:
        runner.stop()


def test_failed_job_does_not_abort_queue(engine, collector, tmp_path):
    loader = _FailOncePcmLoader()
    runner, _, _ = _make_runner(engine, tmp_path, collector, pcm_loader=loader)
    try:
        jid1 = runner.submit(_request("a.wav", tmp_path=tmp_path))
        jid2 = runner.submit(_request("b.wav", tmp_path=tmp_path))
        s1 = collector.wait_terminal(jid1)
        s2 = collector.wait_terminal(jid2)
        assert s1 == JobStatus.FAILED
        assert s2 == JobStatus.DONE
    finally:
        runner.stop()


def test_progress_callbacks_increase(engine, collector, tmp_path):
    runner, _, _ = _make_runner(engine, tmp_path, collector)
    try:
        jid = runner.submit(_request(tmp_path=tmp_path))
        collector.wait_terminal(jid)
        fractions = collector.progresses_for(jid)
        assert len(fractions) > 0
        assert fractions[-1] == pytest.approx(1.0)
        # Each reported value must be >= the previous.
        for a, b in zip(fractions, fractions[1:]):
            assert b >= a
    finally:
        runner.stop()


def test_status_callbacks_fired(engine, collector, tmp_path):
    runner, _, _ = _make_runner(engine, tmp_path, collector)
    try:
        jid = runner.submit(_request(tmp_path=tmp_path))
        collector.wait_terminal(jid)
        statuses = collector.statuses_for(jid)
        assert JobStatus.RUNNING in statuses
        assert JobStatus.DONE in statuses
    finally:
        runner.stop()


def test_persist_restore_queued_job(engine, collector, tmp_path):
    """A QUEUED job persisted before the runner starts is picked up on restore."""
    repo = JsonFileJobRepository(tmp_path / "jobs")
    req = _request(tmp_path=tmp_path)
    job = Job.create(req)
    repo.save(job)

    # New runner restores from repo and processes the pre-saved job.
    queue = JobQueue(repo)
    queue.restore()
    runner = QueueRunner(
        engine,
        queue,
        _MockPcmLoader(),
        on_status=collector.on_status,
        on_progress=collector.on_progress,
    )
    runner.start()
    try:
        status = collector.wait_terminal(job.job_id)
        assert status == JobStatus.DONE
    finally:
        runner.stop()


def test_running_job_crash_recovery(engine, collector, tmp_path):
    """A job persisted as RUNNING (simulated crash) is retried by a new runner."""
    repo = JsonFileJobRepository(tmp_path / "jobs")
    req = _request(tmp_path=tmp_path)
    job = Job.create(req)
    job.transition(JobStatus.RUNNING)
    repo.save(job)  # persisted mid-run — simulates crash

    queue = JobQueue(repo)
    queue.restore()  # RUNNING → QUEUED
    assert queue.next_queued() is not None

    runner = QueueRunner(
        engine,
        queue,
        _MockPcmLoader(),
        on_status=collector.on_status,
    )
    runner.start()
    try:
        status = collector.wait_terminal(job.job_id)
        assert status == JobStatus.DONE
    finally:
        runner.stop()


def test_stop_waits_for_current_job(engine, collector, tmp_path):
    """stop() lets the in-flight job finish before returning."""
    rng = np.random.default_rng(3)
    long_pcm = rng.uniform(-0.1, 0.1, 22050).astype(np.float32)
    loader = _MockPcmLoader(pcm=long_pcm)

    runner, _, _ = _make_runner(engine, tmp_path, collector, pcm_loader=loader)
    jid = runner.submit(_request(tmp_path=tmp_path))

    deadline = time.time() + 10.0
    while JobStatus.RUNNING not in collector.statuses_for(jid):
        if time.time() > deadline:
            raise TimeoutError("job never reached RUNNING")
        time.sleep(0.01)

    runner.stop(timeout=15.0)
    # After stop(), the job must be in a terminal state.
    final = runner.get_job(jid).status
    assert final in (JobStatus.DONE, JobStatus.CANCELLED, JobStatus.FAILED)


def test_retry_requires_failed_or_cancelled(engine, collector, tmp_path):
    runner, _, _ = _make_runner(engine, tmp_path, collector)
    try:
        jid = runner.submit(_request(tmp_path=tmp_path))
        collector.wait_terminal(jid)
        with pytest.raises(ValueError, match="retry requires"):
            runner.retry(jid)
    finally:
        runner.stop()
