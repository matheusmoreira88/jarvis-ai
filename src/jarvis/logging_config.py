"""Local rotating diagnostics with credential redaction."""
from __future__ import annotations

import logging
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from platformdirs import user_log_path

LOG_DIR = user_log_path("JarvisAI", "Matheus")
LOG_FILE = LOG_DIR / "jarvis.log"

_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_ -]?key|authorization|token|secret)(\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
)


def redact(value: object) -> str:
    """Remove common credential shapes before a message reaches disk."""
    text = str(value)
    for pattern in _SECRET_PATTERNS:
        if pattern.groups >= 3:
            text = pattern.sub(r"\1\2[REDACTED]", text)
        else:
            text = pattern.sub("[REDACTED]", text)
    return text


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        rendered = super().format(record)
        return redact(rendered)


def configure_logging() -> Path:
    """Configure one bounded local file and preserve the default exception hook."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    if not any(getattr(handler, "_jarvis_handler", False) for handler in root.handlers):
        handler = RotatingFileHandler(
            LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        handler._jarvis_handler = True
        handler.setFormatter(RedactingFormatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(handler)
        root.setLevel(logging.INFO)

    previous_hook = sys.excepthook

    def report_unhandled(exc_type, exc_value, traceback):
        logging.getLogger("jarvis.unhandled").critical(
            "Unhandled exception", exc_info=(exc_type, exc_value, traceback))
        previous_hook(exc_type, exc_value, traceback)

    if not getattr(sys.excepthook, "_jarvis_hook", False):
        report_unhandled._jarvis_hook = True
        sys.excepthook = report_unhandled
    return LOG_FILE

