This session continues voicebuilder development. Read docs/phases/README.md
and docs/phases/phase-2-queue-and-management.md before starting.

## Current state
- Branch: main (merge phase-2-m2-queue-ui when ready)
- Phase 0 complete: model selection (OpenVoice V2 default, FreeVC alternative)
- Phase 1 complete (M1–M6):
  - M1: VoiceConversionEngine ABC, WorkerAdapter, IPC (stdio + shm), mock engine — 29 tests
  - M2: FfmpegLoader, FfmpegEncoder, rms_normalize, AudioEncoder protocol — 16 tests
  - M3: Converter (prepare_profile + convert_file, stateless) — 7 tests
  - M4: ConsentRecord, VoiceProfile, JsonFileProfileRepository, AppSettings,
        SettingsStore, setup_logging() — 24 tests
  - M5: PySide6 GUI MVP — first-run dialog, Create Profile, Convert, Preview & Export — 15 tests
  - M6: check_offline_invariant(), E2E integration tests, long-file tests,
        app startup robustness — 9 tests
- Phase 2 M1 complete: QueueRunner, JobStatus state machine, JobQueue,
  JsonFileJobRepository, PcmLoader protocol, StdlibWavLoader — 43 tests
- Phase 2 M2 complete: Queue UI — QueueBridge, QueueViewModel, QueueView,
  engine-lock serialisation — 13 tests
- Total: 156/156 tests passing
- Dev env: Python 3.13.5, .venv/, numpy 2.4.6, pytest 9.0.3, PySide6 installed
- Run tests: .venv\Scripts\python -m pytest -v
- Run app:   $env:PYTHONPATH = "src"; .venv\Scripts\python -m voiceconv
  (no build backend yet — PYTHONPATH required until pyproject.toml is finalized)

## Key APIs

### Services layer (unchanged)
- services/job.py: JobStatus (QUEUED/RUNNING/DONE/CANCELLED/FAILED), Job, ConversionRequest
- services/queue.py: JobQueue — thread-safe, backed by JobRepository
- services/runner.py: QueueRunner(engine, queue, pcm_loader, audio_encoder,
  on_status=cb, on_progress=cb) — background thread, submit/cancel/retry
- services/converter.py: Converter — single-shot; used by Convert tab

### Storage (unchanged)
- storage/profile.py: VoiceProfile (artifacts stored on disk), JsonFileProfileRepository
- storage/settings.py: AppSettings (device, output_format, output_dir), SettingsStore

### App layer (Phase 2 M2 additions)
- app/_app_state.py: AppState — DI container; now includes queue, runner, engine_lock
- app/_queue_bridge.py: QueueBridge(QObject) — relays runner background callbacks to
  Qt signals (status_changed, progress_changed, runner_busy_changed)
- app/main.py: _LockedQueueRunner subclass wraps _run_job with engine_lock; runner
  started after warmup; bridge passed to MainWindow
- app/view_models/queue_vm.py: QueueViewModel — add_files, cancel_job, retry_job,
  open_output_folder, clear_done (display-only filter), refresh_profiles
- app/views/queue_view.py: QueueView — QTableWidget with 5 cols (File/Status/Progress/
  Elapsed/Action); QTimer refreshes elapsed every 1 s; actions per-row
- app/views/main_window.py: 4 tabs (Create Profile / Convert / Preview & Export / Queue)
- app/view_models/convert_vm.py: engine_lock acquire (non-blocking) / release;
  set_engine_busy() slot from bridge; engine_busy_changed signal to ConvertView

### Engine conflict resolution
- A threading.Lock (engine_lock in AppState) is shared between the two paths:
  - _LockedQueueRunner: blocking acquire before _run_job (fine on background thread)
  - ConvertViewModel.start_convert(): non-blocking acquire → error if busy
- QueueBridge.runner_busy_changed(bool) drives ConvertView button enable/disable

## Mandatory safeguards (non-negotiable, carry through all phases)
- No silent recording; consent gate on profile creation; offline-runtime invariant;
  output provenance; GUI never imports models/audio backends directly;
  all heavy work off UI thread.

## Next task: Phase 2 M3 — Profile Library UI
See docs/phases/phase-2-queue-and-management.md for scope:
- Browse/rename/delete profiles in a new view
- Deletion goes through storage/ (removes all artifacts, no orphaned files)
- Consent record visible per profile before deletion
- Unit tests (headless) for the profile-library view-model
