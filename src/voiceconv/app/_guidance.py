"""Acceptable-use guidance copy (Phase 3 M3).

Single source of truth for the user-facing safeguard language so it can be
reviewed in one place and asserted by tests. Wording is deliberately plain and
non-marketing; it must not position the tool for impersonation or deception.
"""

from __future__ import annotations

# Bump when the acceptable-use wording changes; the accepted version is recorded
# in AppSettings.acceptable_use_acknowledged_version.
ACCEPTABLE_USE_VERSION = "1"

# Full statement shown at first run and re-viewable from Settings.
ACCEPTABLE_USE = (
    "VoiceBuilder converts speech audio into a target speaker's voice.\n\n"
    "Before using this tool you must confirm:\n"
    "  • You own, or have explicit permission to use, any voice you create "
    "a profile from.\n"
    "  • You will not use generated audio to impersonate, deceive, or "
    "defraud anyone.\n"
    "  • You accept full responsibility for any use of the generated "
    "output.\n\n"
    "Generated files are tagged in their metadata as AI voice-converted by this "
    "tool.\n\n"
    "All processing is performed locally on your machine. No audio or voice "
    "data leaves your device."
)

# Short contextual reminder shown on the Create Profile tab.
PROFILE_REMINDER = (
    "Only create a profile from a voice you own or have explicit permission to "
    "use. Creating a profile records your consent."
)

# Short contextual reminder shown on the Convert tab.
CONVERT_REMINDER = (
    "Converted audio is tagged as AI voice-converted by this tool. Do not use "
    "it to impersonate, deceive, or defraud. You are responsible for how it is "
    "used."
)
