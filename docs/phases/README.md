# Phases Index

Execution roadmap for the Windows 11 voice-conversion app. Product scope lives in
[`../spec.md`](../spec.md); architecture in [`../architecture.md`](../architecture.md). This file is the
sequencing/status index — keep it current as milestones land.

## Dependency order

```
phase-0 (model)  →  phase-1 (MVP)  →  phase-2 (queue/mgmt)  →  phase-3 (safeguards)  →  phase-4 (packaging)
```

Each phase assumes the previous phase's **exit criteria** are met.

## Phases

| Phase | Doc | Focus | Status |
|---|---|---|---|
| 0 | [phase-0-model-selection.md](phase-0-model-selection.md) | Zero-shot VC model bake-off; default engine = OpenVoice V2, FreeVC alternative, seed-VC deferred (GPLv3) | **Complete** |
| 1 / M1 | [phase-1-mvp.md](phase-1-mvp.md) | `VoiceConversionEngine` ABC, worker subprocess, IPC (stdio + shared memory), mock engine, 29 tests passing | **Complete** (2026-06-07) |
| 1 / M2 | [phase-1-mvp.md](phase-1-mvp.md) | Audio pipeline: `FfmpegLoader` (pipe decode, resample), `FfmpegEncoder` (pipe encode, WAV/FLAC), `rms_normalize`, `AudioEncoder` protocol, `get_ffmpeg_path()`; 16 tests | **Complete** (2026-06-07) |
| 1 / M3 | [phase-1-mvp.md](phase-1-mvp.md) | Headless conversion path: `Converter` class — `prepare_profile(ref)` + `convert_file(src, profile, params, out)`; cancel + VRAM release; profile reuse; 7 tests | **Complete** (2026-06-07) |
| 1 / M4 | [phase-1-mvp.md](phase-1-mvp.md) | Storage + consent: `ConsentRecord` (required), `VoiceProfile` (frozen, consent structurally enforced), `JsonFileProfileRepository`, `AppSettings`, `SettingsStore`, `setup_logging()`; 24 tests | **Complete** (2026-06-07) |
| 1 / M5 | [phase-1-mvp.md](phase-1-mvp.md) | GUI MVP (PySide6): first-run probe, profile creation (consent gate), convert, A/B preview, export | Not started |
| 1 / M6 | [phase-1-mvp.md](phase-1-mvp.md) | Offline + integration hardening: self-check, GPU + CPU end-to-end, responsiveness on long files | Not started |
| 2 / M1 | [phase-2-queue-and-management.md](phase-2-queue-and-management.md) | Queue engine (services layer): `JobStatus` state machine, `JobQueue`, `JsonFileJobRepository`, `PcmLoader` protocol, `QueueRunner`; 43 tests | **Complete** (2026-06-07) |
| 2 / M2 | [phase-2-queue-and-management.md](phase-2-queue-and-management.md) | Queue UI (PySide6): add files, per-job progress/ETA/status, cancel/retry, open output folder | Not started |
| 2 / M3 | [phase-2-queue-and-management.md](phase-2-queue-and-management.md) | Profile library UI: browse/rename/delete profiles; consent record visible per profile | Not started |
| 2 / M4 | [phase-2-queue-and-management.md](phase-2-queue-and-management.md) | Settings UI + persistence: `SettingsStore`; engine/device switch; storage-location migration | Not started |
| 2 / M5 | [phase-2-queue-and-management.md](phase-2-queue-and-management.md) | Diagnostics: rotating logs; one-click diagnostics-bundle export (excludes audio) | Not started |
| 2 / M6 | [phase-2-queue-and-management.md](phase-2-queue-and-management.md) | Accessibility pass: keyboard nav, screen-reader labels, high-DPI/contrast, no color-only status cues | Not started |
| 3 | [phase-3-safeguards-and-provenance.md](phase-3-safeguards-and-provenance.md) | Consent-record finalization, output provenance, acceptable-use guidance, watermark evaluation, offline hardening | Not started |
| 4 | [phase-4-packaging-and-beta.md](phase-4-packaging-and-beta.md) | Embedded-Python bundle, install-time weight fetch, Inno Setup installer, hardening, clean-VM beta | Not started |

## Cross-phase decisions to resolve

These span multiple phases; resolving them early avoids rework.

- **App's own license (open-source vs proprietary)** — gates the seed-VC reconsideration (Phase 0), legal
  copy review (Phase 3), and the dependency license audit + code-signing (Phase 4).
- **Provenance depth (metadata-only vs +inaudible watermark)** — opened in spec, decided in Phase 3 (M4),
  consumed by Phase 4.
- **Default engine confirmation** — provisional (OpenVoice V2); settled by the Phase 1 (M1) listening-test
  A/B against FreeVC.
