"""Unit tests for ShadowService.grade — tallies, trust feed, graduation.

Uses a fake session (session.get based) and a spied TrustScoreService so no DB
is required. The pure graduation bar is covered separately in test_shadow.py.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

import life_graph.autonomy.shadow.service as svc_mod
from life_graph.autonomy.models import ShadowEnrollment, ShadowRun
from life_graph.autonomy.shadow.service import ShadowService
from life_graph.core.shadow import ShadowGrade


class _TrustSpy:
    """Stands in for TrustScoreService; records which method was called."""

    def __init__(self, _session):
        self.successes = 0
        self.failures = 0
        _TrustSpy.last = self

    async def record_success(self, *_a, **_k):
        self.successes += 1

    async def record_failure(self, *_a, **_k):
        self.failures += 1


class _FakeSession:
    def __init__(self, objects: dict):
        self._objects = objects  # id -> ORM object

    async def get(self, _model, oid):
        return self._objects.get(oid)

    async def commit(self):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        return False


def _wire(monkeypatch, session):
    monkeypatch.setattr(svc_mod, "async_session", lambda: session)
    monkeypatch.setattr(svc_mod, "TrustScoreService", _TrustSpy)

    async def _noemit(*_a, **_k):
        return None

    monkeypatch.setattr(svc_mod.event_bus, "emit", _noemit)


def _make(enrolled_days_ago=20, good=4, bad=0, status="shadow"):
    enr = ShadowEnrollment(
        id="enr1", tenant_id="t1", agent_id="a1", status=status,
        graded_good=good, graded_bad=bad,
        enrolled_at=datetime.now(UTC) - timedelta(days=enrolled_days_ago),
    )
    run = ShadowRun(
        id="run1", tenant_id="t1", agent_id="a1", enrollment_id="enr1",
        action_type="deploy", command="echo hi", risk_level="safe",
        project_id=None, would_have_routed="auto_executed", grade=None,
    )
    return enr, run


# ── grade GOOD: tally, trust success, graduation at the bar ───────────

async def test_grade_good_graduates_at_threshold(monkeypatch):
    enr, run = _make(enrolled_days_ago=20, good=4, bad=0)  # 5th good, 20 days
    _wire(monkeypatch, _FakeSession({"run1": run, "enr1": enr}))

    result = await ShadowService().grade("t1", "run1", ShadowGrade.GOOD)

    assert result.graded_good == 5
    assert result.graduated is True
    assert result.status == "graduated"
    assert _TrustSpy.last.successes == 1  # trust fed once


async def test_grade_good_below_bar_does_not_graduate(monkeypatch):
    enr, run = _make(enrolled_days_ago=3, good=1, bad=0)  # too soon, too few
    _wire(monkeypatch, _FakeSession({"run1": run, "enr1": enr}))

    result = await ShadowService().grade("t1", "run1", ShadowGrade.GOOD)

    assert result.graded_good == 2
    assert result.graduated is False
    assert result.status == "shadow"


# ── grade BAD: tally + trust failure, never graduates ─────────────────

async def test_grade_bad_feeds_failure_and_stays_shadow(monkeypatch):
    # 3 good + this bad -> rate 0.75 and only 3 good samples: below the bar.
    enr, run = _make(enrolled_days_ago=30, good=3, bad=0)
    _wire(monkeypatch, _FakeSession({"run1": run, "enr1": enr}))

    result = await ShadowService().grade("t1", "run1", ShadowGrade.BAD)

    assert result.graded_bad == 1
    assert result.graduated is False
    assert result.status == "shadow"
    assert _TrustSpy.last.failures == 1
    assert _TrustSpy.last.successes == 0


# ── unknown run raises ────────────────────────────────────────────────

async def test_grade_unknown_run_raises(monkeypatch):
    _wire(monkeypatch, _FakeSession({}))
    with pytest.raises(ValueError):
        await ShadowService().grade("t1", "missing", ShadowGrade.GOOD)
