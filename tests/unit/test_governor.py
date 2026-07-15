"""Unit tests for the Governor service (life_graph.services.governor).

Uses a fake async_session so no database is required. Covers authorization
wiring, pre-emptive projection, fail-open safety, and the record upsert path.
"""

from __future__ import annotations

import life_graph.services.governor as gov_mod
from life_graph.core.budget import BudgetCategory
from life_graph.services.governor import Governor

# ── Fake async_session plumbing ───────────────────────────────────────

class _FakeResult:
    def __init__(self, scalar=0.0, rows=None):
        self._scalar = scalar
        self._rows = rows or []

    def scalar_one(self):
        return self._scalar

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, result=None, raise_on_execute=False):
        self._result = result or _FakeResult()
        self._raise = raise_on_execute
        self.executed = 0
        self.committed = 0

    async def execute(self, *_a, **_k):
        self.executed += 1
        if self._raise:
            raise RuntimeError("db down")
        return self._result

    async def commit(self):
        self.committed += 1


class _FakeSessionCtx:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *_a):
        return False


def _patch_session(monkeypatch, session):
    monkeypatch.setattr(gov_mod, "async_session", lambda: _FakeSessionCtx(session))


def _set_cap(monkeypatch, cap=10.0, soft=0.8):
    monkeypatch.setattr(gov_mod.settings, "monthly_budget_usd", cap)
    monkeypatch.setattr(gov_mod.settings, "budget_soft_threshold", soft)


# ── authorize: decision wiring ────────────────────────────────────────

async def test_authorize_allows_within_budget(monkeypatch):
    _set_cap(monkeypatch)
    _patch_session(monkeypatch, _FakeSession(_FakeResult(scalar=2.0)))
    d = await Governor().authorize("t1", BudgetCategory.RESEARCH, estimated_usd=0.1)
    assert d.allowed and not d.throttled


async def test_authorize_throttles_low_priority_in_soft_band(monkeypatch):
    _set_cap(monkeypatch)
    _patch_session(monkeypatch, _FakeSession(_FakeResult(scalar=8.5)))  # 85%
    d = await Governor().authorize("t1", BudgetCategory.RESEARCH)
    assert not d.allowed and d.throttled


async def test_authorize_allows_high_priority_in_soft_band(monkeypatch):
    _set_cap(monkeypatch)
    _patch_session(monkeypatch, _FakeSession(_FakeResult(scalar=8.5)))
    d = await Governor().authorize("t1", BudgetCategory.DRIVER)
    assert d.allowed


async def test_authorize_projects_estimate_over_cap(monkeypatch):
    """A spend whose estimate would cross the cap is denied pre-emptively."""
    _set_cap(monkeypatch)
    _patch_session(monkeypatch, _FakeSession(_FakeResult(scalar=9.5)))  # 95%
    # +1.0 projects to 10.5 (>cap) even though spent alone is under.
    d = await Governor().authorize("t1", BudgetCategory.DRIVER, estimated_usd=1.0)
    assert not d.allowed


async def test_authorize_interactive_never_blocked(monkeypatch):
    _set_cap(monkeypatch)
    _patch_session(monkeypatch, _FakeSession(_FakeResult(scalar=100.0)))  # way over
    d = await Governor().authorize(
        "t1", BudgetCategory.DRIVER, estimated_usd=5.0, interactive=True
    )
    assert d.allowed and d.throttled


async def test_authorize_fails_open_on_error(monkeypatch):
    _set_cap(monkeypatch)
    _patch_session(monkeypatch, _FakeSession(raise_on_execute=True))
    d = await Governor().authorize("t1", BudgetCategory.RESEARCH)
    assert d.allowed and not d.throttled
    assert "failed open" in d.reason


# ── record ────────────────────────────────────────────────────────────

async def test_record_noop_for_nonpositive(monkeypatch):
    session = _FakeSession()
    _patch_session(monkeypatch, session)
    await Governor().record("t1", BudgetCategory.DRIVER, 0.0)
    assert session.executed == 0  # never touched the DB


async def test_record_upserts_positive_spend(monkeypatch):
    session = _FakeSession()
    _patch_session(monkeypatch, session)
    await Governor().record("t1", BudgetCategory.DRIVER, 0.25)
    assert session.executed == 1 and session.committed == 1


async def test_record_swallows_errors(monkeypatch):
    session = _FakeSession(raise_on_execute=True)
    _patch_session(monkeypatch, session)
    # Must not raise — recording is best-effort.
    await Governor().record("t1", BudgetCategory.DRIVER, 0.25)


# ── status ────────────────────────────────────────────────────────────

async def test_status_sums_categories(monkeypatch):
    _set_cap(monkeypatch, cap=10.0)
    rows = [("driver", 1.5), ("research", 0.5)]
    _patch_session(monkeypatch, _FakeSession(_FakeResult(rows=rows)))
    st = await Governor().status("t1")
    assert st.spent_usd == 2.0
    assert st.remaining_usd == 8.0
    assert st.by_category == {"driver": 1.5, "research": 0.5}
