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
- Phase 3 M2 complete: Output provenance metadata — audio/_provenance.py
  (marker, ffmpeg_metadata_args, RIFF INFO chunk, file_has_provenance);
  embedded by FfmpegEncoder (WAV/FLAC) and StdlibWavEncoder; survives export
  copy; docs/provenance.md — 11 tests
- Fixed: flaky QThread abort in test_profile_vm (ProfileViewModel now binds
  worker.finished to a method, not a lambda → result handled on main thread)
- Total: 221/221 tests passing
- Dev env: Python 3.13.5, .venv/, numpy 2.4.6, pytest 9.0.3, PySide6 installed
- Run tests: .venv\Scripts\python -m pytest -v
- Run app:   $env:PYTHONPATH = "src"; .venv\Scripts\python -m voiceconv

## Next: Phase 3 M3 — Acceptable-use guidance
See docs/phases/phase-3-safeguards-and-provenance.md. First-run acceptable-use
acknowledgement is recorded (Phase 1 first-run gate) — review/finalize it; add
contextual in-product guidance; review copy for clarity and non-misuse
positioning (no impersonation framing). Then M4 (watermark eval + decision),
M5 (offline hardening). Manual a11y audit (docs/accessibility.md) still open.

## Key APIs

### Services
- services/job.py: JobStatus (QUEUED/RUNNING/DONE/CANCELLED/FAILED), Job, ConversionRequest
- services/queue.py: JobQueue — thread-safe
- services/runner.py: QueueRunner — submit/cancel/retry; callbacks fire from background thread
- services/converter.py: Converter — single-shot
- services/diagnostics.py: collect_app_info() → env/hardware dict;
  build_bundle(output_zip_path, log_dir, app_info) → ZIP (manifest.json +
  logs/voiceconv.log*); audio excluded by name whitelist + extension denylist

### Audio / provenance
- audio/_codec.py: FfmpegEncoder (prod, WAV/FLAC), FfmpegLoader
- services/_audio_encoder.py: AudioEncoder protocol, StdlibWavEncoder (fallback)
- audio/_provenance.py: PROVENANCE_MARKER, provenance_tags(),
  ffmpeg_metadata_args(), build_wav_info_chunk()/append_info_chunk(),
  file_has_provenance(path). Both encoders embed the marker; export = byte copy
  so it survives. Metadata-layer only (stripped by re-encode → watermark = M4).
  Schema doc: docs/provenance.md

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

## Task: Phase 3, Milestone M3 — Acceptable-use guidance
See docs/phases/phase-3-safeguards-and-provenance.md for full scope.

M3 scope:
- First-run acceptable-use acknowledgement is required and recorded (the Phase 1
  first-run gate already exists: FirstRunViewModel/FirstRunDialog,
  AppSettings.first_run_acknowledged). Review/finalize wording and recording.
- Add contextual in-product guidance (e.g. near profile creation / convert):
  clear, non-marketing language; no positioning for impersonation.
- Copy review for clarity and non-misuse framing (acceptance: reviewed copy).
- Likely UI + settings only; keep headless-testable bits in view-models.

Done in M1/M2: consent schema + load enforcement (docs/consent.md); output
provenance marker in WAV/FLAC via both encoders (docs/provenance.md).

Remaining Phase 3 after M3: M4 watermark eval + decision, M5 offline hardening.

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
- Start in PLAN MODE: propose the guidance copy + placement BEFORE writing code.
