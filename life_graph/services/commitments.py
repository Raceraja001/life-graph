"""What the owner said they would do, and by when (web-chat-wave1 F2, nudges).

``find_commitment`` reads one of the owner's own messages — "I'll call the
insurer this week", "I need to pay the school fees by Friday" — and returns
what they said and the window to nudge them in, or None. It is plain code, not
a model: it runs on every message, sees personal text, and must be predictable.
A reminder they asked for ("remind me…") is reminder_set's, a repeat ("every
Monday…") ask_schedule's, and a question is not a promise.

``store`` keeps one as a ``nudge`` Intention (services/nudges.py sends it).
Only the owner's words ever reach here: capture_processors calls it for the
Jarvis app's own surface at the SELF trust tier, never for shared text or mail.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

NUDGE_HOUR = 10  # a day's nudge comes mid-morning…
EVENING_HOUR = 17  # …and "today" in the late afternoon
MAX_WHAT_CHARS = 200

_DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_COMMIT = re.compile(
    r"\b(i'?ll|i will|i'?m going to|i am going to|i need to|i have to|i must|i should"
    r"|i'?ve got to|i gotta|i promised to|i'?m supposed to)\b",
    re.IGNORECASE,
)
_NOT_A_PROMISE = re.compile(r"\bremind me\b|\bevery\b|\bdon'?t remind\b", re.IGNORECASE)
_WHEN = re.compile(
    r"\b(?P<rel>today|tonight|tomorrow"
    r"|this (?:week|weekend|month)|next week"
    r"|(?:by )?(?:the )?end of (?:the |this )?(?:week|month))\b"
    r"|\b(?P<prep>by|on|before)?\s*(?:this |next )?(?P<day>" + "|".join(_DAYS) + r")\b",
    re.IGNORECASE,
)


def _sentence(text: str, at: int) -> str:
    """The sentence of *text* around position *at*."""
    start = max(text.rfind(c, 0, at) for c in ".!?\n") + 1
    ends = [i for i in (text.find(c, at) for c in ".!?\n") if i != -1]
    end = min(ends) if ends else len(text)
    return " ".join(text[start:end].split())[:MAX_WHAT_CHARS]


def _at(day, hour: int, tz: ZoneInfo) -> datetime:
    return datetime.combine(day, time(hour, 0), tzinfo=tz)


def _end(day, tz: ZoneInfo) -> datetime:
    return datetime.combine(day, time(23, 59), tzinfo=tz)


def _window(m: re.Match, now: datetime, tz: ZoneInfo) -> tuple[datetime, datetime] | None:
    local = now.astimezone(tz)
    today = local.date()
    soon = local + timedelta(hours=1)
    rel = (m.group("rel") or "").lower()
    if rel in ("today", "tonight"):
        due_by = _end(today, tz)
        start = max(soon, _at(today, EVENING_HOUR, tz))
        return (min(start, due_by), due_by)
    if rel == "tomorrow":
        day = today + timedelta(days=1)
        return (_at(day, NUDGE_HOUR, tz), _end(day, tz))
    if rel == "this week" or ("end of" in rel and rel.endswith("week")):
        sunday = today + timedelta(days=6 - today.weekday())
        return (max(soon, _at(sunday - timedelta(days=3), NUDGE_HOUR, tz)), _end(sunday, tz))
    if rel == "this weekend":
        saturday = today + timedelta(days=(5 - today.weekday()) % 7)
        sunday = saturday + timedelta(days=1) if today.weekday() != 6 else today
        return (max(soon, _at(saturday, NUDGE_HOUR, tz)), _end(sunday, tz))
    if rel == "next week":
        monday = today + timedelta(days=7 - today.weekday())
        return (
            _at(monday + timedelta(days=2), NUDGE_HOUR, tz),
            _end(monday + timedelta(days=6), tz),
        )
    if rel.endswith("month"):  # this month / end of (the) month
        first_next = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
        last = first_next - timedelta(days=1)
        return (max(soon, _at(last - timedelta(days=5), NUDGE_HOUR, tz)), _end(last, tz))
    day_name = (m.group("day") or "").lower()
    if day_name:
        ahead = (_DAYS.index(day_name) - today.weekday()) % 7
        if "next" in m.group(0).lower() and ahead == 0:
            ahead = 7
        target = today + timedelta(days=ahead)
        if (m.group("prep") or "").lower() in ("by", "before") and ahead > 0:
            start = max(soon, _at(target - timedelta(days=1), NUDGE_HOUR, tz))
        else:
            start = (
                max(soon, _at(target, NUDGE_HOUR, tz))
                if ahead
                else max(soon, _at(target, EVENING_HOUR, tz))
            )
        due_by = _end(target, tz)
        return (min(start, due_by), due_by)
    return None


def find_commitment(text: str, now: datetime, tz: str) -> dict[str, Any] | None:
    """``{"what", "when", "due_from", "due_by"}`` (UTC) for a promise with a time, or None."""
    if not text or text.rstrip().endswith("?") or _NOT_A_PROMISE.search(text):
        return None
    commit = _COMMIT.search(text)
    if commit is None:
        return None
    what = _sentence(text, commit.start())
    when = _WHEN.search(what)
    if when is None:
        return None
    try:
        zone = ZoneInfo(tz)
    except Exception:  # noqa: BLE001
        zone = ZoneInfo("UTC")
    window = _window(when, now, zone)
    if window is None:
        return None
    due_from, due_by = window
    if due_by <= now:
        return None
    return {
        "what": what,
        "when": " ".join(when.group(0).split()),
        "due_from": due_from.astimezone(UTC),
        "due_by": due_by.astimezone(UTC),
    }


async def store(
    session, tenant_id: str, found: dict[str, Any], *, source: dict[str, Any]
) -> Any | None:
    """Keep *found* as a nudge Intention; None when the same promise is already open."""
    from sqlalchemy import func, select

    from life_graph.models.db import Intention

    week_ago = datetime.now(UTC) - timedelta(days=7)
    same = await session.scalar(
        select(func.count())
        .select_from(Intention)
        .where(
            Intention.tenant_id == tenant_id,
            Intention.trigger_type == "nudge",
            Intention.status.in_(("pending", "nudged")),
            Intention.created_at >= week_ago,
            func.lower(Intention.content) == found["what"].lower(),
        )
    )
    if same:
        return None
    row = Intention(
        tenant_id=tenant_id,
        content=found["what"],
        trigger_type="nudge",
        trigger_time=found["due_from"],
        expires_at=found["due_by"] + timedelta(days=2),
        status="pending",
        context_match={
            "due_by": found["due_by"].isoformat(),
            "when": found["when"],
            "said_at": datetime.now(UTC).isoformat(),
            **source,
        },
    )
    session.add(row)
    return row
