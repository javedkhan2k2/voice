"""Output provenance marker (Phase 3 M2).

Every file this tool generates carries a recoverable marker in its container
metadata identifying it as AI voice-converted by this tool. This is a
non-negotiable safeguard (``CLAUDE.md``): there is no toggle.

The marker is stored as literal UTF-8 text in standard container tags:

- **WAV:** RIFF ``LIST``/``INFO`` chunk — ``ICMT`` (comment) and ``ISFT``
  (software). Written by ffmpeg's ``-metadata`` for the production encoder, or
  by :func:`build_wav_info_chunk` for the stdlib fallback encoder.
- **FLAC:** Vorbis ``COMMENT`` / ``ENCODED_BY`` fields via ffmpeg ``-metadata``.

Because the marker is stored verbatim, :func:`file_has_provenance` can verify
any supported container by scanning the bytes — no ffmpeg/ffprobe required.

Limitation: container metadata can be stripped by re-encoding the file in
another tool. A durable, signal-domain watermark is evaluated separately in
Phase 3 M4; this metadata marker is the guaranteed baseline.
"""

from __future__ import annotations

import struct
from pathlib import Path

from voiceconv import __version__

# Stable, documented token. Detecting this string in a file's metadata is the
# provenance check. Do not change without bumping the documented format.
PROVENANCE_MARKER = "AI voice-converted by VoiceBuilder"

_TOOL = f"VoiceBuilder {__version__}"


def provenance_comment() -> str:
    """Human-readable provenance statement embedded as the file comment."""
    return (
        f"{PROVENANCE_MARKER} v{__version__}. Synthetic audio produced by voice "
        f"conversion; not an authentic recording of the named speaker."
    )


def provenance_tags() -> dict[str, str]:
    """Container metadata tags to embed. Keys are ffmpeg/Vorbis tag names."""
    return {
        "comment": provenance_comment(),
        "encoded_by": _TOOL,
    }


def ffmpeg_metadata_args() -> list[str]:
    """Flatten :func:`provenance_tags` into ffmpeg ``-metadata key=value`` args."""
    args: list[str] = []
    for key, value in provenance_tags().items():
        args += ["-metadata", f"{key}={value}"]
    return args


# ---------------------------------------------------------------------------
# RIFF INFO chunk (stdlib WAV encoder path — no ffmpeg)
# ---------------------------------------------------------------------------


def _info_subchunk(chunk_id: bytes, text: str) -> bytes:
    """One RIFF INFO subchunk: id + size + null-terminated, word-aligned text."""
    data = text.encode("utf-8") + b"\x00"
    size = len(data)
    if size % 2:  # RIFF chunks are word-aligned; pad byte is not counted in size
        data += b"\x00"
    return chunk_id + struct.pack("<I", size) + data


def build_wav_info_chunk() -> bytes:
    """Build a ``LIST``/``INFO`` chunk carrying the provenance tags."""
    body = (
        b"INFO"
        + _info_subchunk(b"ICMT", provenance_comment())
        + _info_subchunk(b"ISFT", _TOOL)
    )
    return b"LIST" + struct.pack("<I", len(body)) + body


def append_info_chunk(wav_bytes: bytes) -> bytes:
    """Append the provenance INFO chunk to a complete WAV and fix the RIFF size.

    The input must be a canonical RIFF/WAVE byte string (e.g. produced by the
    stdlib ``wave`` module). The data chunk is left untouched, so the result is
    still a valid WAV with identical audio frames.
    """
    new = wav_bytes + build_wav_info_chunk()
    riff_size = len(new) - 8  # RIFF size field excludes the 'RIFF' + size words
    return new[:4] + struct.pack("<I", riff_size) + new[8:]


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def file_has_provenance(path: str | Path) -> bool:
    """Return True if *path* contains the provenance marker in its metadata.

    Container-agnostic: the marker is stored as literal UTF-8 in WAV INFO and
    FLAC Vorbis comments, so a byte-presence check is reliable without ffmpeg.
    """
    try:
        data = Path(path).read_bytes()
    except OSError:
        return False
    return PROVENANCE_MARKER.encode("utf-8") in data
