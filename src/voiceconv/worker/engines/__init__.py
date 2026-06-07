"""Engine registry — maps engine_id strings to factory callables.

To add a new engine:
  1. Implement a class with the WorkerEngine protocol in a new module under engines/.
  2. Import it here and add an entry to REGISTRY.
"""

from __future__ import annotations

from typing import Callable

from voiceconv.worker.engines.freevc import FreeVCEngine
from voiceconv.worker.engines.mock import MockEngine
from voiceconv.worker.engines.openvoice_v2 import OpenVoiceV2Engine

REGISTRY: dict[str, Callable[[], object]] = {
    "openvoice_v2": OpenVoiceV2Engine,
    "freevc": FreeVCEngine,
    "mock": MockEngine,
}
