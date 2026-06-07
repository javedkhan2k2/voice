"""Offline runtime invariant check.

``check_offline_invariant`` wraps a callable and asserts that no code within
it opens a network socket.  It works by temporarily replacing
``socket.socket.__init__`` with a function that raises AssertionError on
first invocation.

Usage in tests::

    check_offline_invariant(lambda: converter.convert_file(...))

Usage as a diagnostic (does not block app startup)::

    try:
        check_offline_invariant(lambda: None)  # sanity-check the patch itself
    except AssertionError:
        log.warning("offline invariant check failed")
"""

from __future__ import annotations

import socket
from typing import Callable, TypeVar

T = TypeVar("T")


def check_offline_invariant(fn: Callable[[], T]) -> T:
    """Execute *fn()* with network socket creation blocked.

    Raises ``AssertionError`` if any code path in *fn* calls
    ``socket.socket()``.  Returns *fn*'s return value if no network
    activity occurred.

    Only the calling process is patched; subprocesses spawned inside *fn*
    are not affected.  This is sufficient for verifying that the services
    layer — which runs in the main process — never opens sockets.
    """
    original_init = socket.socket.__init__

    def _blocked(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError(
            "Network socket opened during conversion — offline invariant violated. "
            "No code in the conversion path may open a network connection."
        )

    socket.socket.__init__ = _blocked  # type: ignore[method-assign]
    try:
        return fn()
    finally:
        socket.socket.__init__ = original_init  # type: ignore[method-assign]
