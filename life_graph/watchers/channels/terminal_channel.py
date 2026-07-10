"""Terminal/log file notification channel.

Writes formatted notification lines to a log file (from config)
or stdout if no log_file is configured.

Config dict keys:
    log_file (optional) — absolute path to write to.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class TerminalChannel:
    """Writes notification events to a log file or stdout."""

    async def send(
        self,
        config: dict[str, Any],
        severity: str,
        watcher_name: str,
        title: str,
        details: str | None = None,
    ) -> bool:
        """Write a formatted notification line.

        Args:
            config: Channel config (log_file optional).
            severity: Event severity level.
            watcher_name: Name of the originating watcher.
            title: Event title.
            details: Optional extra details.

        Returns:
            True on success, False on failure.
        """
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        line = f"[{ts}] [{severity.upper()}] [{watcher_name}] {title}"
        if details:
            line += f"\n    {details}"
        line += "\n"

        log_file = config.get("log_file")

        try:
            if log_file:
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(line)
            else:
                sys.stdout.write(line)
                sys.stdout.flush()
            return True
        except Exception as e:
            logger.error("Terminal channel write failed: %s", e)
            return False
