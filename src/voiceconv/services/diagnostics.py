"""Diagnostics-bundle assembly — headless, Qt-free.

Collects local log files plus an environment/hardware manifest into a single
ZIP file so a user can hand a support bundle to a maintainer.

Privacy invariant: **no audio ever enters the bundle.**  Two independent
guards enforce this:

1. *Name whitelist* — only files matching ``voiceconv.log*`` (the active log
   and its rotated siblings) are collected.  Audio recordings cannot match
   this glob.
2. *Extension denylist* — every collected file is checked against
   :data:`_AUDIO_EXTENSIONS` and assembly aborts if any audio file slips
   through.  This is the property asserted by the unit tests.

No network access occurs here; the offline-runtime invariant is preserved.
"""

from __future__ import annotations

import importlib.metadata
import json
import platform
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from voiceconv.platform_support.device import detect_device

MANIFEST_NAME = "manifest.json"
MANIFEST_SCHEMA_VERSION = 1

# Only files whose name matches this glob are eligible for the bundle.
_LOG_GLOB = "voiceconv.log*"

# Audio extensions that must never appear in a diagnostics bundle.
_AUDIO_EXTENSIONS = frozenset(
    {
        ".wav",
        ".flac",
        ".mp3",
        ".ogg",
        ".m4a",
        ".aac",
        ".wma",
        ".aiff",
        ".aif",
        ".opus",
        ".raw",
        ".pcm",
    }
)

# Packages whose versions are useful when triaging a report.
_TRACKED_PACKAGES = ("PySide6", "numpy", "torch")


def _package_version(name: str) -> str:
    """Return the installed version of *name*, or ``"not installed"``."""
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not installed"


def collect_app_info() -> dict[str, Any]:
    """Gather environment/hardware metadata for the bundle manifest.

    Pure read-only probe of the local machine — no audio, no PII, no network.
    """
    return {
        "tool": "VoiceBuilder",
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
        },
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "executable": sys.executable,
        },
        "packages": {name: _package_version(name) for name in _TRACKED_PACKAGES},
        "device": detect_device(),
    }


def _is_audio(path: Path) -> bool:
    return path.suffix.lower() in _AUDIO_EXTENSIONS


def build_bundle(
    output_zip_path: Path,
    log_dir: Path,
    app_info: dict[str, Any],
) -> Path:
    """Assemble a diagnostics ZIP at *output_zip_path*.

    The bundle contains:

    - ``manifest.json`` — the *app_info* dict, serialised verbatim.
    - ``logs/<name>`` — every ``voiceconv.log*`` file found in *log_dir*.

    Parameters
    ----------
    output_zip_path:
        Destination ``.zip`` path; parent directories are created.
    log_dir:
        Directory holding the rotating log files.  May be missing/empty.
    app_info:
        Manifest payload (see :func:`collect_app_info`).

    Returns
    -------
    Path
        ``output_zip_path``.

    Raises
    ------
    ValueError
        If any file selected for inclusion has an audio extension.  This is a
        defensive guard that should be unreachable given the name whitelist.
    """
    output_zip_path = Path(output_zip_path)
    log_dir = Path(log_dir)

    log_files = sorted(
        p for p in log_dir.glob(_LOG_GLOB) if p.is_file()
    ) if log_dir.is_dir() else []

    # Guard 2: extension denylist — assembly aborts rather than leak audio.
    for path in log_files:
        if _is_audio(path):
            raise ValueError(
                f"refusing to add audio file to diagnostics bundle: {path.name}"
            )

    output_zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output_zip_path, "w", compression=zipfile.ZIP_DEFLATED
    ) as zf:
        zf.writestr(MANIFEST_NAME, json.dumps(app_info, indent=2))
        for path in log_files:
            zf.write(path, arcname=f"logs/{path.name}")

    return output_zip_path
