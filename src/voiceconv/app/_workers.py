"""Background QObject workers — run heavy work off the UI thread."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from voiceconv.inference.engine import CancelledError, CancelToken, ConvertParams, ProfileArtifacts
from voiceconv.services.converter import Converter


class PrepareProfileWorker(QObject):
    """Runs Converter.prepare_profile() on a background QThread."""

    finished = Signal(object)  # ProfileArtifacts
    error = Signal(str)

    def __init__(self, converter: Converter, reference_path: str) -> None:
        super().__init__()
        self._converter = converter
        self._reference_path = reference_path

    def run(self) -> None:
        try:
            artifacts = self._converter.prepare_profile(self._reference_path)
            self.finished.emit(artifacts)
        except Exception as exc:
            self.error.emit(str(exc))


class ConvertWorker(QObject):
    """Runs Converter.convert_file() on a background QThread."""

    progress = Signal(float)
    finished = Signal(str)   # output_path
    error = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        converter: Converter,
        source_path: str,
        profile_artifacts: ProfileArtifacts,
        params: ConvertParams,
        output_path: str,
    ) -> None:
        super().__init__()
        self._converter = converter
        self._source_path = source_path
        self._profile_artifacts = profile_artifacts
        self._params = params
        self._output_path = output_path
        self._cancel_token = CancelToken()

    def request_cancel(self) -> None:
        self._cancel_token.cancel()

    def run(self) -> None:
        try:
            self._converter.convert_file(
                self._source_path,
                self._profile_artifacts,
                self._params,
                self._output_path,
                progress=self._on_progress,
                cancel_token=self._cancel_token,
            )
            self.finished.emit(self._output_path)
        except CancelledError:
            self.cancelled.emit()
        except Exception as exc:
            self.error.emit(str(exc))

    def _on_progress(self, value: float) -> None:
        self.progress.emit(value)
