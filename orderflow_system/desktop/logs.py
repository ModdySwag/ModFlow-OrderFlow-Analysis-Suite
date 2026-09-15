"""
Log plumbing for the desktop shell: a ring buffer the GUI can tail, plus a
rotating file handler under the per-user config directory.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from collections import deque
from typing import Deque

from orderflow_system.desktop.config_store import log_path

MAX_LINES = 1000
_buffer: Deque[dict] = deque(maxlen=MAX_LINES)


class BufferHandler(logging.Handler):
    """Keeps the last N records in memory for the GUI's live log view."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            _buffer.append({
                "t": record.created,
                "level": record.levelname,
                "name": record.name,
                "msg": self.format(record),
            })
        except Exception:                      # logging must never raise
            pass


def install(level: str = "INFO") -> None:
    """Attach the buffer + rotating file handler to the root logger (idempotent)."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, str(level).upper(), logging.INFO))

    if not any(isinstance(h, BufferHandler) for h in root.handlers):
        buf = BufferHandler()
        buf.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S"))
        root.addHandler(buf)

    if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers):
        try:
            fh = logging.handlers.RotatingFileHandler(
                log_path(), maxBytes=2_000_000, backupCount=3, encoding="utf-8"
            )
            fh.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"))
            root.addHandler(fh)
        except OSError:
            pass                                # read-only FS → buffer only

    # A console handler is optional: under pythonw.exe (a desktop shortcut, no
    # console attached) sys.stderr is None, and a StreamHandler built from it
    # raises on every record — which kills whatever thread logged. The file and
    # buffer handlers above are what the Logs view reads anyway.
    console = sys.stderr
    if console is not None and not any(
            isinstance(h, logging.StreamHandler) and not isinstance(h, BufferHandler)
            for h in root.handlers):
        sh = logging.StreamHandler(console)
        sh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S"))
        root.addHandler(sh)


def tail(lines: int = 200, min_level: str = "") -> list[dict]:
    """Most recent buffered records, oldest first."""
    want = getattr(logging, str(min_level).upper(), None) if min_level else None
    items = list(_buffer)
    if want is not None:
        items = [r for r in items if logging.getLevelName(r["level"]) >= want]
    return items[-max(1, min(lines, MAX_LINES)):]
