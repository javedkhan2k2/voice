"""Output-provenance tests (Phase 3 M2).

The stdlib-encoder path is deterministic and ffmpeg-free, so it carries the
core guarantees. FfmpegEncoder cases are guarded by ``needs_ffmpeg``.
"""

from __future__ import annotations

import os
import shutil
import wave

import numpy as np
import pytest

from voiceconv import __version__
from voiceconv.audio._provenance import (
    PROVENANCE_MARKER,
    append_info_chunk,
    build_wav_info_chunk,
    ffmpeg_metadata_args,
    file_has_provenance,
    provenance_tags,
)
from voiceconv.services._audio_encoder import StdlibWavEncoder

_FFMPEG = os.environ.get("VOICECONV_FFMPEG_PATH") or shutil.which("ffmpeg")
needs_ffmpeg = pytest.mark.skipif(_FFMPEG is None, reason="ffmpeg not available")


def _sine(sr: int = 22050, duration: float = 0.2) -> np.ndarray:
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    return (0.5 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)


# ---------------------------------------------------------------------------
# Marker / tags
# ---------------------------------------------------------------------------


def test_provenance_tags_include_marker_and_version():
    tags = provenance_tags()
    assert PROVENANCE_MARKER in tags["comment"]
    assert __version__ in tags["comment"]
    assert __version__ in tags["encoded_by"]


def test_ffmpeg_metadata_args_well_formed():
    args = ffmpeg_metadata_args()
    # Alternating -metadata / key=value pairs.
    assert args[0] == "-metadata"
    assert any(a.startswith("comment=") and PROVENANCE_MARKER in a for a in args)
    assert len(args) % 2 == 0


def test_info_chunk_structure():
    chunk = build_wav_info_chunk()
    assert chunk[:4] == b"LIST"
    assert b"INFO" in chunk
    assert b"ICMT" in chunk and b"ISFT" in chunk
    assert PROVENANCE_MARKER.encode() in chunk


# ---------------------------------------------------------------------------
# Stdlib WAV encoder (production-independent guarantee)
# ---------------------------------------------------------------------------


def test_stdlib_encoder_embeds_provenance(tmp_path):
    out = str(tmp_path / "out.wav")
    StdlibWavEncoder().encode(_sine(), 22050, out)
    assert file_has_provenance(out)


def test_stdlib_output_is_still_valid_wav_with_same_frames(tmp_path):
    pcm = _sine()
    out = str(tmp_path / "out.wav")
    StdlibWavEncoder().encode(pcm, 22050, out)

    with wave.open(out, "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 22050
        frames = wf.readframes(wf.getnframes())
    expected = (np.clip(pcm, -1.0, 1.0) * 32767.0).astype(np.int16).tobytes()
    assert frames == expected


def test_plain_wav_has_no_provenance(tmp_path):
    """A WAV written without the chunk must NOT report provenance — proving the
    check is meaningful, not always-true."""
    pcm = _sine()
    out = str(tmp_path / "plain.wav")
    int16 = (np.clip(pcm, -1.0, 1.0) * 32767.0).astype(np.int16)
    with wave.open(out, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(22050)
        wf.writeframes(int16.tobytes())
    assert not file_has_provenance(out)


def test_provenance_survives_export_copy(tmp_path):
    """Preview 'Export' is a byte copy (shutil.copy2); provenance must survive."""
    src = str(tmp_path / "converted.wav")
    StdlibWavEncoder().encode(_sine(), 22050, src)
    dest = str(tmp_path / "exported.wav")
    shutil.copy2(src, dest)
    assert file_has_provenance(dest)


def test_append_info_chunk_patches_riff_size(tmp_path):
    pcm = _sine()
    int16 = (np.clip(pcm, -1.0, 1.0) * 32767.0).astype(np.int16)
    import io
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(22050)
        wf.writeframes(int16.tobytes())
    out = append_info_chunk(buf.getvalue())
    import struct
    declared = struct.unpack("<I", out[4:8])[0]
    assert declared == len(out) - 8


def test_file_has_provenance_missing_file():
    assert file_has_provenance("does/not/exist.wav") is False


# ---------------------------------------------------------------------------
# FfmpegEncoder (production encoder) — guarded
# ---------------------------------------------------------------------------


@needs_ffmpeg
def test_ffmpeg_wav_has_provenance(tmp_path):
    from voiceconv.audio._codec import FfmpegEncoder

    out = str(tmp_path / "out.wav")
    FfmpegEncoder().encode(_sine(), 22050, out)
    assert file_has_provenance(out)


@needs_ffmpeg
def test_ffmpeg_flac_has_provenance(tmp_path):
    from voiceconv.audio._codec import FfmpegEncoder

    out = str(tmp_path / "out.flac")
    FfmpegEncoder().encode(_sine(), 22050, out)
    assert file_has_provenance(out)
