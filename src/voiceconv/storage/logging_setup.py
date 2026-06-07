"""Rotating file log handler setup.

Call ``setup_logging()`` once at app startup.  Idempotent — a second call
with the same log directory does not add a duplicate handler.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

_LOG_FILENAME = "voiceconv.log"
_configured_dirs: set[str] = set()


def setup_logging(
    log_dir: Path,
    level: int = logging.INFO,
    max_bytes: int = 5_242_880,
    backup_count: int = 3,
) -> None:
    """Add a ``RotatingFileHandler`` writing to *log_dir*/voiceconv.log.

    Does not call ``logging.basicConfig`` — only attaches the handler to the
    root logger so pytest's log capture is unaffected.

    Parameters
    ----------
    log_dir:
        Directory for log files; created if it does not exist.
    level:
        Minimum log level for the file handler.
    max_bytes:
        Rotate when the log file exceeds this size (default 5 MB).
    backup_count:
        Number of rotated files to keep alongside the active log.
    """
    log_dir = Path(log_dir)
    key = str(log_dir.resolve())
    if key in _configured_dirs:
        return
    _configured_dirs.add(key)

    log_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        log_dir / _LOG_FILENAME,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")
    )
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(min(logging.getLogger().level or level, level))
