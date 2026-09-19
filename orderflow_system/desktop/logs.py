"""
Log plumbing for the desktop shell: a ring buffer the GUI can tail, plus a
rotating file handler under the per-user config directory.
"""

from __future__ import annotations

import logging
import logging.handlers
import re
import sys
from collections import deque
from typing import Deque

from orderflow_system.desktop.config_store import log_path

MAX_LINES = 1000
_buffer: Deque[dict] = deque(maxlen=MAX_LINES)

#: Text that must never reach a log sink. Two shapes, in order: a token inside a URL path
#: (`…/bot8123456789:AAF…`, which is how httpx logs a request and how Telegram's own
#: InvalidToken reads) and a bare `digits:secret` token. Both are rewritten, never dropped —
#: the line stays useful (audit SEC-01).
_TOKEN_PATTERNS = (
    # (pattern, replacement) — URL form first, then a bare token, then any `key=…` query form.
    (re.compile(r"(?i)\bbot\d{5,15}[:\-][A-Za-z0-9_\-]{20,}"), "bot<redacted>"),
    (re.compile(r"\b\d{5,15}:[A-Za-z0-9_\-]{20,}\b"), "<redacted>"),
    (re.compile(r"(?i)([?&](?:token|access_token|api_key|apikey|key|secret|password)=)[^&\s\"']+"),
     r"\1<redacted>"),
)
REDACTED = "<redacted>"


def redact(text: object) -> str:
    """Every token-shaped run in ``text`` replaced with ``<redacted>``. Pure, never raises."""
    out = str(text)
    for pattern, replacement in _TOKEN_PATTERNS:
        out = pattern.sub(replacement, out)
    return out


class RedactingFilter(logging.Filter):
    """Rewrites token-shaped text in a record before any handler formats it.

    Attached to the handlers (not one logger) so third-party records — httpx's request URL,
    python-telegram-bot's InvalidToken text — are covered too.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str):
                record.msg = redact(record.msg)
            args = record.args
            if isinstance(args, tuple):
                record.args = tuple(redact(a) if isinstance(a, str) else a for a in args)
            elif isinstance(args, dict):
                record.args = {k: (redact(v) if isinstance(v, str) else v) for k, v in args.items()}
        except Exception:                      # logging must never raise
            pass
        return True


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
    # SEC-01: the noisy third-party loggers stay, but quiet — their INFO lines carry URLs, and a
    # Telegram URL carries the bot token in its path. Warnings/errors still come through (redacted).
    for noisy in ("httpx", "httpcore", "telegram", "aiohttp", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    if not any(isinstance(h, BufferHandler) for h in root.handlers):
        buf = BufferHandler()
        buf.addFilter(RedactingFilter())
        buf.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S"))
        root.addHandler(buf)

    if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers):
        try:
            fh = logging.handlers.RotatingFileHandler(
                log_path(), maxBytes=2_000_000, backupCount=3, encoding="utf-8"
            )
            fh.addFilter(RedactingFilter())
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
