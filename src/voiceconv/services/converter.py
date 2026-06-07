"""Single-shot headless voice-conversion pipeline.

Converter wires: pcm_loader → engine.prepare_profile / engine.convert → audio_encoder.
No queue, no persistence, no state between calls.  The caller supplies all dependencies
via constructor injection (same pattern as QueueRunner).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

from voiceconv.inference.engine import (
    CancelToken,
    ConvertParams,
    ProfileArtifacts,
    VoiceConversionEngine,
)
from voiceconv.services._audio_encoder import AudioEncoder
from voiceconv.services._pcm_loader import PcmLoader

log = logging.getLogger(__name__)


class Converter:
    """Single-shot headless voice-conversion pipeline.

    Parameters
    ----------
    engine:
        A warmed-up ``VoiceConversionEngine`` (typically ``WorkerAdapter``).
    pcm_loader:
        Audio decode backend (``FfmpegLoader`` in production, ``_MockPcmLoader``
        in tests).
    audio_encoder:
        Audio encode backend (``FfmpegEncoder`` in production,
        ``StdlibWavEncoder`` in tests).
    """

    def __init__(
        self,
        engine: VoiceConversionEngine,
        pcm_loader: PcmLoader,
        audio_encoder: AudioEncoder,
    ) -> None:
        self._engine = engine
        self._pcm_loader = pcm_loader
        self._audio_encoder = audio_encoder

    def prepare_profile(self, reference_path: str) -> ProfileArtifacts:
        """Load *reference_path* and derive a zero-shot voice embedding.

        The returned ``ProfileArtifacts`` can be cached and reused for multiple
        ``convert_file`` calls without re-processing the reference clip.
        """
        ref_pcm, ref_sr = self._pcm_loader.load(reference_path)
        return self._engine.prepare_profile(ref_pcm, ref_sr)

    def convert_file(
        self,
        source_path: str,
        profile: ProfileArtifacts,
        params: ConvertParams,
        output_path: str,
        *,
        progress: Optional[Callable[[float], None]] = None,
        cancel_token: Optional[CancelToken] = None,
    ) -> None:
        """Decode *source_path*, convert to the target voice, encode to *output_path*.

        Parameters
        ----------
        source_path:
            Path to the source speech file (any ffmpeg-supported format).
        profile:
            Voice embedding produced by :meth:`prepare_profile`.
        params:
            Conversion options including ``target_sample_rate``.
        output_path:
            Destination file path.  Parent directories are created if needed.
            Format is inferred from the extension by the injected encoder.
        progress:
            Called with a float in ``[0.0, 1.0]`` at each engine progress tick.
        cancel_token:
            Checked at chunk boundaries; raises ``CancelledError`` when set.
            VRAM release after cancel is the caller's responsibility.

        Raises
        ------
        CancelledError
            If *cancel_token* is set mid-conversion.
        EngineError
            On unrecoverable model failure.
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        src_pcm, src_sr = self._pcm_loader.load(source_path)
        out_pcm = self._engine.convert(
            src_pcm,
            src_sr,
            profile,
            params,
            progress=progress,
            cancel_token=cancel_token,
        )
        self._audio_encoder.encode(out_pcm, params.target_sample_rate, output_path)
