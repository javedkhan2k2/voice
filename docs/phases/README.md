# Phases Index

Execution roadmap for the Windows 11 voice-conversion app. Product scope lives in
[`../spec.md`](../spec.md); architecture in [`../architecture.md`](../architecture.md). This file is the
sequencing/status index — keep it current as milestones land.

## Dependency order

```
phase-0 (model)  →  phase-1 (MVP)  →  phase-2 (queue/mgmt)  →  phase-3 (safeguards)  →  phase-4 (packaging)
```

Each phase assumes the previous phase's **exit criteria** are met.

## Phases

| Phase | Doc | Focus | Status |
|---|---|---|---|
| 0 | [phase-0-model-selection.md](phase-0-model-selection.md) | Zero-shot VC model bake-off; default engine = OpenVoice V2, FreeVC alternative, seed-VC deferred (GPLv3) | Complete (recommendation) |
| 1 | [phase-1-mvp.md](phase-1-mvp.md) | Core engine + worker boundary, audio pipeline, single-job convert (GUI + headless), consent gate, offline self-check | Not started |
| 2 | [phase-2-queue-and-management.md](phase-2-queue-and-management.md) | Batch queue, profile library UI, settings, diagnostics bundle, accessibility | Not started |
| 3 | [phase-3-safeguards-and-provenance.md](phase-3-safeguards-and-provenance.md) | Consent-record finalization, output provenance, acceptable-use guidance, watermark evaluation, offline hardening | Not started |
| 4 | [phase-4-packaging-and-beta.md](phase-4-packaging-and-beta.md) | Embedded-Python bundle, install-time weight fetch, Inno Setup installer, hardening, clean-VM beta | Not started |

## Cross-phase decisions to resolve

These span multiple phases; resolving them early avoids rework.

- **App's own license (open-source vs proprietary)** — gates the seed-VC reconsideration (Phase 0), legal
  copy review (Phase 3), and the dependency license audit + code-signing (Phase 4).
- **Provenance depth (metadata-only vs +inaudible watermark)** — opened in spec, decided in Phase 3 (M4),
  consumed by Phase 4.
- **Default engine confirmation** — provisional (OpenVoice V2); settled by the Phase 1 (M1) listening-test
  A/B against FreeVC.
