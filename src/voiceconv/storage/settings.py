"""Versioned application settings store."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


@dataclass
class AppSettings:
    """Application-level configuration.

    All paths default to empty string; the app layer resolves them to
    platform-appropriate defaults via ``platform_support/`` at use time.
    """

    device: str = "auto"        # "auto" | "cuda" | "cpu"
    output_format: str = "wav"  # "wav" | "flac"
    output_dir: str = ""        # empty → platform default
    log_dir: str = ""           # empty → platform default
    schema_version: int = SCHEMA_VERSION


class SettingsStore:
    """Read/write :class:`AppSettings` from a single JSON file.

    - Missing file returns dataclass defaults.
    - Unknown keys on load are silently ignored (forward-compatibility).
    - Missing keys on load fall back to dataclass defaults (back-compat).
    - Writes are atomic (tmp + rename).
    """

    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    def load(self) -> AppSettings:
        if not self._path.exists():
            return AppSettings()
        try:
            raw: dict[str, Any] = json.loads(self._path.read_bytes())
        except Exception:
            return AppSettings()
        defaults = asdict(AppSettings())
        merged = {k: raw.get(k, v) for k, v in defaults.items()}
        return AppSettings(**merged)

    def save(self, settings: AppSettings) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.parent / f".{uuid.uuid4().hex}.tmp"
        tmp.write_bytes(json.dumps(asdict(settings), indent=2).encode())
        tmp.replace(self._path)
