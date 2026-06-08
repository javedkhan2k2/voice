# Inaudible watermark — evaluation & decision (Phase 3 M4)

**Decision: DEFER to a post-v1 fast-follow.** Output provenance ships in v1 as
container **metadata** (Phase 3 M2, `docs/provenance.md`). A durable, signal-domain
watermark is **not** robust enough in prototype form to justify shipping in v1
and is tracked as a named fast-follow.

## What was evaluated

A blind, additive **spread-spectrum** prototype (`src/voiceconv/audio/_watermark.py`,
experimental — not wired into the conversion path): a key-seeded pseudo-noise
chip tiled in 2048-sample blocks, scaled per block to local RMS; detection
correlates each block with the chip and averages (processing gain). Measured via
`scripts/watermark_eval.py` on a 3 s speech-like signal at 22050 Hz,
strength 0.04, threshold 0.02.

## Results

Detection statistic = mean per-block normalised correlation (≈ embed strength
when present, ≈ 0 when absent). Baselines: unmarked host **+0.0016**,
watermarked with the **wrong key −0.0003** — no false positives.

Watermark **SNR (clean): 28.0 dB**.

| Attack | score (matching key) | detected (≥ 0.02) |
|---|---:|:--:|
| identity | +0.0416 | ✅ |
| 16-bit requantize | +0.0416 | ✅ |
| FLAC re-encode (lossless) | +0.0416 | ✅ |
| MP3 128 kbps | +0.0279 | ✅ (margin halved) |
| **leading trim 0.3 s** | +0.0007 | ❌ |
| **resample 22.05→16→22.05 kHz** | −0.0011 | ❌ |

## Reading the evidence

- **Survives lossless paths and even MP3 128k** — promising, but the MP3 margin
  is already ~⅓ of clean and would erode at lower bitrates.
- **Fails on trim and resample** — both are trivial, extremely common operations.
  The prototype has no **synchronisation recovery**: a sub-block time shift or a
  resample destroys block alignment and the correlation collapses to noise. This
  is the disqualifying gap; a shippable mark needs self-synchronising patterns or
  a correlation-peak search, plus robustness-oriented redundancy.
- **Inaudibility is only borderline** — 28 dB flat additive with no psychoacoustic
  masking is audible in quiet passages. Production inaudibility needs masking-model
  shaping, which interacts with (and complicates) robustness.

## Why defer (not ship, not drop)

- Shipping a watermark that silently fails on trim/resample would **overclaim**
  provenance — worse than not claiming it. The metadata marker is honest about
  its own limitation (stripped by re-encode) and is the guaranteed baseline.
- The gap is well understood (sync + psychoacoustic shaping), so this is an
  engineering investment, not a dead end — appropriate as a **fast-follow**.

## Fast-follow scope (if/when prioritised)

1. Synchronisation: self-sync chip / preamble or sliding correlation peak search
   to survive trim and resample.
2. Psychoacoustic masking to reach genuine inaudibility (target ≳ 40 dB perceptual).
3. Robustness target: survive MP3 ≤ 96 kbps, ±10% time-stretch, and 8–48 kHz
   resampling, with a quantified false-positive rate.
4. Then evaluate wiring behind the encoder (offline invariant preserved).

## Reproduce

```
$env:PYTHONPATH = "src"; .venv\Scripts\python scripts\watermark_eval.py
```

Prototype behaviour is pinned by `tests/audio/test_watermark.py` (detection, no
false positive, SNR floor, lossless survival). Robustness *gaps* are documented
here, not asserted as passing.
