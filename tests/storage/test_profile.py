"""Unit tests for ConsentRecord, VoiceProfile, and JsonFileProfileRepository."""

import json

import pytest

from voiceconv import __version__
from voiceconv.inference.engine import ProfileArtifacts
from voiceconv.storage.profile import (
    CONSENT_SCHEMA_VERSION,
    ConsentRecord,
    JsonFileProfileRepository,
    VoiceProfile,
    _dict_to_profile,
    _profile_to_dict,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _artifacts(data: bytes = b"embedding") -> ProfileArtifacts:
    return ProfileArtifacts("mock", "0.1", data, {})


def _consent(statement: str = "I consent.") -> ConsentRecord:
    return ConsentRecord.create(statement)


def _profile(name: str = "Test Voice", data: bytes = b"emb") -> VoiceProfile:
    return VoiceProfile.create(name, _artifacts(data), _consent())


# ---------------------------------------------------------------------------
# ConsentRecord
# ---------------------------------------------------------------------------


def test_consent_create_sets_fields():
    c = ConsentRecord.create("I affirm.")
    assert c.statement == "I affirm."
    assert c.affirmed_by == "user"
    assert len(c.record_id) == 32
    assert c.affirmed_at > 0


def test_consent_create_custom_affirmed_by():
    c = ConsentRecord.create("stmt", affirmed_by="api_caller")
    assert c.affirmed_by == "api_caller"


def test_consent_empty_statement_raises():
    with pytest.raises(ValueError, match="empty"):
        ConsentRecord.create("   ")


def test_two_consent_records_unique_ids():
    assert ConsentRecord.create("x").record_id != ConsentRecord.create("x").record_id


def test_consent_create_defaults_app_version_and_schema():
    c = ConsentRecord.create("I affirm.")
    assert c.app_version == __version__
    assert c.consent_schema_version == CONSENT_SCHEMA_VERSION
    assert c.profile_id == ""  # not bound until VoiceProfile.create


# ---------------------------------------------------------------------------
# Consent record finalization (Phase 3 M1)
# ---------------------------------------------------------------------------


def test_profile_create_binds_consent_to_profile_id():
    p = _profile("Alice")
    # The persisted consent must reference the profile it belongs to.
    assert p.consent.profile_id == p.profile_id


def test_consent_profile_id_rebound_even_if_caller_sets_wrong_one():
    consent = ConsentRecord.create("stmt", profile_id="some-other-id")
    p = VoiceProfile.create("Bob", _artifacts(), consent)
    assert p.consent.profile_id == p.profile_id  # caller value overridden


def test_consent_new_fields_roundtrip(tmp_path):
    repo = JsonFileProfileRepository(tmp_path)
    p = _profile("Carol")
    repo.save(p)
    raw = json.loads((tmp_path / f"{p.profile_id}.json").read_text())
    consent = raw["consent"]
    assert consent["profile_id"] == p.profile_id
    assert consent["app_version"] == __version__
    assert consent["consent_schema_version"] == CONSENT_SCHEMA_VERSION

    loaded = repo.load(p.profile_id)
    assert loaded.consent.profile_id == p.profile_id
    assert loaded.consent.app_version == __version__


def test_legacy_consent_without_new_fields_loads(tmp_path):
    """Back-compat: a profile written before M1 (no profile_id/app_version/
    schema in the consent block) must still load."""
    repo = JsonFileProfileRepository(tmp_path)
    p = _profile("Legacy")
    d = _profile_to_dict(p)
    d["consent"] = {
        "record_id": p.consent.record_id,
        "statement": p.consent.statement,
        "affirmed_at": p.consent.affirmed_at,
        "affirmed_by": p.consent.affirmed_by,
    }
    (tmp_path / f"{p.profile_id}.json").write_text(json.dumps(d))

    loaded = repo.load(p.profile_id)
    assert loaded is not None
    assert loaded.consent.app_version == "unknown"
    assert loaded.consent.profile_id == p.profile_id  # falls back to profile id


# ---------------------------------------------------------------------------
# Enforcement audit — no profile without a consent record
# ---------------------------------------------------------------------------


def test_voice_profile_requires_consent_argument():
    with pytest.raises(TypeError):
        VoiceProfile.create("NoConsent", _artifacts())  # type: ignore[call-arg]


def test_dict_to_profile_rejects_missing_consent():
    p = _profile()
    d = _profile_to_dict(p)
    del d["consent"]
    with pytest.raises(ValueError, match="consent"):
        _dict_to_profile(d)


def test_dict_to_profile_rejects_empty_consent_statement():
    p = _profile()
    d = _profile_to_dict(p)
    d["consent"]["statement"] = "   "
    with pytest.raises(ValueError, match="consent"):
        _dict_to_profile(d)


def test_load_blocks_consentless_profile_file(tmp_path):
    """A tampered profile file with no consent block must not load."""
    repo = JsonFileProfileRepository(tmp_path)
    p = _profile()
    d = _profile_to_dict(p)
    del d["consent"]
    (tmp_path / f"{p.profile_id}.json").write_text(json.dumps(d))
    assert repo.load(p.profile_id) is None
    assert repo.list_all() == []  # skipped, not surfaced


# ---------------------------------------------------------------------------
# VoiceProfile
# ---------------------------------------------------------------------------


def test_profile_create_sets_fields():
    p = _profile("Alice")
    assert p.name == "Alice"
    assert len(p.profile_id) == 32
    assert p.created_at > 0
    assert isinstance(p.consent, ConsentRecord)


def test_profile_empty_name_raises():
    with pytest.raises(ValueError, match="empty"):
        VoiceProfile.create("  ", _artifacts(), _consent())


def test_two_profiles_unique_ids():
    assert _profile().profile_id != _profile().profile_id


# ---------------------------------------------------------------------------
# JsonFileProfileRepository
# ---------------------------------------------------------------------------


def test_save_and_load_roundtrip(tmp_path):
    repo = JsonFileProfileRepository(tmp_path)
    p = _profile()
    repo.save(p)
    loaded = repo.load(p.profile_id)
    assert loaded is not None
    assert loaded.profile_id == p.profile_id
    assert loaded.name == p.name
    assert loaded.artifacts.data == p.artifacts.data
    assert loaded.consent.record_id == p.consent.record_id
    assert loaded.consent.statement == p.consent.statement


def test_load_unknown_id_returns_none(tmp_path):
    repo = JsonFileProfileRepository(tmp_path)
    assert repo.load("nonexistent") is None


def test_list_all_returns_saved_profiles(tmp_path):
    repo = JsonFileProfileRepository(tmp_path)
    p1 = _profile("Alice")
    p2 = _profile("Bob")
    repo.save(p1)
    repo.save(p2)
    ids = {p.profile_id for p in repo.list_all()}
    assert p1.profile_id in ids
    assert p2.profile_id in ids


def test_delete_removes_profile(tmp_path):
    repo = JsonFileProfileRepository(tmp_path)
    p = _profile()
    repo.save(p)
    repo.delete(p.profile_id)
    assert repo.load(p.profile_id) is None


def test_delete_nonexistent_is_noop(tmp_path):
    repo = JsonFileProfileRepository(tmp_path)
    repo.delete("ghost")  # must not raise


def test_corrupt_file_skipped_in_list_all(tmp_path):
    repo = JsonFileProfileRepository(tmp_path)
    p = _profile()
    repo.save(p)
    (tmp_path / "bad.json").write_text("not valid json")
    profiles = repo.list_all()
    assert any(x.profile_id == p.profile_id for x in profiles)
    assert len(profiles) == 1  # corrupt file skipped


def test_schema_version_written(tmp_path):
    repo = JsonFileProfileRepository(tmp_path)
    p = _profile()
    repo.save(p)
    raw = json.loads((tmp_path / f"{p.profile_id}.json").read_text())
    assert raw["schema_version"] == 1


def test_binary_artifacts_data_roundtrip(tmp_path):
    data = bytes(range(256))
    repo = JsonFileProfileRepository(tmp_path)
    p = VoiceProfile.create("bin", _artifacts(data), _consent())
    repo.save(p)
    loaded = repo.load(p.profile_id)
    assert loaded.artifacts.data == data
