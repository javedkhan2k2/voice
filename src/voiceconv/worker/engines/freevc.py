"""FreeVC engine adapter for the worker process.

Stub only for M1.  Actual model imports are deferred inside warmup().  Fill in
the TODO sections once the install-time weight-fetch step is implemented.

Before bundling FreeVC weights, confirm:
  1. The checkpoint license (author-published; not explicitly stated on the repo).
  2. Required VCTK 0.92 ODC-By v1.0 attribution text for the training data.

References:
  - https://github.com/OlaWod/FreeVC  (MIT code)
  - Checkpoints trained on VCTK 0.92 → ODC-By v1.0 (commercial OK with attribution)
  - WavLM encoder — confirm weight license on the HuggingFace model card
"""

from __future__ import annotations

from typing import Callable, Optional

import numpy as np

from voiceconv.inference.engine import (
    CancelToken,
    ConvertParams,
    EngineCapabilities,
    EngineError,
    ProfileArtifacts,
)

_ENGINE_ID = "freevc"
_ENGINE_VERSION = "1.0"  # TODO: read from installed package at runtime


class FreeVCEngine:
    """Worker-side adapter for FreeVC.

    Model imports are inside warmup() to defer the heavy import until first use.
    """

    def static_capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            engine_id=_ENGINE_ID,
            engine_version=_ENGINE_VERSION,
            supported_sample_rates=(16000, 22050),
            min_reference_duration_sec=3.0,
            max_reference_duration_sec=30.0,
            preferred_device="cuda",
        )

    def warmup(self, device: str) -> None:
        # TODO: load FreeVC model and WavLM encoder onto device.
        raise EngineError(
            "FreeVC is not yet installed.  "
            "Run the weight-fetch step first (TODO: installer script).  "
            "Also confirm checkpoint license and VCTK ODC-By attribution before bundling.",
            code="NOT_INSTALLED",
        )

    def prepare_profile(
        self,
        reference_pcm: np.ndarray,
        sample_rate: int,
    ) -> ProfileArtifacts:
        # TODO: extract WavLM speaker embedding from the reference clip.
        raise EngineError("FreeVC not installed", code="NOT_INSTALLED")

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
        # TODO: run FreeVC conversion with the stored WavLM speaker embedding.
        raise EngineError("FreeVC not installed", code="NOT_INSTALLED")

    def release(self) -> None:
        # TODO: delete model tensors, call torch.cuda.empty_cache().
        pass
