# Acceptable-use guidance (Phase 3 M3)

VoiceBuilder is a dual-use tool. These safeguards keep its use lawful and
honest. The user-facing copy lives in one place — `src/voiceconv/app/_guidance.py`
— so it can be reviewed and tested as a unit.

## What the user sees

| Surface | Copy | When |
|---|---|---|
| First-run dialog | `ACCEPTABLE_USE` (full statement) | Once, before any use; blocks entry until accepted. |
| Settings → Acceptable use | `ACCEPTABLE_USE` (re-viewable) | Any time, via "Review acceptable-use terms…". |
| Create Profile tab | `PROFILE_REMINDER` | Persistent contextual reminder. |
| Convert tab | `CONVERT_REMINDER` | Persistent contextual reminder. |

The full statement covers the four required points: ownership/permission of the
source voice; no impersonation/deception/fraud; full user responsibility;
provenance disclosure (outputs tagged as AI voice-converted); and the offline
guarantee (nothing leaves the device).

## Recording

- `AppSettings.first_run_acknowledged` — whether the user accepted.
- `AppSettings.acceptable_use_acknowledged_version` — which version of the terms
  was accepted (`ACCEPTABLE_USE_VERSION`, currently `"1"`). Bump the version when
  the wording materially changes so a re-acknowledgement can be required later.

Per-profile consent is recorded separately (see `docs/consent.md`).

## Review discipline

`tests/app/test_guidance.py` asserts the copy states the core obligations,
surfaces the offline and provenance facts, and contains **no** misuse-positive
phrasing (a denylist of terms like "undetectable", "untraceable", "bypass",
"prank"). Update the test denylist alongside any copy change. Whether the copy
needs external/legal review before GA is tracked in Phase 4.
