"""View-model for the Settings tab."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from voiceconv.app._app_state import AppState
from voiceconv.services import diagnostics
from voiceconv.services.job import JobStatus
from voiceconv.services.offline_check import verify_offline

log = logging.getLogger(__name__)


class SettingsViewModel(QObject):
    """Reads and persists AppSettings; validates output_dir changes."""

    settings_changed = Signal()
    error = Signal(str)
    export_succeeded = Signal(str)  # absolute path of the written bundle
    offline_verified = Signal(bool, str)  # (ok, detail) from verify_offline()

    def __init__(self, state: AppState, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state = state

    # ------------------------------------------------------------------
    # Properties (live reads from shared AppSettings)
    # ------------------------------------------------------------------

    @property
    def device(self) -> str:
        return self._state.settings.device

    @property
    def active_engine(self) -> str:
        return self._state.settings.active_engine

    @property
    def output_format(self) -> str:
        return self._state.settings.output_format

    @property
    def output_dir(self) -> str:
        return self._state.settings.output_dir

    @property
    def loudness_normalize(self) -> bool:
        return self._state.settings.loudness_normalize

    @property
    def log_level(self) -> str:
        return self._state.settings.log_level

    # ------------------------------------------------------------------
    # Setters
    # ------------------------------------------------------------------

    def set_device(self, value: str) -> None:
        self._state.settings.device = value
        self._save()

    def set_active_engine(self, value: str) -> None:
        self._state.settings.active_engine = value
        self._save()

    def set_output_format(self, value: str) -> None:
        self._state.settings.output_format = value
        self._save()

    def set_output_dir(self, value: str) -> None:
        if self._has_running_job():
            self.error.emit(
                "Cannot change the output folder while a job is running."
            )
            return
        self._state.settings.output_dir = value
        self._save()

    def set_loudness_normalize(self, value: bool) -> None:
        self._state.settings.loudness_normalize = value
        self._save()

    def set_log_level(self, value: str) -> None:
        self._state.settings.log_level = value
        numeric = getattr(logging, value.upper(), logging.INFO)
        logging.getLogger().setLevel(numeric)
        self._save()

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def export_diagnostics(self, out_path: str) -> None:
        """Assemble a diagnostics bundle (logs + environment) at *out_path*.

        Bounded, fast work (logs are size-capped by rotation), so it runs
        synchronously.  Emits :attr:`export_succeeded` on success and
        :attr:`error` on failure.
        """
        if not out_path:
            return
        log_dir = self._state.log_dir or Path(self._state.settings.log_dir or ".")
        try:
            app_info = diagnostics.collect_app_info()
            app_info["settings"] = {
                "active_engine": self._state.settings.active_engine,
                "device": self._state.settings.device,
            }
            written = diagnostics.build_bundle(Path(out_path), log_dir, app_info)
        except Exception as exc:  # noqa: BLE001 — surface any failure to the user
            log.exception("diagnostics export failed")
            self.error.emit(f"Could not export diagnostics: {exc}")
            return
        log.info("diagnostics bundle written to %s", written)
        self.export_succeeded.emit(str(written))

    def verify_offline(self) -> None:
        """Run the offline self-check and emit :attr:`offline_verified`."""
        result = verify_offline()
        log.info("offline self-check: ok=%s (%s)", result.ok, result.detail)
        self.offline_verified.emit(result.ok, result.detail)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _save(self) -> None:
        self._state.settings_store.save(self._state.settings)
        self.settings_changed.emit()

    def _has_running_job(self) -> bool:
        if self._state.runner is None:
            return False
        return any(
            j.status == JobStatus.RUNNING
            for j in self._state.runner.list_jobs()
        )
