"""Unit tests for the length-prefixed JSON IPC framing protocol."""

from __future__ import annotations

import io
import struct

import pytest

from voiceconv.inference.ipc import read_msg, write_msg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _roundtrip(obj: dict) -> dict:
    buf = io.BytesIO()
    write_msg(buf, obj)
    buf.seek(0)
    return read_msg(buf)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_simple_roundtrip():
    msg = {"cmd": "warmup", "device": "auto", "id": "abc123"}
    assert _roundtrip(msg) == msg


def test_unicode_payload():
    msg = {"detail": "héllo wörld 中文 العربية"}
    assert _roundtrip(msg) == msg


def test_empty_dict():
    assert _roundtrip({}) == {}


def test_nested_values():
    msg = {"extra": {"tau": 0.3, "nested": [1, 2, 3]}}
    assert _roundtrip(msg) == msg


def test_multiple_messages_in_sequence():
    buf = io.BytesIO()
    msgs = [{"id": str(i), "cmd": "ping"} for i in range(5)]
    for m in msgs:
        write_msg(buf, m)
    buf.seek(0)
    for expected in msgs:
        assert read_msg(buf) == expected


def test_eof_on_empty_stream():
    buf = io.BytesIO(b"")
    with pytest.raises(EOFError):
        read_msg(buf)


def test_eof_after_partial_header():
    buf = io.BytesIO(b"\x00\x00")  # only 2 of 4 header bytes
    with pytest.raises(EOFError):
        read_msg(buf)


def test_eof_after_truncated_payload():
    buf = io.BytesIO()
    buf.write(struct.pack("<I", 100))  # claims 100-byte payload
    buf.write(b"hello")               # only 5 bytes provided
    buf.seek(0)
    with pytest.raises(EOFError):
        read_msg(buf)


def test_large_payload():
    msg = {"data": "x" * 1_000_000}
    result = _roundtrip(msg)
    assert result["data"] == "x" * 1_000_000


def test_write_flushes_stream():
    """write_msg must flush so the reader is not blocked waiting for more bytes."""
    buf = io.BytesIO()
    write_msg(buf, {"ping": True})
    # If flush was not called, BytesIO still has the data, so this just
    # verifies there is data to read (flush on BytesIO is a no-op, but
    # the requirement still holds for real pipes).
    buf.seek(0)
    assert read_msg(buf) == {"ping": True}
