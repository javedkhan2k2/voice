"""EXPERIMENTAL spread-spectrum audio watermark — Phase 3 M4 evaluation spike.

This module is **not** part of the conversion path and is **not** wired into any
encoder. It exists to measure whether an inaudible watermark is robust enough to
ship in v1 (see ``scripts/watermark_eval.py`` and ``docs/watermark-eval.md``).
The shipping provenance guarantee is the container-metadata marker in
``audio/_provenance.py``; this is a candidate *durable* layer under evaluation.

Technique: blind, additive spread-spectrum. A key-seeded pseudo-noise chip is
tiled across the signal in fixed blocks, scaled per block to the local RMS (a
crude inaudibility shaping). Detection correlates each block with the chip and
averages — the coherent watermark term survives averaging while the host signal
averages toward zero (processing gain). No psychoacoustic masking and no
synchronisation recovery: this is a measurement prototype, not a product.
"""

from __future__ import annotations

import numpy as np

# Default watermark parameters (tuned for ~28 dB SNR while staying detectable).
DEFAULT_KEY = 0x564F4943  # "VOIC"
DEFAULT_BLOCK = 2048
DEFAULT_STRENGTH = 0.04
# Detection threshold on the mean per-block normalised correlation. The host
# signal yields ~0; a present watermark yields ~= strength.
DEFAULT_THRESHOLD = 0.02


def _unit_chip(key: int, length: int) -> np.ndarray:
    """Key-seeded pseudo-noise chip, normalised to unit standard deviation."""
    rng = np.random.default_rng(key)
    chip = rng.standard_normal(length).astype(np.float64)
    chip -= chip.mean()
    std = chip.std()
    return chip / (std + 1e-12)


def embed(
    pcm: np.ndarray,
    *,
    key: int = DEFAULT_KEY,
    strength: float = DEFAULT_STRENGTH,
    block: int = DEFAULT_BLOCK,
) -> np.ndarray:
    """Return a watermarked copy of float32 mono *pcm*.

    The watermark adds ``strength * local_rms`` worth of chip energy per block,
    so quieter passages get a proportionally quieter mark.
    """
    x = pcm.astype(np.float64)
    out = x.copy()
    chip = _unit_chip(key, block)
    n_blocks = len(x) // block
    for i in range(n_blocks):
        seg = x[i * block : (i + 1) * block]
        local_rms = np.sqrt(np.mean(seg**2))
        out[i * block : (i + 1) * block] = seg + strength * local_rms * chip
    return out.astype(np.float32)


def correlation_score(
    pcm: np.ndarray,
    *,
    key: int = DEFAULT_KEY,
    block: int = DEFAULT_BLOCK,
) -> float:
    """Blind detection statistic: mean per-block normalised correlation w/ chip.

    ~0 for an unmarked signal or the wrong key; ~= embed strength when the
    matching watermark is present and block-aligned.
    """
    x = pcm.astype(np.float64)
    chip = _unit_chip(key, block)
    chip_norm = np.linalg.norm(chip)
    n_blocks = len(x) // block
    if n_blocks == 0:
        return 0.0
    corrs = []
    for i in range(n_blocks):
        seg = x[i * block : (i + 1) * block]
        seg = seg - seg.mean()
        denom = np.linalg.norm(seg) * chip_norm + 1e-12
        corrs.append(float(np.dot(seg, chip) / denom))
    return float(np.mean(corrs))


def is_watermarked(
    pcm: np.ndarray,
    *,
    key: int = DEFAULT_KEY,
    block: int = DEFAULT_BLOCK,
    threshold: float = DEFAULT_THRESHOLD,
) -> bool:
    """True if the matching watermark is detected above *threshold*."""
    return correlation_score(pcm, key=key, block=block) >= threshold


def snr_db(original: np.ndarray, watermarked: np.ndarray) -> float:
    """Signal-to-noise ratio (dB) of the watermark vs the host — inaudibility proxy."""
    n = min(len(original), len(watermarked))
    x = original[:n].astype(np.float64)
    noise = watermarked[:n].astype(np.float64) - x
    sig_power = np.mean(x**2)
    noise_power = np.mean(noise**2)
    if noise_power <= 0:
        return float("inf")
    return float(10.0 * np.log10(sig_power / noise_power))
