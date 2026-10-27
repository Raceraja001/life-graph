"""Which of the owner's promises to nudge now (web-chat-wave1 F2, T2.1).

Pure: the nudge job (services/nudges.py) hands in plain dicts and sends what
comes back. A few a day at most, never in quiet hours, soonest deadline first.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime


def in_quiet_hours(now: datetime, quiet_hours: tuple[int, int]) -> bool:
    """*quiet_hours* (start, end) in now's own zone; (22, 7) is 22:00-06:59."""
    start, end = quiet_hours
    hour = now.hour
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def pick(
    candidates: list[dict[str, Any]],
    now: datetime,
    *,
    sent_today: int,
    quiet_hours: tuple[int, int] = (22, 7),
    max_per_day: int = 3,
) -> list[dict[str, Any]]:
    """The candidates to nudge now: open, due to start, not snoozed — at most what
    is left of today's allowance, none at all in quiet hours."""
    if in_quiet_hours(now, quiet_hours):
        return []
    room = max(0, max_per_day - sent_today)
    if room == 0:
        return []
    due = [
        c
        for c in candidates
        if c.get("state") == "open"
        and c["due_from"] <= now
        and (c.get("snoozed_until") is None or c["snoozed_until"] <= now)
    ]
    due.sort(key=lambda c: (c["due_by"], str(c["id"])))
    return due[:room]
