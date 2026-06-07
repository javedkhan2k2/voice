"""Unit tests for rms_normalize — no ffmpeg dependency."""

import numpy as np
import pytest

from voiceconv.audio._normalize import rms_normalize


def _rms(pcm: np.ndarray) -> float:
    return float(np.sqrt(np.mean(pcm.astype(np.float64) ** 2)))


def test_output_rms_equals_target():
    rng = np.random.default_rng(0)
    pcm = rng.uniform(-0.5, 0.5, 22050).astype(np.float32)
    out = rms_normalize(pcm, target_rms=0.1)
    assert _rms(out) == pytest.approx(0.1, rel=1e-4)


def test_default_target_rms():
    rng = np.random.default_rng(1)
    pcm = rng.uniform(-0.8, 0.8, 4410).astype(np.float32)
    out = rms_normalize(pcm)
    assert _rms(out) == pytest.approx(0.1, rel=1e-4)


def test_output_is_float32():
    pcm = np.ones(100, dtype=np.float64)
    out = rms_normalize(pcm, target_rms=0.2)
    assert out.dtype == np.float32


def test_output_shape_unchanged():
    pcm = np.ones(1000, dtype=np.float32) * 0.5
    out = rms_normalize(pcm, target_rms=0.3)
    assert out.shape == pcm.shape


def test_silent_signal_returns_zeros():
    pcm = np.zeros(512, dtype=np.float32)
    out = rms_normalize(pcm, target_rms=0.1)
    assert np.all(out == 0.0)
    assert not np.any(np.isnan(out))


def test_already_at_target_rms():
    rng = np.random.default_rng(2)
    pcm = rng.uniform(-1.0, 1.0, 8000).astype(np.float32)
    target = _rms(pcm)
    out = rms_normalize(pcm, target_rms=target)
    np.testing.assert_allclose(out, pcm, rtol=1e-4)


def test_various_target_rms_values():
    rng = np.random.default_rng(3)
    pcm = rng.uniform(-0.3, 0.3, 4000).astype(np.float32)
    for target in (0.01, 0.05, 0.2, 0.5, 1.0):
        out = rms_normalize(pcm, target_rms=target)
        assert _rms(out) == pytest.approx(target, rel=1e-4)
