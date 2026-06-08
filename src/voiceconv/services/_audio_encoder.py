"""AudioEncoder protocol and stdlib WAV fallback.

The runner accepts an injected AudioEncoder so the output backend is swappable:
  M1/fallback: StdlibWavEncoder  (stdlib wave; 16-bit PCM WAV only)
  M2+:         FfmpegEncoder     (ffmpeg; WAV, FLAC, any container ffmpeg supports)
"""

from __future__ import annotations

import io
import wave
from pathlib import Path
from typing import Protocol

import numpy as np

from voiceconv.audio._provenance import append_info_chunk


class AudioEncoder(Protocol):
    def encode(self, pcm: np.ndarray, sample_rate: int, path: str) -> None:
        """Write float32 mono *pcm* to *path* at *sample_rate* Hz."""
        ...


class StdlibWavEncoder:
    """Encode float32 mono PCM as a 16-bit PCM WAV using the stdlib ``wave`` module.

    Used as the default when no ``FfmpegEncoder`` is injected into ``QueueRunner``,
    preserving backwards compatibility with M1 tests.
    """

    def encode(self, pcm: np.ndarray, sample_rate: int, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        clipped = np.clip(pcm, -1.0, 1.0)
        int16 = (clipped * 32767.0).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(int16.tobytes())
        # Output provenance: append a RIFF INFO chunk marking the file as AI
        # voice-converted (M2). Audio frames are unchanged.
        Path(path).write_bytes(append_info_chunk(buf.getvalue()))
