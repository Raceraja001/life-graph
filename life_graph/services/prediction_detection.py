"""Detect explicit confidence claims in captured text.

"I'm 80% sure the migration lands by Friday" is a prediction the user has
already made, with the confidence stated. The capture spine turns each one
into a *suggested* prediction that the user accepts or dismisses on the
Calibration page; nothing enters calibration math without that step.

Only claims with a stated number are detected. "I think the client will sign"
has no confidence to calibrate against, and guessing one would poison the
curve (judgment-engine spec: false outcome data is worse than missing data).

Pure functions — no DB, no LLM.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

_NUM = r"(?P<pct>\d{1,2}(?:\.\d+)?)\s*(?:%|percent\b|per\s+cent\b)"
_QUALIFIER = r"(?:sure|confident|certain|likely|chance|probability)"

# Confidence first: "I'm 80% sure (that) X", "80% chance (that) X".
_LEADING = [
    re.compile(
        r"\b(?:I'?m|I\s+am|we'?re|we\s+are|I'?d\s+say(?:\s+I'?m)?)\s+(?:about\s+|~)?"
        + _NUM
        + r"\s+(?:sure|confident|certain)\s+(?:that\s+)?(?P<stmt>.+)",
        re.IGNORECASE,
    ),
    # "chance of rain" names an event, not a checkable statement, so "of" is
    # not accepted as the start of one.
    re.compile(
        r"(?:^|\s)~?"
        + _NUM
        + r"\s+(?:chance|likely|probability|likelihood)\s+(?:that\s+)?(?!of\b)(?P<stmt>.+)",
        re.IGNORECASE,
    ),
]

# Statement first: "X by Friday, 85% confident" / "X (70% likely)".
_TRAILING = re.compile(
    r"^(?P<stmt>.+?)[\s,;:\-–—(]+(?:I'?m\s+|I'?d\s+say\s+|about\s+|~)?"
    + _NUM
    + r"\s+"
    + _QUALIFIER
    + r"\)?[.!?]*\s*$",
    re.IGNORECASE,
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_MIN_STATEMENT_CHARS = 8
_MAX_STATEMENT_CHARS = 300

_WEEKDAYS = {name.lower(): i for i, name in enumerate(calendar.day_name)}
_MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}


@dataclass(frozen=True)
class DetectedPrediction:
    """A confidence claim found in text."""

    statement: str
    confidence: float  # as stated, in (0, 1); the service normalizes < 0.5
    resolve_by: datetime | None
    quote: str


def detect_predictions(text: str, now: datetime) -> list[DetectedPrediction]:
    """Return every explicit confidence claim in ``text``, in order.

    Args:
        text: Captured text.
        now: Capture time, the anchor for relative horizons ("by Friday").
    """
    found: list[DetectedPrediction] = []
    seen: set[str] = set()
    for sentence in _SENTENCE_SPLIT.split(text or ""):
        sentence = sentence.strip()
        if not sentence:
            continue
        match = _match(sentence)
        if match is None:
            continue
        pct = float(match.group("pct"))
        if not 1 <= pct <= 99:
            continue
        statement = _clean(match.group("stmt"))
        if len(statement) < _MIN_STATEMENT_CHARS or statement.lower() in seen:
            continue
        seen.add(statement.lower())
        found.append(
            DetectedPrediction(
                statement=statement,
                confidence=pct / 100.0,
                resolve_by=parse_horizon(statement, now),
                quote=sentence[:500],
            )
        )
    return found


def _match(sentence: str) -> re.Match[str] | None:
    for pattern in _LEADING:
        m = pattern.search(sentence)
        if m:
            return m
    return _TRAILING.search(sentence)


def _clean(statement: str) -> str:
    s = statement.strip().strip(" ,;:-–—(").rstrip(".!?)").strip()
    s = s[:_MAX_STATEMENT_CHARS]
    return s[:1].upper() + s[1:] if s else s


# ── Horizon parsing ──────────────────────────────────────────────────────

_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_BY_MONTH_DAY = re.compile(
    r"\b(?:by|before|on|until)\s+(?:the\s+)?(?:(?P<d1>\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?"
    r"(?P<m1>[a-z]+)|(?P<m2>[a-z]+)\s+(?P<d2>\d{1,2})(?:st|nd|rd|th)?)\b",
    re.IGNORECASE,
)
_WEEKDAY = re.compile(
    r"\b(?:by|before|on|until|this|next)\s+(?:next\s+)?(?P<day>" + "|".join(_WEEKDAYS) + r")\b",
    re.IGNORECASE,
)
_IN_N = re.compile(
    r"\b(?:in|within)\s+(?P<n>\d{1,3}|a|an|one|two|three|four|six)\s+"
    r"(?P<unit>day|week|month|year)s?\b",
    re.IGNORECASE,
)
_WORD_NUM = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "six": 6}


def parse_horizon(text: str, now: datetime) -> datetime | None:
    """Resolve the first recognizable deadline in ``text`` to a datetime.

    Deadlines resolve to the *end* of the named day or period, since "by
    Friday" means the prediction is still open all of Friday. Returns None
    when no deadline is stated; the user sets one when accepting.
    """
    lower = text.lower()

    if m := _ISO_DATE.search(lower):
        try:
            return _end_of_day(now.replace(year=int(m[1]), month=int(m[2]), day=int(m[3])))
        except ValueError:
            pass

    if m := _BY_MONTH_DAY.search(lower):
        month = _MONTHS.get((m["m1"] or m["m2"] or "").lower())
        day = int(m["d1"] or m["d2"])
        if month:
            try:
                target = now.replace(month=month, day=day)
                if target.date() < now.date():
                    target = target.replace(year=now.year + 1)
                return _end_of_day(target)
            except ValueError:
                pass

    if m := _WEEKDAY.search(lower):
        # The coming occurrence ("by Friday" said on a Friday means a week
        # out); "next Friday" is the one after that.
        ahead = (_WEEKDAYS[m["day"]] - now.weekday()) % 7 or 7
        if "next" in m.group(0):
            ahead += 7
        return _end_of_day(now + timedelta(days=ahead))

    if m := _IN_N.search(lower):
        n = _WORD_NUM.get(m["n"].lower()) or int(m["n"])
        unit = m["unit"].lower()
        days = {"day": 1, "week": 7, "month": 30, "year": 365}[unit] * n
        return _end_of_day(now + timedelta(days=days))

    if "tomorrow" in lower:
        return _end_of_day(now + timedelta(days=1))
    if re.search(r"\b(?:today|tonight)\b", lower):
        return _end_of_day(now)
    if re.search(r"\b(?:this|end of(?: the)?) week\b", lower):
        return _end_of_day(now + timedelta(days=6 - now.weekday()))
    if re.search(r"\bnext week\b", lower):
        return _end_of_day(now + timedelta(days=13 - now.weekday()))
    if re.search(r"\b(?:this|end of(?: the)?) month\b", lower):
        return _end_of_month(now)
    if re.search(r"\bnext month\b", lower):
        return _end_of_month(_end_of_month(now) + timedelta(days=1))
    if re.search(r"\b(?:this|end of(?: the)?) year\b", lower):
        return _end_of_day(now.replace(month=12, day=31))
    if re.search(r"\bnext year\b", lower):
        return _end_of_day(now.replace(year=now.year + 1, month=12, day=31))
    return None


def _end_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=23, minute=59, second=59, microsecond=0)


def _end_of_month(dt: datetime) -> datetime:
    last = calendar.monthrange(dt.year, dt.month)[1]
    return _end_of_day(dt.replace(day=last))
