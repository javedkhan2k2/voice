"""PcmLoader protocol and stdlib WAV implementation.

The runner accepts an injected PcmLoader so the audio backend is swappable:
  M1: StdlibWavLoader  (stdlib wave; PCM WAV only)
  M2: FfmpegLoader     (ffmpeg; all common formats, proper resampling)
"""

from __future__ import annotations

import wave
from typing import Protocol

import numpy as np


class PcmLoader(Protocol):
    def load(self, path: str) -> tuple[np.ndarray, int]:
        """Return (float32 mono PCM, sample_rate_hz)."""
        ...


class StdlibWavLoader:
    """Loads PCM WAV files using the stdlib ``wave`` module.

    Supports 8/16/24/32-bit integer PCM.  Downmixes multi-channel to mono
    by averaging channels.  Does not resample — the caller's ConvertParams
    specify the target rate; actual resampling is an M2 concern.
    """

    def load(self, path: str) -> tuple[np.ndarray, int]:
        with wave.open(path, "rb") as wf:
            n_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            frame_rate = wf.getframerate()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)

        samples = _decode_pcm(raw, sample_width)

        if n_channels > 1:
            samples = samples.reshape(-1, n_channels).mean(axis=1)

        return np.ascontiguousarray(samples, dtype=np.float32), frame_rate


def _decode_pcm(raw: bytes, sample_width: int) -> np.ndarray:
    if sample_width == 1:
        u8 = np.frombuffer(raw, dtype=np.uint8)
        return (u8.astype(np.float32) - 128.0) / 128.0
    if sample_width == 2:
        return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if sample_width == 3:
        n = len(raw) // 3
        b = np.frombuffer(raw, dtype=np.uint8).reshape(n, 3)
        uint32 = (
            b[:, 0].astype(np.uint32)
            | (b[:, 1].astype(np.uint32) << 8)
            | (b[:, 2].astype(np.uint32) << 16)
        )
        int32 = uint32.astype(np.int32)
        mask = uint32 >= 0x800000
        int32[mask] -= 0x1000000
        return int32.astype(np.float32) / 8388608.0
    if sample_width == 4:
        return np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    raise ValueError(f"unsupported sample width: {sample_width} bytes")
