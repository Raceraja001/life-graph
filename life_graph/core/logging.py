"""Structured logging configuration for Life Graph.

Supports two modes:
  - "text": Human-readable format for development
  - "json": JSON format for production (ELK/CloudWatch/Datadog)

Usage:
    from life_graph.core.logging import setup_logging
    setup_logging(format="json")  # Call once during startup
"""

from __future__ import annotations

import logging
import re
import sys
from datetime import UTC, datetime

# A Telegram bot token ("<digits>:<35ish url-safe chars>"), either in a Bot API
# URL path (".../bot<token>/method") or bare. The token is a credential and
# the API only accepts it in the URL, so any logged URL or HTTP error message
# can carry it (audit M22).
_BOT_TOKEN = re.compile(
    r"(?<=/)bot\d+:[A-Za-z0-9_-]+|(?<![A-Za-z0-9])(?:bot)?\d{6,}:[A-Za-z0-9_-]{30,}"
)


def mask_log_secrets(text: str) -> str:
    """*text* with Telegram bot tokens replaced by ``<redacted>``."""
    return _BOT_TOKEN.sub(
        lambda m: "bot<redacted>" if m.group().startswith("bot") else "<redacted>", text
    )


class SecretMaskFilter(logging.Filter):
    """Masks bot tokens in a record's message, traceback and stack.

    Attach it to a *handler* (a filter on a logger only sees records logged
    to that exact logger, not ones propagated from its children). The record
    is rewritten in place, so every later handler sees the masked text too.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 - a bad format string is logging's problem
            return True
        masked = mask_log_secrets(message)
        if masked != message:
            record.msg, record.args = masked, None
        if record.exc_info and record.exc_info[1] is not None and not record.exc_text:
            # Formatters reuse exc_text when it is set, so the traceback is
            # rendered once here and masked before any handler prints it.
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = mask_log_secrets(record.exc_text)
        if record.stack_info:
            record.stack_info = mask_log_secrets(record.stack_info)
        return True


def add_secret_mask(handler: logging.Handler) -> None:
    """Attach :class:`SecretMaskFilter` to *handler* once."""
    if not any(isinstance(f, SecretMaskFilter) for f in handler.filters):
        handler.addFilter(SecretMaskFilter())


class JSONFormatter(logging.Formatter):
    """JSON log formatter with request context fields.

    Produces one JSON object per log line with fields:
    timestamp, level, logger, message, and any extras.
    """

    def format(self, record: logging.LogRecord) -> str:
        import json

        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields if present
        for key in ("request_id", "tenant_id", "duration_ms", "method", "path", "status"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val

        # Add exception info
        if record.exc_info and record.exc_info[1]:
            # exc_text first: SecretMaskFilter leaves the masked text there.
            log_entry["exception"] = record.exc_text or self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


class TextFormatter(logging.Formatter):
    """Human-readable log format for development."""

    FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"

    def __init__(self) -> None:
        super().__init__(fmt=self.FORMAT, datefmt="%H:%M:%S")


def setup_logging(format: str = "text", level: str = "INFO") -> None:
    """Configure the root logger for the application.

    Args:
        format: "text" for development, "json" for production.
        level: Log level (DEBUG, INFO, WARNING, ERROR).
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create handler
    handler = logging.StreamHandler(sys.stdout)

    if format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(TextFormatter())
    add_secret_mask(handler)

    root_logger.addHandler(handler)

    # Quiet noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    logging.getLogger(__name__).info("Logging configured: format=%s, level=%s", format, level)
