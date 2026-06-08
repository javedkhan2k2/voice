"""Headless unit tests for SettingsViewModel."""

from __future__ import annotations

import json
import logging
import threading
import zipfile
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


# ---------------------------------------------------------------------------
# Diagnostics export
# ---------------------------------------------------------------------------


def test_export_diagnostics_writes_bundle(qapp, tmp_path):
    state, _ = _make_state(tmp_path)
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "voiceconv.log").write_text("log line\n", encoding="utf-8")
    state.log_dir = log_dir
    vm = SettingsViewModel(state)

    out = tmp_path / "bundle.zip"
    succeeded: list[str] = []
    vm.export_succeeded.connect(succeeded.append)
    vm.export_diagnostics(str(out))
    _pump()

    assert out.exists()
    assert succeeded == [str(out)]
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
    assert "logs/voiceconv.log" in names
    manifest = json.loads(zipfile.ZipFile(out).read("manifest.json"))
    assert manifest["settings"]["active_engine"] == state.settings.active_engine


def test_export_diagnostics_empty_path_is_noop(qapp, tmp_path):
    state, _ = _make_state(tmp_path)
    vm = SettingsViewModel(state)
    succeeded: list[str] = []
    errors: list[str] = []
    vm.export_succeeded.connect(succeeded.append)
    vm.error.connect(errors.append)

    vm.export_diagnostics("")
    _pump()

    assert not succeeded
    assert not errors


def test_export_diagnostics_error_emits(qapp, tmp_path):
    state, _ = _make_state(tmp_path)
    state.log_dir = tmp_path / "logs"
    (tmp_path / "logs").mkdir()
    vm = SettingsViewModel(state)

    errors: list[str] = []
    vm.error.connect(errors.append)
    # A directory path can't be written as a zip file → triggers the error path.
    bad_target = tmp_path / "adir"
    bad_target.mkdir()
    vm.export_diagnostics(str(bad_target))
    _pump()

    assert errors
