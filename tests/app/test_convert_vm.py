"""Tests for ConvertViewModel."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication

from voiceconv.app._app_state import AppState
from voiceconv.app.view_models.convert_vm import ConvertViewModel
from voiceconv.inference.engine import CancelledError, ConvertParams, ProfileArtifacts
from voiceconv.storage.profile import JsonFileProfileRepository
from voiceconv.storage.settings import AppSettings, SettingsStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_artifacts():
    return ProfileArtifacts("mock", "0.1", b"emb", {})


def _make_converter(output_pcm=None):
    pcm = output_pcm if output_pcm is not None else np.zeros(100, dtype=np.float32)
    conv = MagicMock()
    conv.convert_file.return_value = None
    return conv


def _make_state(tmp_path: Path, converter=None):
    repo = JsonFileProfileRepository(tmp_path / "profiles")
    store = SettingsStore(tmp_path / "settings.json")
    settings = AppSettings()
    engine = MagicMock()
    return AppState(
        converter=converter or _make_converter(),
        profile_repo=repo,
        settings_store=store,
        settings=settings,
        engine=engine,
    )


def _wait(vm: ConvertViewModel, timeout_ms: int = 3000) -> None:
    if vm._thread:
        vm._thread.wait(timeout_ms)
    for _ in range(20):
        QCoreApplication.processEvents()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_start_convert_requires_source_path(qapp, tmp_path):
    state = _make_state(tmp_path)
    vm = ConvertViewModel(state)
    vm.set_profile_artifacts(_make_artifacts())
    vm.set_output_path(str(tmp_path / "out.wav"))

    errors = []
    vm.error.connect(errors.append)
    vm.start_convert()

    assert any("source" in e.lower() for e in errors)


def test_start_convert_requires_profile(qapp, tmp_path):
    state = _make_state(tmp_path)
    vm = ConvertViewModel(state)
    vm.set_source_path(str(tmp_path / "src.wav"))
    vm.set_output_path(str(tmp_path / "out.wav"))
    # no profile

    errors = []
    vm.error.connect(errors.append)
    vm.start_convert()

    assert any("profile" in e.lower() for e in errors)


def test_output_path_auto_suggested_from_source(qapp, tmp_path):
    state = _make_state(tmp_path)
    vm = ConvertViewModel(state)

    paths = []
    vm.output_path_changed.connect(paths.append)
    vm.set_source_path(str(tmp_path / "speech.wav"))

    assert any("speech_converted" in p for p in paths)


def test_conversion_done_emitted(qapp, tmp_path):
    # Converter.convert_file does nothing (mock); encoder does nothing
    state = _make_state(tmp_path)
    vm = ConvertViewModel(state)
    vm.set_source_path(str(tmp_path / "src.wav"))
    vm.set_profile_artifacts(_make_artifacts())
    out = str(tmp_path / "out.wav")
    vm.set_output_path(out)

    done_paths: list[str] = []
    vm.conversion_done.connect(done_paths.append)

    vm.start_convert()
    _wait(vm)

    assert len(done_paths) == 1
    assert done_paths[0] == out


def test_is_running_resets_after_done(qapp, tmp_path):
    state = _make_state(tmp_path)
    vm = ConvertViewModel(state)
    vm.set_source_path(str(tmp_path / "src.wav"))
    vm.set_profile_artifacts(_make_artifacts())
    vm.set_output_path(str(tmp_path / "out.wav"))

    vm.start_convert()
    _wait(vm)

    assert not vm.is_running


def test_cancel_stops_conversion(qapp, tmp_path):
    def slow_convert(src, arts, params, out, *, progress=None, cancel_token=None):
        for _ in range(20):
            time.sleep(0.02)
            if cancel_token and cancel_token.is_cancelled:
                raise CancelledError()

    conv = MagicMock()
    conv.convert_file.side_effect = slow_convert

    state = _make_state(tmp_path, converter=conv)
    vm = ConvertViewModel(state)
    vm.set_source_path(str(tmp_path / "src.wav"))
    vm.set_profile_artifacts(_make_artifacts())
    vm.set_output_path(str(tmp_path / "out.wav"))

    done_paths: list[str] = []
    vm.conversion_done.connect(done_paths.append)

    vm.start_convert()
    time.sleep(0.05)
    vm.cancel()
    _wait(vm, 2000)

    assert not vm.is_running
    assert len(done_paths) == 0
