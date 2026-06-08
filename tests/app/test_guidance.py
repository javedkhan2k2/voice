"""Acceptable-use guidance copy + placement (Phase 3 M3).

The copy guards make "copy reviewed for clarity and non-misuse positioning" an
automated check, not a one-off human pass.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from voiceconv.app._guidance import (
    ACCEPTABLE_USE,
    ACCEPTABLE_USE_VERSION,
    CONVERT_REMINDER,
    PROFILE_REMINDER,
)
from voiceconv.app.views.convert_view import ConvertView
from voiceconv.app.views.profile_view import ProfileView

# Marketing / misuse-positive phrasing that must never appear in the copy.
_RED_FLAGS = [
    "undetectable",
    "untraceable",
    "anonymous",
    "bypass",
    "prank",
    "fool",
    "get away with",
]


# ---------------------------------------------------------------------------
# Copy guards
# ---------------------------------------------------------------------------


def test_acceptable_use_states_core_obligations():
    text = ACCEPTABLE_USE.lower()
    assert "permission" in text
    assert "impersonate" in text and "deceive" in text and "defraud" in text
    assert "responsibility" in text
    # Offline guarantee surfaced to the user.
    assert "locally" in text or "leaves your device" in text
    # Provenance disclosure surfaced.
    assert "ai voice-converted" in text


def test_reminders_are_non_empty_and_on_point():
    assert "permission" in PROFILE_REMINDER.lower()
    assert "consent" in PROFILE_REMINDER.lower()
    assert "impersonate" in CONVERT_REMINDER.lower()
    assert "responsible" in CONVERT_REMINDER.lower()


def test_copy_has_no_misuse_positive_phrasing():
    blob = " ".join([ACCEPTABLE_USE, PROFILE_REMINDER, CONVERT_REMINDER]).lower()
    for flag in _RED_FLAGS:
        assert flag not in blob, f"red-flag phrase in guidance copy: {flag!r}"


def test_acceptable_use_version_is_set():
    assert ACCEPTABLE_USE_VERSION
    assert isinstance(ACCEPTABLE_USE_VERSION, str)


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------


def test_profile_view_shows_reminder(qapp):
    view = ProfileView(MagicMock())
    assert view._guidance_label.text() == PROFILE_REMINDER
    assert view._guidance_label.accessibleName()


def test_convert_view_shows_reminder(qapp):
    view = ConvertView(MagicMock(), MagicMock())
    assert view._guidance_label.text() == CONVERT_REMINDER
    assert view._guidance_label.accessibleName()
