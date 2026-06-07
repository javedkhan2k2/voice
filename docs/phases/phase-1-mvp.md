# Phase 1 — MVP

Execution plan for the first shippable slice. Product scope: `docs/spec.md`. Architecture:
`docs/architecture.md`. This document covers the MVP only; later phases are out of scope here.

> Prerequisite: **Phase 0 (model bake-off)** is complete (`docs/phases/phase-0-model-selection.md`).
> Default engine is **OpenVoice V2** (MIT code + weights); **FreeVC** is the alternative behind the same
> adapter. The default is provisional pending the M1 listening-test A/B below. seed-VC is deferred (GPLv3).

## MVP scope

A Windows 11 desktop app that lets a user:

1. Create a single voice profile from a short reference clip, behind a consent gate.
2. Convert one source speech file into that voice, fully offline.
3. Preview (A/B source vs output) and export to WAV/FLAC.

Explicitly **in** scope: single-job conversion, GPU + CPU paths, progress + clean cancel, consent gate,
basic settings (device, output format, storage location), local logging.

Explicitly **out** of scope for the MVP (deferred to later phases): batch queue, profile library
management UI, diagnostics-bundle export, watermarking, installer/packaging polish.

## Milestone breakdown

| # | Milestone | Outcome |
|---|---|---|
| M1 | **Core engine + worker boundary** | `VoiceConversionEngine` interface + adapters for **OpenVoice V2** and **FreeVC**; worker process loads the model and serves `prepare_profile`/`convert`; IPC chosen and working. Includes a **listening-test A/B** on the Phase-0 sample set to confirm the default engine. |
| M2 | **Audio pipeline** | Decode (ffmpeg) → float32 PCM → chunk → encode (WAV/FLAC); resampling + optional loudness normalize. |
| M3 | **Headless conversion path** | One headless call: source file + reference → output file, with progress callbacks and mid-job cancel that releases VRAM. |
| M4 | **Storage + consent** | Profile schema (versioned), consent record persisted on creation, settings store, local rotating logs. |
| M5 | **GUI MVP (PySide6)** | First-run hardware probe + acceptable-use ack; create-profile (with consent gate); convert; progress; A/B preview; export. |
| M6 | **Offline + integration hardening** | Offline self-check passes; end-to-end run on GPU and CPU; UI stays responsive on a long file. |

Dependency order: M1 → M2 → M3 → (M4 ∥ start M5) → M6.

## Acceptance criteria

- A non-technical user can: create a profile (consenting), convert a source file, preview A/B, and export
  WAV/FLAC — without reading documentation.
- Conversion produces audibly target-voiced output on the Phase 0 sample set.
- Conversion runs on an NVIDIA GPU and also completes on CPU (slower, with a clear warning).
- Cancelling mid-conversion stops promptly and releases VRAM; the app remains usable.
- No network connection is opened during conversion (verified by the offline self-check).
- Creating a profile without affirming consent is **impossible**; the consent record is persisted.
- The GUI never freezes during conversion.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Model quality/licensing unresolved | Blocks everything | Gate Phase 1 on Phase 0; keep engine swappable. |
| CUDA/driver variance | Install/run failures | Hardware probe + clear messaging; CPU fallback path. |
| IPC / large-PCM transfer overhead | Slow conversions | Decide payload mechanism early (shared memory / temp files); benchmark in M1. |
| Chunk-boundary artifacts on long files | Audible quality loss | Overlap-add chunking; validate on long clips in M6. |
| UI/threading bugs with Qt + async work | Freezes/races | Keep all heavy work off the UI thread / in the worker; view-model tests. |
| VRAM exhaustion / leaks | Crashes on repeat jobs | Release VRAM between/after jobs; bound memory; test repeated runs. |

## Test strategy

- **Unit (headless):** audio pipeline (decode/resample/chunk/encode), queue/job state, profile + consent
  persistence, settings.
- **Integration (headless):** source + reference → output via the worker, with progress and a mid-job
  cancel that releases VRAM; GPU and CPU runs.
- **Offline invariant:** automated self-check asserting no network calls in the conversion path.
- **GUI:** view-model unit tests; manual E2E pass of the create → convert → preview → export flow;
  responsiveness check on a long file.
- **Quality:** subjective review + a speaker-similarity check on the Phase 0 sample set.
- TODO: select the test runner and wire CI (none configured yet).

## Exit criteria

Phase 1 is complete when:

- All acceptance criteria pass on a clean Windows 11 machine (GPU present and GPU absent).
- The headless and GUI conversion paths share the same core (no GUI-only logic).
- The consent gate and offline self-check are enforced and tested.
- Known artifacts/limitations are documented; deferred items are clearly assigned to later phases.

## Phase 1 TODOs

- Confirm the default engine via the M1 A/B (OpenVoice V2 vs FreeVC); confirm checkpoint/attribution terms
  for whichever is bundled (FreeVC → VCTK ODC-By; WavLM weight license).
- Choose IPC transport + PCM payload mechanism (see `docs/architecture.md`).
- Choose profile storage backend (lean SQLite) and freeze the v1 profile schema.
- Select Python version, dependency tool, and test runner; replace `pyproject.toml` placeholders.
- Decide ffmpeg bundling approach.
