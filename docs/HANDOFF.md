# Session Handoff

Copy the prompt below to start a fresh session (any model) and continue this project. The new session has
no memory of prior work — the prompt points it at the docs, which are the source of truth.

---

```
You are continuing work on an existing project. Repository root: E:\Projects\voicebuilder
(Windows 11, PowerShell). The repo currently contains documentation and an empty scaffold only —
no implementation code yet.

START BY READING THESE, IN ORDER:
- CLAUDE.md                                   (stack, constraints, rules — authoritative)
- docs/spec.md                                (v1 product spec)
- docs/architecture.md                        (module boundaries, refactor-risk flags)
- docs/phases/README.md                       (phase index + dependency order + open decisions)
- docs/phases/phase-0-model-selection.md      (model decision)
- docs/phases/phase-1-mvp.md                  (the work to do next)

PROJECT IN ONE LINE:
A Windows 11 desktop GUI app that converts a source speech recording into a target person's voice
(audio-to-audio voice conversion — NOT TTS, NOT transcription).

LOCKED DECISIONS (do not relitigate without flagging):
- Stack: Python; PySide6/Qt GUI; PyTorch inference in an ISOLATED WORKER PROCESS.
- Mode: batch (file in → file out), v1; pipeline must stay streaming-friendly for future real-time.
- Voice profiles: zero-shot from a short reference clip (no per-voice training in v1).
- Inference: strictly local/offline at RUNTIME (weights may be fetched once at install time).
- Hardware: NVIDIA GPU preferred, CPU fallback must complete.
- Default model: OpenVoice V2 (MIT code+weights); FreeVC as the alternative behind the engine adapter;
  seed-VC deferred (GPLv3 blocks proprietary bundling).
- Mandatory safeguards: consent gate on profile creation, NO silent recording, output provenance,
  offline-runtime invariant. These are non-negotiable product requirements.

KEY OPEN DECISIONS (carried across phases — surface them, don't silently assume):
- The app's OWN license (open-source vs proprietary) — gates whether seed-VC is reconsidered, the
  dependency license audit, and code-signing.
- Provenance depth: metadata-only vs + inaudible watermark.
- IPC transport + PCM payload mechanism for the GUI↔worker boundary.
- Python/PyTorch/CUDA pinned versions; test runner; profile/queue storage backend (leaning SQLite).

WORKING RULES:
- Where a command, package, version, or model detail isn't finalized, write `TODO` — do NOT guess.
- Do not collapse the GUI/inference process boundary; the GUI must never import models directly.
- Keep the core (services/audio/storage/engine-interface) OS-agnostic; OS specifics go in
  src/voiceconv/platform_support/.
- Update the relevant doc in the same change that alters behavior.

YOUR TASK THIS SESSION — Phase 1, Milestone M1 (see docs/phases/phase-1-mvp.md):
Design and define the `VoiceConversionEngine` interface and the inference worker-process boundary
(IPC transport, message contract, PCM payload mechanism, lifecycle: warmup/convert/prepare_profile/
release, cancellation, progress). Include the M1 listening-test A/B plan (OpenVoice V2 vs FreeVC).

Start in PLAN MODE: propose the interface, the worker boundary design, and the file tree you intend to
create BEFORE writing any code. Ask me clarifying questions only where a decision is genuinely
load-bearing and underconstrained. Do not write implementation code until the plan is approved.
```

---

## Notes

- The "YOUR TASK" block targets **Phase 1 / M1** (engine interface + worker boundary) — the natural entry
  point and the riskiest architectural seam. Swap that block to redirect the next session.
- Current repo state at handoff: documentation + empty scaffold; no implementation code. See
  [phases/README.md](phases/README.md) for phase status.
