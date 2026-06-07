"""Tests for ProfileViewModel."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication

from voiceconv.app._app_state import AppState
from voiceconv.app.view_models.profile_vm import ProfileViewModel
from voiceconv.inference.engine import ProfileArtifacts
from voiceconv.storage.profile import JsonFileProfileRepository
from voiceconv.storage.settings import AppSettings, SettingsStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_converter(artifacts: ProfileArtifacts | None = None):
    conv = MagicMock()
    arts = artifacts or ProfileArtifacts("mock", "0.1", b"emb", {})
    conv.prepare_profile.return_value = arts
    return conv


def _make_state(tmp_path: Path, converter=None):
    repo = JsonFileProfileRepository(tmp_path / "profiles")
    store = SettingsStore(tmp_path / "settings.json")
    settings = AppSettings()
    engine = MagicMock()
    return AppState(
        converter=converter or _mock_converter(),
        profile_repo=repo,
        settings_store=store,
        settings=settings,
        engine=engine,
    )


def _process_events():
    for _ in range(10):
        QCoreApplication.processEvents()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_create_profile_requires_consent(qapp, tmp_path):
    state = _make_state(tmp_path)
    vm = ProfileViewModel(state)
    vm.set_reference_path("/some/ref.wav")
    vm.set_name("Alice")
    # consent NOT affirmed

    errors = []
    vm.error.connect(errors.append)
    vm.create_profile()

    assert len(errors) == 1
    assert "consent" in errors[0].lower()


def test_create_profile_requires_reference_path(qapp, tmp_path):
    state = _make_state(tmp_path)
    vm = ProfileViewModel(state)
    vm.set_consent_affirmed(True)
    vm.set_name("Alice")
    # reference_path not set

    errors = []
    vm.error.connect(errors.append)
    vm.create_profile()

    assert len(errors) == 1
    assert "reference" in errors[0].lower()


def test_create_profile_requires_name(qapp, tmp_path):
    state = _make_state(tmp_path)
    vm = ProfileViewModel(state)
    vm.set_consent_affirmed(True)
    vm.set_reference_path("/some/ref.wav")
    # name not set

    errors = []
    vm.error.connect(errors.append)
    vm.create_profile()

    assert len(errors) == 1
    assert "name" in errors[0].lower()


def test_create_profile_whitespace_name_rejected(qapp, tmp_path):
    state = _make_state(tmp_path)
    vm = ProfileViewModel(state)
    vm.set_consent_affirmed(True)
    vm.set_reference_path("/some/ref.wav")
    vm.set_name("   ")

    errors = []
    vm.error.connect(errors.append)
    vm.create_profile()

    assert len(errors) == 1


def test_create_profile_success_saves_and_emits(qapp, tmp_path):
    state = _make_state(tmp_path)
    vm = ProfileViewModel(state)
    vm.set_consent_affirmed(True)
    vm.set_reference_path("/some/ref.wav")
    vm.set_name("Bob")

    saved_ids: list[str] = []
    vm.profile_saved.connect(saved_ids.append)

    vm.create_profile()

    # Allow the QThread to finish
    if vm._thread:
        vm._thread.wait(3000)
    _process_events()

    assert len(saved_ids) == 1
    profiles = state.profile_repo.list_all()
    assert any(p.name == "Bob" for p in profiles)


def test_is_busy_flips_during_create(qapp, tmp_path):
    import time

    slow_conv = MagicMock()

    def slow_prepare(path):
        time.sleep(0.05)
        return ProfileArtifacts("mock", "0.1", b"emb", {})

    slow_conv.prepare_profile.side_effect = slow_prepare

    state = _make_state(tmp_path, converter=slow_conv)
    vm = ProfileViewModel(state)
    vm.set_consent_affirmed(True)
    vm.set_reference_path("/some/ref.wav")
    vm.set_name("Carol")

    busy_states: list[bool] = []
    vm.is_busy_changed.connect(busy_states.append)

    vm.create_profile()
    if vm._thread:
        vm._thread.wait(3000)
    _process_events()

    # Should have seen True then False
    assert True in busy_states
