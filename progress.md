# Project Progress

Windows 11 desktop app — offline audio-to-target-voice conversion.
Tracks what is done, what is in progress, and what is next across all phases.

---

## Phase 0 — Model Selection
**Status: Complete (recommendation locked)**
**Date completed: prior to 2026-06-07**

### What was done
- Evaluated four zero-shot VC models against hard constraints: audio-to-audio VC,
  zero-shot from a short reference clip, strictly local/offline at runtime,
  NVIDIA GPU + CPU fallback, license must permit bundled redistribution.
- Scored candidates on license/bundling fit, short-clip quality, CPU fallback,
  VRAM footprint, real-time future fit, and maintenance maturity.

### Decisions locked
| Decision | Outcome |
|---|---|
| Default engine | **OpenVoice V2** (MIT code + weights — cleanest license, lowest legal risk) |
| Alternative engine | **FreeVC** (MIT code; checkpoint license + VCTK ODC-By attribution to confirm before bundling) |
| Deferred | **seed-VC** — GPLv3 blocks proprietary bundling; revisit only if app commits to GPL |
| Deferred | **kNN-VC** — needs minutes of reference audio; candidate for future high-fidelity opt-in mode |

### Residual TODOs (carry forward)
- [ ] Confirm WavLM-Large weight license on HuggingFace model card (low risk, treated as MIT)
- [ ] Confirm FreeVC checkpoint license + required VCTK ODC-By attribution text before bundling
- [ ] A/B listening test (OpenVoice V2 vs FreeVC) — scheduled for Phase 1 M1 once adapters are runnable
- [ ] Decide app's own license (open-source vs proprietary) — gates seed-VC reconsideration

---

## Phase 1 — MVP
**Status: Complete (M1–M6)**

### Milestone M1 — Core engine + worker boundary
**Status: Complete**
**Date completed: 2026-06-07**
**Tests: 29/29 passing**

#### What was built

**Interface layer (`src/voiceconv/inference/`)**

| File | Description |
|---|---|
| `engine.py` | `VoiceConversionEngine` ABC; `EngineCapabilities`, `ProfileArtifacts`, `ConvertParams` data classes; `CancelToken`; `CancelledError`, `EngineError` exceptions |
| `ipc.py` | Length-prefixed JSON wire protocol — `read_msg` / `write_msg` (4-byte LE uint32 header + UTF-8 JSON payload) |
| `shm_buffer.py` | `ShmBuffer` — `multiprocessing.shared_memory` wrapper for zero-copy PCM transfer across the process boundary |
| `worker_adapter.py` | `WorkerAdapter(VoiceConversionEngine)` — manages worker subprocess, routes IPC, handles shm lifecycle, cancel watcher thread, crash detection |

**Worker process (`src/voiceconv/worker/`)**

| File | Description |
|---|---|
| `__main__.py` | Entry point: `python -m voiceconv.worker --engine <id>` |
| `host.py` | Main dispatch loop; `convert` runs in a background thread so `cancel` messages remain readable during inference |
| `engines/__init__.py` | Engine registry: `{"openvoice_v2": …, "freevc": …, "mock": …}` |
| `engines/base.py` | `WorkerEngine` protocol (what `host.py` calls) |
| `engines/openvoice_v2.py` | OpenVoice V2 adapter stub — raises `NOT_INSTALLED` until weights + install script are ready |
| `engines/freevc.py` | FreeVC adapter stub — raises `NOT_INSTALLED`; includes attribution TODO |
| `engines/mock.py` | Fully working mock engine — echoes source audio, chunk-sleeps to allow cancel testing |

**A/B test runner (`scripts/`)**

| File | Description |
|---|---|
| `ab_listen_test.py` | Headless script: runs both engines against source+reference pairs, exports blind WAV pairs, prints latency + VRAM peak |

**Tests**

| File | Coverage |
|---|---|
| `tests/inference/test_ipc.py` | 10 unit tests — framing, unicode, large payloads, partial-read EOFs |
| `tests/inference/test_worker_adapter.py` | 10 integration tests — subprocess spawn, warmup, prepare_profile, convert, progress callbacks, mid-job cancel, stereo downmix, rewarm after release |
| `tests/worker/test_host.py` | 9 unit tests — dispatch loop with in-process BytesIO (no subprocess) |

#### Architectural decisions locked in Phase 1 M1
| Decision | Choice | Notes |
|---|---|---|
| IPC transport | stdio (length-prefixed JSON) for control + progress | Simple, no socket setup, reliable on Windows |
| PCM payload | `multiprocessing.shared_memory` | Zero-copy across process boundary; handles batch |
| `convert()` scope | Full buffer per call | Chunking is internal to the engine/worker |
| Worker lifespan | Persistent per session | Model stays in VRAM between jobs; `release()` frees VRAM on request |

#### Dev environment
- Python 3.13.5, venv at `.venv/`
- Dependencies installed: `numpy 2.4.6`, `pytest 9.0.3`
- `WorkerAdapter` propagates `PYTHONPATH=src/` to the subprocess (editable install deferred)
- `pyproject.toml`: `[tool.pytest.ini_options]` with `pythonpath = ["src"]`, `testpaths = ["tests"]`

#### Run tests
```
.venv\Scripts\python -m pytest -v
```

---

### Milestone M2 — Audio pipeline
**Status: Complete**
**Date completed: 2026-06-07**
**Tests: 16/16 new (88/88 total)**
**Branch: merged to main**

#### What was built

| File | Description |
|---|---|
| `src/voiceconv/platform_support/ffmpeg.py` | `get_ffmpeg_path()` — checks `VOICECONV_FFMPEG_PATH` env var then PATH; single OS-specific shim for binary location |
| `src/voiceconv/audio/_codec.py` | `FfmpegLoader` (pipe decode to float32 mono PCM; optional `-ar` resample baked at construction); `FfmpegEncoder` (pipe encode to WAV/FLAC inferred from extension); `_probe_sample_rate` (ffprobe → ffmpeg stderr fallback) |
| `src/voiceconv/audio/_normalize.py` | `rms_normalize(pcm, target_rms=0.1)` — numpy-only, no-op on silence; EBU R128 two-pass deferred |
| `src/voiceconv/audio/__init__.py` | Exports `FfmpegLoader`, `FfmpegEncoder`, `rms_normalize` |
| `src/voiceconv/services/_audio_encoder.py` | `AudioEncoder` protocol; `StdlibWavEncoder` fallback (replaces `_write_wav` in runner) |
| `src/voiceconv/services/runner.py` | `audio_encoder` param added (mirrors `pcm_loader`); `_write_wav` removed; defaults to `StdlibWavEncoder` — all 72 prior tests unchanged |
| `tests/audio/test_codec.py` | 9 tests (skipped if ffmpeg unavailable); round-trip decode→encode, resample, FLAC output, bad-path error |
| `tests/audio/test_normalize.py` | 7 tests (numpy-only, always run); RMS target, silence, float32 output |

#### Architectural decisions locked in Phase 1 M2
| Decision | Choice | Notes |
|---|---|---|
| Decode strategy | ffmpeg pipe (stdout) | No temp files; clean on process death |
| Encode strategy | ffmpeg pipe (stdin) | ffmpeg writes proper container headers; format inferred from extension |
| Resampling | ffmpeg `-ar` flag, baked into `FfmpegLoader` at construction | No extra Python dep (scipy/librosa/soxr); ffmpeg handles it |
| Loudness normalize | RMS only (numpy) | Simple, zero deps; EBU R128 two-pass deferred to M3/later |
| `AudioEncoder` injection | Optional; defaults to `StdlibWavEncoder` | Mirrors `PcmLoader` pattern; no breaking change to any existing test |
| ffmpeg binary location | `VOICECONV_FFMPEG_PATH` env var → `shutil.which("ffmpeg")` → error | Configurable; tests can override without touching PATH |

Depends on: M1 complete ✓

---

### Milestone M3 — Headless conversion path
**Status: Complete**
**Date completed: 2026-06-07**
**Tests: 7/7 new (95/95 total)**
**Branch: merged to main**

#### What was built

| File | Description |
|---|---|
| `src/voiceconv/services/converter.py` | `Converter` class — `prepare_profile(reference_path) -> ProfileArtifacts` and `convert_file(source, profile, params, output, progress, cancel_token)`; stateless, no queue |
| `tests/services/test_converter.py` | 7 integration tests using `WorkerAdapter("mock")` + `_MockPcmLoader` + `StdlibWavEncoder` |

#### API

```python
conv = Converter(engine, pcm_loader, audio_encoder)
profile = conv.prepare_profile("reference.wav")   # reusable across calls
conv.convert_file("source.wav", profile, params, "output.wav",
                  progress=cb, cancel_token=token)
```

#### Architectural decisions locked in Phase 1 M3
| Decision | Choice | Notes |
|---|---|---|
| Two methods vs one combined | `prepare_profile` + `convert_file` separate | Profile is reusable across multiple source files without re-processing |
| VRAM release on cancel | Caller's responsibility | `convert_file` re-raises `CancelledError`; caller calls `engine.release()` if desired |
| State | None | `Converter` holds no per-call state; safe to call from any thread |

Depends on: M2 ✓

---

### Milestone M4 — Storage + consent
**Status: Complete**
**Date completed: 2026-06-07**
**Tests: 24/24 new (119/119 total)**
**Branch: merged to main**

#### What was built

| File | Description |
|---|---|
| `src/voiceconv/storage/profile.py` | `ConsentRecord` (immutable, `create()` requires non-empty statement); `VoiceProfile` (frozen, `consent` is structurally required — no code path to create a profile without one); `ProfileRepository` ABC; `JsonFileProfileRepository` (atomic JSON write, corrupt-file skip on `list_all`) |
| `src/voiceconv/storage/settings.py` | `AppSettings` dataclass (device, output_format, output_dir, log_dir, schema_version); `SettingsStore` (atomic JSON, defaults on missing file, unknown-key forward-compat, missing-key backward-compat) |
| `src/voiceconv/storage/logging_setup.py` | `setup_logging(log_dir, level, max_bytes, backup_count)` — `RotatingFileHandler`, idempotent on same directory, does not call `basicConfig` (pytest-safe) |
| `src/voiceconv/storage/__init__.py` | Exports all public types |
| `tests/storage/test_profile.py` | 15 tests — consent/profile creation, empty-name/statement guards, UUID uniqueness, save/load round-trip, list, delete, corrupt-skip, schema_version, binary data |
| `tests/storage/test_settings.py` | 6 tests — defaults, round-trip, single-field update, unknown-key forward-compat, schema_version, atomic write |
| `tests/storage/test_logging_setup.py` | 3 tests — file created, message appears, double-call idempotent |

#### Consent gate enforcement

`VoiceProfile` is `frozen=True` and its `create()` factory requires a `ConsentRecord`.
`ConsentRecord.create()` rejects empty statements. There is no code path that produces
a `VoiceProfile` without a persisted, non-empty consent statement.

#### Architectural decisions locked in Phase 1 M4
| Decision | Choice | Notes |
|---|---|---|
| Storage backend | JSON files (atomic tmp+rename) | Consistent with `JsonFileJobRepository`; SQLite migration deferred |
| Consent enforcement | Structural (frozen dataclass, required field) | Not just documentation — the type system prevents bypassing |
| Settings compat | Forward-compat (unknown keys ignored) + backward-compat (missing keys → defaults) | Safe to add/remove fields in future schema versions |
| Logging | `RotatingFileHandler` on root logger, no `basicConfig` | pytest-safe; does not swallow test output |

Depends on: M1 ✓ (parallelizable with M5 once M3 is done)

---

### Milestone M5 — GUI MVP (PySide6)
**Status: Complete**
**Date completed: 2026-06-07**
**Tests: 15/15 new (134/134 total)**
**Branch: merged to main**

#### What was built

| File | Description |
|---|---|
| `src/voiceconv/__main__.py` | `python -m voiceconv` entry point |
| `src/voiceconv/platform_support/_app_paths.py` | `get_app_data_dir()` — resolves `%APPDATA%\voiceconv` |
| `src/voiceconv/platform_support/device.py` | `detect_device()` — PyTorch CUDA probe with `ImportError` fallback |
| `src/voiceconv/storage/settings.py` | Added `first_run_acknowledged: bool = False` to `AppSettings` (backward-compat) |
| `src/voiceconv/app/_app_state.py` | `AppState` dataclass — single DI container passed to all view-models |
| `src/voiceconv/app/_workers.py` | `PrepareProfileWorker` + `ConvertWorker` (QObject on QThread; cancel via `CancelToken`) |
| `src/voiceconv/app/main.py` | Bootstrap — `QApplication`, `AppState` construction, `MainWindow` launch, `engine.release()` on exit |
| `src/voiceconv/app/view_models/first_run_vm.py` | Device info, ack state, persists `first_run_acknowledged` via `SettingsStore` |
| `src/voiceconv/app/view_models/profile_vm.py` | Reference clip, name, consent gate; `create_profile()` launches `PrepareProfileWorker` |
| `src/voiceconv/app/view_models/convert_vm.py` | Source/output paths, profile selection, progress float, `is_running`, cancel; auto-suggests output path from source stem |
| `src/voiceconv/app/view_models/preview_vm.py` | `play_source()` / `play_output()` via `os.startfile`; `export_to()` via `shutil.copy2` |
| `src/voiceconv/app/views/first_run_dialog.py` | Device info label + acceptable-use text + affirm checkbox + Continue/Exit buttons |
| `src/voiceconv/app/views/profile_view.py` | Reference file picker, name field, consent checkbox, Create button, status label |
| `src/voiceconv/app/views/convert_view.py` | Source picker, profile `QComboBox`, output picker, `QProgressBar`, Convert/Cancel buttons |
| `src/voiceconv/app/views/preview_view.py` | Play Source / Play Output buttons + Export/Save As dialog |
| `src/voiceconv/app/views/main_window.py` | `QMainWindow` + `QTabWidget` (Create Profile / Convert / Preview & Export); first-run as modal `QDialog` |
| `tests/app/conftest.py` | Session-scoped `QApplication` singleton fixture (headless) |
| `tests/app/test_first_run_vm.py` | 3 tests — `detect_device()` keys, ack persistence, `needs_first_run` flag |
| `tests/app/test_profile_vm.py` | 6 tests — consent/name/path guards, success saves profile, `is_busy` flip |
| `tests/app/test_convert_vm.py` | 6 tests — source/profile guards, output path suggestion, done signal, `is_running` reset, cancel |

#### Architectural decisions locked in Phase 1 M5

| Decision | Choice | Notes |
|---|---|---|
| Converter vs QueueRunner | `Converter` directly | M5 is single-job; `QueueRunner` is for Phase 2 batch UI |
| Thread pattern | `QObject` worker + `QThread` | Proper signal/slot lifecycle; explicit cancel/cleanup |
| Navigation | First-run as `QDialog` (blocking); main as `QTabWidget` | Ack must be affirmed before entering the app |
| A/B preview | `os.startfile(path)` | No custom audio widget; system default player |
| Engine in M5 | `WorkerAdapter("mock")` | Real model weights deferred to after M6 |
| App data dir | `%APPDATA%\voiceconv` via `platform_support._app_paths` | OS-standard; no extra dependency |

Depends on: M4 ✓

---

---

### Milestone M6 — Offline + integration hardening
**Status: Complete**
**Date completed: 2026-06-07**
**Tests: 9/9 new (143/143 total)**
**Branch: merged to main**

#### What was built

| File | Description |
|---|---|
| `src/voiceconv/services/offline_check.py` | `check_offline_invariant(fn)` — patches `socket.socket.__init__` during *fn*; raises `AssertionError` if any network socket is opened; exported from `services/__init__.py` |
| `src/voiceconv/app/main.py` | Wrap `engine.warmup()` in `try/except EngineError` → `QMessageBox.critical` + `sys.exit(1)` so startup failures surface clearly |
| `src/voiceconv/app/views/main_window.py` | `QStatusBar` shows `detect_device()` note at startup (GPU name + VRAM or CPU warning) |
| `src/voiceconv/app/views/first_run_dialog.py` | Explicit CPU-speed warning when no GPU detected |
| `tests/integration/conftest.py` | `needs_ffmpeg` skip mark + `make_wav()` helper (mono 16-bit PCM sine-wave WAV) |
| `tests/integration/test_e2e.py` | 4 end-to-end tests: roundtrip WAV, progress callbacks monotone, cancel mid-run, FLAC output |
| `tests/integration/test_long_file.py` | 3 large-buffer tests: 30 s PCM (661 500 samples) via shared memory → mock worker; progress callbacks; cancel |
| `tests/integration/test_offline.py` | 2 offline invariant tests: full pipeline in `check_offline_invariant`; socket-detection self-test |

#### What was validated

- **Offline invariant**: the full `Converter` pipeline (FfmpegLoader → WorkerAdapter → FfmpegEncoder) opens no network sockets in the main process
- **End-to-end roundtrip**: `reference.wav` + `source.wav` → `output.wav`/`.flac` through the real audio stack + mock engine
- **Large-buffer transfer**: 30-second PCM (≈2.6 MB float32) passes through shared memory boundary without error; progress fires; cancel works
- **App robustness**: warmup failure shows a critical dialog rather than an unhandled exception

#### Notes

- E2E + offline tests ran fully (ffmpeg is on PATH in dev env); they auto-skip in environments without ffmpeg
- Overlap-add chunking is internal to real engine adapters and will be validated when model weights are installed (Phase 1 exit criteria note)

Depends on: M5 ✓

---

## Phase 2 — Queue and Management
**Status: M1 complete; M2–M6 not started**

### Milestone M1 — Queue engine (services layer)
**Status: Complete**
**Date completed: 2026-06-07**
**Tests: 43/43 new (72/72 total)**
**Branch: `phase-2-m1-queue-engine`**

#### What was built

| File | Description |
|---|---|
| `src/voiceconv/services/job.py` | `JobStatus` enum; `ConversionRequest` (frozen DC); `Job` (mutable DC) with `transition()` enforcing the state machine |
| `src/voiceconv/services/_pcm_loader.py` | `PcmLoader` protocol; `StdlibWavLoader` (stdlib `wave`; 8/16/24/32-bit PCM; mono downmix) |
| `src/voiceconv/services/_repository.py` | `JobRepository` ABC; `JsonFileJobRepository` (atomic write via tmp+rename; `RUNNING → QUEUED` on reload) |
| `src/voiceconv/services/queue.py` | `JobQueue` — thread-safe ordered list backed by a `JobRepository` |
| `src/voiceconv/services/runner.py` | `QueueRunner` — background thread drains the queue; per-job `CancelToken`; `on_progress` / `on_status` callbacks; retry re-enqueues same `job_id` (attempt++) |
| `tests/services/test_job.py` | 12 state machine unit tests |
| `tests/services/test_queue.py` | 16 queue + repository unit tests (incl. persist + restore) |
| `tests/services/test_runner.py` | 15 integration tests using `WorkerAdapter("mock")` — real subprocess, no GPU |

#### State machine
```
QUEUED → RUNNING → DONE
                 → CANCELLED
                 → FAILED → QUEUED (retry, attempt++)
QUEUED → CANCELLED → QUEUED (retry)
```
`DONE` is terminal (no retry). `RUNNING` jobs persisted at crash time are reloaded as `QUEUED`.

#### Architectural decisions locked in Phase 2 M1
| Decision | Choice | Notes |
|---|---|---|
| PCM loader | `PcmLoader` protocol injected at construction | Swap `StdlibWavLoader` → `FfmpegLoader` in Phase 1 M2 without touching runner |
| Persistence format | `JsonFileJobRepository` (one JSON file per job, atomic write) | `JobRepository` ABC; `SqliteJobRepository` deferred to Phase 1 M4 |
| Retry semantics | Same `job_id`, `attempt++`, re-enqueue | History preserved; simpler than issuing a new job_id |
| Output write | stdlib `wave` (16-bit PCM WAV) | Replaced by ffmpeg encode when Phase 1 M2 lands |

---

### Milestone M2 — Queue UI
**Status: Not started**

Planned scope: add files, see per-job progress/ETA/status, cancel/retry, open output folder.

Depends on: Phase 2 M1 ✓

---

### Milestone M3 — Profile library UI
**Status: Not started**

Planned scope: browse/rename/delete profiles; delete performs full artifact cleanup;
consent record visible per profile.

Depends on: Phase 2 M1 ✓ (parallelizable with M4, M5)

---

### Milestone M4 — Settings UI + persistence
**Status: Not started**

Planned scope: all settings read/write through `SettingsStore`; engine/device switch
takes effect on next job; storage-location change migrates safely.

---

### Milestone M5 — Diagnostics
**Status: Not started**

Planned scope: rotating logs; one-click diagnostics-bundle export that provably excludes audio.

---

### Milestone M6 — Accessibility pass
**Status: Not started**

Planned scope: keyboard navigation, screen-reader labels, high-DPI/contrast, no
color-only status cues across all new views.

---

## Phase 3 — Safeguards and Provenance
**Status: Not started** (depends on Phase 2 exit criteria)

Consent-record finalization, output provenance (metadata + watermark evaluation),
acceptable-use guidance, offline hardening.

## Phase 4 — Packaging and Beta
**Status: Not started** (depends on Phase 3)

Embedded-Python bundle, install-time weight fetch with checksum verification,
Inno Setup installer, clean-VM beta test.

---

## Open decisions (cross-phase, unresolved)

| Decision | Blocks | Notes |
|---|---|---|
| App's own license (open-source vs proprietary) | seed-VC reconsideration; dependency audit; code-signing | Must be resolved before Phase 4 |
| Provenance depth: metadata-only vs + inaudible watermark | Phase 3 / Phase 4 | Opened in spec; decided in Phase 3 |
| Python / PyTorch / CUDA pinned versions | Phase 1 M1 engine stubs becoming runnable | Needed before model imports work |
| Test runner / CI | All phases | Placeholder in pyproject.toml |
| ffmpeg bundling approach | Phase 1 M2 | Not touched yet |
| Profile storage backend | Phase 1 M4 | Leaning SQLite; `JobRepository` ABC already in place |
| FreeVC checkpoint license + VCTK ODC-By attribution | Before FreeVC bundling | Low effort; do before Phase 1 M1 A/B |
| WavLM-Large weight license | Before any engine bundling | Low risk; treated as MIT |
| A/B listening test result (OpenVoice V2 vs FreeVC default) | Default engine confirmation | Script ready in `scripts/ab_listen_test.py`; run once weights installed |
