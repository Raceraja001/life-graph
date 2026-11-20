"""Pending approvals nobody answered are marked stale, never approved
(autonomy/approvals/service.py expire_stale)."""

from __future__ import annotations

from life_graph.autonomy.approvals.service import ApprovalService
from tests.unit.fakes import FakeSession, session_factory, sql


async def test_old_pending_entries_become_stale_and_their_actions_skipped():
    old = [("a1", "raja"), ("a2", "raja")]
    # The candidates, their feed copies (none), the candidates again under a
    # row lock, then the writes.
    session = FakeSession(old, [], old, None)
    service = ApprovalService(session_factory(session))

    count = await service.expire_stale(14)

    assert count == 2
    assert session.commits == 1
    select_stmt, copies_stmt, locked_stmt, *updates = session.statements
    assert "status = 'pending'" in sql(select_stmt)
    assert "created_at <=" in sql(select_stmt)
    assert "'autonomous_action'" in sql(copies_stmt)
    assert "FOR UPDATE" in sql(locked_stmt)
    assert len(updates) == 5  # entry + its auto action, twice; then the feed copies
    feed_update = sql(updates[4])
    assert "UPDATE approvals" in feed_update
    assert "'rejected'" in feed_update and "'approved'" not in feed_update
    entry_update = sql(updates[0])
    assert "'stale'" in entry_update
    assert "'approved'" not in entry_update
    assert "resolved_by='system'" in entry_update.replace(" ", "")
    assert "No decision in 14 days" in entry_update
    action_update = sql(updates[1])
    assert "'skipped'" in action_update
    assert "tenant_id = 'raja'" in action_update


async def test_zero_days_means_never():
    session = FakeSession()
    service = ApprovalService(session_factory(session))

    assert await service.expire_stale(0) == 0
    assert session.statements == []


async def test_nothing_old_enough():
    session = FakeSession([])
    service = ApprovalService(session_factory(session))

    assert await service.expire_stale(14) == 0
    assert len(session.statements) == 1
    assert session.commits == 1
