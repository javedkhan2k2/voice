"""QueueRunner: sequential job processor backed by a VoiceConversionEngine."""

from __future__ import annotations

import logging
import threading
import time
import wave
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from voiceconv.inference.engine import (
    CancelledError,
    CancelToken,
    VoiceConversionEngine,
)
from voiceconv.services._pcm_loader import PcmLoader
from voiceconv.services.job import ConversionRequest, Job, JobStatus
from voiceconv.services.queue import JobQueue

log = logging.getLogger(__name__)


def _write_wav(path: str, pcm: np.ndarray, sample_rate: int) -> None:
    """Write float32 mono PCM as a 16-bit PCM WAV file."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(pcm, -1.0, 1.0)
    int16 = (clipped * 32767.0).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(int16.tobytes())


class QueueRunner:
    """Runs conversion jobs sequentially from a ``JobQueue``.

    Parameters
    ----------
    engine:
        Injected ``VoiceConversionEngine`` (typically ``WorkerAdapter``).
        Must be warmed up before ``start()`` is called.
    queue:
        The job queue to drain.  Call ``queue.restore()`` before ``start()``
        if you want to resume persisted jobs after a restart.
    pcm_loader:
        Injected audio loader.  ``StdlibWavLoader`` for M1; replaced by an
        ffmpeg loader in M2 without touching this class.
    on_progress:
        Called with ``(job_id, fraction)`` on every progress tick (0.0–1.0).
    on_status:
        Called with ``(job_id, new_status)`` on every state transition.
        Fired from the runner background thread; keep callbacks fast.
    """

    def __init__(
        self,
        engine: VoiceConversionEngine,
        queue: JobQueue,
        pcm_loader: PcmLoader,
        *,
        on_progress: Optional[Callable[[str, float], None]] = None,
        on_status: Optional[Callable[[str, JobStatus], None]] = None,
    ) -> None:
        self._engine = engine
        self._queue = queue
        self._pcm_loader = pcm_loader
        self._on_progress = on_progress
        self._on_status = on_status

        self._condition = threading.Condition(threading.Lock())
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Guarded by _token_lock; written by background thread, read by cancel().
        self._token_lock = threading.Lock()
        self._current_token: Optional[CancelToken] = None
        self._current_job_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Launch the background runner thread.  Idempotent if already running."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop, name="queue-runner", daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Signal the runner to stop and wait for the current job to finish."""
        self._stop_event.set()
        with self._condition:
            self._condition.notify_all()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    # ------------------------------------------------------------------
    # Public job API (thread-safe; callable from any thread)
    # ------------------------------------------------------------------

    def submit(self, request: ConversionRequest) -> str:
        """Create a new job from *request*, enqueue it, and return the job_id."""
        job = Job.create(request)
        self._queue.add(job)
        with self._condition:
            self._condition.notify()
        return job.job_id

    def cancel(self, job_id: str) -> None:
        """Cancel a queued or in-flight job.

        If the job is QUEUED, it transitions to CANCELLED immediately.
        If the job is RUNNING, the cancel token is signalled and the job
        transitions to CANCELLED once the engine acknowledges.
        """
        if self._queue.cancel_if_queued(job_id):
            self._emit_status(job_id, JobStatus.CANCELLED)
            return
        with self._token_lock:
            if self._current_job_id == job_id and self._current_token is not None:
                self._current_token.cancel()

    def retry(self, job_id: str) -> None:
        """Re-enqueue a FAILED or CANCELLED job (same job_id, attempt++)."""
        job = self._queue.get(job_id)
        if job is None:
            raise ValueError(f"unknown job_id: {job_id!r}")
        if job.status not in (JobStatus.FAILED, JobStatus.CANCELLED):
            raise ValueError(
                f"retry requires FAILED or CANCELLED, got {job.status.value!r}"
            )
        job.attempt += 1
        job.transition(JobStatus.QUEUED)
        job.error = None
        job.progress = 0.0
        job.started_at = None
        job.finished_at = None
        self._queue.update(job)
        self._emit_status(job_id, JobStatus.QUEUED)
        with self._condition:
            self._condition.notify()

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._queue.get(job_id)

    def list_jobs(self) -> list[Job]:
        return self._queue.list_all()

    # ------------------------------------------------------------------
    # Background loop
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            with self._condition:
                while (
                    self._queue.next_queued() is None
                    and not self._stop_event.is_set()
                ):
                    self._condition.wait(timeout=0.5)
            if self._stop_event.is_set():
                break
            job = self._queue.next_queued()
            if job is None:
                continue
            self._run_job(job)

    def _run_job(self, job: Job) -> None:
        cancel_token = CancelToken()
        with self._token_lock:
            self._current_token = cancel_token
            self._current_job_id = job.job_id

        job.transition(JobStatus.RUNNING)
        job.started_at = time.time()
        self._queue.update(job)
        self._emit_status(job.job_id, JobStatus.RUNNING)

        try:
            pcm, sr = self._pcm_loader.load(job.request.source_path)
            out = self._engine.convert(
                pcm,
                sr,
                job.request.profile,
                job.request.params,
                progress=self._make_progress_cb(job),
                cancel_token=cancel_token,
            )
            _write_wav(
                job.request.output_path,
                out,
                job.request.params.target_sample_rate,
            )
            job.transition(JobStatus.DONE)
            job.finished_at = time.time()
            self._queue.update(job)
            self._emit_status(job.job_id, JobStatus.DONE)

        except CancelledError:
            job.transition(JobStatus.CANCELLED)
            job.finished_at = time.time()
            self._queue.update(job)
            self._emit_status(job.job_id, JobStatus.CANCELLED)

        except Exception as exc:
            log.error("job %s failed: %s", job.job_id, exc, exc_info=True)
            job.error = str(exc)
            job.transition(JobStatus.FAILED)
            job.finished_at = time.time()
            self._queue.update(job)
            self._emit_status(job.job_id, JobStatus.FAILED)

        finally:
            with self._token_lock:
                self._current_token = None
                self._current_job_id = None

    def _make_progress_cb(self, job: Job) -> Callable[[float], None]:
        def _cb(fraction: float) -> None:
            job.progress = max(0.0, min(1.0, fraction))
            if self._on_progress is not None:
                self._on_progress(job.job_id, job.progress)

        return _cb

    def _emit_status(self, job_id: str, status: JobStatus) -> None:
        if self._on_status is not None:
            try:
                self._on_status(job_id, status)
            except Exception:
                log.exception("on_status callback raised for job %s", job_id)
