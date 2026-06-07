"""View-model for the Convert flow."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from voiceconv.app._app_state import AppState
from voiceconv.app._workers import ConvertWorker
from voiceconv.inference.engine import ConvertParams, ProfileArtifacts

log = logging.getLogger(__name__)

_DEFAULT_SR = 22050


class ConvertViewModel(QObject):
    source_path_changed = Signal(str)
    output_path_changed = Signal(str)
    profile_changed = Signal(object)
    progress_changed = Signal(float)
    is_running_changed = Signal(bool)
    conversion_done = Signal(str)  # output_path
    error = Signal(str)

    def __init__(self, state: AppState, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._source_path = ""
        self._output_path = ""
        self._profile_artifacts: ProfileArtifacts | None = None
        self._progress = 0.0
        self._is_running = False
        self._thread: QThread | None = None
        self._worker: ConvertWorker | None = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def source_path(self) -> str:
        return self._source_path

    def set_source_path(self, path: str) -> None:
        self._source_path = path
        self.source_path_changed.emit(path)
        self._auto_suggest_output()

    @property
    def output_path(self) -> str:
        return self._output_path

    def set_output_path(self, path: str) -> None:
        self._output_path = path
        self.output_path_changed.emit(path)

    @property
    def profile_artifacts(self) -> ProfileArtifacts | None:
        return self._profile_artifacts

    def set_profile_artifacts(self, artifacts: ProfileArtifacts | None) -> None:
        self._profile_artifacts = artifacts
        self.profile_changed.emit(artifacts)

    @property
    def progress(self) -> float:
        return self._progress

    @property
    def is_running(self) -> bool:
        return self._is_running

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def start_convert(self) -> None:
        if not self._source_path.strip():
            self.error.emit("Please select a source audio file.")
            return
        if self._profile_artifacts is None:
            self.error.emit("Please select a voice profile.")
            return
        if not self._output_path.strip():
            self.error.emit("Please set an output path.")
            return

        params = ConvertParams(target_sample_rate=_DEFAULT_SR)
        worker = ConvertWorker(
            self._state.converter,
            self._source_path,
            self._profile_artifacts,
            params,
            self._output_path,
        )
        thread = QThread()
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_finished)
        worker.error.connect(self._on_error)
        worker.cancelled.connect(self._on_cancelled)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        worker.cancelled.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self._thread = thread
        self._worker = worker
        self._set_running(True)
        self._set_progress(0.0)
        thread.start()

    def cancel(self) -> None:
        if self._worker:
            self._worker.request_cancel()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _auto_suggest_output(self) -> None:
        if not self._source_path:
            return
        src = Path(self._source_path)
        out_dir = Path(self._state.settings.output_dir) if self._state.settings.output_dir else src.parent
        fmt = self._state.settings.output_format or "wav"
        suggested = str(out_dir / f"{src.stem}_converted.{fmt}")
        self.set_output_path(suggested)

    def _on_progress(self, value: float) -> None:
        self._set_progress(value)

    def _on_finished(self, output_path: str) -> None:
        self._set_progress(1.0)
        self._set_running(False)
        log.info("Conversion complete: %s", output_path)
        self.conversion_done.emit(output_path)

    def _on_error(self, msg: str) -> None:
        self._set_running(False)
        self.error.emit(msg)

    def _on_cancelled(self) -> None:
        self._set_running(False)
        self._set_progress(0.0)

    def _set_running(self, value: bool) -> None:
        if self._is_running != value:
            self._is_running = value
            self.is_running_changed.emit(value)

    def _set_progress(self, value: float) -> None:
        self._progress = value
        self.progress_changed.emit(value)
