"""Headless unit tests for SettingsViewModel."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QCoreApplication

from voiceconv.app._app_state import AppState
from voiceconv.app.view_models.settings_vm import SettingsViewModel
from voiceconv.services.job import Job, JobStatus, ConversionRequest
from voiceconv.inference.engine import ConvertParams, ProfileArtifacts
from voiceconv.storage.settings import AppSettings, SettingsStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(tmp_path: Path) -> tuple[AppState, SettingsStore]:
    store = SettingsStore(tmp_path / "settings.json")
    settings = AppSettings()
    runner = MagicMock()
    runner.list_jobs.return_value = []
    state = AppState(
        converter=MagicMock(),
        profile_repo=MagicMock(),
        settings_store=store,
        settings=settings,
        engine=MagicMock(),
        queue=MagicMock(),
        runner=runner,
        engine_lock=threading.Lock(),
    )
    return state, store


def _make_running_job() -> Job:
    arts = ProfileArtifacts("mock", "0.1", b"e", {})
    req = ConversionRequest("src.wav", arts, ConvertParams(target_sample_rate=22050), "out.wav")
    job = Job(job_id="j1", request=req, status=JobStatus.RUNNING)
    return job


def _pump() -> None:
    for _ in range(10):
        QCoreApplication.processEvents()


# ---------------------------------------------------------------------------
# Persist tests
# ---------------------------------------------------------------------------


def test_set_device_persists(qapp, tmp_path):
    state, store = _make_state(tmp_path)
    vm = SettingsViewModel(state)
    vm.set_device("cuda")
    reloaded = store.load()
    assert reloaded.device == "cuda"


def test_set_output_format_persists(qapp, tmp_path):
    state, store = _make_state(tmp_path)
    vm = SettingsViewModel(state)
    vm.set_output_format("flac")
    assert store.load().output_format == "flac"


def test_set_loudness_normalize_persists(qapp, tmp_path):
    state, store = _make_state(tmp_path)
    vm = SettingsViewModel(state)
    vm.set_loudness_normalize(False)
    assert store.load().loudness_normalize is False


def test_set_log_level_persists(qapp, tmp_path):
    state, store = _make_state(tmp_path)
    vm = SettingsViewModel(state)
    vm.set_log_level("DEBUG")
    assert store.load().log_level == "DEBUG"


def test_set_log_level_updates_root_logger(qapp, tmp_path):
    state, _ = _make_state(tmp_path)
    vm = SettingsViewModel(state)
    vm.set_log_level("DEBUG")
    assert logging.getLogger().level == logging.DEBUG
    # Restore to not pollute other tests
    logging.getLogger().setLevel(logging.WARNING)


def test_set_active_engine_persists(qapp, tmp_path):
    state, store = _make_state(tmp_path)
    vm = SettingsViewModel(state)
    vm.set_active_engine("openvoice-v2")
    assert store.load().active_engine == "openvoice-v2"


# ---------------------------------------------------------------------------
# output_dir blocking
# ---------------------------------------------------------------------------


def test_set_output_dir_persists_when_idle(qapp, tmp_path):
    state, store = _make_state(tmp_path)
    state.runner.list_jobs.return_value = []
    vm = SettingsViewModel(state)
    vm.set_output_dir(str(tmp_path / "out"))
    assert store.load().output_dir == str(tmp_path / "out")


def test_set_output_dir_blocked_when_running(qapp, tmp_path):
    state, store = _make_state(tmp_path)
    state.runner.list_jobs.return_value = [_make_running_job()]
    vm = SettingsViewModel(state)

    errors: list[str] = []
    vm.error.connect(errors.append)
    vm.set_output_dir(str(tmp_path / "blocked"))

    assert errors
    assert store.load().output_dir == ""  # unchanged


# ---------------------------------------------------------------------------
# settings_changed signal
# ---------------------------------------------------------------------------


def test_settings_changed_emitted_on_setter(qapp, tmp_path):
    state, _ = _make_state(tmp_path)
    vm = SettingsViewModel(state)

    fired: list[None] = []
    vm.settings_changed.connect(lambda: fired.append(None))
    vm.set_device("cpu")
    _pump()

    assert fired
