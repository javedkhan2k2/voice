"""WorkerEngine — protocol implemented by each model adapter inside the worker process.

host.py interacts only with this protocol; it does not import engine implementations
directly.  The REGISTRY in worker/engines/__init__.py maps engine IDs to factories.

WorkerEngine shares the same data types as VoiceConversionEngine (they live in
inference/engine.py) because the worker process imports them for type annotations
and for reconstructing ProfileArtifacts from IPC messages.
"""

from __future__ import annotations

from typing import Callable, Optional, Protocol, runtime_checkable

import numpy as np

from voiceconv.inference.engine import (
    CancelToken,
    ConvertParams,
    EngineCapabilities,
    ProfileArtifacts,
)


@runtime_checkable
class WorkerEngine(Protocol):
    """Protocol that every model adapter inside the worker process must satisfy."""

    def static_capabilities(self) -> EngineCapabilities: ...

    def warmup(self, device: str) -> None: ...

    def prepare_profile(
        self,
        reference_pcm: np.ndarray,
        sample_rate: int,
    ) -> ProfileArtifacts: ...

    def convert(
        self,
        source_pcm: np.ndarray,
        sample_rate: int,
        profile: ProfileArtifacts,
        params: ConvertParams,
        *,
        progress: Optional[Callable[[float], None]] = None,
        cancel_token: Optional[CancelToken] = None,
    ) -> np.ndarray: ...

    def release(self) -> None: ...
