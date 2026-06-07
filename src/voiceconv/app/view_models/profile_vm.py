"""View-model for the Create Profile flow."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QThread, Signal

from voiceconv.app._app_state import AppState
from voiceconv.app._workers import PrepareProfileWorker
from voiceconv.storage.profile import ConsentRecord, VoiceProfile

log = logging.getLogger(__name__)


class ProfileViewModel(QObject):
    reference_path_changed = Signal(str)
    name_changed = Signal(str)
    consent_affirmed_changed = Signal(bool)
    is_busy_changed = Signal(bool)
    profile_saved = Signal(str)  # profile_id
    error = Signal(str)

    def __init__(self, state: AppState, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._reference_path = ""
        self._name = ""
        self._consent_affirmed = False
        self._is_busy = False
        self._thread: QThread | None = None
        self._worker: PrepareProfileWorker | None = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def reference_path(self) -> str:
        return self._reference_path

    def set_reference_path(self, path: str) -> None:
        self._reference_path = path
        self.reference_path_changed.emit(path)

    @property
    def name(self) -> str:
        return self._name

    def set_name(self, name: str) -> None:
        self._name = name
        self.name_changed.emit(name)

    @property
    def consent_affirmed(self) -> bool:
        return self._consent_affirmed

    def set_consent_affirmed(self, value: bool) -> None:
        self._consent_affirmed = value
        self.consent_affirmed_changed.emit(value)

    @property
    def is_busy(self) -> bool:
        return self._is_busy

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def create_profile(self) -> None:
        if not self._consent_affirmed:
            self.error.emit("You must affirm consent before creating a profile.")
            return
        if not self._reference_path.strip():
            self.error.emit("Please select a reference audio file.")
            return
        if not self._name.strip():
            self.error.emit("Please enter a profile name.")
            return

        self._set_busy(True)

        worker = PrepareProfileWorker(self._state.converter, self._reference_path)
        thread = QThread()
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.finished.connect(lambda arts: self._on_prepared(arts))
        worker.error.connect(self._on_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self._thread = thread
        self._worker = worker
        thread.start()

    def _on_prepared(self, artifacts: object) -> None:
        try:
            consent = ConsentRecord.create()
            profile = VoiceProfile.create(self._name.strip(), artifacts, consent)  # type: ignore[arg-type]
            self._state.profile_repo.save(profile)
            log.info("Profile created: %s (%s)", profile.name, profile.profile_id)
            self.profile_saved.emit(profile.profile_id)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self._set_busy(False)

    def _on_error(self, msg: str) -> None:
        self.error.emit(msg)
        self._set_busy(False)

    def _set_busy(self, value: bool) -> None:
        if self._is_busy != value:
            self._is_busy = value
            self.is_busy_changed.emit(value)
