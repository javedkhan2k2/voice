"""Headless unit tests for ProfileLibraryViewModel."""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QCoreApplication

from voiceconv.app._app_state import AppState
from voiceconv.app.view_models.profile_library_vm import ProfileLibraryViewModel
from voiceconv.inference.engine import ProfileArtifacts
from voiceconv.storage.profile import (
    ConsentRecord,
    JsonFileProfileRepository,
    VoiceProfile,
)
from voiceconv.storage.settings import AppSettings, SettingsStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_profile(name: str = "Alice") -> VoiceProfile:
    arts = ProfileArtifacts("mock", "0.1", b"emb", {})
    consent = ConsentRecord.create()
    return VoiceProfile.create(name, arts, consent)


def _make_state(tmp_path: Path) -> tuple[AppState, JsonFileProfileRepository]:
    repo = JsonFileProfileRepository(tmp_path / "profiles")
    store = SettingsStore(tmp_path / "settings.json")
    settings = AppSettings()
    state = AppState(
        converter=MagicMock(),
        profile_repo=repo,
        settings_store=store,
        settings=settings,
        engine=MagicMock(),
        queue=MagicMock(),
        runner=MagicMock(),
        engine_lock=threading.Lock(),
    )
    return state, repo


def _pump() -> None:
    for _ in range(10):
        QCoreApplication.processEvents()


# ---------------------------------------------------------------------------
# refresh
# ---------------------------------------------------------------------------


def test_refresh_loads_profiles(qapp, tmp_path):
    state, repo = _make_state(tmp_path)
    p1, p2 = _make_profile("Alice"), _make_profile("Bob")
    repo.save(p1)
    repo.save(p2)

    vm = ProfileLibraryViewModel(state)
    vm.refresh()

    names = {p.name for p in vm.profiles()}
    assert names == {"Alice", "Bob"}


def test_refresh_emits_profiles_changed(qapp, tmp_path):
    state, _ = _make_state(tmp_path)
    vm = ProfileLibraryViewModel(state)

    fired: list[None] = []
    vm.profiles_changed.connect(lambda: fired.append(None))
    vm.refresh()
    _pump()

    assert fired


# ---------------------------------------------------------------------------
# select
# ---------------------------------------------------------------------------


def test_select_sets_selected_profile(qapp, tmp_path):
    state, repo = _make_state(tmp_path)
    profile = _make_profile()
    repo.save(profile)

    vm = ProfileLibraryViewModel(state)
    vm.refresh()
    vm.select(profile.profile_id)

    assert vm.selected_profile() is not None
    assert vm.selected_profile().profile_id == profile.profile_id


def test_select_emits_selection_changed(qapp, tmp_path):
    state, repo = _make_state(tmp_path)
    profile = _make_profile()
    repo.save(profile)

    vm = ProfileLibraryViewModel(state)
    vm.refresh()

    received: list[str] = []
    vm.selection_changed.connect(received.append)
    vm.select(profile.profile_id)
    _pump()

    assert profile.profile_id in received


# ---------------------------------------------------------------------------
# rename
# ---------------------------------------------------------------------------


def test_rename_updates_stored_name(qapp, tmp_path):
    state, repo = _make_state(tmp_path)
    profile = _make_profile("Old Name")
    repo.save(profile)

    vm = ProfileLibraryViewModel(state)
    vm.refresh()
    vm.rename(profile.profile_id, "New Name")

    reloaded = repo.load(profile.profile_id)
    assert reloaded is not None
    assert reloaded.name == "New Name"


def test_rename_emits_profiles_changed(qapp, tmp_path):
    state, repo = _make_state(tmp_path)
    profile = _make_profile()
    repo.save(profile)

    vm = ProfileLibraryViewModel(state)
    vm.refresh()

    fired: list[None] = []
    vm.profiles_changed.connect(lambda: fired.append(None))
    vm.rename(profile.profile_id, "Renamed")
    _pump()

    assert fired


def test_rename_empty_name_emits_error(qapp, tmp_path):
    state, repo = _make_state(tmp_path)
    profile = _make_profile()
    repo.save(profile)

    vm = ProfileLibraryViewModel(state)
    vm.refresh()

    errors: list[str] = []
    vm.error.connect(errors.append)
    vm.rename(profile.profile_id, "")

    assert errors


def test_rename_whitespace_only_emits_error(qapp, tmp_path):
    state, repo = _make_state(tmp_path)
    profile = _make_profile()
    repo.save(profile)

    vm = ProfileLibraryViewModel(state)
    vm.refresh()

    errors: list[str] = []
    vm.error.connect(errors.append)
    vm.rename(profile.profile_id, "   ")

    assert errors


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


def test_delete_removes_profile(qapp, tmp_path):
    state, repo = _make_state(tmp_path)
    profile = _make_profile()
    repo.save(profile)

    vm = ProfileLibraryViewModel(state)
    vm.refresh()
    vm.delete(profile.profile_id)

    assert repo.load(profile.profile_id) is None


def test_delete_emits_profiles_changed(qapp, tmp_path):
    state, repo = _make_state(tmp_path)
    profile = _make_profile()
    repo.save(profile)

    vm = ProfileLibraryViewModel(state)
    vm.refresh()

    fired: list[None] = []
    vm.profiles_changed.connect(lambda: fired.append(None))
    vm.delete(profile.profile_id)
    _pump()

    assert fired


def test_delete_clears_selection(qapp, tmp_path):
    state, repo = _make_state(tmp_path)
    profile = _make_profile()
    repo.save(profile)

    vm = ProfileLibraryViewModel(state)
    vm.refresh()
    vm.select(profile.profile_id)
    assert vm.selected_profile() is not None

    vm.delete(profile.profile_id)

    assert vm.selected_profile() is None
