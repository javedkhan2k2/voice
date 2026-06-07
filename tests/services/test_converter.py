"""Integration tests for Converter.

All tests use WorkerAdapter("mock") — real subprocess, no GPU.
_MockPcmLoader is injected to avoid file I/O; StdlibWavEncoder writes real output files.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Optional

import numpy as np
import pytest

from voiceconv.inference.engine import CancelToken, CancelledError, ConvertParams
from voiceconv.inference.worker_adapter import WorkerAdapter
from voiceconv.services._audio_encoder import StdlibWavEncoder
from voiceconv.services.converter import Converter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _MockPcmLoader:
    """Returns a noise clip for any path; avoids file I/O in tests."""

    def __init__(
        self,
        pcm: Optional[np.ndarray] = None,
        sample_rate: int = 22050,
    ) -> None:
        if pcm is None:
            rng = np.random.default_rng(42)
            pcm = rng.uniform(-0.1, 0.1, 2205).astype(np.float32)
        self._pcm = pcm
        self._sr = sample_rate

    def load(self, path: str) -> tuple[np.ndarray, int]:
        return self._pcm.copy(), self._sr


def _params() -> ConvertParams:
    return ConvertParams(target_sample_rate=22050)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine():
    e = WorkerAdapter("mock")
    e.warmup("cpu")
    yield e
    e.terminate()


@pytest.fixture
def converter(engine):
    return Converter(engine, _MockPcmLoader(), StdlibWavEncoder())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_prepare_profile_returns_artifacts(converter):
    profile = converter.prepare_profile("ref.wav")
    assert profile.engine_id == "mock"
    assert isinstance(profile.data, bytes)
    assert len(profile.data) > 0


def test_convert_file_creates_output(converter, tmp_path):
    profile = converter.prepare_profile("ref.wav")
    out = str(tmp_path / "out.wav")
    converter.convert_file("src.wav", profile, _params(), out)
    assert os.path.exists(out)
    assert os.path.getsize(out) > 0


def test_headless_end_to_end(converter, tmp_path):
    profile = converter.prepare_profile("reference.wav")
    out = str(tmp_path / "result.wav")
    converter.convert_file("source.wav", profile, _params(), out)
    assert os.path.exists(out)


def test_progress_callbacks_fire(converter, tmp_path):
    profile = converter.prepare_profile("ref.wav")
    fractions: list[float] = []
    out = str(tmp_path / "out.wav")
    converter.convert_file(
        "src.wav", profile, _params(), out, progress=fractions.append
    )
    assert len(fractions) > 0
    assert all(0.0 <= f <= 1.0 for f in fractions)
    assert fractions[-1] == pytest.approx(1.0)


def test_cancel_mid_convert_raises(engine, tmp_path):
    rng = np.random.default_rng(1)
    long_pcm = rng.uniform(-0.1, 0.1, 22050 * 20).astype(np.float32)
    conv = Converter(engine, _MockPcmLoader(pcm=long_pcm), StdlibWavEncoder())

    profile = conv.prepare_profile("ref.wav")
    token = CancelToken()
    out = str(tmp_path / "out.wav")

    result: list[Exception] = []

    def _run():
        try:
            conv.convert_file("src.wav", profile, _params(), out, cancel_token=token)
        except Exception as exc:
            result.append(exc)

    t = threading.Thread(target=_run)
    t.start()
    time.sleep(0.05)
    token.cancel()
    t.join(timeout=10.0)

    assert len(result) == 1
    assert isinstance(result[0], CancelledError)


def test_vram_release_after_cancel(engine, tmp_path):
    rng = np.random.default_rng(2)
    long_pcm = rng.uniform(-0.1, 0.1, 22050 * 20).astype(np.float32)
    conv = Converter(engine, _MockPcmLoader(pcm=long_pcm), StdlibWavEncoder())

    profile = conv.prepare_profile("ref.wav")
    token = CancelToken()
    out = str(tmp_path / "out.wav")

    def _run():
        try:
            conv.convert_file("src.wav", profile, _params(), out, cancel_token=token)
        except CancelledError:
            pass

    t = threading.Thread(target=_run)
    t.start()
    time.sleep(0.05)
    token.cancel()
    t.join(timeout=10.0)

    # After cancel, release + re-warmup must succeed (no VRAM leak or deadlock)
    engine.release()
    engine.warmup("cpu")

    # Engine is functional again — prepare_profile should work
    profile2 = conv.prepare_profile("ref2.wav")
    assert profile2.engine_id == "mock"


def test_reuse_profile_for_two_sources(converter, tmp_path):
    profile = converter.prepare_profile("ref.wav")
    out1 = str(tmp_path / "out1.wav")
    out2 = str(tmp_path / "out2.wav")
    converter.convert_file("src1.wav", profile, _params(), out1)
    converter.convert_file("src2.wav", profile, _params(), out2)
    assert os.path.exists(out1)
    assert os.path.exists(out2)
