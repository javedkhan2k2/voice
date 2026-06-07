"""Loudness normalization utilities for float32 mono PCM arrays."""

from __future__ import annotations

import numpy as np


def rms_normalize(pcm: np.ndarray, target_rms: float = 0.1) -> np.ndarray:
    """Scale *pcm* so its RMS amplitude equals *target_rms*.

    Silent signals (RMS == 0) are returned unchanged to avoid division by zero.
    The output is float32 and may contain values outside [-1, 1]; clip before
    encoding if the encoder requires it.
    """
    rms = float(np.sqrt(np.mean(pcm.astype(np.float64) ** 2)))
    if rms < 1e-9:
        return pcm.copy().astype(np.float32)
    return (pcm * (target_rms / rms)).astype(np.float32)
