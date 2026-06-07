# Phase 2 — Batch Queue, Profile Management, Settings & Diagnostics

Builds on the Phase 1 MVP. Product scope: `docs/spec.md`. Architecture: `docs/architecture.md`.
This phase turns the single-job MVP into a multi-job tool a user can manage day to day.

> Prerequisite: **Phase 1 exit criteria met** — a single conversion works end-to-end (headless + GUI),
> consent gate enforced, offline self-check passing.

## Scope

In scope:

- **Batch queue:** add multiple source files against one profile; sequential execution; per-job status,
  cancel, retry; resumable across restarts.
- **Profile library UI:** list / rename / delete profiles; deletion removes all artifacts; surface each
  profile's consent record.
- **Settings UI:** device (auto/GPU/CPU), active engine, output format/rate, loudness normalize, storage
  location, log level.
- **Diagnostics:** rotating local logs + exportable diagnostics bundle (logs + hardware/model versions,
  **never audio**).
- **Accessibility pass** across the now-larger surface.

Out of scope (later phases): provenance/watermarking (Phase 3), installer/packaging (Phase 4), parallel/
multi-GPU jobs, cloud anything.

## Milestone breakdown

| # | Milestone | Outcome |
|---|---|---|
| M1 | **Queue engine (services)** | Sequential job scheduler with a `queued → running → (done\|canceled\|failed)` state machine; cancel/retry; persisted so the queue survives restart. Headless + tested. |
| M2 | **Queue UI** | Add files, see per-job progress/ETA/status, cancel/retry, open output folder. Stays responsive during runs. |
| M3 | **Profile library UI** | Browse/rename/delete profiles; delete performs full artifact cleanup via `storage/`; consent record visible per profile. |
| M4 | **Settings UI + persistence** | All settings read/write through `SettingsStore`; engine/device switch takes effect on next job; storage-location change migrates safely. |
| M5 | **Diagnostics** | Rotating logs; one-click diagnostics-bundle export that provably excludes audio. |
| M6 | **Accessibility pass** | Keyboard navigation, screen-reader labels, high-DPI/contrast, no color-only status cues across all new views. |

Dependency order: M1 → M2; M3/M4/M5 parallelizable after M1; M6 last.

## Acceptance criteria

- A user can queue several files against one profile and let them run unattended to completion.
- Per-job cancel and retry work; a failed job does not abort the rest of the queue.
- Killing and relaunching the app restores the queue and in-flight job state (resumable).
- Deleting a profile removes its artifacts with no orphaned files; its consent record was viewable first.
- Changing device/engine/output settings takes effect on the next job without a restart.
- The diagnostics bundle contains logs + environment info and **no audio** (asserted by a test).
- All new views are keyboard-navigable and screen-reader-labeled.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Queue state/edge cases (crash mid-job, retry semantics) | Lost or duplicated work | Explicit state machine + persisted journal; integration tests for crash/restart. |
| Storage-location change mid-history | Broken paths / data loss | Migration routine + dry-run validation; block change while jobs run. |
| Profile deletion leaving orphaned artifacts | Disk bloat, privacy gap | Deletion goes through `storage/` with an artifact manifest; test for zero orphans. |
| Diagnostics bundle leaking audio/PII | Privacy violation | Whitelist-based bundle assembly; automated content assertion. |
| Accessibility regressions as UI grows | Excludes users | Per-view a11y checklist; audit in M6. |

## Test strategy

- **Unit (headless):** queue state machine (all transitions, cancel/retry), settings round-trip, profile
  deletion artifact cleanup, diagnostics-bundle content filter.
- **Integration:** queue of mixed pass/fail/cancel jobs; kill-and-restart resumes correctly; storage-
  location migration.
- **GUI:** view-model tests for queue/library/settings; manual E2E of a multi-file batch run.
- **Accessibility:** keyboard-only walkthrough + screen-reader label audit.

## Exit criteria

- All acceptance criteria pass on Windows 11 (GPU present and absent).
- Queue is resumable and robust to crash/restart; no orphaned artifacts on profile deletion.
- Diagnostics bundle verified audio-free.
- Accessibility audit passes for all Phase 2 views.

## Phase 2 TODOs

- Confirm profile storage backend (lean SQLite) and freeze the v1 profile + queue-journal schema.
- Decide queue-journal format and crash-recovery semantics (at-least-once vs exactly-once retry).
- Define the diagnostics-bundle manifest (exact fields; explicit audio exclusion).
