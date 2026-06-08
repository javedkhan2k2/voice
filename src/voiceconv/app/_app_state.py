"""Central application state passed to all view-models."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path

from voiceconv.inference.engine import VoiceConversionEngine
from voiceconv.services.converter import Converter
from voiceconv.services.queue import JobQueue
from voiceconv.services.runner import QueueRunner
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
    # Added in Phase 2 M2:
    queue: JobQueue = field(default=None)   # type: ignore[assignment]
    runner: QueueRunner = field(default=None)   # type: ignore[assignment]
    engine_lock: threading.Lock = field(default_factory=threading.Lock)
    # Added in Phase 2 M5 — resolved log directory for diagnostics export:
    log_dir: Path = field(default=None)   # type: ignore[assignment]
