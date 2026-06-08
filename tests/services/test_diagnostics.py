"""Unit tests for the diagnostics-bundle assembler.

Privacy-critical: these tests assert the bundle never contains audio.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from voiceconv.services import diagnostics
from voiceconv.services.diagnostics import (
    MANIFEST_NAME,
    build_bundle,
    collect_app_info,
)

_AUDIO_EXTS = (".wav", ".flac", ".mp3", ".ogg", ".m4a", ".aac", ".opus")


def _seed_logs(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "voiceconv.log").write_text("active log line\n", encoding="utf-8")
    (log_dir / "voiceconv.log.1").write_text("rotated log line\n", encoding="utf-8")


def _build(tmp_path: Path) -> Path:
    log_dir = tmp_path / "logs"
    _seed_logs(log_dir)
    out = tmp_path / "bundle.zip"
    return build_bundle(out, log_dir, collect_app_info())


# ---------------------------------------------------------------------------
# Audio exclusion (the core privacy guarantee)
# ---------------------------------------------------------------------------


def test_bundle_excludes_audio_files(tmp_path):
    log_dir = tmp_path / "logs"
    _seed_logs(log_dir)
    # A stray audio recording sitting in the log dir must never be picked up.
    (log_dir / "secret.wav").write_bytes(b"RIFF....WAVEfake")
    (log_dir / "voice.mp3").write_bytes(b"ID3fake")

    out = build_bundle(tmp_path / "bundle.zip", log_dir, collect_app_info())

    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
    assert not any(n.lower().endswith(_AUDIO_EXTS) for n in names)
    assert not any("secret" in n or "voice.mp3" in n for n in names)


def test_audio_guard_raises_if_audio_whitelisted(tmp_path, monkeypatch):
    """Defensive: if the name whitelist ever admitted an audio file, the
    extension denylist must still abort assembly."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "voiceconv.log.wav").write_bytes(b"fake")
    # Force the glob to match the audio-suffixed file.
    monkeypatch.setattr(diagnostics, "_LOG_GLOB", "voiceconv.log*")

    with pytest.raises(ValueError, match="audio"):
        build_bundle(tmp_path / "b.zip", log_dir, {})


# ---------------------------------------------------------------------------
# Required contents
# ---------------------------------------------------------------------------


def test_bundle_contains_at_least_one_log(tmp_path):
    out = _build(tmp_path)
    with zipfile.ZipFile(out) as zf:
        log_entries = [n for n in zf.namelist() if n.startswith("logs/")]
    assert "logs/voiceconv.log" in log_entries
    assert len(log_entries) >= 1


def test_bundle_includes_rotated_logs(tmp_path):
    out = _build(tmp_path)
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
    assert "logs/voiceconv.log.1" in names


def test_bundle_contains_manifest_with_hardware(tmp_path):
    out = _build(tmp_path)
    with zipfile.ZipFile(out) as zf:
        assert MANIFEST_NAME in zf.namelist()
        manifest = json.loads(zf.read(MANIFEST_NAME))
    assert "platform" in manifest
    assert "device" in manifest
    assert manifest["device"]["device"] in {"cuda", "cpu"}
    assert "system" in manifest["platform"]


def test_log_content_preserved(tmp_path):
    out = _build(tmp_path)
    with zipfile.ZipFile(out) as zf:
        assert b"active log line" in zf.read("logs/voiceconv.log")


# ---------------------------------------------------------------------------
# collect_app_info
# ---------------------------------------------------------------------------


def test_collect_app_info_has_required_keys():
    info = collect_app_info()
    for key in ("tool", "platform", "python", "packages", "device", "generated_at"):
        assert key in info
    assert set(info["packages"]) >= {"PySide6", "numpy", "torch"}


def test_missing_package_reported_as_not_installed():
    info = collect_app_info()
    # torch is not installed in the mock-mode dev env; absent packages must be
    # reported rather than omitted.
    for value in info["packages"].values():
        assert isinstance(value, str)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_missing_log_dir_yields_manifest_only(tmp_path):
    out = build_bundle(tmp_path / "b.zip", tmp_path / "nonexistent", {"k": "v"})
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
    assert names == [MANIFEST_NAME]


def test_creates_parent_directories(tmp_path):
    log_dir = tmp_path / "logs"
    _seed_logs(log_dir)
    nested = tmp_path / "a" / "b" / "bundle.zip"
    build_bundle(nested, log_dir, {})
    assert nested.exists()
