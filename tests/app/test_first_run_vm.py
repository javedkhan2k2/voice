"""Tests for FirstRunViewModel and detect_device()."""

from __future__ import annotations

import pytest

from voiceconv.platform_support.device import detect_device
from voiceconv.storage.settings import AppSettings, SettingsStore


@pytest.fixture()
def store(tmp_path):
    return SettingsStore(tmp_path / "settings.json")


def test_detect_device_returns_required_keys():
    info = detect_device()
    assert "device" in info
    assert "vram_mb" in info
    assert "note" in info
    assert info["device"] in ("cuda", "cpu")


def test_set_acknowledged_persists(qapp, store, tmp_path):
    from voiceconv.app.view_models.first_run_vm import FirstRunViewModel

    settings = AppSettings()
    vm = FirstRunViewModel(settings, store)
    assert not vm.is_acknowledged

    vm.set_acknowledged(True)

    reloaded = store.load()
    assert reloaded.first_run_acknowledged is True


def test_needs_first_run_false_after_ack(qapp, store):
    from voiceconv.app.view_models.first_run_vm import FirstRunViewModel

    settings = AppSettings(first_run_acknowledged=False)
    vm = FirstRunViewModel(settings, store)
    assert vm.needs_first_run is True

    vm.set_acknowledged(True)
    assert vm.needs_first_run is False
