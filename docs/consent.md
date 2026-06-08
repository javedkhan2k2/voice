# Consent record (Phase 3 M1)

Every voice profile is bound to a **consent record** affirming the user owns, or
has explicit permission to use, the target voice. This is a non-negotiable
safeguard (`CLAUDE.md`): there is no code path that produces a profile without a
persisted consent record.

## Schema

`ConsentRecord` (`src/voiceconv/storage/profile.py`), versioned by
`consent_schema_version` (current: `1`):

| Field | Type | Meaning |
|---|---|---|
| `consent_schema_version` | int | Schema version of this record. |
| `record_id` | str (uuid4 hex) | Unique id for the consent record. |
| `statement` | str | The acknowledgement text the user affirmed. Must be non-empty. |
| `affirmed_at` | float (epoch seconds) | When consent was affirmed. |
| `affirmed_by` | str | Who affirmed (default `"user"`; `"api_caller"` for headless callers). |
| `profile_id` | str | The profile this consent belongs to. Bound by `VoiceProfile.create`. |
| `app_version` | str | App version (`voiceconv.__version__`) at the time of capture. |

The four spec-required fields — *timestamp, acknowledgement text, profile id,
app version* — map to `affirmed_at`, `statement`, `profile_id`, `app_version`.

## Guarantees

- **Structural:** `VoiceProfile` requires a `ConsentRecord` argument; it cannot be
  instantiated without one.
- **Bound id:** `VoiceProfile.create` sets `consent.profile_id` to the new
  profile's id (overriding any caller value), so a persisted consent always
  references the profile it belongs to.
- **Load enforcement:** `_dict_to_profile` raises `ValueError` if a profile's
  JSON has no consent block or an empty statement; `load()`/`list_all()` therefore
  refuse to surface a consent-less or tampered profile.
- **Persistence:** the consent block is written inside each profile's JSON file
  via `storage/`, atomically (tmp + rename).

## Compatibility

- **Back-compat:** profiles written before M1 (consent block without
  `profile_id`/`app_version`/`consent_schema_version`) still load —
  `app_version` defaults to `"unknown"`, `profile_id` falls back to the profile's
  own id, schema version to `1`.
- **Forward-compat:** unknown keys in the consent block are ignored on load.

## Tests

`tests/storage/test_profile.py` covers schema round-trip, profile-id binding,
back-compat load, and the enforcement audit (missing/empty consent is rejected on
construction and on load).
