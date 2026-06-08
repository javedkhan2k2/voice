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
- Phase 3 M3 complete: Acceptable-use guidance — app/_guidance.py (single
  source of reviewed copy), contextual reminders on Create Profile + Convert,
  re-viewable terms in Settings, AppSettings.acceptable_use_acknowledged_version
  recorded on first-run ack; copy-guard tests; docs/acceptable-use.md — 7 tests
- Phase 3 M4 complete: Watermark evaluation — experimental spread-spectrum
  spike (audio/_watermark.py, NOT wired to production) + scripts/watermark_eval.py;
  measured: survives lossless+MP3, fails trim/resample, ~28 dB SNR →
  DECISION: defer watermark to fast-follow, metadata provenance is v1 baseline;
  docs/watermark-eval.md — 7 tests
- Phase 3 M5 complete: Offline-invariant hardening — block_network() context
  manager + verify_offline() self-check in services/offline_check.py; status-bar
  offline indicator; Settings "Verify offline" button (SettingsViewModel.
  verify_offline → offline_verified signal); docs/offline.md — 4 tests
- Phase 3 COMPLETE (M1–M5).
- Total: 239/239 tests passing
- Dev env: Python 3.13.5, .venv/, numpy 2.4.6, pytest 9.0.3, PySide6 installed
- Run tests: .venv\Scripts\python -m pytest -v
- Run app:   $env:PYTHONPATH = "src"; .venv\Scripts\python -m voiceconv

## Next: Phase 4 — Packaging & beta
See docs/phases/phase-4-packaging-and-beta.md. Focus: embedded-CPython bundle,
install-time model-weight fetch, Inno Setup installer, hardening, clean-VM beta.
Read the phase doc and break into milestones; start in PLAN MODE.
Still open from earlier phases:
- Manual a11y audit log (docs/accessibility.md) to formally close Phase 2.
- External/legal review of acceptable-use + consent copy before GA (Phase 4).
- Watermark fast-follow (docs/watermark-eval.md) — post-v1.

## Key APIs

### Services
- services/job.py: JobStatus (QUEUED/RUNNING/DONE/CANCELLED/FAILED), Job, ConversionRequest
- services/queue.py: JobQueue — thread-safe
- services/runner.py: QueueRunner — submit/cancel/retry; callbacks fire from background thread
- services/converter.py: Converter — single-shot
- services/offline_check.py: block_network() ctx mgr, check_offline_invariant(fn),
  verify_offline() → OfflineCheckResult(ok, detail). Socket-layer guard (main
  process only; subprocesses excluded). Doc: docs/offline.md
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
- audio/_watermark.py: EXPERIMENTAL spread-spectrum watermark (embed/
  correlation_score/is_watermarked/snr_db). NOT wired to production. Evaluated
  in M4 and DEFERRED — see docs/watermark-eval.md + scripts/watermark_eval.py

### Storage
- storage/settings.py: AppSettings (device, output_format, output_dir, log_dir,
  first_run_acknowledged, loudness_normalize, log_level, active_engine,
  acceptable_use_acknowledged_version), SettingsStore — atomic save/load,
  forward/back compat
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
- app/_guidance.py: ACCEPTABLE_USE(+_VERSION), PROFILE_REMINDER, CONVERT_REMINDER
  — single source of safeguard copy (first-run dialog, Settings re-view, tab
  reminders). Copy guarded by tests/app/test_guidance.py. Doc: docs/acceptable-use.md
- app/main.py: _LockedQueueRunner; runner started after engine.warmup(); bridge → MainWindow

### Engine conflict (M2)
- threading.Lock (engine_lock in AppState): _LockedQueueRunner (blocking acquire
  wraps _run_job) and ConvertViewModel.start_convert() (non-blocking acquire, fails fast)
- QueueBridge.runner_busy_changed(bool) → ConvertViewModel.set_engine_busy() → disables button

## Mandatory safeguards (non-negotiable, carry through all phases)
- No silent recording; consent gate on profile creation; offline-runtime invariant;
  output provenance; GUI never imports models/audio backends directly;
  all heavy work off UI thread.

## Task: Phase 4 — Packaging & beta (read the phase doc, break into milestones)
See docs/phases/phase-4-packaging-and-beta.md for full scope.

Phase 4 themes:
- Embedded CPython bundle (app runs without a system Python).
- Install-time model-weight fetch (the ONLY allowed network use; runtime stays
  offline — keep the conversion-path invariant intact).
- Inno Setup installer; finalize ffmpeg bundling (CLAUDE.md TODO).
- Hardening + clean-VM beta; dependency license audit; code signing.

Phase 3 is COMPLETE. Safeguards in place: consent schema + enforcement
(docs/consent.md); output provenance metadata (docs/provenance.md); acceptable-
use guidance (docs/acceptable-use.md); watermark evaluated + DEFERRED
(docs/watermark-eval.md); offline invariant hardened (docs/offline.md).

Cross-phase open items to resolve in Phase 4: app license (gates seed-VC
reconsideration + signing), external/legal copy review, the manual a11y audit.

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
