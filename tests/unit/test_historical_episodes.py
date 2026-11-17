"""A question about an earlier present is anchored to *that* present.

``retrieve(question, as_of=...)`` reconstructs what was known and true at a
point in the past. "What did we talk about yesterday?" asked with
``as_of=2025-06-15`` is a question about 14 June 2025 — not about yesterday
relative to whenever the test happens to run.

It used to be the latter: ``services/memory/retrieval.py`` anchored the
episode window to ``datetime.now()`` whatever ``as_of`` said, so a historical
query was answered with today's day summaries. That is the worst shape of
wrong available here, because the reply came back sourced: real episodes,
really retrieved, for the wrong days.

These tests pin the anchor, the windows either side of a week and a month
boundary, the timezone the calendar day is computed in, and the two kinds of
time stayed apart — when something happened (valid time) versus when the
system learned it (transaction time).

No database and no model: the store, the embedding and the entity index are
fakes, and ``episodes_between`` is replaced by a probe that records the window
it was asked for.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from life_graph.services.episodes import time_window
from life_graph.services.memory.retrieval import retrieve

#: A Sunday, so "last week" and "this week" are different weeks and a weekday
#: reference ("on Monday") has a defined answer.
AS_OF = datetime(2025, 6, 15, 12, 0, tzinfo=UTC)
SUNDAY = date(2025, 6, 15)
IST = ZoneInfo("Asia/Kolkata")
TENANT = "t1"


# ── The harness ──────────────────────────────────────────────────────────


def _episode(day: date, text: str = "we talked", **props) -> SimpleNamespace:
    """An episode memory as ``services/episodes.py`` writes one."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        content=text,
        status="active",
        created_at=datetime.combine(day, datetime.min.time(), tzinfo=UTC),
        properties={"kind": "episode", "date": day.isoformat(), **props},
    )


class _Probe:
    """Stands in for ``episodes.episodes_between``, recording what it was asked."""

    def __init__(self, rows: list[SimpleNamespace] | None = None) -> None:
        self.windows: list[tuple[date, date]] = []
        self.rows: list[SimpleNamespace] = rows or []

    async def __call__(self, tenant_id, start, end, limit=8):
        self.windows.append((start, end))
        return list(self.rows)

    @property
    def window(self) -> tuple[date, date] | None:
        return self.windows[-1] if self.windows else None


async def _unreachable_judge(question, memories):
    raise AssertionError("the relevance judge should not be reached here")


@pytest.fixture
def probe(monkeypatch):
    """A wired ``retrieve`` with no database, no model and no entity index."""
    import life_graph.api.dependencies as deps
    from life_graph.core.tenant import tenant_scope
    from life_graph.services import entities, episodes
    from life_graph.services.memory import retrieval as memory_retrieval

    class _Manager:
        async def generate_embedding(self, text):
            return [0.1]

    class _Store:
        async def hybrid_search(self, **kw):
            return []

    async def _no_entities(tenant_id, text_):
        return []

    recorder = _Probe()
    monkeypatch.setattr(deps, "get_memory_manager", lambda: _Manager())
    monkeypatch.setattr(deps, "get_store", lambda: _Store())
    monkeypatch.setattr(entities, "known_in_text", _no_entities)
    monkeypatch.setattr(episodes, "episodes_between", recorder)
    # Search returns nothing, so the judge is never reached — but a stray
    # model call would make this suite depend on a network.
    monkeypatch.setattr(memory_retrieval, "_judged", _unreachable_judge)
    with tenant_scope(TENANT):
        yield recorder


# ── The anchor ───────────────────────────────────────────────────────────


async def test_yesterday_of_an_as_of_query_is_the_day_before_as_of(probe):
    """The bug, pinned: the window is 14 June 2025, whatever today is."""
    await retrieve("What did we talk about yesterday?", as_of=AS_OF)

    assert probe.window == (date(2025, 6, 14), date(2025, 6, 14))


async def test_last_week_of_an_as_of_query_is_that_weeks_predecessor(probe):
    """15 June 2025 is a Sunday, so last week is Mon 2 — Sun 8 June."""
    await retrieve("What happened last week?", as_of=AS_OF)

    assert probe.window == (date(2025, 6, 2), date(2025, 6, 8))


async def test_an_as_of_window_is_never_the_wall_clocks_window(probe):
    """The regression itself: the historical window cannot be today's.

    Written as its own test because the two above would both pass if the
    clock happened to sit on 15 June 2025.
    """
    from life_graph.services import episodes

    today = datetime.now(episodes._tz()).date()

    await retrieve("What did we talk about yesterday?", as_of=AS_OF)

    assert probe.window == (date(2025, 6, 14), date(2025, 6, 14))
    assert probe.window != (today - timedelta(days=1), today - timedelta(days=1))


async def test_current_retrieval_still_anchors_to_today(probe):
    """as_of absent: unchanged behaviour, anchored to the tenant's today."""
    from life_graph.services import episodes

    today = datetime.now(episodes._tz()).date()

    await retrieve("What did we talk about yesterday?")

    assert probe.window == (today - timedelta(days=1), today - timedelta(days=1))


async def test_a_question_naming_no_time_asks_for_no_window(probe):
    """No episode fetch at all, so the anchor cannot matter either way."""
    await retrieve("When does my car insurance renew?", as_of=AS_OF)

    assert probe.windows == []


async def test_the_historical_episodes_are_what_comes_back(probe):
    """Not just the right window: the rows from it are the answer.

    Search returns nothing here, so anything in the result arrived through
    the dated-episode path and is therefore from the window above.
    """
    yesterday = _episode(date(2025, 6, 14), "we talked about the move")
    probe.rows = [yesterday]

    out = await retrieve("What did we talk about yesterday?", as_of=AS_OF)

    assert out == [yesterday]


# ── The timezone the calendar day is computed in ─────────────────────────


async def test_the_anchor_is_the_tenants_calendar_day_not_utcs(probe, monkeypatch):
    """A day is a local thing, and the day summaries are written per local day.

    20:00 UTC on 15 June is already 01:30 on 16 June in Asia/Kolkata, so
    "yesterday" is the 15th there and the 14th in UTC. The episodes were
    written against local days, so the local reading is the right one.
    """
    from life_graph.services import episodes

    monkeypatch.setattr(episodes, "_tz", lambda: IST)

    await retrieve(
        "What did we talk about yesterday?", as_of=datetime(2025, 6, 15, 20, 0, tzinfo=UTC)
    )

    assert probe.window == (SUNDAY, SUNDAY)


async def test_a_naive_as_of_is_read_as_utc_rather_than_raising(probe):
    """Callers pass timestamps out of JSON; a naive one must not blow up here."""
    await retrieve("What did we talk about yesterday?", as_of=datetime(2025, 6, 15, 12, 0))

    assert probe.window == (date(2025, 6, 14), date(2025, 6, 14))


# ── Valid time versus transaction time ───────────────────────────────────


async def test_a_late_arriving_episode_is_invisible_to_an_earlier_cutoff(probe):
    """What we knew *then*, not what we know now about then.

    The episode is about 14 June and was recorded on 20 June. A query with a
    transaction-time cutoff of 16 June must not see it: on 16 June the system
    did not hold it. ``recorded_as_of`` is the only thing that hides it —
    ``as_of`` alone asks the other question.
    """
    late = _episode(
        date(2025, 6, 14), "the bit we only found out later", recorded_at="2025-06-20T00:00:00Z"
    )
    probe.rows = [late]

    hidden = await retrieve(
        "What did we talk about yesterday?",
        as_of=AS_OF,
        recorded_as_of=datetime(2025, 6, 16, tzinfo=UTC),
    )
    assert hidden == []
    # The same window either way: the cutoff filters the rows, it does not
    # move the days being asked about.
    assert probe.window == (date(2025, 6, 14), date(2025, 6, 14))

    # And with no cutoff, "what do we now believe about 14 June" includes it.
    shown = await retrieve("What did we talk about yesterday?", as_of=AS_OF)
    assert shown == [late]


async def test_a_superseded_episode_is_history_after_the_correction_landed(probe):
    """Transaction time has two edges, and this is the other one.

    The row was the current belief from 15 June and was replaced on 18 June.
    Asked as of 16 June it was still what we believed; asked as of 19 June it
    is history, not current belief.
    """
    corrected = _episode(
        date(2025, 6, 14),
        "the first version",
        recorded_at="2025-06-15T00:00:00Z",
        superseded_at="2025-06-18T00:00:00Z",
    )
    probe.rows = [corrected]

    believed = await retrieve(
        "What did we talk about yesterday?",
        as_of=AS_OF,
        recorded_as_of=datetime(2025, 6, 16, tzinfo=UTC),
    )
    assert believed == [corrected]

    after = await retrieve(
        "What did we talk about yesterday?",
        as_of=AS_OF,
        recorded_as_of=datetime(2025, 6, 19, tzinfo=UTC),
    )
    assert after == []


# ── The windows themselves, around the boundaries ────────────────────────
#
# ``time_window`` is pure, so the boundary cases are pinned directly rather
# than through six more wirings of ``retrieve``.


@pytest.mark.parametrize(
    ("question", "window"),
    [
        ("what did we talk about yesterday?", (date(2025, 6, 14), date(2025, 6, 14))),
        ("and the day before yesterday?", (date(2025, 6, 13), date(2025, 6, 13))),
        ("what was I doing 3 days ago", (date(2025, 6, 12), date(2025, 6, 12))),
        ("what happened last week?", (date(2025, 6, 2), date(2025, 6, 8))),
        # A Sunday: weekday() is 6, so this week began on the 9th.
        ("summarise this week", (date(2025, 6, 9), SUNDAY)),
        ("anything from last month?", (date(2025, 5, 1), date(2025, 5, 31))),
        ("what did I ask on Monday?", (date(2025, 6, 9), date(2025, 6, 9))),
        # Today is Sunday, so "on Sunday" means the previous one, not today.
        ("what did I decide on Sunday", (date(2025, 6, 8), date(2025, 6, 8))),
        ("what did I say today", (SUNDAY, SUNDAY)),
        ("when does my car insurance renew?", None),
    ],
)
def test_the_windows_around_a_june_2025_sunday(question, window):
    assert time_window(question, SUNDAY) == window


@pytest.mark.parametrize(
    ("anchor", "window"),
    [
        # Crossing into the previous month…
        (date(2025, 6, 1), (date(2025, 5, 31), date(2025, 5, 31))),
        # …the previous year…
        (date(2025, 1, 1), (date(2024, 12, 31), date(2024, 12, 31))),
        # …and out of a leap day.
        (date(2024, 3, 1), (date(2024, 2, 29), date(2024, 2, 29))),
    ],
)
def test_yesterday_crosses_month_year_and_leap_boundaries(anchor, window):
    assert time_window("what did we talk about yesterday?", anchor) == window


@pytest.mark.parametrize(
    ("anchor", "window"),
    [
        # January back into December, including the year.
        (date(2025, 1, 15), (date(2024, 12, 1), date(2024, 12, 31))),
        # A 31st back into a 30-day month: the last day, not the 31st.
        (date(2025, 5, 31), (date(2025, 4, 1), date(2025, 4, 30))),
        # Into February of a leap year.
        (date(2024, 3, 15), (date(2024, 2, 1), date(2024, 2, 29))),
    ],
)
def test_last_month_lands_on_real_days(anchor, window):
    assert time_window("anything from last month?", anchor) == window


@pytest.mark.parametrize(
    ("anchor", "window"),
    [
        # A Monday: this week is one day long, last week the seven before it.
        (date(2025, 6, 9), (date(2025, 6, 2), date(2025, 6, 8))),
        # Crossing the year: the week of 30 Dec 2024 — 5 Jan 2025.
        (date(2025, 1, 6), (date(2024, 12, 30), date(2025, 1, 5))),
    ],
)
def test_last_week_is_always_seven_days_ending_on_a_sunday(anchor, window):
    start, end = window
    assert time_window("what happened last week?", anchor) == window
    assert (end - start).days == 6
    assert start.weekday() == 0 and end.weekday() == 6


async def test_last_year_and_this_month_anchor_to_as_of(probe):
    """15 June 2025 -> last year is 2024-01-01..2024-12-31, this month is 2025-06-01..2025-06-15."""
    await retrieve("What major milestones happened last year?", as_of=AS_OF)
    assert probe.window == (date(2024, 1, 1), date(2024, 12, 31))

    await retrieve("What have we worked on this month?", as_of=AS_OF)
    assert probe.window == (date(2025, 6, 1), date(2025, 6, 15))

    await retrieve("What have we worked on this year?", as_of=AS_OF)
    assert probe.window == (date(2025, 1, 1), date(2025, 6, 15))
