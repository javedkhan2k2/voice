"""View-model for the Queue tab."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from voiceconv.app._app_state import AppState
from voiceconv.app._queue_bridge import QueueBridge
from voiceconv.inference.engine import ConvertParams
from voiceconv.services.job import ConversionRequest, Job, JobStatus
from voiceconv.storage.profile import VoiceProfile

log = logging.getLogger(__name__)

_DEFAULT_SR = 22050


class QueueViewModel(QObject):
    """Manages the job list and delegates actions to QueueRunner."""

    jobs_reset = Signal()                    # full list changed — view should rebuild
    job_status_changed = Signal(str, object) # (job_id, JobStatus)
    job_progress_changed = Signal(str, float) # (job_id, fraction)
    error = Signal(str)

    def __init__(
        self,
        state: AppState,
        bridge: QueueBridge,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._selected_profile_id: str | None = None
        self._hidden_job_ids: set[str] = set()  # cleared-done display filter
        self._profiles: list[VoiceProfile] = []

        bridge.status_changed.connect(self._on_status)
        bridge.progress_changed.connect(self._on_progress)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_jobs(self) -> list[Job]:
        """Return all non-hidden jobs (most recently submitted last)."""
        return [
            j for j in self._state.runner.list_jobs()
            if j.job_id not in self._hidden_job_ids
        ]

    def profiles(self) -> list[VoiceProfile]:
        return list(self._profiles)

    def selected_profile_id(self) -> str | None:
        return self._selected_profile_id

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def refresh_profiles(self) -> None:
        self._profiles = self._state.profile_repo.list_all()
        if self._selected_profile_id not in {p.profile_id for p in self._profiles}:
            self._selected_profile_id = self._profiles[0].profile_id if self._profiles else None

    def set_selected_profile_id(self, profile_id: str) -> None:
        self._selected_profile_id = profile_id

    def add_files(self, paths: list[str]) -> None:
        """Submit one job per path using the currently selected profile."""
        if not self._selected_profile_id:
            self.error.emit("Please select a voice profile before adding files.")
            return
        profile = self._state.profile_repo.load(self._selected_profile_id)
        if profile is None:
            self.error.emit("Selected profile could not be loaded.")
            return

        params = ConvertParams(target_sample_rate=_DEFAULT_SR)
        for path in paths:
            output_path = self._suggest_output(path)
            request = ConversionRequest(
                source_path=path,
                profile=profile.artifacts,
                params=params,
                output_path=output_path,
            )
            self._state.runner.submit(request)

        self.jobs_reset.emit()

    def cancel_job(self, job_id: str) -> None:
        self._state.runner.cancel(job_id)

    def retry_job(self, job_id: str) -> None:
        try:
            self._state.runner.retry(job_id)
        except ValueError as exc:
            self.error.emit(str(exc))

    def open_output_folder(self, job_id: str) -> None:
        job = self._state.runner.get_job(job_id)
        if job is None:
            return
        folder = str(Path(job.request.output_path).parent)
        try:
            subprocess.Popen(["explorer", folder])
        except Exception as exc:
            log.error("open_output_folder failed: %s", exc)
            self.error.emit(f"Could not open folder: {exc}")

    def clear_done(self) -> None:
        """Hide all DONE jobs from the display (display-only filter for M2)."""
        for job in self._state.runner.list_jobs():
            if job.status == JobStatus.DONE:
                self._hidden_job_ids.add(job.job_id)
        self.jobs_reset.emit()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _suggest_output(self, source_path: str) -> str:
        src = Path(source_path)
        out_dir = (
            Path(self._state.settings.output_dir)
            if self._state.settings.output_dir
            else src.parent
        )
        fmt = self._state.settings.output_format or "wav"
        return str(out_dir / f"{src.stem}_converted.{fmt}")

    def _on_status(self, job_id: str, status: object) -> None:
        self.job_status_changed.emit(job_id, status)

    def _on_progress(self, job_id: str, fraction: float) -> None:
        self.job_progress_changed.emit(job_id, fraction)
