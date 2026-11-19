"""H4 (audit 2026-11-19): resolving an approval claims its row first.

``resolve()`` used to read the row, check ``status == "pending"`` and run the
side effect (a merge, a deploy of up to ten minutes) before the request
committed. Two approvals of the same item at once both saw ``pending`` and
both ran it. Now the row is locked (``FOR UPDATE NOWAIT``) and re-read before
the status check: a second resolve meanwhile gets the "already resolved" path
(409), and the status checked is the committed one.

The real two-connection race is in tests/integration/test_approvals.py.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError

from life_graph.services import approvals as approvals_mod


def _approval(kind: str = "merge", status: str = "pending"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id="t",
        kind=kind,
        status=status,
        title="x",
        detail="",
        source="test",
        payload={},
        created_at=None,
        resolved_by=None,
        resolved_at=None,
        resolution_note=None,
    )


class _PgError(Exception):
    def __init__(self, sqlstate: str):
        super().__init__(f"sqlstate {sqlstate}")
        self.sqlstate = sqlstate


class _Session:
    """get() returns the row as this session last saw it; refresh() is the
    locking re-read, and says what the database holds now."""

    def __init__(self, appr, *, committed_status=None, refresh_error=None):
        self.appr = appr
        self.committed_status = committed_status
        self.refresh_error = refresh_error
        self.refreshes: list[dict] = []
        self.flushed = False

    async def get(self, model, pk, **_kw):
        return self.appr

    async def refresh(self, obj, **kwargs):
        self.refreshes.append(kwargs)
        if self.refresh_error is not None:
            raise self.refresh_error
        if self.committed_status is not None:
            obj.status = self.committed_status

    async def flush(self):
        self.flushed = True

    def add(self, _obj):
        pass


@pytest.fixture
def side_effects(monkeypatch):
    calls = []

    async def fake_merge(self, tenant_id, appr, approve):
        calls.append(appr.id)

    monkeypatch.setattr(approvals_mod.ApprovalService, "_apply_merge", fake_merge)
    return calls


async def test_resolve_locks_the_row_before_checking_its_status(side_effects):
    appr = _approval()
    session = _Session(appr)

    result = await approvals_mod.ApprovalService(session).resolve("t", str(appr.id), "approve")

    assert result["status"] == "approved"
    assert session.refreshes == [{"with_for_update": {"nowait": True}}]
    assert side_effects == [appr.id]


async def test_a_row_resolved_by_someone_else_meanwhile_conflicts(side_effects):
    """This session read ``pending``; the locking re-read sees ``approved``
    (the other request committed first). The side effect must not run again."""
    appr = _approval()
    session = _Session(appr, committed_status="approved")

    with pytest.raises(approvals_mod.ApprovalAlreadyResolvedError, match="approved"):
        await approvals_mod.ApprovalService(session).resolve("t", str(appr.id), "approve")

    assert side_effects == []


async def test_a_row_being_resolved_right_now_conflicts_without_waiting(side_effects):
    """Another request holds the lock (its deploy is still running): NOWAIT
    fails with 55P03, and this one is told the item is being resolved."""
    appr = _approval()
    locked = OperationalError("SELECT ... FOR UPDATE NOWAIT", {}, _PgError("55P03"))
    session = _Session(appr, refresh_error=locked)

    with pytest.raises(approvals_mod.ApprovalAlreadyResolvedError) as info:
        await approvals_mod.ApprovalService(session).resolve("t", str(appr.id), "approve")

    assert str(info.value) == "being resolved"
    assert side_effects == []
    assert appr.status == "pending"


async def test_any_other_database_error_is_not_reported_as_a_conflict(side_effects):
    appr = _approval()
    broken = OperationalError("SELECT", {}, _PgError("08006"))
    session = _Session(appr, refresh_error=broken)

    with pytest.raises(OperationalError):
        await approvals_mod.ApprovalService(session).resolve("t", str(appr.id), "approve")
    assert side_effects == []


async def test_another_tenants_row_is_never_locked(side_effects):
    appr = _approval()
    appr.tenant_id = "someone-else"
    session = _Session(appr)

    with pytest.raises(LookupError):
        await approvals_mod.ApprovalService(session).resolve("t", str(appr.id), "approve")
    assert session.refreshes == []


async def test_the_api_answers_409_while_the_item_is_being_resolved(monkeypatch):
    from fastapi import HTTPException

    from life_graph.api import approvals as api

    async def busy(self, *_a, **_k):
        raise approvals_mod.ApprovalAlreadyResolvedError("being resolved")

    monkeypatch.setattr(approvals_mod.ApprovalService, "resolve", busy)

    with pytest.raises(HTTPException) as info:
        await api._resolve(str(uuid.uuid4()), "approve", None, "t", SimpleNamespace())
    assert info.value.status_code == 409
    assert info.value.detail == "Approval already being resolved"
