"""Central application state passed to all view-models."""

from __future__ import annotations

from dataclasses import dataclass

from voiceconv.inference.engine import VoiceConversionEngine
from voiceconv.services.converter import Converter
from voiceconv.storage.profile import JsonFileProfileRepository
from voiceconv.storage.settings import AppSettings, SettingsStore


@dataclass
class AppState:
    """Holds all shared service objects for the lifetime of the application."""

    converter: Converter
    profile_repo: JsonFileProfileRepository
    settings_store: SettingsStore
    settings: AppSettings
    engine: VoiceConversionEngine
