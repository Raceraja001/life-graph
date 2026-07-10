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
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """JSON log formatter with request context fields.

    Produces one JSON object per log line with fields:
    timestamp, level, logger, message, and any extras.
    """

    def format(self, record: logging.LogRecord) -> str:
        import json

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
            log_entry["exception"] = self.formatException(record.exc_info)

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

    root_logger.addHandler(handler)

    # Quiet noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Logging configured: format=%s, level=%s", format, level
    )
