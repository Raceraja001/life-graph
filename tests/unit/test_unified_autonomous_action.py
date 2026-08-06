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

    async def flush(self):
        self.flushed = True


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
