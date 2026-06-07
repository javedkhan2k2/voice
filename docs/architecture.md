# Architecture

Architecture for the v1 Windows desktop voice-conversion app. Product scope is in `docs/spec.md`.

## Principles

- **Strict layering, dependencies point downward.** Upper layers depend on lower ones, never the reverse.
- **The GUI never touches models or audio backends directly** — only the services layer.
- **Inference runs in a separate process**, behind one engine interface.
- **The core is OS-agnostic;** platform specifics are quarantined behind a single seam.
- **Offline runtime is an invariant** — no network in the conversion path.

## Layered overview

```
┌──────────────────────────────────────────────────────────┐
│ app/            GUI layer — PySide6 views + view-models    │
├──────────────────────────────────────────────────────────┤
│ services/       jobs, queue, profiles, settings, consent,  │
│                 orchestration (portable core, GUI-agnostic) │
├───────────────────────────────┬──────────────────────────┤
│ audio/  decode→resample→       │ inference/  engine API +   │
│         chunk→encode pipeline  │   in-process adapter       │
│                                │      ── process boundary ──┤
│                                │ worker/  PyTorch model host │
├──────────────────────────────────────────────────────────┤
│ storage/        app data, profiles, settings, model manifest│
├──────────────────────────────────────────────────────────┤
│ platform_support/  OS shims: paths, device/GPU detection    │
└──────────────────────────────────────────────────────────┘
```

## Module boundaries

| Package | Responsibility | Must not |
|---|---|---|
| `app/` | Qt views + view-models; dispatch user intent to services; render progress/state. | Import models/audio backends; run heavy work on the UI thread. |
| `services/` | Job queue, cancellation, profile lifecycle, consent enforcement, settings, orchestration of pipeline + engine. | Contain Qt or model code; this layer must run headless. |
| `audio/` | ffmpeg-backed decode/encode, resampling, mono/stereo handling, chunking, loudness normalization. Chunk-shaped (streaming-ready). | Know about the GUI or specific models. |
| `inference/` | `VoiceConversionEngine` interface + in-process adapter that owns the worker handle and IPC. | Run model code in-process; block the caller without cancellation. |
| `worker/` | Separate-process host that loads PyTorch + the chosen model and serves convert/prepare requests. | Import GUI or services packages. |
| `storage/` | App-data layout, profile repository, settings store, model manifest/cache, history. | Contain business logic or model code. |
| `platform_support/` | OS-specific shims: data paths, GPU/CUDA detection, ffmpeg locating. Only place with `if windows/...`. | Leak OS specifics into other layers. |

## Key interfaces (conceptual; not yet implemented)

- `VoiceConversionEngine`
  - `capabilities()` → supported rates, devices, limits.
  - `prepare_profile(reference_audio) -> ProfileArtifacts` — derive zero-shot voice representation.
  - `convert(source_pcm, profile, params) -> output_pcm` — chunk-callable, cancellable, progress callbacks.
  - `warmup()` / `release()` — model load and VRAM teardown.
- `ProfileRepository` — CRUD for voice profiles + consent records.
- `SettingsStore` — versioned settings read/write.
- `AudioCodec` — decode/encode between container formats and internal float32 PCM.

The GUI depends only on services; services depend on these interfaces, not concrete implementations.

## Data & control flow (single conversion)

1. `app/` collects source file + chosen profile + params; calls a services command (async, off UI thread).
2. `services/` validates inputs, enforces consent/state, enqueues a job.
3. `audio/` decodes source → internal float32 PCM and yields chunks.
4. `inference/` adapter streams chunks across the **process boundary** to `worker/`; the worker runs the
   model on GPU/CPU and returns converted PCM with progress.
5. `audio/` encodes the result to the chosen output format; loudness-normalized if enabled.
6. `storage/` records job history + output path + provenance metadata.
7. `app/` updates progress and offers A/B preview / export.

Cancellation: cooperative stop signal → escalates to worker-process termination; partial output discarded.

## IPC across the process boundary

- Control messages: length-prefixed JSON over stdio or a local socket (TODO: pick one in Phase 1).
- Audio payloads: shared memory or temp files to avoid copying large PCM buffers (TODO: confirm).
- The worker is launched, monitored, and torn down by the `inference/` adapter.

## Extensibility points

- **New models:** add a `VoiceConversionEngine` implementation; no GUI/services change.
- **Real-time mode (future):** the audio pipeline is already chunk-shaped; add a streaming engine + a live
  I/O source/sink behind the same services orchestration.
- **Alternative inference runtime (future):** replace the `worker/` internals (e.g. ONNX Runtime / C++)
  without touching layers above the engine interface.
- **Alternative GUI shell (future, e.g. Avalonia/.NET):** because inference and core sit behind a process
  boundary / interfaces, the shell can be replaced without rewriting the core.

## Portability strategy

- `services/`, `audio/`, `inference/` (interface), `storage/` are pure, OS-agnostic Python.
- All OS-specific behavior is confined to `platform_support/` (paths, device detection, ffmpeg locating)
  plus the `packaging/` artifacts.
- Qt + Python already run on macOS/Linux, so a future port is "new installer + platform shims + bundled
  binaries," not a rewrite.

## Architectural decisions that are costly to change later (flag for review)

> These should be deliberately confirmed early; reversing them mid-project forces broad refactors.

1. **Inference as a separate process vs in-process.** Chosen: **separate process.** Reversing later
   (or having chosen in-process first) touches the entire inference/worker boundary, cancellation model,
   and IPC. **High refactor cost — keep the boundary from day one.**
2. **GUI framework = PySide6/Qt.** Switching desktop frameworks later is a near-rewrite of `app/`. The
   process boundary limits blast radius to the GUI layer, but it is still expensive. (Confirmed in plan.)
3. **Strictly-local runtime invariant.** Code is written assuming no network in the conversion path. Adding
   cloud inference later is an additive adapter, but relaxing "offline-by-design" affects privacy posture,
   UI affordances, and the worker contract.
4. **Voice profile data model & on-disk format.** Profiles bind to an engine id + version and a consent
   record. Getting the schema wrong forces migrations of user data. Define versioned storage up front.
5. **IPC payload mechanism for PCM** (shared memory vs temp files vs streaming). Changing it later affects
   the worker contract and performance characteristics, especially when real-time is added. (TODO: decide
   in Phase 1.)
6. **Internal audio representation** (float32 PCM at model-native rate). Changing the canonical internal
   format ripples through `audio/` and every engine adapter.

## Open architectural TODOs

- IPC transport (stdio vs local socket) and PCM payload mechanism.
- Default model and its runtime (PyTorch only vs ONNX path) — set in Phase 0.
- ffmpeg bundling/licensing approach.
- Profile storage backend (SQLite vs flat files) — lean SQLite for history; confirm in Phase 1.
