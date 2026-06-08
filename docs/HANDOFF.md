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
- Phase 2 M6 complete: Accessibility pass — accessibleName on all view
  controls (per-row Queue context), Alt mnemonics, AA-contrast status colours,
  status conveyed by text; docs/accessibility.md checklist — 12 tests
- Phase 2 COMPLETE (M1–M6). Manual a11y audit log in docs/accessibility.md
  still to be walked before Phase 2 exit sign-off.
- Phase 3 M1 complete: Consent record finalization — versioned ConsentRecord
  (adds profile_id, app_version, consent_schema_version), bound to its profile;
  voiceconv.__version__ = "0.1.0"; load-time enforcement (no profile without a
  consent statement); docs/consent.md — 9 tests
- Total: 210/210 tests passing
- Dev env: Python 3.13.5, .venv/, numpy 2.4.6, pytest 9.0.3, PySide6 installed
- Run tests: .venv\Scripts\python -m pytest -v
- Run app:   $env:PYTHONPATH = "src"; .venv\Scripts\python -m voiceconv

## Next: Phase 3 M2 — Output provenance metadata
See docs/phases/phase-3-safeguards-and-provenance.md. Every exported file must
carry a documented provenance marker in container metadata (marking it as AI
voice-converted by this tool) that survives a normal export round-trip.
Then M3 (acceptable-use guidance), M4 (watermark eval + decision), M5 (offline
hardening). Manual a11y audit (docs/accessibility.md) still open from Phase 2.

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
  - ConsentRecord (frozen, versioned): record_id, statement, affirmed_at,
    affirmed_by, profile_id, app_version, consent_schema_version. profile_id
    bound by VoiceProfile.create; _dict_to_profile raises if consent missing/empty
    (load enforces "no profile without consent"). Schema doc: docs/consent.md
- voiceconv.__version__ = "0.1.0" — single source (consent + diagnostics manifest)
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

## Task: Phase 3, Milestone M2 — Output provenance metadata
See docs/phases/phase-3-safeguards-and-provenance.md for full scope.

M2 scope:
- Embed a recoverable provenance marker in every exported file's container
  metadata, marking it AI voice-converted by this tool. Survives normal export.
- Choose the marker per output container: WAV (RIFF INFO / bext), FLAC (Vorbis
  comment). MP3 deferred unless an export path exists.
- Wire into the encode path: audio/_codec.py FfmpegEncoder is where files are
  written (ffmpeg -metadata ...). Keep it headless-testable.
- Decide provenance depth for v1 is M4's call (watermark); M2 ships the
  metadata baseline regardless.
- Tests: write→read-back the metadata marker; round-trip survives re-export.

Done in M1: consent schema (profile_id/app_version/consent_schema_version),
voiceconv.__version__, load enforcement, docs/consent.md.

Remaining Phase 3 after M2: M3 acceptable-use guidance, M4 watermark eval +
decision, M5 offline-invariant hardening.

## Architecture constraints (carry forward)
- GUI never imports models/audio backends directly; all heavy work off UI thread.
- Offline-runtime invariant; consent gate; output provenance; no telemetry.
- Dual-use tool: keep impersonation/fraud safeguards intact.

## Notes
- Create a new branch per milestone before starting.
- Phase 2 leftovers: walk the manual a11y audit log in docs/accessibility.md and
  record results to formally close the Phase 2 exit criteria.
- Diagnostics safeguard: the bundle excludes audio via name whitelist
  (voiceconv.log*) AND extension denylist in services/diagnostics.py — keep both.
- Start in PLAN MODE: propose the metadata marker format + encode-path wiring
  BEFORE writing code.
