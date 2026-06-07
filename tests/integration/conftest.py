"""Shared fixtures and helpers for integration tests."""

from __future__ import annotations

import os
import shutil
import wave
from pathlib import Path

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# ffmpeg skip guard (mirrors tests/audio/test_codec.py pattern)
# ---------------------------------------------------------------------------

_FFMPEG = os.environ.get("VOICECONV_FFMPEG_PATH") or shutil.which("ffmpeg")
needs_ffmpeg = pytest.mark.skipif(
    _FFMPEG is None,
    reason="ffmpeg not available (set VOICECONV_FFMPEG_PATH or install ffmpeg)",
)


# ---------------------------------------------------------------------------
# WAV synthesis helper
# ---------------------------------------------------------------------------


def make_wav(
    path: Path,
    duration_sec: float = 1.0,
    sample_rate: int = 22050,
    freq_hz: float = 440.0,
) -> Path:
    """Write a mono 16-bit PCM WAV with a sine wave to *path*.

    Returns *path* for convenience so callers can inline::

        ref = make_wav(tmp_path / "ref.wav", 2.0)
    """
    n = int(sample_rate * duration_sec)
    t = np.linspace(0, duration_sec, n, endpoint=False)
    pcm = (np.sin(2 * np.pi * freq_hz * t) * 0.5 * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return path
