"""End-to-end integration tests: real files through the full pipeline.

All tests use WorkerAdapter("mock") + FfmpegLoader + FfmpegEncoder.
Skipped when ffmpeg is not available.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from tests.integration.conftest import make_wav, needs_ffmpeg
from voiceconv.audio._codec import FfmpegEncoder, FfmpegLoader
from voiceconv.inference.engine import CancelledError, CancelToken, ConvertParams
from voiceconv.inference.worker_adapter import WorkerAdapter
from voiceconv.services.converter import Converter


def _make_converter() -> tuple[WorkerAdapter, Converter]:
    engine = WorkerAdapter("mock")
    engine.warmup()
    converter = Converter(engine, FfmpegLoader(target_sample_rate=22050), FfmpegEncoder())
    return engine, converter


@needs_ffmpeg
def test_e2e_mock_roundtrip(tmp_path):
    ref = make_wav(tmp_path / "ref.wav", duration_sec=2.0)
    src = make_wav(tmp_path / "src.wav", duration_sec=1.5, freq_hz=660.0)
    out = str(tmp_path / "out.wav")

    engine, converter = _make_converter()
    try:
        artifacts = converter.prepare_profile(str(ref))
        converter.convert_file(str(src), artifacts, ConvertParams(target_sample_rate=22050), out)
    finally:
        engine.release()

    assert Path(out).exists(), "output file was not created"
    assert Path(out).stat().st_size > 44, "output is empty (just WAV header)"


@needs_ffmpeg
def test_e2e_progress_callbacks_fire(tmp_path):
    ref = make_wav(tmp_path / "ref.wav", duration_sec=1.0)
    src = make_wav(tmp_path / "src.wav", duration_sec=1.0)
    out = str(tmp_path / "out.wav")

    ticks: list[float] = []
    engine, converter = _make_converter()
    try:
        artifacts = converter.prepare_profile(str(ref))
        converter.convert_file(
            str(src), artifacts, ConvertParams(22050), out, progress=ticks.append
        )
    finally:
        engine.release()

    assert len(ticks) >= 1, "no progress callbacks received"
    assert all(0.0 <= v <= 1.0 for v in ticks), "progress values out of range"
    assert ticks == sorted(ticks), "progress callbacks not monotonically increasing"
    assert ticks[-1] == pytest.approx(1.0), "last progress tick should be 1.0"


@needs_ffmpeg
def test_e2e_cancel_mid_conversion(tmp_path):
    ref = make_wav(tmp_path / "ref.wav", duration_sec=1.0)
    src = make_wav(tmp_path / "src.wav", duration_sec=2.0)
    out = str(tmp_path / "out.wav")

    token = CancelToken()
    engine, converter = _make_converter()

    error_holder: list[Exception] = []

    def _convert():
        try:
            artifacts = converter.prepare_profile(str(ref))
            converter.convert_file(
                str(src), artifacts, ConvertParams(22050), out,
                cancel_token=token,
            )
        except CancelledError as exc:
            error_holder.append(exc)
        finally:
            engine.release()

    t = threading.Thread(target=_convert)
    t.start()

    # Cancel after the first progress tick
    import time
    time.sleep(0.05)
    token.cancel()
    t.join(timeout=10)

    assert not t.is_alive(), "conversion thread did not finish after cancel"
    assert len(error_holder) == 1, "CancelledError was not raised"
    assert not Path(out).exists() or Path(out).stat().st_size <= 44, (
        "output file should not be fully written after cancel"
    )


@needs_ffmpeg
def test_e2e_flac_output(tmp_path):
    ref = make_wav(tmp_path / "ref.wav", duration_sec=1.0)
    src = make_wav(tmp_path / "src.wav", duration_sec=1.0)
    out = str(tmp_path / "out.flac")

    engine, converter = _make_converter()
    try:
        artifacts = converter.prepare_profile(str(ref))
        converter.convert_file(str(src), artifacts, ConvertParams(22050), out)
    finally:
        engine.release()

    assert Path(out).exists(), "FLAC output file was not created"
    assert Path(out).stat().st_size > 0
