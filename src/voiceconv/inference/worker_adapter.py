"""WorkerAdapter — concrete VoiceConversionEngine backed by an isolated subprocess.

The adapter owns the worker subprocess lifecycle, routes each method call to
an IPC message, manages shared-memory buffers for PCM payloads, and dispatches
progress callbacks to the caller while the convert is in flight.

Thread-safety: all public methods acquire ``_lock``, so concurrent calls from
different threads serialise safely.  Do not call convert() from two threads
simultaneously — the second call will block until the first completes.
"""

from __future__ import annotations

import base64
import logging
import os
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

# src/ directory containing the voiceconv package.
# Used to propagate the import path to the worker subprocess when the package
# is not yet installed (dev mode).  Once installed via the Inno Setup bundle,
# PYTHONPATH propagation is not needed.
_SRC_DIR = str(Path(__file__).resolve().parent.parent.parent)
from typing import Any, Callable, Optional

import numpy as np

from voiceconv.inference.engine import (
    CancelToken,
    CancelledError,
    ConvertParams,
    EngineCapabilities,
    EngineError,
    ProfileArtifacts,
    VoiceConversionEngine,
)
from voiceconv.inference.ipc import read_msg, write_msg
from voiceconv.inference.shm_buffer import ShmBuffer

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static capabilities table
# Maintained here to avoid importing from worker/ (layer boundary).
# TODO: replace with a "hello" handshake once pinned versions are known.
# ---------------------------------------------------------------------------

_STATIC_CAPABILITIES: dict[str, EngineCapabilities] = {
    "openvoice_v2": EngineCapabilities(
        engine_id="openvoice_v2",
        engine_version="2.0",  # TODO: query installed package
        supported_sample_rates=(22050, 44100),
        min_reference_duration_sec=3.0,
        max_reference_duration_sec=30.0,
        preferred_device="cuda",
    ),
    "freevc": EngineCapabilities(
        engine_id="freevc",
        engine_version="1.0",  # TODO: query installed package
        supported_sample_rates=(16000, 22050),
        min_reference_duration_sec=3.0,
        max_reference_duration_sec=30.0,
        preferred_device="cuda",
    ),
    "mock": EngineCapabilities(
        engine_id="mock",
        engine_version="0.1",
        supported_sample_rates=(16000, 22050, 44100),
        min_reference_duration_sec=0.1,
        max_reference_duration_sec=60.0,
        preferred_device="cpu",
    ),
}

# Safety multiplier for the output shared-memory pre-allocation.
# Worst case: target_rate >> source_rate.  For v1, target_rate == source_rate.
_OUT_SHM_SCALE = 2


def _new_id() -> str:
    return uuid.uuid4().hex


class WorkerAdapter(VoiceConversionEngine):
    """VoiceConversionEngine that runs the model in an isolated worker process.

    Parameters
    ----------
    engine_id:
        One of the engine IDs understood by the worker, e.g. ``"openvoice_v2"``.
    worker_args:
        Extra command-line arguments forwarded to the worker entry point.
    """

    def __init__(
        self,
        engine_id: str,
        worker_args: Optional[list[str]] = None,
    ) -> None:
        if engine_id not in _STATIC_CAPABILITIES:
            raise ValueError(f"unknown engine_id {engine_id!r}")
        self._engine_id = engine_id
        self._worker_args = worker_args or []
        self._proc: Optional[subprocess.Popen[bytes]] = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Subprocess lifecycle
    # ------------------------------------------------------------------

    def _ensure_running(self) -> subprocess.Popen[bytes]:
        """Return the worker process, starting it if necessary."""
        if self._proc is not None and self._proc.poll() is None:
            return self._proc
        log.debug("spawning worker --engine %s", self._engine_id)
        env = os.environ.copy()
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (_SRC_DIR + os.pathsep + existing) if existing else _SRC_DIR
        self._proc = subprocess.Popen(
            [sys.executable, "-m", "voiceconv.worker",
             "--engine", self._engine_id] + self._worker_args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,  # inherit parent's stderr so worker logs appear
            env=env,
        )
        return self._proc

    def _assert_alive(self) -> subprocess.Popen[bytes]:
        proc = self._proc
        if proc is None or proc.poll() is not None:
            code = proc.returncode if proc is not None else None
            raise EngineError(
                f"worker process is not running (returncode={code})",
                code="WORKER_DEAD",
            )
        return proc

    # ------------------------------------------------------------------
    # Low-level IPC helpers
    # ------------------------------------------------------------------

    def _send(self, obj: dict[str, Any]) -> None:
        proc = self._assert_alive()
        assert proc.stdin is not None
        write_msg(proc.stdin, obj)

    def _recv_until_final(
        self,
        req_id: str,
        *,
        progress: Optional[Callable[[float], None]] = None,
    ) -> dict[str, Any]:
        """Read worker responses until a final message for *req_id* arrives.

        Progress messages are dispatched to *progress* inline (on the calling
        thread).  Raises EngineError on error responses, CancelledError on
        cancelled responses, and EngineError(WORKER_CRASH) on premature EOF.
        """
        proc = self._assert_alive()
        assert proc.stdout is not None
        try:
            while True:
                msg = read_msg(proc.stdout)
                if msg.get("id") != req_id:
                    log.debug("skipping stale message id=%s", msg.get("id"))
                    continue
                t = msg["type"]
                if t == "progress":
                    if progress is not None:
                        progress(float(msg["fraction"]))
                    continue
                if t == "error":
                    raise EngineError(
                        msg.get("detail", "worker error"),
                        code=msg.get("code", "ENGINE_ERROR"),
                    )
                if t == "cancelled":
                    raise CancelledError("worker reported cancellation")
                return msg  # "ok", "profile", "convert_ok"
        except EOFError as exc:
            code = self._proc.poll() if self._proc is not None else None
            raise EngineError(
                f"worker exited unexpectedly (returncode={code})",
                code="WORKER_CRASH",
            ) from exc

    # ------------------------------------------------------------------
    # VoiceConversionEngine implementation
    # ------------------------------------------------------------------

    def capabilities(self) -> EngineCapabilities:
        return _STATIC_CAPABILITIES[self._engine_id]

    def warmup(self, device: str = "auto") -> None:
        with self._lock:
            self._ensure_running()
            req_id = _new_id()
            self._send({"id": req_id, "cmd": "warmup", "device": device,
                        "engine": self._engine_id})
            self._recv_until_final(req_id)
            log.debug("warmup complete engine=%s device=%s", self._engine_id, device)

    def prepare_profile(
        self,
        reference_pcm: np.ndarray,
        sample_rate: int,
    ) -> ProfileArtifacts:
        with self._lock:
            pcm = _to_float32_mono(reference_pcm)
            req_id = _new_id()
            with ShmBuffer.alloc(pcm.nbytes) as shm:
                shm.as_ndarray("float32", pcm.shape)[:] = pcm
                self._send({
                    "id": req_id,
                    "cmd": "prepare_profile",
                    "shm_name": shm.name,
                    "shm_size": shm.size,
                    "n_samples": len(pcm),
                    "sample_rate": sample_rate,
                })
                msg = self._recv_until_final(req_id)
            return ProfileArtifacts(
                engine_id=msg["engine_id"],
                engine_version=msg["engine_version"],
                data=base64.b64decode(msg["data_b64"]),
                metadata=msg.get("metadata", {}),
            )

    def convert(
        self,
        source_pcm: np.ndarray,
        sample_rate: int,
        profile: ProfileArtifacts,
        params: ConvertParams,
        *,
        progress: Optional[Callable[[float], None]] = None,
        cancel_token: Optional[CancelToken] = None,
    ) -> np.ndarray:
        with self._lock:
            src = _to_float32_mono(source_pcm)
            req_id = _new_id()

            # Pre-allocate output shm conservatively.
            out_bytes = src.nbytes * _OUT_SHM_SCALE

            stop_event = threading.Event()
            cancel_watcher: Optional[threading.Thread] = None

            with (
                ShmBuffer.alloc(src.nbytes) as shm_src,
                ShmBuffer.alloc(out_bytes) as shm_out,
            ):
                shm_src.as_ndarray("float32", src.shape)[:] = src

                self._send({
                    "id": req_id,
                    "cmd": "convert",
                    "shm_src_name": shm_src.name,
                    "shm_src_size": shm_src.size,
                    "shm_out_name": shm_out.name,
                    "shm_out_size": shm_out.size,
                    "n_src_samples": len(src),
                    "sample_rate": sample_rate,
                    "profile_b64": base64.b64encode(profile.data).decode(),
                    "engine_id": profile.engine_id,
                    "engine_version": profile.engine_version,
                    "target_sample_rate": params.target_sample_rate,
                    "device": params.device,
                    "extra": params.extra,
                })

                if cancel_token is not None:
                    cancel_watcher = threading.Thread(
                        target=self._watch_cancel,
                        args=(cancel_token, req_id, stop_event),
                        daemon=True,
                    )
                    cancel_watcher.start()

                try:
                    msg = self._recv_until_final(req_id, progress=progress)
                finally:
                    stop_event.set()
                    if cancel_watcher is not None:
                        cancel_watcher.join(timeout=0.5)

                n_out: int = msg["n_out_samples"]
                return shm_out.as_ndarray("float32", (n_out,)).copy()

    def _watch_cancel(
        self,
        token: CancelToken,
        req_id: str,
        stop_event: threading.Event,
    ) -> None:
        """Background thread: forward cancel signal to the worker when token fires."""
        while not token.is_cancelled and not stop_event.is_set():
            time.sleep(0.05)
        if token.is_cancelled and not stop_event.is_set():
            try:
                self._send({"id": _new_id(), "cmd": "cancel"})
            except Exception:
                pass  # worker may have already exited

    def release(self) -> None:
        with self._lock:
            if self._proc is None or self._proc.poll() is not None:
                return
            req_id = _new_id()
            try:
                self._send({"id": req_id, "cmd": "release"})
                self._recv_until_final(req_id)
            except (EngineError, EOFError):
                pass

    def terminate(self) -> None:
        """Hard-terminate the worker.  Call on app quit or after a crash."""
        proc = self._proc
        if proc is not None and proc.poll() is None:
            log.debug("terminating worker pid=%d", proc.pid)
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        self._proc = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_float32_mono(pcm: np.ndarray) -> np.ndarray:
    """Coerce *pcm* to float32 mono; downmix stereo by averaging channels."""
    arr = np.asarray(pcm, dtype=np.float32)
    if arr.ndim == 2:
        arr = arr.mean(axis=1)
    elif arr.ndim != 1:
        raise ValueError(f"PCM must be 1-D or 2-D, got shape {arr.shape}")
    return np.ascontiguousarray(arr)
