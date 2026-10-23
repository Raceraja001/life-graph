"""Conversation memory dates and facts that change over time (pure logic)."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from life_graph.core.memory_manager import _end_of_day
from life_graph.extraction.llm import _validity
from life_graph.services.episodes import time_window
from life_graph.services.memory_context import render

THU = date(2026, 10, 22)  # a Thursday


@pytest.mark.parametrize(
    ("question", "window"),
    [
        ("what did we talk about yesterday?", (date(2026, 10, 21), date(2026, 10, 21))),
        ("and the day before yesterday?", (date(2026, 10, 20), date(2026, 10, 20))),
        ("what was I doing 3 days ago", (date(2026, 10, 19), date(2026, 10, 19))),
        ("what did I work on last week?", (date(2026, 10, 12), date(2026, 10, 18))),
        ("summarise this week", (date(2026, 10, 19), THU)),
        ("anything from last month?", (date(2026, 9, 1), date(2026, 9, 30))),
        ("what did I ask on Monday?", (date(2026, 10, 19), date(2026, 10, 19))),
        ("what did we decide last thursday", (date(2026, 10, 15), date(2026, 10, 15))),
        ("what did I say today", (THU, THU)),
        ("when does my car insurance renew?", None),
    ],
)
def test_time_window(question, window):
    assert time_window(question, THU) == window


def test_render_marks_changing_facts_as_of_and_gives_episodes_room():
    when = datetime(2026, 10, 3, tzinfo=UTC)
    long = "x" * 700
    out = render(
        [
            ("The owner lives in Chennai.", when, {"changes_over_time": True}),
            ("Life Graph is closed source.", when, {}),
            (f"Conversations with Jarvis on Tuesday: {long}", when, {"kind": "episode"}),
        ]
    ).splitlines()
    assert out[-3] == "- (as of 2026-10-03) The owner lives in Chennai."
    assert out[-2] == "- (2026-10-03) Life Graph is closed source."
    assert out[-1].startswith("- Conversations with Jarvis") and not out[-1].endswith("…")


@pytest.mark.parametrize(
    ("item", "expected"),
    [
        ({"changes_over_time": True, "valid_until": "2026-10-24"}, (True, "2026-10-24")),
        ({"valid_until": "next Friday"}, (False, None)),  # not a date: dropped, not guessed
        ({}, (False, None)),
        ({"valid_until": None, "changes_over_time": False}, (False, None)),
    ],
)
def test_validity_is_checked(item, expected):
    out = _validity(item)
    assert (out["changes_over_time"], out["valid_until"]) == expected


def test_a_fact_true_until_friday_is_true_all_friday(monkeypatch):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "user_timezone", "Asia/Kolkata")
    end = _end_of_day("2026-10-24")
    assert end.date() == date(2026, 10, 24) and end.hour == 23 and end.tzinfo is not None
    assert _end_of_day(None) is None and _end_of_day("soon") is None


def test_filler_sentences_are_dropped():
    from life_graph.services.episodes import clean

    text = (
        "They proposed building an Android app. They did not mention specific project names. "
        "No projects or decisions were made. They showed consistent intent to move forward. "
        "They decided to sell school management first."
    )
    assert clean(text) == (
        "They proposed building an Android app. They decided to sell school management first."
    )
