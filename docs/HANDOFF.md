This session continues voicebuilder development. Read docs/phases/README.md
and docs/phases/phase-2-queue-and-management.md before starting.

## Current state
- Branch: phase-2-m2-queue-ui (M2 + M3 + M4 all on this branch)
- Phase 0 complete: model selection (OpenVoice V2 default, FreeVC alternative)
- Phase 1 complete (M1–M6): 100 tests
- Phase 2 M1 complete: Queue engine (services) — 43 tests
- Phase 2 M2 complete: Queue UI — QueueBridge, QueueViewModel, QueueView,
  engine-lock serialisation — 13 tests
- Phase 2 M3 complete: Profile Library UI — ProfileLibraryViewModel,
  ProfileLibraryView — 11 tests
- Phase 2 M4 complete: Settings UI — SettingsViewModel, SettingsView,
  AppSettings extended, ConvertParams wired to device+loudness — 9 tests
- Total: 176/176 tests passing
- Dev env: Python 3.13.5, .venv/, numpy 2.4.6, pytest 9.0.3, PySide6 installed
- Run tests: .venv\Scripts\python -m pytest -v
- Run app:   $env:PYTHONPATH = "src"; .venv\Scripts\python -m voiceconv

## Key APIs

### Services layer
- services/job.py: JobStatus, Job, ConversionRequest
- services/queue.py: JobQueue
- services/runner.py: QueueRunner — submit/cancel/retry
- services/converter.py: Converter — single-shot

### Storage
- storage/settings.py: AppSettings (device, output_format, output_dir, log_dir,
  first_run_acknowledged, loudness_normalize, log_level, active_engine),
  SettingsStore — atomic save/load with forward/back compat
- storage/profile.py: VoiceProfile (frozen, artifacts embedded), JsonFileProfileRepository

### App layer (tabs in order)
- Tab 0  Create Profile  — ProfileViewModel / ProfileView
- Tab 1  Convert         — ConvertViewModel / ConvertView (engine_lock, device+loudness in params)
- Tab 2  Preview & Export— PreviewViewModel / PreviewView
- Tab 3  Queue           — QueueViewModel / QueueView (device+loudness in params)
- Tab 4  Profile Library — ProfileLibraryViewModel / ProfileLibraryView
- Tab 5  Settings        — SettingsViewModel / SettingsView

- app/_app_state.py: AppState — converter, profile_repo, settings_store, settings,
  engine, queue, runner, engine_lock
- app/_queue_bridge.py: QueueBridge — runner thread → Qt signals
- app/main.py: _LockedQueueRunner; runner started after warmup

### Settings VM key behaviours
- All setters mutate state.settings in-place and call settings_store.save() immediately
- set_output_dir: blocked (error signal) if runner has a RUNNING job
- set_log_level: also calls logging.getLogger().setLevel() for immediate effect
- active_engine saved but requires app restart to take effect

## Mandatory safeguards (non-negotiable)
- No silent recording; consent gate on profile creation; offline-runtime invariant;
  output provenance; GUI never imports models/audio backends directly;
  all heavy work off UI thread.

## Next task: Phase 2 M5 — Diagnostics
See docs/phases/phase-2-queue-and-management.md for scope:
- Rotating logs (already wired via setup_logging — verify rotation config)
- One-click diagnostics bundle export: logs + hardware/model versions, NO audio
- Bundle assembler tested to assert zero audio files in output
- A new "Export Diagnostics…" button, likely in the Settings tab or a dialog
- Unit test: assert diagnostics bundle contains no audio extensions
