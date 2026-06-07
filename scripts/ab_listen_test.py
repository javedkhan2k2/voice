"""M1 A/B listening-test runner.

Runs both candidate engines (OpenVoice V2 and FreeVC) against a set of
source+reference audio pairs and exports blind WAV files for scoring.

Usage::

    python scripts/ab_listen_test.py \\
        --pair source1.wav reference1.wav \\
        --pair source2.wav reference2.wav \\
        --output-dir ab_results/

The script produces::

    ab_results/
        pair-1-A.wav        # OpenVoice V2 output
        pair-1-B.wav        # FreeVC output
        pair-2-A.wav
        pair-2-B.wav
        results.json        # latency, VRAM peak, engine mapping (reveal after scoring)

Engine mapping (A=OpenVoice V2, B=FreeVC) is stored in results.json but
intentionally not printed to the console during a blind listening session.

Prerequisites
-------------
- Both engines must be installed (weights downloaded, packages importable).
  The script will fail with EngineError(NOT_INSTALLED) until then.
- numpy, scipy (for WAV I/O) must be importable.
- Run from the repository root so voiceconv is on sys.path.

Scoring procedure (manual)
--------------------------
1. Listen to each pair blindly (A vs B, randomised playback order).
2. Rate: speaker similarity 1-5, naturalness 1-5.
3. Run with ``--reveal`` to see which file was which engine.
4. Objective sanity: compute WavLM speaker-embedding cosine similarity
   (output vs reference) with an external script.

Decision rule
-------------
- Mean score gap < 0.5 across all pairs → keep OpenVoice V2 (cleaner license).
- FreeVC ≥ 0.5 better AND checkpoint license confirmed → switch default.
- Document outcome in docs/phases/phase-0-model-selection.md.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np

# voiceconv must be on sys.path (run from repo root or install in editable mode)
from voiceconv.inference.engine import ConvertParams, ProfileArtifacts
from voiceconv.inference.worker_adapter import WorkerAdapter


# ---------------------------------------------------------------------------
# WAV helpers (stdlib only — no soundfile dependency in M1)
# ---------------------------------------------------------------------------


def _write_wav(path: Path, pcm: np.ndarray, sample_rate: int) -> None:
    """Write float32 mono PCM as a 16-bit PCM WAV file."""
    pcm_int = np.clip(pcm, -1.0, 1.0)
    pcm_int16 = (pcm_int * 32767).astype(np.int16)
    data_bytes = pcm_int16.tobytes()
    n_samples = len(pcm_int16)
    n_channels = 1
    sample_width = 2  # bytes (16-bit)
    byte_rate = sample_rate * n_channels * sample_width
    block_align = n_channels * sample_width
    data_len = len(data_bytes)

    with path.open("wb") as f:
        # RIFF header
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_len))
        f.write(b"WAVE")
        # fmt chunk
        f.write(b"fmt ")
        f.write(struct.pack("<IHHIIHH", 16, 1, n_channels, sample_rate,
                            byte_rate, block_align, 16))
        # data chunk
        f.write(b"data")
        f.write(struct.pack("<I", data_len))
        f.write(data_bytes)


def _read_wav(path: Path) -> tuple[np.ndarray, int]:
    """Read a WAV file to float32 mono PCM.  Handles 8/16/32-bit PCM WAV only."""
    # TODO(M2): replace with the full audio pipeline (ffmpeg decode) once M2 is done.
    # This naive reader is sufficient for WAV-only test assets.
    import wave as _wave
    with _wave.open(str(path), "rb") as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        sample_rate = wf.getframerate()
        raw = wf.readframes(wf.getnframes())
    if sampwidth == 1:
        pcm = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128) / 128
    elif sampwidth == 2:
        pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    elif sampwidth == 4:
        pcm = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2**31
    else:
        raise ValueError(f"unsupported sample width {sampwidth}")
    if n_channels > 1:
        pcm = pcm.reshape(-1, n_channels).mean(axis=1)
    return pcm, sample_rate


# ---------------------------------------------------------------------------
# Per-engine run
# ---------------------------------------------------------------------------


def _run_engine(
    engine_id: str,
    source_pcm: np.ndarray,
    reference_pcm: np.ndarray,
    sample_rate: int,
) -> tuple[np.ndarray, float, int]:
    """Warmup, prepare profile, convert, release.  Returns (output_pcm, latency_sec, vram_peak_bytes)."""
    adapter = WorkerAdapter(engine_id)
    try:
        adapter.warmup("auto")
        profile = adapter.prepare_profile(reference_pcm, sample_rate)

        # VRAM peak reset before conversion (best effort — requires torch on path)
        vram_before = 0
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.reset_peak_memory_stats()
                vram_before = torch.cuda.memory_allocated()
        except ImportError:
            pass

        t0 = time.perf_counter()
        out = adapter.convert(
            source_pcm, sample_rate, profile,
            ConvertParams(target_sample_rate=sample_rate, device="auto"),
        )
        latency = time.perf_counter() - t0

        vram_peak = 0
        try:
            import torch
            if torch.cuda.is_available():
                vram_peak = torch.cuda.max_memory_allocated() - vram_before
        except ImportError:
            pass

        adapter.release()
        return out, latency, vram_peak
    finally:
        adapter.terminate()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="M1 A/B listening-test runner for OpenVoice V2 vs FreeVC",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--pair",
        nargs=2,
        metavar=("SOURCE", "REFERENCE"),
        action="append",
        required=True,
        help="source and reference audio pair (WAV).  Repeat for multiple pairs.",
    )
    parser.add_argument(
        "--output-dir",
        default="ab_results",
        help="directory to write blind WAV outputs and results.json",
    )
    parser.add_argument(
        "--reveal",
        action="store_true",
        help="print the engine-to-file mapping (use AFTER scoring)",
    )
    args = parser.parse_args(argv)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    engine_ids = ["openvoice_v2", "freevc"]
    slots = ["A", "B"]  # A=engine_ids[0], B=engine_ids[1]

    results: list[dict] = []

    for pair_idx, (source_path, reference_path) in enumerate(args.pair, start=1):
        print(f"\n=== Pair {pair_idx}: {source_path} | ref: {reference_path} ===")
        source_pcm, source_sr = _read_wav(Path(source_path))
        reference_pcm, ref_sr = _read_wav(Path(reference_path))
        # Resample to common rate if needed (TODO: use audio pipeline from M2)
        if source_sr != ref_sr:
            print(f"  WARNING: source SR {source_sr} != reference SR {ref_sr}; "
                  "results may be degraded.  Use the M2 audio pipeline for resampling.")

        pair_result: dict = {"pair": pair_idx, "source": source_path,
                             "reference": reference_path, "engines": []}

        for engine_id, slot in zip(engine_ids, slots):
            print(f"  Running {engine_id} → slot {slot} ...", end=" ", flush=True)
            try:
                out_pcm, latency, vram_peak = _run_engine(
                    engine_id, source_pcm, reference_pcm, source_sr,
                )
                out_path = out_dir / f"pair-{pair_idx}-{slot}.wav"
                _write_wav(out_path, out_pcm, source_sr)
                print(f"done  latency={latency:.2f}s  vram={vram_peak // 1024 // 1024} MB")
                pair_result["engines"].append({
                    "engine_id": engine_id,
                    "slot": slot,
                    "output_file": str(out_path),
                    "latency_sec": round(latency, 3),
                    "vram_peak_mb": vram_peak // 1024 // 1024,
                })
            except Exception as exc:
                print(f"FAILED: {exc}")
                pair_result["engines"].append({
                    "engine_id": engine_id,
                    "slot": slot,
                    "error": str(exc),
                })

        results.append(pair_result)

    results_path = out_dir / "results.json"
    results_path.write_text(json.dumps(results, indent=2))
    print(f"\nResults written to {results_path}")

    if args.reveal:
        print("\n--- Engine mapping (reveal after scoring) ---")
        print(f"  A = {engine_ids[0]}")
        print(f"  B = {engine_ids[1]}")
    else:
        print("\nRun with --reveal to see which slot corresponds to which engine.")

    print("\nScoring procedure:")
    print("  1. Listen to pair-N-A.wav and pair-N-B.wav for each pair.")
    print("  2. Rate speaker similarity (1-5) and naturalness (1-5).")
    print("  3. Decision rule: gap < 0.5 → keep OpenVoice V2; FreeVC ≥ 0.5 better")
    print("     AND checkpoint license confirmed → update default in pyproject.toml.")
    print("  4. Record outcome in docs/phases/phase-0-model-selection.md.")


if __name__ == "__main__":
    main()
