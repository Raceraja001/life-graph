"""Batch and stale approval decisions leave audit_log rows (autonomy/approvals/service.py).

Only ApprovalService.resolve wrote an ``approval_decision`` audit row. A
batch resolve (POST /autonomy/approvals/batch) and the stale sweep
(expire_stale, a daily cron) decided entries and wrote nothing, so the audit
log missed those decisions.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from life_graph.autonomy.approvals.service import ApprovalService
from life_graph.autonomy.audit.service import AuditService
from tests.unit.fakes import FakeSession, session_factory


def _entry(entry_id):
    return SimpleNamespace(id=entry_id, status="pending", requested_by=None)


def _logged(audit):
    return [
        (c.kwargs["tenant_id"], c.kwargs["approval_id"], c.kwargs["decision"],
         c.kwargs["resolved_by"])
        for c in audit.log_approval.await_args_list
    ]  # fmt: skip


@pytest.mark.parametrize("decision", ["approve", "reject"])
async def test_a_batch_writes_one_audit_row_per_entry(decision):
    entries = [_entry("q1"), _entry("q2")]
    # match, copies (none), entries under lock, then the writes.
    session = FakeSession(entries, [], entries, None)
    audit = SimpleNamespace(log_approval=AsyncMock())
    service = ApprovalService(session_factory(session), audit_service=audit)

    await service.batch_resolve("t1", {"approval_ids": ["q1", "q2"]}, decision, "n", "owner")

    assert _logged(audit) == [("t1", "q1", decision, "owner"), ("t1", "q2", decision, "owner")]
    assert all(c.kwargs["note"] == "n" for c in audit.log_approval.await_args_list)


async def test_a_batch_that_matches_nothing_writes_nothing():
    session = FakeSession([], [], [], None)
    audit = SimpleNamespace(log_approval=AsyncMock())

    await ApprovalService(session_factory(session), audit_service=audit).batch_resolve(
        "t1", {"approval_ids": []}, "reject", None, "owner"
    )

    audit.log_approval.assert_not_awaited()


async def test_stale_entries_write_an_expired_audit_row_each():
    old = [("a1", "raja"), ("a2", "other")]
    session = FakeSession(old, [], old, None)
    audit = SimpleNamespace(log_approval=AsyncMock())

    service = ApprovalService(session_factory(session), audit_service=audit)

    assert await service.expire_stale(14) == 2

    assert _logged(audit) == [("raja", "a1", "stale", "system"), ("other", "a2", "stale", "system")]


async def test_a_failed_audit_write_does_not_undo_the_batch(caplog):
    entries = [_entry("q1"), _entry("q2")]
    session = FakeSession(entries, [], entries, None)
    audit = SimpleNamespace(log_approval=AsyncMock(side_effect=[RuntimeError("db"), None]))
    service = ApprovalService(session_factory(session), audit_service=audit)

    result = await service.batch_resolve("t1", {"approval_ids": ["q1", "q2"]}, "reject", None, "o")

    assert result["resolved_ids"] == ["q1", "q2"]
    assert session.commits == 1
    assert audit.log_approval.await_count == 2  # the second is still written
    assert "q1" in caplog.text and "not written to the audit log" in caplog.text


@pytest.mark.parametrize(
    ("decision", "result"), [("approve", "success"), ("reject", "rejected"), ("stale", "expired")]
)
async def test_log_approval_maps_each_decision_to_an_allowed_result(decision, result):
    session = FakeSession()
    await AuditService(session_factory(session)).log_approval("t1", "q1", None, decision, "o")

    (row,) = session.added
    assert row.result == result
    assert row.action_type == "approval_decision"
    assert row.approval_id == "q1"
    assert row.classification_reasoning["decision"] == decision
