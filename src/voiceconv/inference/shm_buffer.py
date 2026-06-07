"""Shared-memory buffer for zero-copy PCM transfer across the process boundary.

The *allocating* side (parent / WorkerAdapter) creates a ShmBuffer, writes
PCM into it, passes the segment name to the worker via IPC JSON, and frees
the segment after the response arrives.

The *attaching* side (worker) creates a ShmBuffer with attach() to read from
or write to the same memory region.

Both sides must call close() when done.  Only the allocating side calls
unlink() (which is a no-op on Windows; the OS handles cleanup automatically
once all handles are closed).

Usage — allocating side::

    with ShmBuffer.alloc(n_bytes) as buf:
        buf.as_ndarray("float32", (n_samples,))[:] = pcm
        worker_ipc.send({"shm_name": buf.name, "shm_size": buf.size, ...})
        response = worker_ipc.recv()
    # buf automatically freed here

Usage — attaching side::

    with ShmBuffer.attach(name, size) as buf:
        pcm = buf.as_ndarray("float32", (n_samples,)).copy()
"""

from __future__ import annotations

import uuid
from multiprocessing import shared_memory
from typing import Optional

import numpy as np


def _unique_name() -> str:
    return f"vcb-{uuid.uuid4().hex[:16]}"


class ShmBuffer:
    """Thin wrapper around multiprocessing.shared_memory.SharedMemory."""

    def __init__(self, shm: shared_memory.SharedMemory, *, owner: bool) -> None:
        self._shm = shm
        self._owner = owner  # True on the allocating side (calls unlink on close)

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def alloc(cls, size: int, *, name: Optional[str] = None) -> "ShmBuffer":
        """Allocate *size* bytes of shared memory.  Caller owns the segment."""
        name = name or _unique_name()
        shm = shared_memory.SharedMemory(name=name, create=True, size=size)
        return cls(shm, owner=True)

    @classmethod
    def attach(cls, name: str, size: int) -> "ShmBuffer":
        """Attach to an existing named segment without taking ownership."""
        shm = shared_memory.SharedMemory(name=name, create=False, size=size)
        return cls(shm, owner=False)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return self._shm.name

    @property
    def size(self) -> int:
        return self._shm.size

    # ------------------------------------------------------------------
    # Data access
    # ------------------------------------------------------------------

    def as_ndarray(self, dtype: str, shape: tuple[int, ...]) -> np.ndarray:
        """Return a numpy view into the shared memory region (zero-copy)."""
        return np.ndarray(shape, dtype=dtype, buffer=self._shm.buf)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Detach from the segment and, if owner, destroy it."""
        self._shm.close()
        if self._owner:
            self._shm.unlink()

    def __enter__(self) -> "ShmBuffer":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
