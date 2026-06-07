"""Resolve platform-appropriate application data directory."""

from __future__ import annotations

import os
from pathlib import Path


def get_app_data_dir() -> Path:
    """Return (and create) the voiceconv app-data directory.

    On Windows this is ``%APPDATA%\\voiceconv``.  Falls back to
    ``~/.voiceconv`` on any other platform or if APPDATA is unset.
    """
    base = Path(os.environ.get("APPDATA", Path.home())) / "voiceconv"
    base.mkdir(parents=True, exist_ok=True)
    return base
