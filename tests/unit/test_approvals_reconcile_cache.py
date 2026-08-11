# tests/unit/test_approvals_reconcile_cache.py
"""Unit tests for ApprovalService.list_approvals()'s reconcile-promotions
TTL cache: reconcile_promotions() used to run (2 extra DB queries) on every
single GET /approvals call — this caps it to at most once per TTL window
per tenant."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from life_graph.services import approvals as approvals_module
from life_graph.services.approvals import ApprovalService


class _FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _FakeScalars(self._rows)


class _FakeSession:
    def __init__(self):
        self.execute_count = 0

    async def execute(self, stmt):
        self.execute_count += 1
        return _FakeResult([])  # empty: no existing approvals, no needs_review runs

    async def flush(self):
        pass


@pytest.fixture(autouse=True)
def _clear_reconcile_cache():
    approvals_module._last_reconciled.clear()
    yield
    approvals_module._last_reconciled.clear()


@pytest.mark.asyncio
async def test_first_call_reconciles():
    session = _FakeSession()
    svc = ApprovalService(session)

    await svc.list_approvals("t1")

    # 2 reconcile queries (existing source_refs + needs_review runs) + 1 list query
    assert session.execute_count == 3


@pytest.mark.asyncio
async def test_second_call_within_ttl_skips_reconcile():
    session = _FakeSession()
    svc = ApprovalService(session)

    await svc.list_approvals("t1")
    session.execute_count = 0
    await svc.list_approvals("t1")

    assert session.execute_count == 1  # only the list query, reconcile skipped


@pytest.mark.asyncio
async def test_different_tenants_reconcile_independently():
    session = _FakeSession()
    svc = ApprovalService(session)

    await svc.list_approvals("t1")
    session.execute_count = 0
    await svc.list_approvals("t2")

    assert session.execute_count == 3  # t2 has never been reconciled


@pytest.mark.asyncio
async def test_reconcile_runs_again_after_ttl_expires(monkeypatch):
    session = _FakeSession()
    svc = ApprovalService(session)

    clock = {"t": 1000.0}
    monkeypatch.setattr(approvals_module.time, "monotonic", lambda: clock["t"])

    await svc.list_approvals("t1")
    clock["t"] += approvals_module._RECONCILE_TTL_SECONDS + 1
    session.execute_count = 0
    await svc.list_approvals("t1")

    assert session.execute_count == 3  # TTL expired, reconcile ran again
