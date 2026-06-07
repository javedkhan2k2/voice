"""View-model for the Profile Library tab."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal

from voiceconv.app._app_state import AppState
from voiceconv.storage.profile import VoiceProfile

log = logging.getLogger(__name__)


class ProfileLibraryViewModel(QObject):
    """Browse, rename, and delete voice profiles."""

    profiles_changed = Signal()    # list changed — view should rebuild
    selection_changed = Signal(str) # profile_id selected, or "" when cleared
    error = Signal(str)

    def __init__(self, state: AppState, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._profiles: list[VoiceProfile] = []
        self._selected_id: str | None = None

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def profiles(self) -> list[VoiceProfile]:
        return list(self._profiles)

    def selected_profile(self) -> VoiceProfile | None:
        if self._selected_id is None:
            return None
        for p in self._profiles:
            if p.profile_id == self._selected_id:
                return p
        return None

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Reload profiles from the repository."""
        self._profiles = self._state.profile_repo.list_all()
        if self._selected_id not in {p.profile_id for p in self._profiles}:
            self._selected_id = None
            self.selection_changed.emit("")
        self.profiles_changed.emit()

    def select(self, profile_id: str) -> None:
        self._selected_id = profile_id
        self.selection_changed.emit(profile_id)

    def rename(self, profile_id: str, new_name: str) -> None:
        new_name = new_name.strip()
        if not new_name:
            self.error.emit("Profile name must not be empty.")
            return
        profile = self._state.profile_repo.load(profile_id)
        if profile is None:
            self.error.emit(f"Profile not found: {profile_id!r}")
            return
        renamed = VoiceProfile(
            profile_id=profile.profile_id,
            name=new_name,
            artifacts=profile.artifacts,
            consent=profile.consent,
            created_at=profile.created_at,
        )
        self._state.profile_repo.save(renamed)
        log.info("Profile renamed: %s → %r", profile_id[:8], new_name)
        self.refresh()

    def delete(self, profile_id: str) -> None:
        self._state.profile_repo.delete(profile_id)
        log.info("Profile deleted: %s", profile_id[:8])
        if self._selected_id == profile_id:
            self._selected_id = None
        self.refresh()
