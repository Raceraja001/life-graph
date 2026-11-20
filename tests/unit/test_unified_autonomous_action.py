"""Unified feed side-effect for ``kind="autonomous_action"`` approvals.

Approving/rejecting the generic ``Approval`` row that the Task 6 producer
(``AutonomousApprovalProducer``) mirrors into the feed must resolve the
underlying autonomy ``approval_queue`` entry and, on approve, execute the
queued ``AutoAction`` via ``AutoFixService.execute_pending``.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from life_graph.models.db import Approval
from life_graph.services.approvals import ApprovalService


class _FakeSession:
    """Stands in for an ``AsyncSession``: ``get`` returns the seeded row."""

    def __init__(self, appr: Approval) -> None:
        self._appr = appr
        self.flushed = False

    async def get(self, model, pk):
        assert str(pk) == str(self._appr.id)
        return self._appr

    async def refresh(self, _obj, **_kw):
        pass  # resolve() re-reads the row under a lock (FOR UPDATE NOWAIT)

    async def flush(self):
        self.flushed = True

    async def commit(self):
        pass  # the execution claim is committed before the side effect

    async def rollback(self):
        pass


def _autonomous_action_approval(**overrides) -> Approval:
    defaults = dict(
        id=uuid.uuid4(),
        tenant_id="t1",
        kind="autonomous_action",
        title="dangerous action: rm-old-logs",
        detail="rm -rf /var/log/old",
        status="pending",
        source="autonomy",
        source_ref="aq-1",
        payload={
            "auto_action_id": "ac-1",
            "approval_id": "aq-1",
            "risk_level": "dangerous",
        },
        priority=90,
    )
    defaults.update(overrides)
    return Approval(**defaults)


@pytest.mark.asyncio
async def test_approve_resolves_autonomy_approval_and_executes_pending(monkeypatch):
    appr = _autonomous_action_approval()
    session = _FakeSession(appr)
    service = ApprovalService(session)

    fake_autonomy_approvals = AsyncMock()
    fake_autofix = AsyncMock()
    monkeypatch.setattr(
        "life_graph.api.dependencies.get_approval_service", lambda: fake_autonomy_approvals
    )
    monkeypatch.setattr("life_graph.api.dependencies.get_autofix_service", lambda: fake_autofix)

    result = await service.resolve("t1", str(appr.id), "approve", resolved_by="user-1")

    fake_autonomy_approvals.resolve.assert_awaited_once_with(
        tenant_id="t1",
        approval_id="aq-1",
        decision="approve",
        note=None,
        resolved_by="user-1",
        close_feed=False,
    )
    fake_autofix.execute_pending.assert_awaited_once_with("t1", "ac-1")
    assert result["status"] == "approved"
    assert session.flushed is True


@pytest.mark.asyncio
async def test_reject_resolves_autonomy_approval_and_does_not_execute(monkeypatch):
    appr = _autonomous_action_approval()
    session = _FakeSession(appr)
    service = ApprovalService(session)

    fake_autonomy_approvals = AsyncMock()
    fake_autofix = AsyncMock()
    monkeypatch.setattr(
        "life_graph.api.dependencies.get_approval_service", lambda: fake_autonomy_approvals
    )
    monkeypatch.setattr("life_graph.api.dependencies.get_autofix_service", lambda: fake_autofix)

    result = await service.resolve(
        "t1", str(appr.id), "reject", note="too risky", resolved_by="user-1"
    )

    fake_autonomy_approvals.resolve.assert_awaited_once_with(
        tenant_id="t1",
        approval_id="aq-1",
        decision="reject",
        note="too risky",
        resolved_by="user-1",
        close_feed=False,
    )
    fake_autofix.execute_pending.assert_not_awaited()
    assert result["status"] == "rejected"
    assert session.flushed is True


@pytest.mark.asyncio
async def test_approve_retry_tolerates_already_resolved_autonomy_side(monkeypatch):
    """Idempotent retry-tap: a prior attempt already committed the autonomy
    ``resolve()`` (e.g. ``execute_pending`` then raised a genuine infra
    error before the generic feed row flushed). The retry must swallow the
    autonomy side's "already resolved" ValueError and still reach
    ``execute_pending`` — never propagate the stale error to the caller."""
    appr = _autonomous_action_approval()
    session = _FakeSession(appr)
    service = ApprovalService(session)

    fake_autonomy_approvals = AsyncMock()
    fake_autonomy_approvals.resolve = AsyncMock(
        side_effect=ValueError("Approval already resolved: approved")
    )
    fake_autofix = AsyncMock()
    monkeypatch.setattr(
        "life_graph.api.dependencies.get_approval_service", lambda: fake_autonomy_approvals
    )
    monkeypatch.setattr("life_graph.api.dependencies.get_autofix_service", lambda: fake_autofix)

    result = await service.resolve("t1", str(appr.id), "approve", resolved_by="user-1")

    fake_autonomy_approvals.resolve.assert_awaited_once()
    fake_autofix.execute_pending.assert_awaited_once_with("t1", "ac-1")
    assert result["status"] == "approved"
    assert session.flushed is True


@pytest.mark.asyncio
async def test_approve_retry_tolerates_already_executed_action(monkeypatch):
    """Symmetric case: the action itself already ran on a prior attempt, so
    ``execute_pending`` raises "Cannot execute action in status: success".
    The retry must still resolve the feed row cleanly rather than raise."""
    appr = _autonomous_action_approval()
    session = _FakeSession(appr)
    service = ApprovalService(session)

    fake_autonomy_approvals = AsyncMock()
    fake_autonomy_approvals.resolve = AsyncMock(
        side_effect=ValueError("Approval already resolved: approved")
    )
    fake_autofix = AsyncMock()
    fake_autofix.execute_pending = AsyncMock(
        side_effect=ValueError("Cannot execute action in status: success")
    )
    monkeypatch.setattr(
        "life_graph.api.dependencies.get_approval_service", lambda: fake_autonomy_approvals
    )
    monkeypatch.setattr("life_graph.api.dependencies.get_autofix_service", lambda: fake_autofix)

    result = await service.resolve("t1", str(appr.id), "approve", resolved_by="user-1")

    fake_autofix.execute_pending.assert_awaited_once_with("t1", "ac-1")
    assert result["status"] == "approved"
    assert session.flushed is True


@pytest.mark.asyncio
async def test_approve_does_not_swallow_unrelated_autonomy_resolve_error(monkeypatch):
    """Only the exact "already resolved" condition is tolerated — any other
    ValueError from the autonomy side (e.g. not-found) must still propagate."""
    appr = _autonomous_action_approval()
    session = _FakeSession(appr)
    service = ApprovalService(session)

    fake_autonomy_approvals = AsyncMock()
    fake_autonomy_approvals.resolve = AsyncMock(side_effect=ValueError("Approval aq-1 not found"))
    fake_autofix = AsyncMock()
    monkeypatch.setattr(
        "life_graph.api.dependencies.get_approval_service", lambda: fake_autonomy_approvals
    )
    monkeypatch.setattr("life_graph.api.dependencies.get_autofix_service", lambda: fake_autofix)

    with pytest.raises(ValueError, match="not found"):
        await service.resolve("t1", str(appr.id), "approve", resolved_by="user-1")

    fake_autofix.execute_pending.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_autonomy_approval_id_skips_side_effect(monkeypatch):
    """Defensive: a malformed payload must not raise — the generic approval
    still resolves, matching the defensive style of the sibling handlers."""
    appr = _autonomous_action_approval(payload={"auto_action_id": "ac-1"})
    session = _FakeSession(appr)
    service = ApprovalService(session)

    fake_autonomy_approvals = AsyncMock()
    fake_autofix = AsyncMock()
    monkeypatch.setattr(
        "life_graph.api.dependencies.get_approval_service", lambda: fake_autonomy_approvals
    )
    monkeypatch.setattr("life_graph.api.dependencies.get_autofix_service", lambda: fake_autofix)

    result = await service.resolve("t1", str(appr.id), "approve", resolved_by="user-1")

    fake_autonomy_approvals.resolve.assert_not_awaited()
    fake_autofix.execute_pending.assert_not_awaited()
    assert result["status"] == "approved"


# ── H9 (audit 2026-11-19): the two stores must not disagree ──────────────


def _queue_service_saying(status: str, reads: str | None = None):
    """An autonomy queue whose entry was already resolved to *status*.

    *reads*: what its status reads as before anything runs (the pre-check),
    when that differs (a decision landing in between).
    """
    from life_graph.autonomy.approvals.service import QueueAlreadyResolvedError

    service = AsyncMock()
    service.status_of = AsyncMock(return_value=reads or status)
    service.resolve = AsyncMock(side_effect=QueueAlreadyResolvedError(status))
    return service


def _patch(monkeypatch, queue, autofix):
    monkeypatch.setattr("life_graph.api.dependencies.get_approval_service", lambda: queue)
    monkeypatch.setattr("life_graph.api.dependencies.get_autofix_service", lambda: autofix)


@pytest.mark.asyncio
async def test_rejecting_the_copy_after_the_queue_approved_is_a_conflict(monkeypatch):
    """The audit's case: the queue side approved (the old timeout, or the queue
    route), then the owner tapped Reject on the still-pending copy. That used
    to be swallowed as a retry tap and the copy said "rejected" over an
    approved action."""
    from life_graph.services.approvals import ApprovalConflictError

    appr = _autonomous_action_approval()
    session = _FakeSession(appr)
    queue, autofix = _queue_service_saying("approved"), AsyncMock()
    _patch(monkeypatch, queue, autofix)

    with pytest.raises(ApprovalConflictError, match="approved in the autonomy queue"):
        await ApprovalService(session).resolve("t1", str(appr.id), "reject", resolved_by="owner")

    assert appr.status == "pending"
    queue.resolve.assert_not_awaited()
    autofix.execute_pending.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_queue_approval_landing_mid_reject_is_still_a_conflict(monkeypatch):
    """Same disagreement, decided between the pre-check and the queue call."""
    from life_graph.services.approvals import ApprovalConflictError

    appr = _autonomous_action_approval()
    session = _FakeSession(appr)
    queue, autofix = _queue_service_saying("approved", reads="pending"), AsyncMock()
    _patch(monkeypatch, queue, autofix)

    with pytest.raises(ApprovalConflictError):
        await ApprovalService(session).resolve("t1", str(appr.id), "reject", resolved_by="owner")
    assert session.flushed is False


@pytest.mark.parametrize("queue_status", ["rejected", "stale", "expired"])
@pytest.mark.asyncio
async def test_approving_the_copy_after_the_queue_refused_runs_nothing(monkeypatch, queue_status):
    from life_graph.services.approvals import ApprovalConflictError

    appr = _autonomous_action_approval()
    session = _FakeSession(appr)
    queue, autofix = _queue_service_saying(queue_status), AsyncMock()
    _patch(monkeypatch, queue, autofix)

    with pytest.raises(ApprovalConflictError, match=queue_status):
        await ApprovalService(session).resolve("t1", str(appr.id), "approve", resolved_by="owner")

    autofix.execute_pending.assert_not_awaited()
    assert "execution" not in (appr.payload or {})  # refused before any claim


@pytest.mark.asyncio
async def test_rejecting_again_after_the_queue_rejected_is_a_harmless_repeat(monkeypatch):
    appr = _autonomous_action_approval()
    session = _FakeSession(appr)
    queue, autofix = _queue_service_saying("rejected"), AsyncMock()
    _patch(monkeypatch, queue, autofix)

    result = await ApprovalService(session).resolve(
        "t1", str(appr.id), "reject", resolved_by="owner"
    )
    assert result["status"] == "rejected"


@pytest.mark.asyncio
async def test_rejecting_after_this_rows_own_failed_attempt_abandons_it(monkeypatch):
    """#293: after an attempt with an unknown outcome, reject is the owner
    abandoning it. That attempt approved the queue entry itself, so the
    queue saying approved is not a disagreement here."""
    appr = _autonomous_action_approval(
        payload={
            "auto_action_id": "ac-1",
            "approval_id": "aq-1",
            "risk_level": "dangerous",
            "execution": {
                "state": "unknown",
                "attempt": 1,
                "attempt_id": "x",
                "started_at": "2026-11-20T00:00:00+00:00",
            },
        }
    )
    session = _FakeSession(appr)
    queue, autofix = _queue_service_saying("approved"), AsyncMock()
    _patch(monkeypatch, queue, autofix)

    result = await ApprovalService(session).resolve(
        "t1", str(appr.id), "reject", resolved_by="owner"
    )
    assert result["status"] == "rejected"
    autofix.execute_pending.assert_not_awaited()
