"""Desktop toast notifications.

Uses ``winotify`` for a reliable Windows toast; falls back to the pystray
balloon if winotify is unavailable. Best-effort — never raises (a failed
notification must never break a capture).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("desktop.notify")

APP_ID = "Life Graph Capture"


def toast(title: str, message: str, *, icon_fallback: Any = None) -> None:
    """Show a desktop toast. Best-effort; swallows all errors."""
    try:
        from winotify import Notification

        Notification(app_id=APP_ID, title=title, msg=message).show()
        return
    except Exception:
        logger.debug("winotify toast failed; trying fallback", exc_info=True)

    if icon_fallback is not None:
        try:
            icon_fallback.notify(message, title)
        except Exception:
            logger.debug("pystray balloon fallback failed", exc_info=True)
