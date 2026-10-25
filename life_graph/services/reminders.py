"""Timed reminders the owner asks Jarvis for (life-graph-android docs/PLAN-v3.md).

A reminder is an ``Intention`` with ``trigger_type="time"``; once its time
comes, services/due_notifications.py writes it as a phone notification (kind
``reminder``, with Done / In 1 hour / Tomorrow buttons).

``parse_when`` turns what the model passes as ``at`` into a time. ISO-8601 is
preferred (the model can read the clock with get_current_datetime), but a
short phrase is accepted and resolved in the owner's timezone with plain code:
"6 pm", "at 18:30", "tomorrow 9am", "in 2 hours", "noon". Anything it cannot
read for certain ("tomorrow at 6": morning or evening?) is refused with a
sentence asking for a time: a guessed time is worse than a question.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

MAX_AHEAD = timedelta(days=366)
MAX_TEXT_CHARS = 500
#: What a refused ``at`` tells the model (and, through it, the owner).
NEED_A_TIME = (
    "I need a clear time for the reminder, like '6 pm', 'tomorrow 9 am' or 'in 2 hours'."
    " Ask the user when."
)

_UNITS = {
    "m": 1,
    "min": 1,
    "mins": 1,
    "minute": 1,
    "minutes": 1,
    "h": 60,
    "hr": 60,
    "hrs": 60,
    "hour": 60,
    "hours": 60,
    "day": 24 * 60,
    "days": 24 * 60,
}
_IN = re.compile(r"^in\s+(an?|half an?|\d+(?:\.\d+)?)\s*([a-z]+)$")
_CLOCK = re.compile(
    r"^(?:(today|tonight|tomorrow)\s+)?(?:at\s+)?"
    r"(?:(noon|midday|midnight)|(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm|a\.m\.?|p\.m\.?)?)"
    r"(?:\s+(today|tonight|tomorrow))?$"
)


class WhenError(ValueError):
    """``at`` could not be read as one certain time; the message says what to ask."""


def parse_when(at: str, now: datetime, tz: Any) -> datetime:
    """The moment *at* means, as an aware datetime in *tz*. Raises WhenError."""
    raw = " ".join(str(at or "").split())
    if not raw:
        raise WhenError(NEED_A_TIME)
    iso = _iso(raw, tz)
    if iso is not None:
        return iso
    text = raw.lower().rstrip(".!")
    local_now = now.astimezone(tz)
    m = _IN.match(text)
    if m:
        return local_now + _duration(m.group(1), m.group(2))
    m = _CLOCK.match(text)
    if not m:
        raise WhenError(NEED_A_TIME)
    before, named, hour_s, minute_s, suffix, after = m.groups()
    if before and after:
        raise WhenError(NEED_A_TIME)
    day = before or after
    today = local_now.date()
    if named == "midnight":
        if day == "tomorrow":
            raise WhenError("Midnight tonight, or the night after? Ask the user.")
        return _at(today + timedelta(days=1), 0, 0, tz)
    if named:  # noon
        return _resolve(day, [(12, 0)], local_now, tz)
    hour, minute = int(hour_s), int(minute_s or 0)
    if minute > 59:
        raise WhenError(NEED_A_TIME)
    if suffix:
        if not 1 <= hour <= 12:
            raise WhenError(NEED_A_TIME)
        return _resolve(day, [(hour % 12 + (12 if suffix[0] == "p" else 0), minute)], local_now, tz)
    if hour >= 24:
        raise WhenError(NEED_A_TIME)
    if hour >= 13 or hour == 0 or hour_s.startswith("0"):
        return _resolve(day, [(hour, minute)], local_now, tz)  # a 24-hour clock
    # 1 to 12 with no am/pm.
    if hour == 12:
        return _resolve(day, [(12, minute)], local_now, tz)
    if day == "tonight":
        return _resolve(day, [(hour + 12, minute)], local_now, tz)
    if day == "tomorrow":
        raise WhenError(f"Is that {hour} am or {hour} pm? Ask the user.")
    # "at 6": the next 6 o'clock to come, morning or evening.
    return _resolve(day, [(hour, minute), (hour + 12, minute)], local_now, tz)


def _iso(raw: str, tz: Any) -> datetime | None:
    if not re.match(r"^\d{4}-\d{2}-\d{2}", raw):
        return None
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise WhenError(NEED_A_TIME) from None
    if value.tzinfo is None:
        value = value.replace(tzinfo=tz)  # the owner's own clock
    return value.astimezone(tz)


def _duration(count: str, unit: str) -> timedelta:
    minutes = _UNITS.get(unit)
    if minutes is None:
        raise WhenError(NEED_A_TIME)
    if count in ("a", "an"):
        n = 1.0
    elif count.startswith("half"):
        n = 0.5
    else:
        n = float(count)
    if n <= 0:
        raise WhenError(NEED_A_TIME)
    return timedelta(minutes=n * minutes)


def _at(day: date, hour: int, minute: int, tz: Any) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=tz)


def _resolve(
    day: str | None, clocks: list[tuple[int, int]], local_now: datetime, tz: Any
) -> datetime:
    """The first of *clocks* still to come on *day*; with no day word, today or else tomorrow."""
    today = local_now.date()
    if day == "tomorrow":
        return _at(today + timedelta(days=1), *clocks[0], tz)
    for hour, minute in clocks:
        when = _at(today, hour, minute, tz)
        if when > local_now:
            return when
    if day in ("today", "tonight"):
        raise WhenError("That time has already passed today. Ask the user for a later time.")
    return _at(today + timedelta(days=1), *clocks[0], tz)


def clock(at: datetime) -> str:
    """``9 am``, ``6:30 pm``."""
    hour = at.hour % 12 or 12
    minutes = f":{at.minute:02d}" if at.minute else ""
    return f"{hour}{minutes} {'am' if at.hour < 12 else 'pm'}"


def say_when(at: datetime, now: datetime, tz: Any) -> str:
    """When *at* is, in plain words of the owner's day: ``tomorrow at 9 am``."""
    local, today = at.astimezone(tz), now.astimezone(tz).date()
    days = (local.date() - today).days
    if days == 0:
        return f"today at {clock(local)}"
    if days == 1:
        return f"tomorrow at {clock(local)}"
    return f"on {local:%a %d %b} at {clock(local)}"


def check_when(at: datetime, now: datetime) -> str | None:
    """Why a reminder cannot be set for *at*, or None."""
    if at <= now:
        return "That time has already passed. Ask the user for a later time."
    if at - now > MAX_AHEAD:
        return "That is more than a year away; reminders go up to a year ahead."
    return None


def clean_text(text: str) -> str:
    return " ".join(str(text or "").split())


async def create(
    session: AsyncSession, tenant_id: str, text: str, at: datetime, *, task_id: str | None
) -> Any:
    """Add one pending time reminder. The caller commits.

    ``context_match`` carries who set it and in which run, as memory_save tags
    a memory: the phone's voice reply lists what was set in that run. Recall's
    context matching reads ``context_match`` only for context/event intentions.
    """
    from life_graph.models.db import Intention

    row = Intention(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        content=text,
        trigger_type="time",
        trigger_condition="set by Jarvis when you asked",
        trigger_time=at,
        context_match={"set_by": "jarvis", **({"task_id": task_id} if task_id else {})},
        priority="normal",
        status="pending",
    )
    session.add(row)
    return row
