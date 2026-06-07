"""Application entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from voiceconv.app._app_state import AppState
from voiceconv.app.views.main_window import MainWindow
from voiceconv.audio._codec import FfmpegEncoder, FfmpegLoader
from voiceconv.inference.engine import EngineError
from voiceconv.inference.worker_adapter import WorkerAdapter
from voiceconv.platform_support._app_paths import get_app_data_dir
from voiceconv.services.converter import Converter
from voiceconv.storage.logging_setup import setup_logging
from voiceconv.storage.profile import JsonFileProfileRepository
from voiceconv.storage.settings import SettingsStore


def _show_fatal(message: str) -> None:
    from PySide6.QtWidgets import QMessageBox
    box = QMessageBox()
    box.setWindowTitle("VoiceBuilder — Fatal Error")
    box.setIcon(QMessageBox.Icon.Critical)
    box.setText(message)
    box.exec()


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("VoiceBuilder")

    data_dir = get_app_data_dir()
    settings_store = SettingsStore(data_dir / "settings.json")
    settings = settings_store.load()
    setup_logging(data_dir / "logs")

    engine = WorkerAdapter("mock")
    try:
        engine.warmup()
    except EngineError as exc:
        _show_fatal(
            f"The voice engine failed to start.\n\n{exc}\n\nCode: {exc.code}"
        )
        sys.exit(1)

    converter = Converter(
        engine,
        FfmpegLoader(target_sample_rate=22050),
        FfmpegEncoder(),
    )
    profile_repo = JsonFileProfileRepository(data_dir / "profiles")

    state = AppState(
        converter=converter,
        profile_repo=profile_repo,
        settings_store=settings_store,
        settings=settings,
        engine=engine,
    )

    window = MainWindow(state)
    window.show()

    rc = app.exec()
    engine.release()
    sys.exit(rc)
