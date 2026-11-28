"""Tenant-local wall-clock parts and schedule slot matching (pure).

Days are local date strings (``YYYY-MM-DD``) and times are minutes since local
midnight, so a DST change never runs a job twice or skips a day: once-per-day
is keyed on the date string, and "time passed" compares wall-clock minutes. On
the spring-forward day a slot inside the skipped hour runs at the first minute
after it (late, within the catch-up window); on the fall-back day the repeated
hour cannot start it again (the date is already handled).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from life_graph.services.dev.automation.settings import parse_hhmm

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from zoneinfo import ZoneInfo

#: A slot later than this (the worker was down) is recorded as missed, never run.
CATCH_UP_MINUTES = 120


@dataclass(frozen=True)
class LocalParts:
    date: str  # local calendar day
    weekday: int  # 0-6, Sunday-Saturday
    minutes: int  # since local midnight, 0-1439


def local_parts(at: datetime, zone: ZoneInfo) -> LocalParts:
    local = at.astimezone(zone)
    return LocalParts(
        date=local.date().isoformat(),
        weekday=(local.weekday() + 1) % 7,
        minutes=local.hour * 60 + local.minute,
    )


def previous_local_parts(at: datetime, zone: ZoneInfo) -> LocalParts:
    """The local day before *at* (the instant just before local midnight)."""
    today = local_parts(at, zone)
    return local_parts(at - timedelta(minutes=today.minutes + 1), zone)


def start_of_local_day(at: datetime, zone: ZoneInfo) -> datetime:
    """Local midnight of *at*, as an aware datetime (the daily-limit window)."""
    local = at.astimezone(zone)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


@dataclass(frozen=True)
class SlotDecision:
    kind: str  # not_due | run | missed
    date: str | None = None
    late_minutes: int = 0


NOT_DUE = SlotDecision("not_due")


def decide_slot(
    *,
    enabled: bool,
    days: Iterable[int],
    time: str,
    after: str | None,
    today: LocalParts,
    yesterday: LocalParts,
    handled: Callable[[str], bool],
    catch_up_minutes: int = CATCH_UP_MINUTES,
) -> SlotDecision:
    """Whether a job's slot is due now.

    Due when the job is enabled, today is one of its days, the local time has
    passed and the day is not handled yet. More than *catch_up_minutes* late →
    ``missed`` (recorded, skipped). Yesterday's slot is still run within the
    window (a 23:30 job caught up at 00:20). A chained job (``after``) never
    runs by days/time.
    """
    if not enabled or after:
        return NOT_DUE
    at = parse_hhmm(time)
    if at is None:
        return NOT_DUE
    days = set(days)
    if today.weekday in days and today.minutes >= at and not handled(today.date):
        late = today.minutes - at
        kind = "missed" if late > catch_up_minutes else "run"
        return SlotDecision(kind, today.date, late)
    late_from_yesterday = today.minutes + 1440 - at
    if (
        yesterday.weekday in days
        and late_from_yesterday <= catch_up_minutes
        and not handled(yesterday.date)
    ):
        return SlotDecision("run", yesterday.date, late_from_yesterday)
    return NOT_DUE
