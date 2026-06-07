"""OpenVoice V2 engine adapter for the worker process.

Stub only for M1.  Actual model imports are deferred inside warmup() so the
worker starts cleanly and fails with a clear error when the package is not
installed.  Fill in the TODO sections once the install-time weight-fetch
step is implemented and Python / PyTorch / CUDA versions are pinned.

References:
  - https://github.com/myshell-ai/OpenVoice  (MIT code + weights since Apr 2024)
  - https://huggingface.co/myshell-ai/OpenVoiceV2
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

_ENGINE_ID = "openvoice_v2"
_ENGINE_VERSION = "2.0"  # TODO: read from installed package at runtime


class OpenVoiceV2Engine:
    """Worker-side adapter for OpenVoice V2.

    The actual model imports (``from openvoice import ...``) are inside warmup()
    so the worker starts quickly and fails clearly if the package is absent.
    """

    def static_capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            engine_id=_ENGINE_ID,
            engine_version=_ENGINE_VERSION,
            supported_sample_rates=(22050, 44100),
            min_reference_duration_sec=3.0,
            max_reference_duration_sec=30.0,
            preferred_device="cuda",
        )

    def warmup(self, device: str) -> None:
        # TODO: import openvoice; load ToneColorConverter and VITS model onto device.
        # Example (not runnable until package is installed):
        #   from openvoice import se_extractor
        #   from openvoice.api import ToneColorConverter
        #   self._converter = ToneColorConverter(...)
        #   self._converter.load_ckpt("checkpoints_v2/converter")
        raise EngineError(
            "OpenVoice V2 is not yet installed.  "
            "Run the weight-fetch step first (TODO: installer script).",
            code="NOT_INSTALLED",
        )

    def prepare_profile(
        self,
        reference_pcm: np.ndarray,
        sample_rate: int,
    ) -> ProfileArtifacts:
        # TODO: call se_extractor.get_se() to derive the tone-color embedding.
        raise EngineError("OpenVoice V2 not installed", code="NOT_INSTALLED")

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
        # TODO: run ToneColorConverter.convert() with the stored embedding.
        raise EngineError("OpenVoice V2 not installed", code="NOT_INSTALLED")

    def release(self) -> None:
        # TODO: delete model tensors, call torch.cuda.empty_cache().
        pass
