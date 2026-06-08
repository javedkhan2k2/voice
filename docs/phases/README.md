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
| 1 / M5 | [phase-1-mvp.md](phase-1-mvp.md) | GUI MVP (PySide6): first-run probe, profile creation (consent gate), convert, A/B preview, export | **Complete** (2026-06-07) |
| 1 / M6 | [phase-1-mvp.md](phase-1-mvp.md) | Offline + integration hardening: `check_offline_invariant()`, E2E tests (roundtrip, progress, cancel, FLAC), 30-second large-buffer test, app startup robustness | **Complete** (2026-06-07) |
| 2 / M1 | [phase-2-queue-and-management.md](phase-2-queue-and-management.md) | Queue engine (services layer): `JobStatus` state machine, `JobQueue`, `JsonFileJobRepository`, `PcmLoader` protocol, `QueueRunner`; 43 tests | **Complete** (2026-06-07) |
| 2 / M2 | [phase-2-queue-and-management.md](phase-2-queue-and-management.md) | Queue UI (PySide6): add files, per-job progress/ETA/status, cancel/retry, open output folder; `QueueBridge` (thread-safe signal relay), `QueueViewModel`, `QueueView`; engine-lock serialisation between Convert tab and QueueRunner; 13 tests | **Complete** (2026-06-07) |
| 2 / M3 | [phase-2-queue-and-management.md](phase-2-queue-and-management.md) | Profile library UI: browse/rename/delete profiles; consent record visible per profile; `ProfileLibraryViewModel`, `ProfileLibraryView`; 11 tests | **Complete** (2026-06-07) |
| 2 / M4 | [phase-2-queue-and-management.md](phase-2-queue-and-management.md) | Settings UI + persistence: `AppSettings` extended (loudness_normalize, log_level, active_engine); `SettingsViewModel`, `SettingsView`; device/loudness wired into `ConvertParams`; output_dir blocked while running; 9 tests | **Complete** (2026-06-07) |
| 2 / M5 | [phase-2-queue-and-management.md](phase-2-queue-and-management.md) | Diagnostics: rotating logs (already present); `services/diagnostics.py` — `collect_app_info()` + `build_bundle()`; one-click diagnostics-bundle export (logs + env manifest, audio-excluded by name whitelist + extension denylist); "Export Diagnostics…" in Settings; 13 tests | **Complete** (2026-06-08) |
| 2 / M6 | [phase-2-queue-and-management.md](phase-2-queue-and-management.md) | Accessibility pass: accessibleName on all controls (incl. per-row Queue context), Alt mnemonics, AA-contrast status colours, status conveyed by text not colour; checklist in `docs/accessibility.md`; 12 tests | **Complete** (2026-06-08) |
| 3 / M1 | [phase-3-safeguards-and-provenance.md](phase-3-safeguards-and-provenance.md) | Consent-record finalization: versioned schema (timestamp, statement, profile_id, app_version) bound to its profile; `voiceconv.__version__`; load-time enforcement (no profile without consent); `docs/consent.md`; 9 tests | **Complete** (2026-06-08) |
| 3 / M2 | [phase-3-safeguards-and-provenance.md](phase-3-safeguards-and-provenance.md) | Output provenance metadata: `audio/_provenance.py` marker embedded in WAV (RIFF INFO) + FLAC (Vorbis) via both encoders; survives export copy; `file_has_provenance()` verifier; `docs/provenance.md`; 11 tests | **Complete** (2026-06-08) |
| 3 / M3 | [phase-3-safeguards-and-provenance.md](phase-3-safeguards-and-provenance.md) | Acceptable-use guidance: centralized reviewed copy (`app/_guidance.py`), contextual reminders on Create Profile + Convert, re-viewable terms in Settings, acknowledged-version recorded; copy-guard tests; `docs/acceptable-use.md`; 7 tests | **Complete** (2026-06-08) |
| 3 / M4 | [phase-3-safeguards-and-provenance.md](phase-3-safeguards-and-provenance.md) | Watermark evaluation: spread-spectrum spike (`audio/_watermark.py`, experimental) + measurement harness; survives lossless/MP3 but fails trim/resample → **decision: DEFER to fast-follow**, metadata provenance ships as baseline; `docs/watermark-eval.md`; 7 tests | **Complete** (2026-06-08) |
| 3 / M5 | [phase-3-safeguards-and-provenance.md](phase-3-safeguards-and-provenance.md) | Offline-invariant hardening: `block_network()` context manager + `verify_offline()` self-check; status-bar offline indicator; Settings "Verify offline" button; `docs/offline.md`; 4 tests. **Phase 3 complete.** | **Complete** (2026-06-08) |
| 4 | [phase-4-packaging-and-beta.md](phase-4-packaging-and-beta.md) | Embedded-Python bundle, install-time weight fetch, Inno Setup installer, hardening, clean-VM beta | Not started |

## Cross-phase decisions to resolve

These span multiple phases; resolving them early avoids rework.

- **App's own license (open-source vs proprietary)** — gates the seed-VC reconsideration (Phase 0), legal
  copy review (Phase 3), and the dependency license audit + code-signing (Phase 4).
- **Provenance depth (metadata-only vs +inaudible watermark)** — opened in spec, **decided in Phase 3 M4:
  metadata-only for v1; inaudible watermark deferred to a fast-follow** (see `docs/watermark-eval.md`).
- **Default engine confirmation** — provisional (OpenVoice V2); settled by the Phase 1 (M1) listening-test
  A/B against FreeVC.
