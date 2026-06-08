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
- Phase 2 M5 complete: Diagnostics — services/diagnostics.py
  (collect_app_info + build_bundle), "Export Diagnostics…" in Settings tab,
  AppState.log_dir threaded through main.py — 13 tests
- Total: 189/189 tests passing
- Dev env: Python 3.13.5, .venv/, numpy 2.4.6, pytest 9.0.3, PySide6 installed
- Run tests: .venv\Scripts\python -m pytest -v
- Run app:   $env:PYTHONPATH = "src"; .venv\Scripts\python -m voiceconv

## Next milestone: Phase 2 M6 — Accessibility pass
Keyboard navigation, screen-reader labels, high-DPI/contrast, no color-only
status cues across all Phase 2 views (Queue, Profile Library, Settings).
Last milestone of Phase 2.

## Key APIs

### Services
- services/job.py: JobStatus (QUEUED/RUNNING/DONE/CANCELLED/FAILED), Job, ConversionRequest
- services/queue.py: JobQueue — thread-safe
- services/runner.py: QueueRunner — submit/cancel/retry; callbacks fire from background thread
- services/converter.py: Converter — single-shot
- services/diagnostics.py: collect_app_info() → env/hardware dict;
  build_bundle(output_zip_path, log_dir, app_info) → ZIP (manifest.json +
  logs/voiceconv.log*); audio excluded by name whitelist + extension denylist

### Storage
- storage/settings.py: AppSettings (device, output_format, output_dir, log_dir,
  first_run_acknowledged, loudness_normalize, log_level, active_engine),
  SettingsStore — atomic save/load, forward/back compat
- storage/profile.py: VoiceProfile (frozen, artifacts base64-embedded in JSON),
  JsonFileProfileRepository — save/load/list_all/delete
- storage/logging_setup.py: setup_logging(log_dir) — call once at startup;
  RotatingFileHandler (5 MB × 3 backups) → voiceconv.log[.1/.2/.3]

### App layer — tabs in order
- Tab 0  Create Profile   — ProfileViewModel / ProfileView
- Tab 1  Convert          — ConvertViewModel / ConvertView
- Tab 2  Preview & Export — PreviewViewModel / PreviewView
- Tab 3  Queue            — QueueViewModel / QueueView
- Tab 4  Profile Library  — ProfileLibraryViewModel / ProfileLibraryView
- Tab 5  Settings         — SettingsViewModel / SettingsView

- app/_app_state.py: AppState (converter, profile_repo, settings_store, settings,
  engine, queue, runner, engine_lock, log_dir)
  - log_dir = data_dir/"logs" (set in main.py); used by SettingsViewModel.export_diagnostics()
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

## Task: Phase 2, Milestone M6 — Accessibility pass
See docs/phases/phase-2-queue-and-management.md for full scope. Last milestone
of Phase 2; ships the exit criteria for the phase.

M6 scope (across all Phase 2 views — Queue, Profile Library, Settings — and
re-check the Phase 1 views):
- Keyboard navigation: logical tab order; every action reachable without a mouse;
  visible focus indicators; mnemonics/accelerators on buttons.
- Screen-reader labels: accessibleName/accessibleDescription on inputs, buttons,
  and status widgets; form labels associated with their fields.
- High-DPI / contrast: no fixed pixel sizes that break scaling; respect system
  contrast; verify against a high-contrast theme.
- No color-only status cues: job status (QUEUED/RUNNING/DONE/CANCELLED/FAILED)
  and busy states must carry text/icon, not just color.

## Architecture constraints (carry forward)
- GUI never imports models/audio backends directly; all heavy work off UI thread.
- Offline-runtime invariant; consent gate; output provenance; no telemetry.

## Notes
- Create a new branch (e.g., phase-2-m6-accessibility) before starting.
- Diagnostics (M5) safeguard: the bundle excludes audio via name whitelist
  (voiceconv.log*) AND extension denylist in services/diagnostics.py — keep both
  if you touch that module.
- Start in PLAN MODE: propose a per-view a11y checklist and the test approach
  (view-model labels are unit-testable; keyboard/SR walkthrough is manual).
