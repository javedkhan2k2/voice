"""ffmpeg binary location — OS-specific shim.

Checks VOICECONV_FFMPEG_PATH env var first, then falls back to PATH lookup.
All other layers import this function; no layer hardcodes an ffmpeg path.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def get_ffmpeg_path() -> str:
    """Return the path to the ffmpeg binary.

    Resolution order:
    1. ``VOICECONV_FFMPEG_PATH`` environment variable (absolute path to binary).
    2. ``shutil.which("ffmpeg")`` — finds ffmpeg on the system PATH.

    Raises ``FileNotFoundError`` if ffmpeg cannot be located.
    """
    env_path = os.environ.get("VOICECONV_FFMPEG_PATH", "")
    if env_path:
        p = Path(env_path)
        if p.is_file():
            return str(p)
        raise FileNotFoundError(
            f"VOICECONV_FFMPEG_PATH is set to {env_path!r} but no file exists there"
        )

    which = shutil.which("ffmpeg")
    if which:
        return which

    raise FileNotFoundError(
        "ffmpeg not found on PATH. "
        "Install ffmpeg or set VOICECONV_FFMPEG_PATH to its absolute path."
    )
