"""Worker process main dispatch loop.

Reads length-prefixed JSON requests from stdin, dispatches to the active
engine adapter, and writes responses back to stdout.  Diagnostic logging
goes to stderr, which is inherited from the parent process.

The convert() operation runs in a background thread so the main loop can
continue reading stdin and receive a ``cancel`` message while the model is
running.  A threading.Event bridges the cancel message → CancelToken.check()
inside the engine.

stdout writes from both the main thread and the convert thread are serialised
by ``_stdout_lock``.
"""

from __future__ import annotations

import base64
import logging
import sys
import threading
from typing import Any, BinaryIO, Optional

import numpy as np

from voiceconv.inference.engine import (
    CancelToken,
    CancelledError,
    ConvertParams,
    EngineError,
    ProfileArtifacts,
)
from voiceconv.inference.ipc import read_msg, write_msg
from voiceconv.inference.shm_buffer import ShmBuffer
from voiceconv.worker.engines import REGISTRY

log = logging.getLogger(__name__)


def run(
    stdin: Optional[BinaryIO] = None,
    stdout: Optional[BinaryIO] = None,
    *,
    allowed_engine: Optional[str] = None,
) -> None:
    """Block serving requests until stdin is closed or a fatal error occurs.

    Parameters
    ----------
    stdin / stdout:
        Overrides for sys.stdin.buffer / sys.stdout.buffer.  Used in tests.
    allowed_engine:
        If set, reject ``warmup`` requests for any other engine ID.
        Set to the ``--engine`` CLI argument in production.
    """
    _stdin: BinaryIO = stdin if stdin is not None else sys.stdin.buffer
    _stdout: BinaryIO = stdout if stdout is not None else sys.stdout.buffer
    _stdout_lock = threading.Lock()

    engine: Optional[Any] = None
    _current_cancel: Optional[CancelToken] = None

    def send(obj: dict[str, Any]) -> None:
        with _stdout_lock:
            write_msg(_stdout, obj)

    def send_ok(req_id: str) -> None:
        send({"id": req_id, "type": "ok"})

    def send_error(req_id: str, code: str, detail: str) -> None:
        send({"id": req_id, "type": "error", "code": code, "detail": detail})

    while True:
        try:
            req = read_msg(_stdin)
        except EOFError:
            log.debug("stdin closed — worker shutting down")
            break

        req_id: str = req.get("id", "")
        cmd: str = req.get("cmd", "")
        log.debug("recv cmd=%s id=%s", cmd, req_id)

        try:
            if cmd == "warmup":
                engine_id: str = req.get("engine", "")
                if allowed_engine is not None and engine_id != allowed_engine:
                    send_error(
                        req_id,
                        "ENGINE_MISMATCH",
                        f"this worker only serves {allowed_engine!r}, got {engine_id!r}",
                    )
                    continue
                if engine_id not in REGISTRY:
                    send_error(req_id, "UNKNOWN_ENGINE", f"unknown engine: {engine_id!r}")
                    continue
                engine = REGISTRY[engine_id]()
                engine.warmup(req.get("device", "auto"))
                send_ok(req_id)

            elif cmd == "prepare_profile":
                if engine is None:
                    send_error(req_id, "NOT_WARMED", "call warmup before prepare_profile")
                    continue
                with ShmBuffer.attach(req["shm_name"], req["shm_size"]) as shm:
                    pcm = shm.as_ndarray("float32", (req["n_samples"],)).copy()
                profile = engine.prepare_profile(pcm, req["sample_rate"])
                send({
                    "id": req_id,
                    "type": "profile",
                    "data_b64": base64.b64encode(profile.data).decode(),
                    "engine_id": profile.engine_id,
                    "engine_version": profile.engine_version,
                    "metadata": profile.metadata,
                })

            elif cmd == "convert":
                if engine is None:
                    send_error(req_id, "NOT_WARMED", "call warmup before convert")
                    continue

                cancel_token = CancelToken()
                _current_cancel = cancel_token

                profile = ProfileArtifacts(
                    engine_id=req["engine_id"],
                    engine_version=req["engine_version"],
                    data=base64.b64decode(req["profile_b64"]),
                )
                params = ConvertParams(
                    target_sample_rate=req["target_sample_rate"],
                    device=req.get("device", "auto"),
                    extra=req.get("extra", {}),
                )
                n_src: int = req["n_src_samples"]
                sample_rate: int = req["sample_rate"]
                shm_src_name: str = req["shm_src_name"]
                shm_src_size: int = req["shm_src_size"]
                shm_out_name: str = req["shm_out_name"]
                shm_out_size: int = req["shm_out_size"]

                def _run_convert(
                    *,
                    _req_id: str = req_id,
                    _profile: ProfileArtifacts = profile,
                    _params: ConvertParams = params,
                    _n_src: int = n_src,
                    _sr: int = sample_rate,
                    _src_name: str = shm_src_name,
                    _src_size: int = shm_src_size,
                    _out_name: str = shm_out_name,
                    _out_size: int = shm_out_size,
                    _tok: CancelToken = cancel_token,
                ) -> None:
                    nonlocal _current_cancel
                    try:
                        with ShmBuffer.attach(_src_name, _src_size) as src_buf:
                            src = src_buf.as_ndarray("float32", (_n_src,)).copy()

                        def _progress(f: float) -> None:
                            send({"id": _req_id, "type": "progress", "fraction": f})

                        out = engine.convert(
                            src, _sr, _profile, _params,
                            progress=_progress,
                            cancel_token=_tok,
                        )

                        max_out = _out_size // 4  # max float32 samples that fit
                        n_out = len(out)
                        if n_out > max_out:
                            log.warning(
                                "output length %d exceeds shm capacity %d; truncating",
                                n_out, max_out,
                            )
                            n_out = max_out
                        with ShmBuffer.attach(_out_name, _out_size) as out_buf:
                            out_buf.as_ndarray("float32", (n_out,))[:] = out[:n_out]

                        send({"id": _req_id, "type": "convert_ok", "n_out_samples": n_out})

                    except CancelledError:
                        send({"id": _req_id, "type": "cancelled"})
                    except EngineError as exc:
                        send_error(_req_id, exc.code, str(exc))
                    except Exception as exc:
                        log.exception("unexpected error in convert thread")
                        send_error(_req_id, "MODEL_ERROR", str(exc))
                    finally:
                        _current_cancel = None

                threading.Thread(target=_run_convert, daemon=True).start()
                # Main loop continues — next iteration will read cancel or other cmds.

            elif cmd == "cancel":
                tok = _current_cancel
                if tok is not None:
                    tok.cancel()
                # No response here; the convert thread sends the cancelled message.

            elif cmd == "release":
                if engine is not None:
                    engine.release()
                    engine = None
                send_ok(req_id)

            else:
                send_error(req_id, "UNKNOWN_CMD", f"unknown command: {cmd!r}")

        except EngineError as exc:
            send_error(req_id, exc.code, str(exc))
        except Exception as exc:
            log.exception("unhandled error dispatching cmd=%s", cmd)
            send_error(req_id, "INTERNAL_ERROR", str(exc))
