"""The owner's "every Monday at 9" as a cron expression (web-chat-wave1 F1, T1.1).

``parse_recurrence(text, tz)`` reads a short English phrase and returns the
5-field cron the scheduler runs (kernel/scheduler.py ``CronExpression``: UTC,
day-of-week 0 = Sunday), or None when it cannot tell — the caller then asks
rather than guesses. Times are in the owner's zone *tz* and converted with
its offset today, so Asia/Kolkata's 09:00 Monday is ``30 3 * * 1`` and its
02:00 Monday is ``30 20 * * 0``.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

_DAYS = {
    "sunday": 0,
    "monday": 1,
    "tuesday": 2,
    "wednesday": 3,
    "thursday": 4,
    "friday": 5,
    "saturday": 6,
}
# Parts of the day, when no time is given.
_PARTS = {"morning": (7, 0), "afternoon": (14, 0), "evening": (19, 0), "night": (21, 0)}
_TIME = re.compile(r"\bat\s+(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?\b")
_EVERY_N_HOURS = re.compile(r"\bevery\s+(\d{1,2})\s+hours?\b")
_MONTHLY = re.compile(r"\bon\s+the\s+(\d{1,2})(?:st|nd|rd|th)?\s+of\s+(?:every|each)\s+month\b")


def _clock(text: str) -> tuple[int, int] | None:
    """The time of day the phrase names, or its part of the day, or None."""
    m = _TIME.search(text)
    if m:
        hour, minute, half = int(m.group(1)), int(m.group(2) or 0), m.group(3)
        if half == "pm" and hour < 12:
            hour += 12
        elif half == "am" and hour == 12:
            hour = 0
        if hour > 23 or minute > 59:
            return None
        return hour, minute
    for word, at in _PARTS.items():
        if re.search(rf"\b{word}s?\b", text):
            return at
    return None


def _to_utc(hour: int, minute: int, tz: str) -> tuple[int, int, int]:
    """(hour, minute, day shift) in UTC for a local time in *tz* today."""
    zone = ZoneInfo(tz)
    today = datetime.now(zone).date()
    local = datetime(today.year, today.month, today.day, hour, minute, tzinfo=zone)
    utc = local.astimezone(UTC)
    return utc.hour, utc.minute, (utc.date() - local.date()).days


def _shift(days: list[int] | None, by: int) -> str:
    """Day-of-week field after moving every day by *by* (wrapping 0..6)."""
    if days is None:
        return "*"
    moved = sorted((d + by) % 7 for d in days)
    if len(moved) > 2 and moved == list(range(moved[0], moved[-1] + 1)):
        return f"{moved[0]}-{moved[-1]}"
    return ",".join(str(d) for d in moved)


def parse_recurrence(text: str, tz: str) -> str | None:
    """The UTC cron for *text* ("every weekday at 8:30"), or None if unclear."""
    t = " ".join(text.lower().split())
    if not t:
        return None

    if re.search(r"\bevery\s+hour\b|\bhourly\b", t):
        return "0 * * * *"
    m = _EVERY_N_HOURS.search(t)
    if m:
        n = int(m.group(1))
        return f"0 */{n} * * *" if 1 <= n <= 23 else None

    monthly = _MONTHLY.search(t)
    days: list[int] | None
    if monthly:
        day_of_month = int(monthly.group(1))
        if not 1 <= day_of_month <= 28:
            return None  # the 29th-31st are missing from some months
        days = None
    elif re.search(r"\bweekdays?\b", t):
        days = [1, 2, 3, 4, 5]
    elif re.search(r"\bweekends?\b", t):
        days = [0, 6]
    else:
        named = [d for word, d in _DAYS.items() if re.search(rf"\b{word}s?\b", t)]
        if named:
            days = sorted(named)
        elif re.search(
            r"\b(?:every|each)\s+(?:day|morning|afternoon|evening|night)\b|\bdaily\b", t
        ):
            days = None
        else:
            return None

    at = _clock(t)
    if at is None:
        return None
    hour, minute, shift = _to_utc(*at, tz)
    if monthly:
        if shift:
            return None  # the day of month would move; ask instead
        return f"{minute} {hour} {day_of_month} * *"
    return f"{minute} {hour} * * {_shift(days, shift)}"
