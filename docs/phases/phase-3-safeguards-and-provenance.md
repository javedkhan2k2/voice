# Phase 3 — Misuse Safeguards & Provenance

Hardens the consent, provenance, and offline guarantees into shipping form. These are first-class product
requirements, not polish — see `docs/spec.md` (Consent & misuse-prevention) and `CLAUDE.md` rules.

> Prerequisite: **Phase 1 + Phase 2 exit criteria met.** The consent gate and offline self-check already
> exist from Phase 1; this phase finalizes, audits, and extends them.

## Scope

In scope:

- **Consent records — finalize:** stable schema, persisted storage, and an enforcement audit proving a
  profile cannot exist without one. (Reaffirms the `CLAUDE.md` rule: no silent recording.)
- **Output provenance:** embed a recoverable marker in every generated file's metadata indicating it was
  AI voice-converted by this tool.
- **Acceptable-use guidance in-product:** first-run acknowledgement (from Phase 1) plus contextual
  reminders; clear, non-marketing language; no positioning for impersonation.
- **Inaudible audio watermark — evaluate:** spike a watermark approach, measure robustness vs audio-quality
  cost, and **decide** whether it ships in v1 or becomes a fast-follow.
- **Offline invariant — harden:** strengthen the conversion-path no-network self-check and surface offline
  status in the UI.

Out of scope: cloud reporting, account-based identity, mandatory server verification (offline-by-design).

## Milestone breakdown

| # | Milestone | Outcome |
|---|---|---|
| M1 | **Consent record finalization** | Versioned consent schema `{timestamp, acknowledgement text, profile id, app version}`; persisted via `storage/`; enforcement audit (cannot create/import a profile without it). |
| M2 | **Output provenance metadata** | Every exported file carries a documented provenance marker in container metadata; survives normal export. |
| M3 | **Acceptable-use guidance** | First-run ack recorded; contextual in-product guidance; copy reviewed for clarity and non-misuse positioning. |
| M4 | **Watermark evaluation + decision** | Spike report: robustness (survives re-encode/trim) vs quality cost; ship-or-defer decision documented. |
| M5 | **Offline invariant hardening** | Automated assertion that no network socket opens during conversion; offline status shown in UI; "verify offline" self-check. |

Dependency order: M1 → M2 → M3 can proceed in parallel; M4 independent; M5 anytime.

## Acceptance criteria

- It is **impossible** to create or import a voice profile without a persisted consent record (audited).
- Every generated audio file carries provenance metadata; this survives a normal export round-trip.
- First-run acceptable-use acknowledgement is required and recorded; contextual guidance is present.
- The watermark decision is documented with evidence (robustness + quality measurements).
- The offline self-check passes and fails loudly if any conversion-path network call is introduced.
- No silent recording path exists anywhere in the app (capture always gated by explicit consent).

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Watermark robustness vs audio quality trade-off | Useless or audible mark | Treat as evaluation with a real ship/defer gate; metadata provenance is the guaranteed baseline. |
| Provenance metadata stripped by re-encoding | Provenance lost downstream | Document limitation; pursue watermark as the durable layer; don't overclaim. |
| Consent UX friction pushing users to bypass | Safeguard ignored | Keep the gate minimal but mandatory; one clear affirmation, persisted. |
| Offline check false-confidence | Privacy claim overstated | Assert at the socket layer in the conversion path, not just config; test with a network monitor. |
| Safeguards perceived as anti-features | Removed under pressure | Codify in `CLAUDE.md` as non-negotiable; gate in CI where feasible. |

## Test strategy

- **Unit:** consent schema round-trip; provenance writer/reader; offline self-check logic.
- **Integration:** attempt profile creation/import without consent → blocked; exported files inspected for
  provenance; conversion run under a network monitor asserts zero outbound connections.
- **Watermark spike:** measured robustness (re-encode, trim, resample) and a listening check for audibility.
- **Copy review:** acceptable-use language reviewed for clarity and non-misuse positioning.

## Exit criteria

- Consent enforced and persisted; no-silent-recording invariant verified across all capture paths.
- All generated files provenance-marked; round-trip-survival tested.
- Offline guarantee verified at the network layer, not just by configuration.
- Watermark ship/defer decision documented; if deferred, tracked as a named fast-follow.

## Phase 3 TODOs

- Decide provenance depth for v1: metadata-only vs metadata + inaudible watermark (output of M4).
- Choose the provenance metadata format/marker per output container (WAV/FLAC/MP3).
- Confirm whether any consent/legal copy needs external (legal) review before GA — see Phase 4.
