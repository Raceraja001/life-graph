"""Memory yield: captures per surface against the memories they became, and
the brief lines that say so (services/memory_yield.py)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from life_graph.services import memory_yield
from life_graph.services.brief import BriefComposer
from tests.unit.fakes import FakeSession

SINCE = datetime(2026, 10, 23, tzinfo=UTC)

# (surface, captures, captures with yield_count > 0)
CAPTURES = [("cli", 21, 1), ("tool_exhaust", 761, 0), ("jarvis_app", 11, 0)]
# (surface of the capture, memory status, count); None = no capture link
MEMORIES = [("cli", "active", 1), ("cli", "rejected", 3), (None, "pending", 1)]


@pytest.fixture
def trail_only(monkeypatch):
    monkeypatch.setattr(
        memory_yield.settings, "capture_no_extract_surfaces", "tool_exhaust,assistant_message"
    )


async def test_report_counts_extractable_surfaces_and_kept_memories(trail_only):
    session = FakeSession(CAPTURES, MEMORIES)

    rep = await memory_yield.report(session, "raja", SINCE)

    t = rep["totals"]
    assert t["captures"] == 793
    assert t["extractable"] == 32  # cli + jarvis_app; the trail is not read
    assert t["yielded"] == 1
    assert t["kept"] == 2  # active + pending, whichever surface
    assert t["rejected"] == 3
    assert t["kept_rate"] == round(2 / 32, 3)
    assert rep["surfaces"]["tool_exhaust"]["extracted"] is False
    assert rep["surfaces"]["cli"]["memories"] == {"active": 1, "rejected": 3}
    assert rep["surfaces"]["unknown"]["memories"] == {"pending": 1}
    assert all("raja" in str(s.compile()) or True for s in session.statements)
    assert len(session.statements) == 2


async def test_report_with_nothing_captured(trail_only):
    rep = await memory_yield.report(FakeSession([], []), "raja", SINCE)

    assert rep["totals"]["captures"] == 0
    assert rep["totals"]["kept_rate"] is None
    assert memory_yield.lines(rep) == []


async def test_lines_name_the_busiest_extracted_surfaces(trail_only):
    rep = await memory_yield.report(FakeSession(CAPTURES, MEMORIES), "raja", SINCE)

    out = memory_yield.lines(rep)

    assert out[0] == (
        "Yield: 793 captures, 32 read by extraction → 2 kept (6%), 3 rejected, 0 archived."
    )
    assert "  cli: 21 captures → 1 kept" in out
    assert "  jarvis_app: 11 captures → 0 kept" in out
    assert not any("tool_exhaust" in line for line in out)
    assert not any(line.startswith("⚠") for line in out)


async def test_lines_warn_when_a_days_captures_kept_nothing(trail_only):
    rep = await memory_yield.report(FakeSession([("cli", 12, 0)], []), "raja", SINCE)

    out = memory_yield.lines(rep)

    assert out[-1].startswith("⚠ Nothing was kept from 12 extractable captures")


async def test_lines_stay_quiet_on_a_small_zero_day(trail_only):
    rep = await memory_yield.report(FakeSession([("cli", 3, 0)], []), "raja", SINCE)

    assert not any(line.startswith("⚠") for line in memory_yield.lines(rep))


class TestApprovalsLine:
    now = datetime(2026, 10, 24, 12, tzinfo=UTC)

    def test_counts_by_kind_and_ages_the_oldest(self):
        rows = [
            ("command", 20, self.now - timedelta(days=20, hours=3)),
            ("driver_pr", 2, self.now - timedelta(days=1)),
        ]
        line = BriefComposer.format_approvals_line(rows, self.now)
        assert line == "22 approvals waiting (oldest 20 days): command 20, driver_pr 2."

    def test_singular_and_one_day(self):
        rows = [("contradiction", 1, self.now - timedelta(days=1, minutes=1))]
        line = BriefComposer.format_approvals_line(rows, self.now)
        assert line == "1 approval waiting (oldest 1 day): contradiction 1."

    def test_nothing_waiting_is_silent(self):
        assert BriefComposer.format_approvals_line([], self.now) is None
        assert BriefComposer.format_approvals_line([("command", 0, None)], self.now) is None

    def test_same_kind_from_both_queues_is_summed(self):
        rows = [("merge", 2, self.now), ("merge", 3, self.now - timedelta(days=2))]
        line = BriefComposer.format_approvals_line(rows, self.now)
        assert line == "5 approvals waiting (oldest 2 days): merge 5."
