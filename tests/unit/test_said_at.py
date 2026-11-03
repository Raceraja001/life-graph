"""A capture delivered late is extracted as of the day it was said (core/said_at.py)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from life_graph.core.said_at import late, said_at
from life_graph.extraction.llm import _user_message


def test_only_an_old_capture_is_late():
    now = datetime.now(UTC)
    assert late(now - timedelta(minutes=2)) is None
    assert late(now - timedelta(days=20)) == now - timedelta(days=20)
    naive = (now - timedelta(days=1)).replace(tzinfo=None)
    assert late(naive).tzinfo == UTC
    assert late(None) is None


def test_the_extractor_is_told_the_day_it_was_said():
    token = said_at.set(datetime(2026, 10, 13, 6, 0, tzinfo=UTC))
    try:
        message = _user_message("I start at Thenral next month", schema_in_prompt=False)
    finally:
        said_at.reset(token)

    assert "Today is Tuesday 2026-10-13." in message


def test_on_time_means_today():
    from life_graph.connectors.tools import user_tz

    assert said_at.get() is None
    today = datetime.now(user_tz())
    assert f"Today is {today:%A %Y-%m-%d}." in _user_message("hello", schema_in_prompt=False)
