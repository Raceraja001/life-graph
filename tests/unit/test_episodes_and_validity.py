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


def test_a_fresh_start_hides_the_days_before_it(monkeypatch):
    from life_graph.config import settings
    from life_graph.services.episodes import _day_bounds

    monkeypatch.setattr(settings, "user_timezone", "Asia/Kolkata")
    monkeypatch.setattr(settings, "memory_start_at", "2026-10-23T12:00:00+05:30")
    floor = datetime(2026, 10, 23, 6, 30, tzinfo=UTC)
    before = _day_bounds(date(2026, 10, 22))
    assert before[0] == before[1]  # nothing to read
    assert _day_bounds(date(2026, 10, 23))[0] == floor  # cut short
    assert _day_bounds(date(2026, 10, 24))[0] == datetime(2026, 10, 23, 18, 30, tzinfo=UTC)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", None),
        ("soon", None),
        ("2026-10-23T12:00:00+05:30", datetime(2026, 10, 23, 6, 30, tzinfo=UTC)),
        ("2026-10-23T06:30:00", datetime(2026, 10, 23, 6, 30, tzinfo=UTC)),
    ],
)
def test_memory_start_is_read(monkeypatch, raw, expected):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "memory_start_at", raw)
    assert settings.memory_start() == expected


class _Rows:
    """``async_session()`` stand-in returning fixed (id, content, properties) rows."""

    def __init__(self, rows) -> None:
        self._rows = rows

    def __call__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    async def execute(self, _stmt):
        rows = self._rows
        return type("R", (), {"all": lambda self: rows})()


def _cc(session: str, project: str) -> dict:
    return {"integration": "claude_code", "claude_code_session_id": session, "project": project}


async def _prompts(monkeypatch, rows):
    from life_graph.services import episodes

    monkeypatch.setattr(episodes, "async_session", _Rows(rows))
    bounds = (datetime(2026, 10, 22, tzinfo=UTC), datetime(2026, 10, 23, tzinfo=UTC))
    monkeypatch.setattr(episodes, "_day_bounds", lambda day: bounds)
    return await episodes._work_prompts("acme", THU)


@pytest.mark.asyncio
async def test_work_prompts_are_grouped_by_session(monkeypatch):
    lines, ids = await _prompts(
        monkeypatch,
        [
            ("1", "fix the recall ranking", _cc("a", "life-graph")),
            ("2", "add school fees report", _cc("b", "uzhavu")),
            ("3", "and a test for it", _cc("a", "life-graph")),
            ("4", "<task-notification>done", _cc("a", "life-graph")),
        ],
    )
    assert lines == [
        "Session 1 (life-graph):",
        "- fix the recall ranking",
        "- and a test for it",
        "Session 2 (uzhavu):",
        "- add school fees report",
    ]
    assert ids == ["1", "3", "2"]


@pytest.mark.asyncio
async def test_prompts_without_a_session_are_their_own_group(monkeypatch):
    lines, _ = await _prompts(
        monkeypatch,
        [("1", "one", _cc("a", "x")), ("2", "two", {"session_id": "older", "integration": "y"})],
    )
    # The second has no Claude Code session: two groups, the second unnamed.
    assert lines == ["Session 1 (x):", "- one", "Session 2:", "- two"]

    lines, _ = await _prompts(monkeypatch, [("1", "one", None), ("2", "two", {})])
    assert lines == ["- one", "- two"]
