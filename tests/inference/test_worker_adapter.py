"""Integration tests for WorkerAdapter: spawn → warmup → prepare → convert → release.

These tests spawn a real worker subprocess using the mock engine, so they run
without model weights installed.  Mark with @pytest.mark.integration if you
want to exclude them from a fast unit-test run.
"""

from __future__ import annotations

import threading
import time

import numpy as np
import pytest

from voiceconv.inference.engine import CancelToken, CancelledError, ConvertParams
from voiceconv.inference.worker_adapter import WorkerAdapter

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SR = 22050  # sample rate used throughout


@pytest.fixture
def adapter():
    """WorkerAdapter backed by the mock engine; terminates on test teardown."""
    a = WorkerAdapter("mock")
    yield a
    a.terminate()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_warmup_and_release(adapter):
    adapter.warmup("cpu")
    adapter.release()


def test_double_warmup_is_idempotent(adapter):
    adapter.warmup("cpu")
    adapter.warmup("cpu")  # second warmup on an already-warm engine must not raise


def test_release_before_warmup_is_safe(adapter):
    adapter.release()  # should not raise


def test_capabilities_returns_mock(adapter):
    caps = adapter.capabilities()
    assert caps.engine_id == "mock"


def test_prepare_profile(adapter):
    adapter.warmup("cpu")
    ref = np.random.randn(SR).astype(np.float32)  # 1 second
    profile = adapter.prepare_profile(ref, SR)
    assert profile.engine_id == "mock"
    assert len(profile.data) > 0


def test_convert_returns_same_length(adapter):
    adapter.warmup("cpu")
    ref = np.random.randn(SR).astype(np.float32)
    profile = adapter.prepare_profile(ref, SR)

    src = np.random.randn(SR * 2).astype(np.float32)  # 2 seconds
    params = ConvertParams(target_sample_rate=SR, device="cpu")
    out = adapter.convert(src, SR, profile, params)

    assert out.dtype == np.float32
    assert len(out) == len(src)


def test_convert_with_progress_callbacks(adapter):
    adapter.warmup("cpu")
    ref = np.random.randn(SR).astype(np.float32)
    profile = adapter.prepare_profile(ref, SR)

    src = np.random.randn(SR * 3).astype(np.float32)
    params = ConvertParams(target_sample_rate=SR, device="cpu")

    received: list[float] = []
    adapter.convert(src, SR, profile, params, progress=received.append)

    assert len(received) > 0
    assert all(0.0 <= p <= 1.0 for p in received)
    assert received[-1] == pytest.approx(1.0)


def test_cancel_raises_cancelled_error(adapter):
    adapter.warmup("cpu")
    ref = np.random.randn(SR).astype(np.float32)
    profile = adapter.prepare_profile(ref, SR)

    # 30-second source gives the mock engine ~300 ms of work to cancel.
    src = np.random.randn(SR * 30).astype(np.float32)
    params = ConvertParams(target_sample_rate=SR, device="cpu")

    cancel_token = CancelToken()

    def _cancel_after() -> None:
        time.sleep(0.1)
        cancel_token.cancel()

    threading.Thread(target=_cancel_after, daemon=True).start()

    with pytest.raises(CancelledError):
        adapter.convert(src, SR, profile, params, cancel_token=cancel_token)


def test_convert_after_release_then_rewarm(adapter):
    adapter.warmup("cpu")
    ref = np.random.randn(SR).astype(np.float32)
    profile = adapter.prepare_profile(ref, SR)
    adapter.release()

    adapter.warmup("cpu")  # re-arm
    src = np.random.randn(SR).astype(np.float32)
    params = ConvertParams(target_sample_rate=SR, device="cpu")
    out = adapter.convert(src, SR, profile, params)
    assert len(out) == len(src)


def test_stereo_input_is_downmixed(adapter):
    adapter.warmup("cpu")
    ref = np.random.randn(SR).astype(np.float32)
    profile = adapter.prepare_profile(ref, SR)

    src_stereo = np.random.randn(SR, 2).astype(np.float32)
    params = ConvertParams(target_sample_rate=SR, device="cpu")
    out = adapter.convert(src_stereo, SR, profile, params)
    assert out.ndim == 1
