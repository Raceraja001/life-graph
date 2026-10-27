"""The owner's recurrence phrases as UTC cron (services/recurrence.py, web-chat-wave1 T1.1)."""

import pytest

from life_graph.kernel.scheduler import CronExpression
from life_graph.services.recurrence import parse_recurrence


@pytest.mark.parametrize(
    ("text", "tz", "cron"),
    [
        ("every day at 7", "UTC", "0 7 * * *"),
        ("every morning", "UTC", "0 7 * * *"),
        ("each evening", "UTC", "0 19 * * *"),
        ("every Monday at 9", "UTC", "0 9 * * 1"),
        ("every weekday at 8:30", "UTC", "30 8 * * 1-5"),
        ("every Sunday evening", "UTC", "0 19 * * 0"),
        ("every hour", "UTC", "0 * * * *"),
        ("every 2 hours", "UTC", "0 */2 * * *"),
        ("on the 1st of every month at 10", "UTC", "0 10 1 * *"),
        ("every day at 9pm", "UTC", "0 21 * * *"),
        ("every day at 21:00", "UTC", "0 21 * * *"),
        ("every day at 9:15 am", "UTC", "15 9 * * *"),
        ("every day at 12 am", "UTC", "0 0 * * *"),
        # India is UTC+05:30: the minute moves, and early hours fall on the day before.
        ("every Monday at 9", "Asia/Kolkata", "30 3 * * 1"),
        ("every Monday at 2", "Asia/Kolkata", "30 20 * * 0"),
        ("every weekday at 2", "Asia/Kolkata", "30 20 * * 0-4"),
        ("every Saturday and Sunday at 8", "Asia/Kolkata", "30 2 * * 0,6"),
    ],
)
def test_phrases_become_utc_cron(text, tz, cron):
    assert parse_recurrence(text, tz) == cron
    CronExpression(cron)  # the scheduler accepts it


@pytest.mark.parametrize(
    "text",
    [
        "sometime soon",
        "",
        "every Monday",  # no time and no part of the day: ask
        "every day at 25",
        "on the 31st of every month at 10",  # missing from some months
        "every 30 hours",
    ],
)
def test_unclear_phrases_are_none(text):
    assert parse_recurrence(text, "UTC") is None


def test_a_monthly_day_that_would_move_is_asked_about():
    # 02:00 on the 1st in India is the last day of the previous month in UTC.
    assert parse_recurrence("on the 1st of every month at 2", "Asia/Kolkata") is None
