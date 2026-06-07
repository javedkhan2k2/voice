"""View-model for the first-run acceptable-use acknowledgement."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from voiceconv.platform_support.device import detect_device
from voiceconv.storage.settings import AppSettings, SettingsStore


class FirstRunViewModel(QObject):
    acknowledged_changed = Signal(bool)

    def __init__(
        self,
        settings: AppSettings,
        settings_store: SettingsStore,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._settings_store = settings_store
        self._acknowledged = settings.first_run_acknowledged

    @property
    def device_info(self) -> dict:
        return detect_device()

    @property
    def is_acknowledged(self) -> bool:
        return self._acknowledged

    def set_acknowledged(self, value: bool) -> None:
        if self._acknowledged == value:
            return
        self._acknowledged = value
        self._settings.first_run_acknowledged = value
        self._settings_store.save(self._settings)
        self.acknowledged_changed.emit(value)

    @property
    def needs_first_run(self) -> bool:
        return not self._settings.first_run_acknowledged
