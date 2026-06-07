"""View-model for the A/B Preview & Export flow."""

from __future__ import annotations

import logging
import os
import shutil

from PySide6.QtCore import QObject, Signal

log = logging.getLogger(__name__)


class PreviewViewModel(QObject):
    paths_changed = Signal()
    error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._source_path = ""
        self._output_path = ""

    def set_paths(self, source_path: str, output_path: str) -> None:
        self._source_path = source_path
        self._output_path = output_path
        self.paths_changed.emit()

    @property
    def source_path(self) -> str:
        return self._source_path

    @property
    def output_path(self) -> str:
        return self._output_path

    @property
    def has_output(self) -> bool:
        return bool(self._output_path)

    def play_source(self) -> None:
        self._open(self._source_path)

    def play_output(self) -> None:
        self._open(self._output_path)

    def export_to(self, destination: str) -> None:
        if not self._output_path:
            self.error.emit("No output file to export.")
            return
        try:
            shutil.copy2(self._output_path, destination)
            log.info("Exported %s → %s", self._output_path, destination)
        except Exception as exc:
            self.error.emit(str(exc))

    def _open(self, path: str) -> None:
        if not path:
            self.error.emit("No file to play.")
            return
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except Exception as exc:
            self.error.emit(str(exc))
