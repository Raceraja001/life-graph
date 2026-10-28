"""Unit tests for ``say_said`` in ``life_graph.services.nudges``.

``say_said`` turns a promise's ``said_at`` timestamp into a human-friendly
relative day label: "today", "yesterday", "on <weekday>", or "on <DD Mon>".
These tests pin its behaviour without touching the database.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from life_graph.services.nudges import say_said

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
# 2026-10-28 is a Wednesday.
KOLKATA = timezone(timedelta(hours=5, minutes=30))


@pytest.mark.parametrize("said_at", [None, ""])
def test_none_and_empty_string_give_empty(said_at):
    assert say_said(said_at, NOW, UTC) == ""


def test_unparseable_string_gives_empty():
    assert say_said("not a date", NOW, UTC) == ""


def test_same_day_gives_today():
    said_at = (NOW - timedelta(days=0)).isoformat()
    assert say_said(said_at, NOW, UTC) == "today"


def test_one_day_earlier_gives_yesterday():
    said_at = (NOW - timedelta(days=1)).isoformat()
    assert say_said(said_at, NOW, UTC) == "yesterday"


@pytest.mark.parametrize(
    "days, weekday",
    [
        (2, "Monday"),
        (3, "Sunday"),
        (4, "Saturday"),
        (5, "Friday"),
        (6, "Thursday"),
    ],
)
def test_two_to_six_days_earlier_gives_weekday(days, weekday):
    said_at = (NOW - timedelta(days=days)).isoformat()
    assert say_said(said_at, NOW, UTC) == f"on {weekday}"


@pytest.mark.parametrize("days", [7, 10, 30])
def test_seven_or_more_days_earlier_gives_date(days):
    said_at = (NOW - timedelta(days=days)).isoformat()
    expected = (NOW - timedelta(days=days)).strftime("on %d %b")
    assert say_said(said_at, NOW, UTC) == expected


def test_day_judged_in_given_timezone():
    """A time just after midnight in Asia/Kolkata is still the previous day in UTC.

    2026-10-27 19:30 UTC == 2026-10-28 01:00 Asia/Kolkata (just after midnight).
    In Kolkata that moment is "today" (the same calendar day as NOW), but in UTC
    it is the previous day, so the timezone argument must win.
    """
    # Just after midnight in Kolkata, still the previous day in UTC.
    moment = datetime(2026, 10, 27, 19, 30, tzinfo=UTC)
    said_at = moment.isoformat()
    # In Kolkata this is the same calendar day as NOW -> "today".
    assert say_said(said_at, NOW, KOLKATA) == "today"
    # In UTC this is the previous day -> "yesterday".
    assert say_said(said_at, NOW, UTC) == "yesterday"
