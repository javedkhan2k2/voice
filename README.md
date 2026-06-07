# voicebuilder

Windows 11 desktop application for **offline audio-to-target-voice conversion**. It transforms a
source speech recording so it matches a target speaker's voice, entirely on-device — no cloud,
no accounts, no audio ever leaves the machine.

> **What this is:** voice conversion (audio → audio).
> **What this is not:** TTS, transcription, or singing conversion.

---

## How it works

1. **Create a voice profile** from a short reference clip (3–30 s). A consent gate enforces that
   you own or have explicit permission to use the target voice. The consent record is persisted.
2. **Convert** a source speech file against that profile. The model runs locally on GPU (NVIDIA/CUDA)
   or CPU, in an isolated subprocess so a crash fails the job — not the app.
3. **Preview and export** the result as WAV or FLAC with A/B comparison to the source.

Target voices are derived **zero-shot** from the reference clip — no per-voice training required.

---

## Status

| Phase | Description | Status |
|---|---|---|
| Phase 0 | Model selection bake-off | **Complete** |
| Phase 1 / M1 | Engine interface + worker boundary | **Complete** (29/29 tests passing) |
| Phase 1 / M2 | Audio pipeline (ffmpeg decode/encode) | Not started |
| Phase 1 / M3 | Headless conversion path | Not started |
| Phase 1 / M4 | Storage + consent | Not started |
| Phase 1 / M5 | GUI MVP (PySide6) | Not started |
| Phase 1 / M6 | Offline + integration hardening | Not started |
| Phase 2 | Batch queue + profile management | Not started |
| Phase 3 | Safeguards + provenance | Not started |
| Phase 4 | Packaging + beta (Inno Setup installer) | Not started |

See [`progress.md`](progress.md) for the detailed tracker.

---

## Stack

| Concern | Choice |
|---|---|
| Language | Python 3.13+ |
| GUI | PySide6 (Qt 6), MVVM-style |
| Inference | PyTorch, CUDA preferred with CPU fallback |
| Default VC model | OpenVoice V2 (MIT code + weights) |
| Alternative model | FreeVC (MIT code; checkpoint license to confirm) |
| Audio I/O | ffmpeg (bundled binary) |
| Packaging | Embedded CPython + Inno Setup |
| IPC | Length-prefixed JSON over stdio + `multiprocessing.shared_memory` for PCM |

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│ app/            GUI layer — PySide6 views + view-models    │
├──────────────────────────────────────────────────────────┤
│ services/       jobs, queue, profiles, settings, consent   │
├───────────────────────────┬──────────────────────────────┤
│ audio/  decode→resample→  │ inference/  engine API +       │
│         chunk→encode      │   WorkerAdapter                │
│                           │      ── process boundary ──    │
│                           │ worker/  PyTorch model host     │
├──────────────────────────────────────────────────────────┤
│ storage/        profiles, consent records, job history     │
├──────────────────────────────────────────────────────────┤
│ platform_support/  OS shims: paths, GPU detection, ffmpeg  │
└──────────────────────────────────────────────────────────┘
```

**Key invariants:**
- The GUI never imports a model or audio backend directly.
- Inference runs behind a process boundary — it can be hard-killed without affecting the app.
- All model adapters implement one interface (`VoiceConversionEngine`); swapping models is a new adapter.
- **No network calls in the conversion path.** The offline runtime invariant is non-negotiable.

Full architecture detail: [`docs/architecture.md`](docs/architecture.md).

---

## Repository layout

```
src/voiceconv/
├── inference/          VoiceConversionEngine ABC, IPC, shm, WorkerAdapter
├── worker/             Isolated model-host subprocess + engine adapters
├── audio/              Audio pipeline (M2, not started)
├── services/           Job orchestration, consent enforcement (M3–M4)
├── storage/            Profile + consent + settings persistence (M4)
├── app/                PySide6 GUI (M5)
└── platform_support/   OS-specific shims

scripts/
└── ab_listen_test.py   Headless A/B runner (OpenVoice V2 vs FreeVC)

tests/
├── inference/          IPC unit tests + WorkerAdapter integration tests
└── worker/             Host dispatch unit tests (in-process BytesIO)

docs/
├── spec.md             Product specification
├── architecture.md     Layered architecture + key interfaces
└── phases/             Per-phase execution plans + status
```

---

## Development setup

> Full environment is not yet finalized. The steps below reflect the current dev state (M1).

```powershell
# Python 3.13.5, venv
python -m venv .venv
.venv\Scripts\python -m pip install numpy pytest

# Run tests (29/29 should pass)
.venv\Scripts\python -m pytest -v
```

The package is not installed in editable mode yet (`pip install -e .` is deferred until the build
backend is chosen). `WorkerAdapter` propagates `PYTHONPATH=src/` to the worker subprocess for
dev-mode compatibility.

Remaining setup TODOs: Python/PyTorch/CUDA version pin, build backend selection, CI wiring,
ffmpeg bundling, and OpenVoice V2 / FreeVC weight-fetch script.

---

## Safeguards (non-negotiable)

- **No silent recording.** Any voice-capture feature requires explicit user consent before capturing.
- **Consent gate on profile creation.** The user must affirm ownership of, or permission for, the
  target voice. The consent record (`{timestamp, acknowledgement, profile_id}`) is persisted.
- **Output provenance.** Generated audio is marked as AI voice-converted by this tool.
- **Offline runtime.** No code in the conversion path may open a network connection.
- **Impersonation / fraud safeguards remain intact.** This tool is not optimized for misuse.

---

## Docs

| Document | Purpose |
|---|---|
| [`docs/spec.md`](docs/spec.md) | Product specification (authoritative scope) |
| [`docs/architecture.md`](docs/architecture.md) | Layered architecture, module boundaries, key interfaces |
| [`docs/phases/`](docs/phases/) | Per-phase execution plans |
| [`progress.md`](progress.md) | Live progress tracker across all phases |
| [`CLAUDE.md`](CLAUDE.md) | Rules and context for Claude Code sessions |
