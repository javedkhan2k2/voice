"""Application entry point."""

from __future__ import annotations

import sys
import threading

from PySide6.QtWidgets import QApplication

from voiceconv.app._app_state import AppState
from voiceconv.app._queue_bridge import QueueBridge
from voiceconv.app.views.main_window import MainWindow
from voiceconv.audio._codec import FfmpegEncoder, FfmpegLoader
from voiceconv.inference.engine import EngineError
from voiceconv.inference.worker_adapter import WorkerAdapter
from voiceconv.platform_support._app_paths import get_app_data_dir
from voiceconv.services._repository import JsonFileJobRepository
from voiceconv.services.converter import Converter
from voiceconv.services.job import Job
from voiceconv.services.queue import JobQueue
from voiceconv.services.runner import QueueRunner
from voiceconv.storage.logging_setup import setup_logging
from voiceconv.storage.profile import JsonFileProfileRepository
from voiceconv.storage.settings import SettingsStore


class _LockedQueueRunner(QueueRunner):
    """QueueRunner that serialises with the shared engine_lock.

    Acquires the lock before each job so the Convert tab cannot run the
    engine concurrently.  Blocking acquire is safe here because this class
    runs on a daemon background thread.
    """

    def __init__(self, *args: object, engine_lock: threading.Lock, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self._engine_lock = engine_lock

    def _run_job(self, job: Job) -> None:
        self._engine_lock.acquire()
        try:
            super()._run_job(job)
        finally:
            self._engine_lock.release()


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
    log_dir = data_dir / "logs"
    settings_store = SettingsStore(data_dir / "settings.json")
    settings = settings_store.load()
    setup_logging(log_dir)

    engine = WorkerAdapter("mock")
    try:
        engine.warmup()
    except EngineError as exc:
        _show_fatal(
            f"The voice engine failed to start.\n\n{exc}\n\nCode: {exc.code}"
        )
        sys.exit(1)

    engine_lock = threading.Lock()

    job_repo = JsonFileJobRepository(data_dir / "jobs")
    queue = JobQueue(job_repo)
    queue.restore()

    bridge = QueueBridge()

    pcm_loader = FfmpegLoader(target_sample_rate=22050)
    audio_encoder = FfmpegEncoder()

    runner = _LockedQueueRunner(
        engine,
        queue,
        pcm_loader,
        audio_encoder=audio_encoder,
        on_status=bridge.on_status,
        on_progress=bridge.on_progress,
        engine_lock=engine_lock,
    )
    runner.start()

    converter = Converter(engine, pcm_loader, audio_encoder)
    profile_repo = JsonFileProfileRepository(data_dir / "profiles")

    state = AppState(
        converter=converter,
        profile_repo=profile_repo,
        settings_store=settings_store,
        settings=settings,
        engine=engine,
        queue=queue,
        runner=runner,
        engine_lock=engine_lock,
        log_dir=log_dir,
    )

    window = MainWindow(state, bridge)
    window.show()

    rc = app.exec()
    runner.stop()
    engine.release()
    sys.exit(rc)
