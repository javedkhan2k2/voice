This session continues voicebuilder development. Read docs/phases/README.md
and docs/phases/phase-2-queue-and-management.md before starting.

## Current state
- Branch: main (all work merged; start a new branch for each milestone)
- Phase 0 complete: model selection (OpenVoice V2 default, FreeVC alternative)
- Phase 1 complete (M1–M6): 100 tests
- Phase 2 M1 complete: Queue engine (services) — 43 tests
- Phase 2 M2 complete: Queue UI — QueueBridge, QueueViewModel, QueueView,
  engine-lock serialisation — 13 tests
- Phase 2 M3 complete: Profile Library UI — ProfileLibraryViewModel,
  ProfileLibraryView — 11 tests
- Phase 2 M4 complete: Settings UI — SettingsViewModel, SettingsView,
  AppSettings extended (loudness_normalize, log_level, active_engine) — 9 tests
- Total: 176/176 tests passing
- Dev env: Python 3.13.5, .venv/, numpy 2.4.6, pytest 9.0.3, PySide6 installed
- Run tests: .venv\Scripts\python -m pytest -v
- Run app:   $env:PYTHONPATH = "src"; .venv\Scripts\python -m voiceconv

## Key APIs

### Services
- services/job.py: JobStatus (QUEUED/RUNNING/DONE/CANCELLED/FAILED), Job, ConversionRequest
- services/queue.py: JobQueue — thread-safe
- services/runner.py: QueueRunner — submit/cancel/retry; callbacks fire from background thread
- services/converter.py: Converter — single-shot

### Storage
- storage/settings.py: AppSettings (device, output_format, output_dir, log_dir,
  first_run_acknowledged, loudness_normalize, log_level, active_engine),
  SettingsStore — atomic save/load, forward/back compat
- storage/profile.py: VoiceProfile (frozen, artifacts base64-embedded in JSON),
  JsonFileProfileRepository — save/load/list_all/delete
- storage/logging_setup.py: setup_logging(log_dir) — call once at startup

### App layer — tabs in order
- Tab 0  Create Profile   — ProfileViewModel / ProfileView
- Tab 1  Convert          — ConvertViewModel / ConvertView
- Tab 2  Preview & Export — PreviewViewModel / PreviewView
- Tab 3  Queue            — QueueViewModel / QueueView
- Tab 4  Profile Library  — ProfileLibraryViewModel / ProfileLibraryView
- Tab 5  Settings         — SettingsViewModel / SettingsView

- app/_app_state.py: AppState (converter, profile_repo, settings_store, settings,
  engine, queue, runner, engine_lock)
- app/_queue_bridge.py: QueueBridge(QObject) — runner thread → Qt signals
- app/main.py: _LockedQueueRunner; runner started after engine.warmup(); bridge → MainWindow

### Engine conflict (M2)
- threading.Lock (engine_lock in AppState): _LockedQueueRunner (blocking acquire
  wraps _run_job) and ConvertViewModel.start_convert() (non-blocking acquire, fails fast)
- QueueBridge.runner_busy_changed(bool) → ConvertViewModel.set_engine_busy() → disables button

## Mandatory safeguards (non-negotiable, carry through all phases)
- No silent recording; consent gate on profile creation; offline-runtime invariant;
  output provenance; GUI never imports models/audio backends directly;
  all heavy work off UI thread.

## Task: Phase 2, Milestone M5 — Diagnostics
See docs/phases/phase-2-queue-and-management.md for full scope.

M5 scope:
- Rotating logs: verify setup_logging() configures rotation; add RotatingFileHandler
  if not already present (check storage/logging_setup.py)
- Diagnostics bundle export: collect logs + hardware/model version info into a
  single ZIP file; content must provably exclude audio (assert by file extension whitelist)
- "Export Diagnostics…" button — place in the Settings tab (SettingsView) or as a
  standalone button; triggers a save-file dialog then assembles the bundle
- A new services/diagnostics.py (or storage/diagnostics.py) module with a
  build_bundle(output_zip_path, log_dir, app_info) function
- Unit test: assert bundle contains zero audio-extension files (.wav .flac .mp3 etc.)
- Unit test: assert bundle contains at least one log file
- Unit test: assert bundle contains a manifest/env JSON with hardware info

## Architecture constraints
- Bundle assembly must be headless-testable (no Qt in the module)
- app/ layer wires the dialog and calls the services/storage module
- No audio data leaves the machine (bundle exclusion is asserted by test)
- Keep offline-runtime invariant: no network calls during bundle assembly

## Notes
- Create a new branch (e.g., phase-2-m5-diagnostics) before starting
- setup_logging() is in storage/logging_setup.py — read it before designing rotation
- The app info dict should include: platform, Python version, installed package versions
  (PySide6, numpy, torch if available), device info from platform_support/device.py
- Start in PLAN MODE: propose the module structure, bundle manifest format, and
  "Export Diagnostics" UX placement BEFORE writing any code
