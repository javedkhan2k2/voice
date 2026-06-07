"""Length-prefixed JSON message framing for the inference worker IPC channel.

Wire format:  [ uint32 LE (4 bytes) ][ UTF-8 JSON payload ]

Reads and writes are blocking and must be called from a single thread per
stream direction (one thread reads stdout; one thread writes stdin).
"""

from __future__ import annotations

import json
import struct
from typing import Any, BinaryIO

_HEADER = struct.Struct("<I")  # 4-byte little-endian uint32


def write_msg(stream: BinaryIO, obj: dict[str, Any]) -> None:
    """Encode *obj* as JSON and write a framed message to *stream*."""
    payload = json.dumps(obj, separators=(",", ":")).encode()
    stream.write(_HEADER.pack(len(payload)))
    stream.write(payload)
    stream.flush()


def read_msg(stream: BinaryIO) -> dict[str, Any]:
    """Read one framed message from *stream* and return the decoded dict.

    Raises
    ------
    EOFError
        When the stream is closed before a complete message is received.
    json.JSONDecodeError
        If the payload is not valid JSON.
    """
    header_bytes = _read_exactly(stream, _HEADER.size)
    (length,) = _HEADER.unpack(header_bytes)
    payload = _read_exactly(stream, length)
    return json.loads(payload.decode())


def _read_exactly(stream: BinaryIO, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = stream.read(n - len(buf))
        if not chunk:
            raise EOFError(
                f"stream closed after {len(buf)}/{n} bytes"
            )
        buf.extend(chunk)
    return bytes(buf)
