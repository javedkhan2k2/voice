"""Thread-safe bridge from QueueRunner background thread to Qt signals."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from voiceconv.services.job import JobStatus


class QueueBridge(QObject):
    """Relays QueueRunner callbacks (fired from runner thread) to Qt signals.

    Signals are delivered to connected slots on the main thread via Qt's
    automatic queued-connection mechanism — no invokeMethod needed.
    """

    status_changed = Signal(str, object)    # (job_id, JobStatus)
    progress_changed = Signal(str, float)   # (job_id, fraction 0.0–1.0)
    runner_busy_changed = Signal(bool)      # True when a job enters RUNNING

    def on_status(self, job_id: str, status: JobStatus) -> None:
        """QueueRunner on_status callback — safe to call from any thread."""
        self.status_changed.emit(job_id, status)
        if status == JobStatus.RUNNING:
            self.runner_busy_changed.emit(True)
        elif status in (JobStatus.DONE, JobStatus.CANCELLED, JobStatus.FAILED):
            self.runner_busy_changed.emit(False)

    def on_progress(self, job_id: str, fraction: float) -> None:
        """QueueRunner on_progress callback — safe to call from any thread."""
        self.progress_changed.emit(job_id, fraction)
