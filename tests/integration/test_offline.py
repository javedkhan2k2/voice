"""Offline invariant tests.

Verifies that the conversion pipeline opens no network sockets in the calling
process.  Skipped when ffmpeg is not available.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.integration.conftest import make_wav, needs_ffmpeg
from voiceconv.audio._codec import FfmpegEncoder, FfmpegLoader
from voiceconv.inference.engine import ConvertParams
from voiceconv.inference.worker_adapter import WorkerAdapter
from voiceconv.services.converter import Converter
from voiceconv.services.offline_check import (
    block_network,
    check_offline_invariant,
    verify_offline,
)


@needs_ffmpeg
def test_full_conversion_opens_no_sockets(tmp_path):
    ref = make_wav(tmp_path / "ref.wav", duration_sec=1.0)
    src = make_wav(tmp_path / "src.wav", duration_sec=1.0)
    out = str(tmp_path / "out.wav")

    engine = WorkerAdapter("mock")
    engine.warmup()
    converter = Converter(engine, FfmpegLoader(target_sample_rate=22050), FfmpegEncoder())
    artifacts = converter.prepare_profile(str(ref))

    def _convert():
        converter.convert_file(str(src), artifacts, ConvertParams(22050), out)

    check_offline_invariant(_convert)  # raises AssertionError if any socket opened
    engine.release()

    assert Path(out).exists()


def test_check_offline_invariant_catches_socket_usage():
    import socket

    def _open_socket():
        # Explicitly attempt to create a socket — invariant must catch this.
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.close()

    with pytest.raises(AssertionError, match="offline invariant violated"):
        check_offline_invariant(_open_socket)


def test_block_network_context_manager_blocks_and_restores():
    import socket

    with block_network():
        with pytest.raises(AssertionError, match="offline invariant violated"):
            socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Guard removed after the block — socket creation works again.
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.close()


def test_verify_offline_reports_ok():
    result = verify_offline()
    assert result.ok is True
    assert "no network" in result.detail.lower() or "device" in result.detail.lower()


def test_verify_offline_leaves_sockets_usable_afterwards():
    import socket

    verify_offline()
    # The self-check must restore normal socket behaviour.
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.close()
