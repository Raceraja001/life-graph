"""Intention extraction — detect prospective memory language from text.

Tier 1 regex-based extractor that identifies TODO/FIXME markers,
'remind me' phrases, and conditional triggers like 'when I open X'.
Parses relative dates for time-based triggers.
"""

from __future__ import annotations

import calendar
import re
from datetime import datetime, timedelta, timezone
from typing import Any


def _utcnow() -> datetime:
    """Return the current UTC timestamp (timezone-aware)."""
    return datetime.now(timezone.utc)


def _end_of_day(dt: datetime) -> datetime:
    """Return 23:59:59 on the same day as *dt*."""
    return dt.replace(hour=23, minute=59, second=59, microsecond=0)


def _next_weekday(weekday: int) -> datetime:
    """Return the next occurrence of *weekday* (0=Monday … 6=Sunday)."""
    now = _utcnow()
    days_ahead = weekday - now.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return _end_of_day(now + timedelta(days=days_ahead))


def _end_of_month() -> datetime:
    """Return 23:59:59 on the last day of the current month."""
    now = _utcnow()
    last_day = calendar.monthrange(now.year, now.month)[1]
    return now.replace(day=last_day, hour=23, minute=59, second=59, microsecond=0)


# ---------------------------------------------------------------------------
# Date-keyword mapping
# ---------------------------------------------------------------------------
_WEEKDAY_MAP: dict[str, int] = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


def _parse_relative_date(text: str) -> datetime | None:
    """Parse simple relative date expressions into a UTC datetime.

    Supports: 'today', 'tomorrow', 'next week', 'end of month',
    'by <weekday>', and 'by <weekday>' variants.

    Returns None if no date expression is recognised.
    """
    lowered = text.lower().strip()

    if "today" in lowered:
        return _end_of_day(_utcnow())

    if "tomorrow" in lowered:
        return _end_of_day(_utcnow() + timedelta(days=1))

    if "next week" in lowered:
        return _end_of_day(_utcnow() + timedelta(days=7))

    if "end of month" in lowered or "end of the month" in lowered:
        return _end_of_month()

    # 'by Friday', 'by next Tuesday', etc.
    for day_name, weekday_num in _WEEKDAY_MAP.items():
        if day_name in lowered:
            return _next_weekday(weekday_num)

    return None


# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

# ── Intention-content patterns ────────────────────────────────────────────
_INTENTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # 'I should X', 'I need to X', 'I will X later'
    (re.compile(
        r"\bi\s+should\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE
    ), "event"),
    (re.compile(
        r"\bi\s+need\s+to\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE
    ), "event"),
    (re.compile(
        r"\bi\s+will\s+(.+?)\s+later\b", re.IGNORECASE
    ), "event"),
    (re.compile(
        r"\blet\s+me\s+(.+?)\s+later\b", re.IGNORECASE
    ), "event"),

    # 'remind me to X', 'remind me about X'
    (re.compile(
        r"\bremind\s+me\s+(?:to|about)\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE
    ), "event"),

    # 'TODO: X', 'FIXME: X', 'HACK: X'
    (re.compile(r"\bTODO\s*:\s*(.+?)(?:\n|$)"), "event"),
    (re.compile(r"\bFIXME\s*:\s*(.+?)(?:\n|$)"), "event"),
    (re.compile(r"\bHACK\s*:\s*(.+?)(?:\n|$)"), "event"),
]

# ── Time trigger patterns ─────────────────────────────────────────────────
_TIME_PATTERN = re.compile(
    r"\bby\s+(today|tomorrow|next\s+week|end\s+of\s+(?:the\s+)?month"
    r"|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.IGNORECASE,
)

# ── Event / context trigger patterns ──────────────────────────────────────
_EVENT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(
        r"\bwhen\s+i\s+open\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE
    ), "files_pattern"),
    (re.compile(
        r"\bwhen\s+i\s+work\s+on\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE
    ), "project"),
    (re.compile(
        r"\bnext\s+time\s+i\s+(.+?)(?:[.,;!?\n]|$)", re.IGNORECASE
    ), "topics"),
]

# ── Priority detection ────────────────────────────────────────────────────
_URGENT_PATTERN = re.compile(
    r"\b(?:urgent|asap|critical|immediately|right\s+away|high\s+priority)\b",
    re.IGNORECASE,
)


class IntentionExtractor:
    """Extract intention-like language from text using regex patterns.

    Returns structured dicts ready for ``IntentionService.create()``.
    Zero LLM calls — pure regex with simple date arithmetic.
    """

    def extract(self, text: str) -> list[dict[str, Any]]:
        """Detect intention language and extract structured data.

        Args:
            text: Raw input text to scan for intentions.

        Returns:
            List of intention dicts, each containing content,
            trigger_type, trigger_condition, trigger_time,
            context_match, and priority.
        """
        results: list[dict[str, Any]] = []
        seen_spans: set[tuple[int, int]] = set()

        for pattern, default_trigger in _INTENTION_PATTERNS:
            for match in pattern.finditer(text):
                span = match.span()
                if self._overlaps(span, seen_spans):
                    continue
                seen_spans.add(span)

                content = match.group(1).strip().rstrip(".,;:!?")
                full_text = match.group(0)

                trigger_type = default_trigger
                trigger_condition: str | None = None
                trigger_time: datetime | None = None
                context_match: dict[str, Any] = {}

                # ── Check for time triggers ───────────────────────
                time_match = _TIME_PATTERN.search(full_text)
                if time_match is None:
                    # Also check content beyond the match in the same line
                    line_end = text.find("\n", span[1])
                    remaining = text[span[1]: line_end if line_end != -1 else len(text)]
                    time_match = _TIME_PATTERN.search(remaining)

                if time_match:
                    parsed = _parse_relative_date(time_match.group(1))
                    if parsed is not None:
                        trigger_type = "time"
                        trigger_time = parsed
                        trigger_condition = time_match.group(0).strip()

                # ── Check for event/context triggers ──────────────
                for evt_pattern, ctx_key in _EVENT_PATTERNS:
                    evt_match = evt_pattern.search(full_text)
                    if evt_match:
                        trigger_type = "context"
                        trigger_condition = evt_match.group(0).strip()
                        ctx_value = evt_match.group(1).strip().rstrip(".,;:!?")
                        context_match[ctx_key] = ctx_value
                        break

                # ── Priority detection ────────────────────────────
                priority = "high" if _URGENT_PATTERN.search(full_text) else "normal"

                results.append({
                    "content": content,
                    "trigger_type": trigger_type,
                    "trigger_condition": trigger_condition,
                    "trigger_time": trigger_time,
                    "context_match": context_match if context_match else None,
                    "priority": priority,
                })

        return results

    @staticmethod
    def _overlaps(span: tuple[int, int], seen: set[tuple[int, int]]) -> bool:
        """Return True if *span* overlaps any previously seen span."""
        return any(
            s[0] <= span[0] < s[1] or s[0] < span[1] <= s[1]
            for s in seen
        )
