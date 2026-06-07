"""VoiceConversionEngine — public interface and shared data types.

The services layer depends only on this module.  No model code, no GUI,
no audio backend may be imported here.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Sequence

import numpy as np


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CancelledError(Exception):
    """Raised inside convert() when a CancelToken is set mid-conversion."""


class EngineError(Exception):
    """Raised for model or runtime failures.

    Attributes
    ----------
    code : str
        Short identifier such as ``"CUDA_OOM"`` or ``"NOT_INSTALLED"``.
    """

    def __init__(self, message: str, code: str = "ENGINE_ERROR") -> None:
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EngineCapabilities:
    """Static metadata and constraints for a specific engine."""

    engine_id: str
    engine_version: str
    supported_sample_rates: tuple[int, ...]
    min_reference_duration_sec: float
    max_reference_duration_sec: float
    preferred_device: str  # "cuda" | "cpu"


@dataclass(frozen=True)
class ConvertParams:
    """Caller-supplied conversion options."""

    target_sample_rate: int
    device: str = "auto"  # "auto" | "cuda" | "cpu"
    # Engine-specific overrides; the engine ignores unknown keys.
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProfileArtifacts:
    """Opaque, engine-specific voice embedding.

    The ``data`` bytes are produced and consumed only by the engine identified
    by ``engine_id`` / ``engine_version``.  The storage layer treats the blob
    as opaque and passes it back verbatim on each convert call.
    """

    engine_id: str
    engine_version: str
    data: bytes
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# CancelToken
# ---------------------------------------------------------------------------


class CancelToken:
    """Thread-safe cancel signal.

    The services layer creates one per job and passes it into convert().
    The engine checks it at chunk boundaries by calling check().
    """

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        """Signal cancellation.  Idempotent and thread-safe."""
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def check(self) -> None:
        """Raise CancelledError if cancel() has been called."""
        if self._event.is_set():
            raise CancelledError("conversion cancelled by caller")


# ---------------------------------------------------------------------------
# Abstract engine interface
# ---------------------------------------------------------------------------


class VoiceConversionEngine(ABC):
    """Public interface for a zero-shot voice-conversion engine.

    Implementations live behind the worker-process boundary (WorkerAdapter)
    or are in-process stubs used in tests.  The services layer depends only
    on this class and the data types above — never on a concrete adapter.

    Lifecycle::

        engine.warmup(device)
        profile = engine.prepare_profile(ref_pcm, sr)
        out_pcm = engine.convert(src_pcm, sr, profile, params, ...)
        engine.release()      # frees VRAM; warmup() re-arms it

    All PCM arrays are float32, mono, shape (n_samples,).
    """

    @abstractmethod
    def capabilities(self) -> EngineCapabilities:
        """Return static engine metadata and constraints."""

    @abstractmethod
    def warmup(self, device: str = "auto") -> None:
        """Load model weights into memory/VRAM.

        Idempotent — calling warmup() on an already-warm engine is safe.

        Raises
        ------
        EngineError
            On unrecoverable failure (e.g. ``NOT_INSTALLED``, ``CUDA_INIT``).
        """

    @abstractmethod
    def prepare_profile(
        self,
        reference_pcm: np.ndarray,
        sample_rate: int,
    ) -> ProfileArtifacts:
        """Derive a zero-shot voice embedding from a reference clip.

        Parameters
        ----------
        reference_pcm:
            float32 mono PCM, shape (n_samples,).
        sample_rate:
            Sample rate of ``reference_pcm`` in Hz.

        Returns
        -------
        ProfileArtifacts
            Opaque embedding to be stored and passed back to convert().
        """

    @abstractmethod
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
        """Convert source audio to the target voice.

        Parameters
        ----------
        source_pcm:
            float32 mono PCM for the *entire* source file.  Chunking for
            long files is handled internally by the engine/worker.
        sample_rate:
            Sample rate of ``source_pcm`` in Hz.
        profile:
            Voice embedding produced by prepare_profile().
        params:
            Conversion options.
        progress:
            Called periodically with a float in [0.0, 1.0].  Optional.
        cancel_token:
            Checked at chunk boundaries; raises CancelledError when set.

        Returns
        -------
        np.ndarray
            float32 mono PCM at ``params.target_sample_rate``.

        Raises
        ------
        CancelledError
            When cancel_token is set mid-conversion.
        EngineError
            On unrecoverable model failure.
        """

    @abstractmethod
    def release(self) -> None:
        """Unload model and free VRAM.

        After release(), warmup() may be called again to re-arm the engine.
        Idempotent — safe to call on an already-released engine.
        """
