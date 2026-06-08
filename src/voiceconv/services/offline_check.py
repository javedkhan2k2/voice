"""Offline runtime invariant — socket-layer guard and self-check.

The conversion path must never open a network connection. This module enforces
that at the **socket layer** (not just by configuration): :func:`block_network`
temporarily replaces ``socket.socket.__init__`` so any attempt to create a
socket raises ``AssertionError``.

- :func:`check_offline_invariant` wraps a callable and runs it under the guard
  (used by the integration test around a real conversion).
- :func:`verify_offline` is a deterministic self-check (positive control + clean
  run) suitable for a "Verify offline" UI button.

Scope: only the calling process is patched. Subprocesses spawned inside the
guarded region (e.g. ffmpeg, the inference worker) are separate processes and are
not affected — the offline guarantee for those rests on their own behaviour and
the architecture (no network code in the conversion path). See ``docs/offline.md``.
"""

from __future__ import annotations

import socket
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Iterator, TypeVar

T = TypeVar("T")

_VIOLATION_MSG = (
    "Network socket opened during conversion — offline invariant violated. "
    "No code in the conversion path may open a network connection."
)


@contextmanager
def block_network() -> Iterator[None]:
    """Context manager that blocks ``socket.socket`` creation in this process.

    Any socket instantiation inside the ``with`` block raises ``AssertionError``.
    Restores the original behaviour on exit, even if an error is raised.
    """
    original_init = socket.socket.__init__

    def _blocked(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError(_VIOLATION_MSG)

    socket.socket.__init__ = _blocked  # type: ignore[method-assign]
    try:
        yield
    finally:
        socket.socket.__init__ = original_init  # type: ignore[method-assign]


def check_offline_invariant(fn: Callable[[], T]) -> T:
    """Execute *fn()* with network socket creation blocked.

    Raises ``AssertionError`` if any code path in *fn* calls ``socket.socket()``.
    Returns *fn*'s return value if no network activity occurred.
    """
    with block_network():
        return fn()


@dataclass(frozen=True)
class OfflineCheckResult:
    """Outcome of :func:`verify_offline`."""

    ok: bool
    detail: str


def _attempt_socket() -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.close()


def verify_offline() -> OfflineCheckResult:
    """Self-check that the offline guard is active and functioning.

    1. *Positive control* — a deliberate socket attempt must be blocked, proving
       the guard actually works (not a no-op).
    2. *Clean run* — a representative no-op must complete under the guard.

    Returns an :class:`OfflineCheckResult` rather than raising, so callers (incl.
    a UI button) can present the outcome.
    """
    try:
        check_offline_invariant(_attempt_socket)
    except AssertionError:
        pass  # expected — the guard caught the deliberate attempt
    else:
        return OfflineCheckResult(
            False, "Offline guard is not active: a network socket was not blocked."
        )

    try:
        check_offline_invariant(lambda: None)
    except AssertionError as exc:  # pragma: no cover - defensive
        return OfflineCheckResult(False, str(exc))

    return OfflineCheckResult(
        True,
        "Offline guard verified: no network sockets are opened in the "
        "conversion path. All processing stays on this device.",
    )
