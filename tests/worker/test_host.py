"""Unit tests for the worker host dispatch loop.

These tests exercise host.run() directly, feeding requests via BytesIO and
capturing responses — no subprocess is spawned.  The mock engine in the
REGISTRY is used so the tests run without real model weights.
"""

from __future__ import annotations

import io

import numpy as np
import pytest

from voiceconv.inference.ipc import read_msg, write_msg
from voiceconv.worker import host


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _host_session(*requests: dict, allowed_engine: str | None = None) -> list[dict]:
    """Run host.run() with the given requests and return all responses."""
    stdin_buf = io.BytesIO()
    for req in requests:
        write_msg(stdin_buf, req)
    stdin_buf.seek(0)
    stdout_buf = io.BytesIO()

    host.run(stdin=stdin_buf, stdout=stdout_buf, allowed_engine=allowed_engine)

    stdout_buf.seek(0)
    responses: list[dict] = []
    try:
        while True:
            responses.append(read_msg(stdout_buf))
    except EOFError:
        pass
    return responses


# ---------------------------------------------------------------------------
# Tests — basic dispatch
# ---------------------------------------------------------------------------


def test_unknown_engine():
    responses = _host_session(
        {"id": "r1", "cmd": "warmup", "device": "cpu", "engine": "nonexistent"},
    )
    assert len(responses) == 1
    assert responses[0]["type"] == "error"
    assert responses[0]["id"] == "r1"
    assert responses[0]["code"] == "UNKNOWN_ENGINE"


def test_warmup_mock():
    responses = _host_session(
        {"id": "r1", "cmd": "warmup", "device": "cpu", "engine": "mock"},
    )
    assert responses == [{"id": "r1", "type": "ok"}]


def test_allowed_engine_mismatch():
    responses = _host_session(
        {"id": "r1", "cmd": "warmup", "device": "cpu", "engine": "mock"},
        allowed_engine="openvoice_v2",
    )
    assert responses[0]["type"] == "error"
    assert responses[0]["code"] == "ENGINE_MISMATCH"


def test_allowed_engine_match():
    responses = _host_session(
        {"id": "r1", "cmd": "warmup", "device": "cpu", "engine": "mock"},
        allowed_engine="mock",
    )
    assert responses[0]["type"] == "ok"


def test_release_without_warmup():
    responses = _host_session({"id": "r1", "cmd": "release"})
    assert responses == [{"id": "r1", "type": "ok"}]


def test_warmup_and_release():
    responses = _host_session(
        {"id": "r1", "cmd": "warmup", "device": "cpu", "engine": "mock"},
        {"id": "r2", "cmd": "release"},
    )
    assert [r["type"] for r in responses] == ["ok", "ok"]


def test_unknown_command():
    responses = _host_session({"id": "r1", "cmd": "fly_to_moon"})
    assert responses[0]["type"] == "error"
    assert responses[0]["code"] == "UNKNOWN_CMD"


def test_prepare_profile_before_warmup():
    responses = _host_session(
        {"id": "r1", "cmd": "prepare_profile",
         "shm_name": "x", "shm_size": 4, "n_samples": 1, "sample_rate": 22050},
    )
    assert responses[0]["type"] == "error"
    assert responses[0]["code"] == "NOT_WARMED"


def test_convert_before_warmup():
    responses = _host_session(
        {"id": "r1", "cmd": "convert",
         "shm_src_name": "x", "shm_src_size": 4,
         "shm_out_name": "y", "shm_out_size": 4,
         "n_src_samples": 1, "sample_rate": 22050,
         "profile_b64": "AAAA", "engine_id": "mock", "engine_version": "0.1",
         "target_sample_rate": 22050, "extra": {}},
    )
    assert responses[0]["type"] == "error"
    assert responses[0]["code"] == "NOT_WARMED"
