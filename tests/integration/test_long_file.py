"""Long-file and large-buffer handling tests.

These tests verify the shared-memory PCM transfer and worker subprocess can
handle large buffers without timeout or memory error.  They do NOT require
ffmpeg — they exercise WorkerAdapter directly with synthetic PCM arrays.

Note: true overlap-add chunking is internal to real engine adapters; these
tests validate that the mock engine and the PCM transfer layer handle 30-second
buffers correctly.  The same tests will cover real adapters once weights land.
"""

from __future__ import annotations

import numpy as np
import pytest

from voiceconv.inference.engine import CancelToken, ConvertParams
from voiceconv.inference.worker_adapter import WorkerAdapter

_SR = 22050
_DURATION_SEC = 30
_N_SAMPLES = _SR * _DURATION_SEC  # 661 500 samples ≈ 2.6 MB float32


@pytest.fixture(scope="module")
def warmed_engine():
    engine = WorkerAdapter("mock")
    engine.warmup()
    yield engine
    engine.release()


def test_large_buffer_returns_valid_array(warmed_engine):
    pcm = np.zeros(_N_SAMPLES, dtype=np.float32)
    artifacts = warmed_engine.prepare_profile(pcm, _SR)
    out = warmed_engine.convert(pcm, _SR, artifacts, ConvertParams(_SR))

    assert isinstance(out, np.ndarray)
    assert out.dtype == np.float32
    assert len(out) > 0


def test_large_buffer_progress_callbacks_fire(warmed_engine):
    pcm = np.zeros(_N_SAMPLES, dtype=np.float32)
    artifacts = warmed_engine.prepare_profile(pcm, _SR)

    ticks: list[float] = []
    warmed_engine.convert(pcm, _SR, artifacts, ConvertParams(_SR), progress=ticks.append)

    assert len(ticks) >= 2, "expected multiple progress callbacks for a 30-second buffer"
    assert ticks[-1] == pytest.approx(1.0)


def test_large_buffer_cancel_respects_token(warmed_engine):
    import threading, time

    pcm = np.zeros(_N_SAMPLES, dtype=np.float32)
    artifacts = warmed_engine.prepare_profile(pcm, _SR)
    token = CancelToken()

    from voiceconv.inference.engine import CancelledError

    result: list[str] = []

    def _run():
        try:
            warmed_engine.convert(pcm, _SR, artifacts, ConvertParams(_SR), cancel_token=token)
            result.append("done")
        except CancelledError:
            result.append("cancelled")

    t = threading.Thread(target=_run)
    t.start()
    time.sleep(0.05)
    token.cancel()
    t.join(timeout=15)

    assert not t.is_alive()
    assert result == ["cancelled"]
