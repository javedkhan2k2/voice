# CLAUDE.md

Guidance for Claude sessions working in this repository. Keep this file concise and stable;
detailed/volatile content belongs in `docs/`.

## Project overview

Windows 11 desktop GUI application that performs **audio-to-target-voice conversion**: it transforms a
user-supplied speech recording so it matches a target speaker's voice characteristics.

- This is **voice conversion (audio → audio)**. It is **not** TTS and **not** transcription.
- Target voices are defined **zero-shot** from a short reference clip (no per-voice training in v1).
- Inference is **strictly local / offline at runtime**. The app makes no network calls to convert audio.
  (Model weights and runtime may be fetched once at install time — see `docs/architecture.md`.)
- v1 mode is **batch** (file in → file out), with the pipeline shaped so real-time can be added later.

Authoritative specs: `docs/spec.md`, `docs/architecture.md`, `docs/phases/phase-1-mvp.md`.

## Stack

- **Language/runtime:** Python (GUI + core + inference in one language).
- **GUI:** PySide6 (Qt 6), MVVM-style views + view-models.
- **Inference:** PyTorch, NVIDIA/CUDA preferred with a CPU fallback, run in an **isolated worker process**.
- **Audio I/O:** bundled ffmpeg for decode/encode (TODO: confirm bundling mechanism).
- **Packaging:** embedded CPython + Inno Setup installer (TODO: finalize).
- **Default VC model:** **OpenVoice V2** (MIT on code + weights), with **FreeVC** as the alternative
  behind the same engine adapter. Final default pending a listening-test A/B in Phase 1. seed-VC is
  deferred (GPLv3 blocks proprietary bundling). See `docs/phases/phase-0-model-selection.md`.

## Architectural constraints (do not violate without updating docs)

- **Strict layering, dependencies point downward:** GUI → services → (audio | inference) → storage.
  The GUI layer **never** imports a model or audio backend directly.
- **Inference runs behind a process boundary**, not in-process, so it can crash, be hard-cancelled, and
  later be swapped for a faster runtime without touching the GUI.
- **Models sit behind one interface** (`VoiceConversionEngine`). Adding/replacing a model is a new adapter.
- **Core is portable:** services/audio/storage/inference-interface are OS-agnostic Python. Anything
  OS-specific (paths, device detection, packaging, ffmpeg binary) lives behind `platform_support/`.
- **Offline runtime is an invariant.** No code in the conversion path may open a network connection.

## Repo conventions

- Source under `src/voiceconv/`, one subpackage per layer (see `docs/architecture.md`).
- Tests under `tests/`, mirroring the package layout.
- Public APIs are typed; prefer explicit interfaces between layers over cross-layer imports.
- Keep `docs/` authoritative — update the relevant doc in the same change that alters behavior.
- No secrets, no telemetry, no audio leaves the machine.

## Build / test / run (placeholders)

- Environment setup: TODO (Python version, virtualenv/dependency tool not finalized).
- Install deps: TODO.
- Run app: TODO (`python -m voiceconv` entrypoint not implemented yet).
- Run tests: TODO (test runner not selected).
- Build installer: TODO (Inno Setup pipeline not implemented).

## Rules for future Claude sessions

- **All features involving voice capture or model training must include explicit user consent mechanisms.
  No silent recording.**
- Enforce the **consent gate** on voice-profile creation: the user must affirm ownership of, or explicit
  permission for, the target voice; persist the consent record.
- Preserve the **offline-runtime invariant**; never add a network call to the conversion path.
- Maintain **output provenance** (mark generated audio as AI voice-converted by this tool).
- Do not collapse the GUI/inference process boundary or let the GUI import models directly.
- Do not introduce cloud inference, accounts, or telemetry without an explicit spec change.
- When a command, dependency, package name, or model is not finalized, write `TODO` — do not guess.
- This is a dual-use tool: keep impersonation/fraud safeguards intact; do not optimize for misuse.
