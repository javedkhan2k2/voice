"""Mock engine for testing the worker IPC boundary without real model weights.

Returns silence (or an identity copy of the source) and simulates chunk-level
processing time so cancellation tests have something to cancel.

This engine is included in the worker REGISTRY so headless integration tests
can use it without installing OpenVoice V2 or FreeVC.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

import numpy as np

from voiceconv.inference.engine import (
    CancelToken,
    ConvertParams,
    EngineCapabilities,
    ProfileArtifacts,
)

_ENGINE_ID = "mock"
_ENGINE_VERSION = "0.1"
_CHUNK_SAMPLES = 4096  # check cancel + report progress every ~185 ms at 22 050 Hz
_SLEEP_PER_CHUNK = 0.002  # seconds; keeps tests fast while still being cancellable


class MockEngine:
    """Minimal engine that echoes the source audio.  Used in tests only."""

    def static_capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            engine_id=_ENGINE_ID,
            engine_version=_ENGINE_VERSION,
            supported_sample_rates=(16000, 22050, 44100),
            min_reference_duration_sec=0.1,
            max_reference_duration_sec=60.0,
            preferred_device="cpu",
        )

    def warmup(self, device: str) -> None:
        pass

    def prepare_profile(
        self,
        reference_pcm: np.ndarray,
        sample_rate: int,
    ) -> ProfileArtifacts:
        # Trivial embedding: the scalar mean of the reference.
        embedding = np.array([reference_pcm.mean()], dtype=np.float32)
        return ProfileArtifacts(
            engine_id=_ENGINE_ID,
            engine_version=_ENGINE_VERSION,
            data=embedding.tobytes(),
            metadata={"n_samples": len(reference_pcm), "sample_rate": sample_rate},
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
        n = len(source_pcm)
        out = np.empty(n, dtype=np.float32)
        n_chunks = max(1, (n + _CHUNK_SAMPLES - 1) // _CHUNK_SAMPLES)

        for i in range(n_chunks):
            if cancel_token is not None:
                cancel_token.check()

            start = i * _CHUNK_SAMPLES
            end = min(start + _CHUNK_SAMPLES, n)
            out[start:end] = source_pcm[start:end]  # identity pass-through
            time.sleep(_SLEEP_PER_CHUNK)

            if progress is not None:
                progress((i + 1) / n_chunks)

        return out

    def release(self) -> None:
        pass
