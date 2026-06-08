"""Watermark robustness/quality measurement harness (Phase 3 M4).

Run:  $env:PYTHONPATH = "src"; .venv\\Scripts\\python scripts\\watermark_eval.py

Embeds the experimental spread-spectrum watermark into a speech-like test
signal, applies a battery of attacks, and reports the blind detection score
(matching key vs wrong key) plus the watermark SNR. ffmpeg attacks are skipped
if ffmpeg is unavailable. Results feed docs/watermark-eval.md.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import numpy as np

from voiceconv.audio._watermark import (
    DEFAULT_KEY,
    correlation_score,
    embed,
    snr_db,
)

SR = 22050
_WRONG_KEY = DEFAULT_KEY ^ 0xFFFF
_FFMPEG = os.environ.get("VOICECONV_FFMPEG_PATH") or shutil.which("ffmpeg")


def speech_like(seconds: float = 3.0, sr: int = SR) -> np.ndarray:
    """A non-trivial test signal: a few harmonics + formant-ish filtered noise."""
    rng = np.random.default_rng(7)
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    sig = np.zeros_like(t)
    for f, a in [(110, 0.5), (220, 0.3), (440, 0.2), (660, 0.1)]:
        sig += a * np.sin(2 * np.pi * f * t)
    # amplitude envelope (syllable-like) + a little noise
    env = 0.5 + 0.5 * np.sin(2 * np.pi * 3.0 * t)
    sig = sig * env + 0.02 * rng.standard_normal(len(t))
    return (0.6 * sig / np.max(np.abs(sig))).astype(np.float32)


def _ffmpeg_roundtrip(pcm: np.ndarray, ext: str, extra: list[str] | None = None,
                      out_sr: int = SR) -> np.ndarray:
    from voiceconv.audio._codec import FfmpegEncoder, FfmpegLoader

    with tempfile.TemporaryDirectory() as d:
        path = str(Path(d) / f"a{ext}")
        FfmpegEncoder().encode(pcm, SR, path)
        return FfmpegLoader(target_sample_rate=out_sr).load(path)[0]


def attacks(wm: np.ndarray) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {"identity": wm}
    # 16-bit requantisation (in-memory)
    out["requantize_16bit"] = (
        (np.clip(wm, -1, 1) * 32767).astype(np.int16).astype(np.float32) / 32767.0
    )
    # 0.3 s leading trim (desync)
    out["trim_0.3s"] = wm[int(0.3 * SR):]
    if _FFMPEG:
        out["flac_reencode"] = _ffmpeg_roundtrip(wm, ".flac")
        out["mp3_128k"] = _ffmpeg_roundtrip(wm, ".mp3")
        # resample 22050 -> 16000 -> 22050
        down = _ffmpeg_roundtrip(wm, ".wav", out_sr=16000)
        out["resample_16k"] = _ffmpeg_roundtrip(down, ".wav", out_sr=SR)
    return out


def main() -> None:
    host = speech_like()
    wm = embed(host)
    print(f"ffmpeg: {'yes' if _FFMPEG else 'NO (codec attacks skipped)'}")
    print(f"watermark SNR (clean): {snr_db(host, wm):.1f} dB")
    print(f"unmarked host score (key):       {correlation_score(host):+.4f}")
    print(f"watermarked score (WRONG key):   {correlation_score(wm, key=_WRONG_KEY):+.4f}")
    print()
    print(f"{'attack':<18} {'score(key)':>11} {'score(wrong)':>13} {'detected':>9}")
    print("-" * 54)
    from voiceconv.audio._watermark import DEFAULT_THRESHOLD
    for name, sig in attacks(wm).items():
        s = correlation_score(sig)
        w = correlation_score(sig, key=_WRONG_KEY)
        print(f"{name:<18} {s:>+11.4f} {w:>+13.4f} {str(s >= DEFAULT_THRESHOLD):>9}")


if __name__ == "__main__":
    main()
