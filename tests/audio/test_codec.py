"""Tests for FfmpegLoader and FfmpegEncoder.

All tests are skipped when ffmpeg is not available on PATH or via
VOICECONV_FFMPEG_PATH, so the suite stays green in environments without ffmpeg.
"""

from __future__ import annotations

import os
import shutil
import struct
import wave

import numpy as np
import pytest

from voiceconv.audio._codec import FfmpegEncoder, FfmpegLoader

# ---------------------------------------------------------------------------
# Skip guard
# ---------------------------------------------------------------------------

_FFMPEG = os.environ.get("VOICECONV_FFMPEG_PATH") or shutil.which("ffmpeg")
needs_ffmpeg = pytest.mark.skipif(
    _FFMPEG is None,
    reason="ffmpeg not available (set VOICECONV_FFMPEG_PATH or install ffmpeg)",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_wav(path: str, pcm: np.ndarray, sample_rate: int) -> None:
    """Write float32 mono PCM as 16-bit PCM WAV (no ffmpeg)."""
    import pathlib
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    int16 = (np.clip(pcm, -1.0, 1.0) * 32767.0).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(int16.tobytes())


def _sine(freq: float = 440.0, sr: int = 22050, duration: float = 0.5) -> np.ndarray:
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    return (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)


# ---------------------------------------------------------------------------
# FfmpegLoader tests
# ---------------------------------------------------------------------------


@needs_ffmpeg
def test_load_wav_returns_float32_mono(tmp_path):
    pcm = _sine(sr=22050)
    wav = str(tmp_path / "test.wav")
    _write_wav(wav, pcm, 22050)

    loader = FfmpegLoader()
    out, sr = loader.load(wav)

    assert out.dtype == np.float32
    assert out.ndim == 1
    assert len(out) > 0
    assert sr == 22050


@needs_ffmpeg
def test_load_resamples_to_target_sr(tmp_path):
    pcm = _sine(sr=22050, duration=1.0)
    wav = str(tmp_path / "src.wav")
    _write_wav(wav, pcm, 22050)

    loader = FfmpegLoader(target_sample_rate=44100)
    out, sr = loader.load(wav)

    assert sr == 44100
    # 1-second file at 44100 Hz → ~44100 samples (allow ±5% tolerance)
    assert abs(len(out) - 44100) < 2205


@needs_ffmpeg
def test_load_native_sr_when_no_target(tmp_path):
    pcm = _sine(sr=16000, duration=0.5)
    wav = str(tmp_path / "native.wav")
    _write_wav(wav, pcm, 16000)

    loader = FfmpegLoader()
    out, sr = loader.load(wav)

    assert sr == 16000
    assert abs(len(out) - 8000) < 500


@needs_ffmpeg
def test_load_values_approximate_source(tmp_path):
    pcm = _sine(sr=22050, duration=0.5)
    wav = str(tmp_path / "approx.wav")
    _write_wav(wav, pcm, 22050)

    loader = FfmpegLoader(target_sample_rate=22050)
    out, sr = loader.load(wav)

    # Round-trip through WAV int16 encode then ffmpeg decode;
    # values should be within int16 quantisation error (~3e-5)
    min_len = min(len(pcm), len(out))
    np.testing.assert_allclose(out[:min_len], pcm[:min_len], atol=4e-4)


@needs_ffmpeg
def test_load_bad_path_raises(tmp_path):
    loader = FfmpegLoader()
    with pytest.raises(Exception):
        loader.load(str(tmp_path / "nonexistent.wav"))


# ---------------------------------------------------------------------------
# FfmpegEncoder tests
# ---------------------------------------------------------------------------


@needs_ffmpeg
def test_encode_wav_file_created(tmp_path):
    pcm = _sine(sr=22050)
    out_path = str(tmp_path / "out.wav")

    encoder = FfmpegEncoder()
    encoder.encode(pcm, 22050, out_path)

    assert (tmp_path / "out.wav").exists()
    assert (tmp_path / "out.wav").stat().st_size > 0


@needs_ffmpeg
def test_encode_flac_file_created(tmp_path):
    pcm = _sine(sr=22050)
    out_path = str(tmp_path / "out.flac")

    encoder = FfmpegEncoder()
    encoder.encode(pcm, 22050, out_path)

    assert (tmp_path / "out.flac").exists()
    assert (tmp_path / "out.flac").stat().st_size > 0


@needs_ffmpeg
def test_encode_creates_parent_dirs(tmp_path):
    pcm = _sine(sr=22050)
    out_path = str(tmp_path / "deep" / "nested" / "out.wav")

    FfmpegEncoder().encode(pcm, 22050, out_path)

    assert (tmp_path / "deep" / "nested" / "out.wav").exists()


# ---------------------------------------------------------------------------
# Round-trip test
# ---------------------------------------------------------------------------


@needs_ffmpeg
def test_encode_decode_roundtrip(tmp_path):
    original = _sine(freq=880.0, sr=22050, duration=1.0)
    wav_path = str(tmp_path / "roundtrip.wav")

    FfmpegEncoder().encode(original, 22050, wav_path)
    recovered, sr = FfmpegLoader(target_sample_rate=22050).load(wav_path)

    assert sr == 22050
    min_len = min(len(original), len(recovered))
    np.testing.assert_allclose(recovered[:min_len], original[:min_len], atol=5e-4)
