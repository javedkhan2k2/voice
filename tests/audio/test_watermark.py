"""Tests for the experimental watermark prototype (Phase 3 M4).

These pin the prototype's measured behaviour: it detects its own mark, does not
false-positive on unmarked audio or the wrong key, stays above an SNR floor, and
survives lossless transforms. Robustness gaps (trim/resample) are documented in
docs/watermark-eval.md, not asserted as passing.
"""

from __future__ import annotations

import os
import shutil

import numpy as np
import pytest

from voiceconv.audio._watermark import (
    DEFAULT_KEY,
    DEFAULT_THRESHOLD,
    correlation_score,
    embed,
    is_watermarked,
    snr_db,
)

_FFMPEG = os.environ.get("VOICECONV_FFMPEG_PATH") or shutil.which("ffmpeg")
needs_ffmpeg = pytest.mark.skipif(_FFMPEG is None, reason="ffmpeg not available")
_WRONG_KEY = DEFAULT_KEY ^ 0xFFFF


def _host(seconds: float = 3.0, sr: int = 22050) -> np.ndarray:
    rng = np.random.default_rng(1)
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    sig = 0.5 * np.sin(2 * np.pi * 220 * t) + 0.2 * np.sin(2 * np.pi * 440 * t)
    sig += 0.02 * rng.standard_normal(len(t))
    return (0.6 * sig / np.max(np.abs(sig))).astype(np.float32)


def test_embed_preserves_shape_and_is_finite():
    host = _host()
    wm = embed(host)
    assert wm.shape == host.shape
    assert wm.dtype == np.float32
    assert np.all(np.isfinite(wm))


def test_detects_matching_watermark():
    wm = embed(_host())
    assert correlation_score(wm) >= DEFAULT_THRESHOLD
    assert is_watermarked(wm)


def test_no_detection_on_unmarked_audio():
    host = _host()
    assert correlation_score(host) < DEFAULT_THRESHOLD
    assert not is_watermarked(host)


def test_no_detection_with_wrong_key():
    wm = embed(_host())
    assert correlation_score(wm, key=_WRONG_KEY) < DEFAULT_THRESHOLD


def test_snr_above_floor():
    host = _host()
    wm = embed(host)
    assert snr_db(host, wm) > 20.0  # measured ~28 dB


def test_survives_16bit_requantize():
    wm = embed(_host())
    requantized = (np.clip(wm, -1, 1) * 32767).astype(np.int16).astype(np.float32) / 32767.0
    assert is_watermarked(requantized)


@needs_ffmpeg
def test_survives_flac_reencode(tmp_path):
    from voiceconv.audio._codec import FfmpegEncoder, FfmpegLoader

    wm = embed(_host())
    path = str(tmp_path / "wm.flac")
    FfmpegEncoder().encode(wm, 22050, path)
    recovered, _ = FfmpegLoader(target_sample_rate=22050).load(path)
    assert is_watermarked(recovered)
