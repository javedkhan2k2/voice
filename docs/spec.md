# v1 Product Specification

Audio-to-target-voice conversion desktop app for Windows 11. This document is the authoritative product
spec for v1. Architecture is in `docs/architecture.md`; MVP execution is in `docs/phases/phase-1-mvp.md`.

## Scope summary

Convert a source speech recording into a chosen target voice, fully offline, with usable quality. The
target voice is defined **zero-shot** from a short reference clip. v1 is **batch** (file in → file out).

## Goals

- Convert a source speech file into a selected target voice, entirely on-device.
- Create and manage zero-shot **voice profiles** from short reference clips, each with a consent record.
- Batch a queue of files against one profile; show progress; cancel cleanly; export standard formats.
- Run acceptably on an NVIDIA GPU and degrade (not break) on CPU.

## Non-goals (v1)

- Real-time / live microphone conversion (architecture preserves it; not shipped).
- Per-voice model training / fine-tuning (RVC-style).
- TTS, transcription, singing/lyric conversion, multi-speaker diarization, denoising suite.
- Cloud inference, accounts, sync, or a voice marketplace.
- macOS/Linux builds (architecture stays portable; not built).
- Telemetry/analytics.

## User flows

1. **First run:** hardware probe (GPU/CUDA/VRAM) → one-time model/runtime setup → acceptable-use
   acknowledgement.
2. **Create voice profile:** import reference clip → validate/auto-trim → **affirm consent/ownership** →
   name and save profile.
3. **Convert (single):** add source file → pick profile → set output format/options → Convert → progress →
   A/B preview (source vs output) → export.
4. **Batch queue:** add multiple source files → run sequentially → per-job status / cancel / retry → open
   output folder.
5. **Manage:** browse profiles and job history; delete a profile (and its artifacts); view/export
   diagnostics.

## Functional requirements

- Import source audio and decode common formats to internal PCM.
- Create / list / rename / delete voice profiles; each stores reference artifacts + metadata + consent.
- Single-profile batch queue: sequential execution, progress %, ETA, cancel, retry.
- Convert with selectable output sample rate/format; optional loudness normalization.
- In-app playback with A/B source-vs-output preview.
- Persistent job history (input/output paths, parameters, status).
- Settings: model selection, device (auto/GPU/CPU), output defaults, storage location, log level.
- Exportable diagnostics bundle (logs + hardware/model versions; **never** audio).

## Non-functional requirements

- **Throughput target:** ≤ ~1× realtime on a mid NVIDIA GPU; CPU may be several× slower with a clear
  warning. (TODO: confirm once default model is chosen.)
- **Responsiveness:** GUI never blocks during conversion (work runs off the UI thread / in the worker).
- **Memory:** bounded; release VRAM between jobs; long files handled via chunking.
- **Reliability:** a model/worker crash fails the *job*, not the app; the queue is resumable.
- **Determinism:** same input + profile + params yields consistent output (TODO: confirm per model).

## Supported audio formats

- **Input (decode):** WAV, FLAC, MP3, M4A/AAC, OGG/Opus.
- **Output (encode):** WAV (PCM 16/24-bit) and FLAC guaranteed; MP3 optional.
- **Internal working format:** float32 PCM at the model's native rate; resampled as needed.

## Local vs cloud processing

- **100% local at runtime.** No network calls in the conversion path; the offline invariant is enforced
  and surfaced in the UI, with a "verify offline" self-check.
- Network is used **only** at install/setup time to fetch weights + runtime, with explicit consent and a
  checksum-verified manifest.

## Privacy & security

- All audio stays on local disk; nothing is uploaded.
- App data lives under the user profile; deleting a profile removes its artifacts.
- Model weights are checksum-verified at install.
- No telemetry. The only network use (install-time fetch) is explicit and disclosed.
- TODO: optional encryption-at-rest for profiles (post-v1 candidate).

## Consent & misuse-prevention requirements (first-class)

- **No silent recording.** Any voice capture or training feature must obtain explicit user consent before
  capturing audio.
- **Consent gate on profile creation:** the user must affirm they own the target voice or have the
  speaker's explicit permission; persist `{timestamp, acknowledgement text, profile id}`.
- **Acceptable-use acknowledgement** at first run (no impersonation, fraud, or harassment).
- **Output provenance:** mark generated audio as AI voice-converted by this tool (metadata in v1;
  inaudible audio watermark under evaluation — TODO).
- In-product acceptable-use guidance; the product is not positioned for impersonation.

## Open product decisions (TODO)

- Default VC model and its license bar (must permit bundled distribution).
- Provenance depth for v1: metadata-only vs required audio watermark.
- MP3 output inclusion in v1.
- Installer strategy: single GPU+CPU build vs base (CPU) + optional GPU pack.
