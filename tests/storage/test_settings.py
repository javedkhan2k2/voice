"""Unit tests for AppSettings and SettingsStore."""

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from voiceconv.storage.settings import AppSettings, SettingsStore


def _store(tmp_path: Path) -> SettingsStore:
    return SettingsStore(tmp_path / "settings.json")


def test_load_missing_file_returns_defaults(tmp_path):
    s = _store(tmp_path).load()
    d = AppSettings()
    assert s.device == d.device
    assert s.output_format == d.output_format
    assert s.schema_version == d.schema_version


def test_save_and_load_roundtrip(tmp_path):
    store = _store(tmp_path)
    settings = AppSettings(device="cuda", output_format="flac", output_dir="/out")
    store.save(settings)
    loaded = store.load()
    assert loaded.device == "cuda"
    assert loaded.output_format == "flac"
    assert loaded.output_dir == "/out"


def test_update_single_field(tmp_path):
    store = _store(tmp_path)
    store.save(AppSettings())
    s = store.load()
    s.device = "cpu"
    store.save(s)
    reloaded = store.load()
    assert reloaded.device == "cpu"
    assert reloaded.output_format == "wav"  # unchanged


def test_unknown_key_ignored_on_load(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"device": "cpu", "unknown_future_key": 42}))
    s = SettingsStore(path).load()
    assert s.device == "cpu"
    assert not hasattr(s, "unknown_future_key")


def test_schema_version_written(tmp_path):
    store = _store(tmp_path)
    store.save(AppSettings())
    raw = json.loads((tmp_path / "settings.json").read_text())
    assert raw["schema_version"] == 1


def test_atomic_write_uses_tmp_then_rename(tmp_path, monkeypatch):
    tmp_files_seen: list[str] = []
    real_replace = Path.replace

    def _patched_replace(self, target):
        tmp_files_seen.append(self.name)
        return real_replace(self, target)

    monkeypatch.setattr(Path, "replace", _patched_replace)
    _store(tmp_path).save(AppSettings())
    assert len(tmp_files_seen) == 1
    assert tmp_files_seen[0].startswith(".")
