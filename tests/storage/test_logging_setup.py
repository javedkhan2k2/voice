"""Unit tests for setup_logging."""

import logging
from pathlib import Path

import pytest

from voiceconv.storage.logging_setup import _configured_dirs, setup_logging


@pytest.fixture(autouse=True)
def _clean_logging_state():
    """Remove any RotatingFileHandlers added during the test and clear the dir cache."""
    root = logging.getLogger()
    before = list(root.handlers)
    before_dirs = set(_configured_dirs)
    yield
    # Remove handlers added by this test
    for h in list(root.handlers):
        if h not in before:
            root.removeHandler(h)
            h.close()
    # Restore dir cache
    _configured_dirs.clear()
    _configured_dirs.update(before_dirs)


def test_log_file_created(tmp_path):
    setup_logging(tmp_path / "logs")
    assert (tmp_path / "logs" / "voiceconv.log").exists()


def test_log_message_appears_in_file(tmp_path):
    log_dir = tmp_path / "logs"
    setup_logging(log_dir)
    logging.getLogger("test.voiceconv").info("hello from test")
    # Flush all handlers
    for h in logging.getLogger().handlers:
        h.flush()
    content = (log_dir / "voiceconv.log").read_text()
    assert "hello from test" in content


def test_double_call_does_not_duplicate_handler(tmp_path):
    log_dir = tmp_path / "logs"
    root = logging.getLogger()
    before_count = len(root.handlers)
    setup_logging(log_dir)
    setup_logging(log_dir)  # second call — same dir
    assert len(root.handlers) == before_count + 1
