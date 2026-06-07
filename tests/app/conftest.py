"""Shared fixtures for app (view-model) tests.

QApplication must exist exactly once per process — create it at module scope
and never tear it down, because Qt asserts on double-init.
"""

from __future__ import annotations

import sys

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app
