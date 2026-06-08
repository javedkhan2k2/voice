"""Voice profile schema, consent record, and profile repository.

ConsentRecord is structurally required to create a VoiceProfile — there is no
code path that produces a profile without a persisted consent record.
"""

from __future__ import annotations

import base64
import json
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Optional

from voiceconv import __version__
from voiceconv.inference.engine import ProfileArtifacts

SCHEMA_VERSION = 1
CONSENT_SCHEMA_VERSION = 1

_CONSENT_STATEMENT = (
    "I confirm that I own or have explicit permission to use this voice, "
    "and I accept full responsibility for any use of the generated output."
)


# ---------------------------------------------------------------------------
# ConsentRecord
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConsentRecord:
    """Immutable record of user consent for a voice profile.

    Versioned schema (``consent_schema_version``) capturing the four fields the
    spec requires: *timestamp* (``affirmed_at``), *acknowledgement text*
    (``statement``), *profile id* (``profile_id``), and *app version*
    (``app_version``).  See ``docs/consent.md``.

    Must be created via :meth:`create` so the timestamp, ID, and app version are
    set by this module rather than supplied by the caller.  ``profile_id`` is
    bound by :meth:`VoiceProfile.create` so it always matches the owning profile.
    """

    record_id: str
    statement: str
    affirmed_at: float
    affirmed_by: str
    profile_id: str = ""
    app_version: str = __version__
    consent_schema_version: int = CONSENT_SCHEMA_VERSION

    @classmethod
    def create(
        cls,
        statement: str = _CONSENT_STATEMENT,
        affirmed_by: str = "user",
        profile_id: str = "",
        app_version: str = __version__,
    ) -> "ConsentRecord":
        if not statement.strip():
            raise ValueError("consent statement must not be empty")
        return cls(
            record_id=uuid.uuid4().hex,
            statement=statement,
            affirmed_at=time.time(),
            affirmed_by=affirmed_by,
            profile_id=profile_id,
            app_version=app_version,
            consent_schema_version=CONSENT_SCHEMA_VERSION,
        )


# ---------------------------------------------------------------------------
# VoiceProfile
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VoiceProfile:
    """A named voice profile binding engine artifacts to a consent record.

    ``consent`` is a required field — ``VoiceProfile`` cannot be instantiated
    without a ``ConsentRecord``.  Use :meth:`create` to generate IDs and
    timestamps automatically.
    """

    profile_id: str
    name: str
    artifacts: ProfileArtifacts
    consent: ConsentRecord
    created_at: float

    @classmethod
    def create(
        cls,
        name: str,
        artifacts: ProfileArtifacts,
        consent: ConsentRecord,
    ) -> "VoiceProfile":
        if not name.strip():
            raise ValueError("profile name must not be empty")
        profile_id = uuid.uuid4().hex
        # Bind the consent to this profile so the persisted record always
        # references the profile it belongs to (single point of truth).
        bound_consent = replace(consent, profile_id=profile_id)
        return cls(
            profile_id=profile_id,
            name=name,
            artifacts=artifacts,
            consent=bound_consent,
            created_at=time.time(),
        )


# ---------------------------------------------------------------------------
# Repository ABC
# ---------------------------------------------------------------------------


class ProfileRepository(ABC):
    @abstractmethod
    def save(self, profile: VoiceProfile) -> None: ...

    @abstractmethod
    def load(self, profile_id: str) -> Optional[VoiceProfile]: ...

    @abstractmethod
    def list_all(self) -> list[VoiceProfile]: ...

    @abstractmethod
    def delete(self, profile_id: str) -> None: ...


# ---------------------------------------------------------------------------
# JSON file implementation
# ---------------------------------------------------------------------------


class JsonFileProfileRepository(ProfileRepository):
    """Stores one JSON file per profile in a directory.

    Atomic writes via tmp+rename (same pattern as ``JsonFileJobRepository``).
    Corrupt or unreadable files are silently skipped on ``list_all()``.
    """

    def __init__(self, directory: Path) -> None:
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, profile: VoiceProfile) -> None:
        d = _profile_to_dict(profile)
        tmp = self._dir / f".{uuid.uuid4().hex}.tmp"
        tmp.write_bytes(json.dumps(d, indent=2).encode())
        tmp.replace(self._dir / f"{profile.profile_id}.json")

    def load(self, profile_id: str) -> Optional[VoiceProfile]:
        path = self._dir / f"{profile_id}.json"
        if not path.exists():
            return None
        try:
            return _dict_to_profile(json.loads(path.read_bytes()))
        except Exception:
            return None

    def list_all(self) -> list[VoiceProfile]:
        profiles = []
        for p in sorted(self._dir.glob("*.json")):
            try:
                profiles.append(_dict_to_profile(json.loads(p.read_bytes())))
            except Exception:
                pass
        return profiles

    def delete(self, profile_id: str) -> None:
        path = self._dir / f"{profile_id}.json"
        path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _profile_to_dict(p: VoiceProfile) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "profile_id": p.profile_id,
        "name": p.name,
        "created_at": p.created_at,
        "artifacts": {
            "engine_id": p.artifacts.engine_id,
            "engine_version": p.artifacts.engine_version,
            "data": base64.b64encode(p.artifacts.data).decode(),
            "metadata": p.artifacts.metadata,
        },
        "consent": {
            "consent_schema_version": p.consent.consent_schema_version,
            "record_id": p.consent.record_id,
            "statement": p.consent.statement,
            "affirmed_at": p.consent.affirmed_at,
            "affirmed_by": p.consent.affirmed_by,
            "profile_id": p.consent.profile_id,
            "app_version": p.consent.app_version,
        },
    }


def _dict_to_profile(d: dict[str, Any]) -> VoiceProfile:
    a = d["artifacts"]
    c = d.get("consent")
    # Enforcement: a profile is invalid without a consent record carrying a
    # non-empty acknowledgement statement. Refuse to materialise one.
    if not c or not str(c.get("statement", "")).strip():
        raise ValueError("profile is missing a required consent record")
    profile_id = d["profile_id"]
    return VoiceProfile(
        profile_id=profile_id,
        name=d["name"],
        created_at=d["created_at"],
        artifacts=ProfileArtifacts(
            engine_id=a["engine_id"],
            engine_version=a["engine_version"],
            data=base64.b64decode(a["data"]),
            metadata=a.get("metadata", {}),
        ),
        consent=ConsentRecord(
            record_id=c["record_id"],
            statement=c["statement"],
            affirmed_at=c["affirmed_at"],
            affirmed_by=c["affirmed_by"],
            # Back-compat: legacy records predate these fields.
            profile_id=c.get("profile_id") or profile_id,
            app_version=c.get("app_version", "unknown"),
            consent_schema_version=c.get("consent_schema_version", 1),
        ),
    )
