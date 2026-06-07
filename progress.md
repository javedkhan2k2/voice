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
**Status: M1 complete; M2–M6 not started**

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
**Status: Not started**

Planned scope: ffmpeg-backed decode (WAV/FLAC/MP3/M4A/OGG) → float32 PCM → chunking →
encode (WAV/FLAC); resampling; optional loudness normalization.
Replaces `StdlibWavLoader` in `services/` with a proper `FfmpegLoader`.

Depends on: M1 complete ✓

---

### Milestone M3 — Headless conversion path
**Status: Not started**

Planned scope: one headless call `source_file + reference → output_file` with progress
callbacks and mid-job cancel that releases VRAM. Wires audio pipeline + queue engine
end-to-end without the GUI.

Depends on: M2

---

### Milestone M4 — Storage + consent
**Status: Not started**

Planned scope: versioned profile schema, consent record persisted on creation, settings
store, local rotating logs. Storage backend leaning SQLite. Replaces
`JsonFileJobRepository` with `SqliteJobRepository`.

Depends on: M1 ✓ (parallelizable with M5 once M3 is done)

---

### Milestone M5 — GUI MVP (PySide6)
**Status: Not started**

Planned scope: first-run hardware probe + acceptable-use acknowledgement; create-profile
flow with consent gate; convert; progress bar; A/B preview; export.

Depends on: M4

---

### Milestone M6 — Offline + integration hardening
**Status: Not started**

Planned scope: offline self-check passes; end-to-end run on GPU and CPU; UI stays
responsive on a long file; overlap-add chunking validated.

Depends on: M5

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
