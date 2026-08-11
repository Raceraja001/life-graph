# tests/unit/test_list_tasks_lean_query.py
"""Unit tests for ProcessManager.list_tasks()'s lean-query behavior:
- COUNT(*) only runs when include_total=True is explicitly requested.
- has_more is derived from an over-fetch (limit+1 rows), not from total.
- The JSONB blob columns (input/result/logs/token_usage) are deferred,
  since the list view (_task_row_to_summary) never reads them.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from life_graph.kernel.process_manager import ProcessManager
from life_graph.models.db import AgentTask


def _make_task(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        tenant_id="t1",
        task_name="t",
        agent_name="cody",
        status="queued",
        priority="normal",
        created_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return AgentTask(**defaults)


class _FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeResult:
    def __init__(self, rows=None, scalar_value=None):
        self._rows = rows
        self._scalar_value = scalar_value

    def scalars(self):
        return _FakeScalars(self._rows or [])

    def scalar(self):
        return self._scalar_value


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows
        self.executed = []  # captured statements, in order

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def execute(self, stmt):
        self.executed.append(stmt)
        # list_tasks() always executes the list SELECT first and the
        # optional COUNT second (see source) -- use call order rather than
        # introspecting statement internals to tell them apart.
        if len(self.executed) == 1:
            return _FakeResult(rows=self._rows)
        return _FakeResult(scalar_value=7)


def _deferred_columns(stmt) -> set[str]:
    deferred = set()
    for opt in stmt._with_options:
        for entry in getattr(opt, "context", ()):
            strategy = dict(getattr(entry, "strategy", ()) or ())
            if strategy.get("deferred"):
                deferred.add(entry.path.path[-1].key)
    return deferred


def _make_pm(rows):
    session = _FakeSession(rows)
    pm = ProcessManager(session_factory=lambda: session, persona_service=None)
    return pm, session


@pytest.mark.asyncio
async def test_include_total_false_skips_count_query():
    pm, session = _make_pm([_make_task() for _ in range(3)])

    tasks, total, has_more = await pm.list_tasks("t1", limit=20)

    assert len(session.executed) == 1  # only the list select, no COUNT
    assert total is None
    assert len(tasks) == 3
    assert has_more is False


@pytest.mark.asyncio
async def test_include_total_true_runs_count_query():
    pm, session = _make_pm([_make_task() for _ in range(3)])

    tasks, total, has_more = await pm.list_tasks("t1", limit=20, include_total=True)

    assert len(session.executed) == 2  # list select + COUNT
    assert total == 7


@pytest.mark.asyncio
async def test_has_more_true_when_overfetch_exceeds_limit():
    # 3 rows returned for limit=2 -- the list query asked for limit+1=3.
    pm, session = _make_pm([_make_task() for _ in range(3)])

    tasks, _total, has_more = await pm.list_tasks("t1", limit=2)

    assert has_more is True
    assert len(tasks) == 2  # trimmed back to the requested limit


@pytest.mark.asyncio
async def test_has_more_false_when_rows_exactly_fill_limit():
    pm, session = _make_pm([_make_task() for _ in range(2)])

    tasks, _total, has_more = await pm.list_tasks("t1", limit=2)

    assert has_more is False
    assert len(tasks) == 2


@pytest.mark.asyncio
async def test_list_query_defers_jsonb_blob_columns():
    pm, session = _make_pm([])

    await pm.list_tasks("t1", limit=20)

    list_stmt = session.executed[0]
    deferred = _deferred_columns(list_stmt)
    assert deferred == {"input", "result", "logs", "token_usage"}
