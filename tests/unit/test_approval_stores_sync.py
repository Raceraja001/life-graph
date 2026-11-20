"""The autonomy queue and the unified feed agree about every decision (audit H9),
a passed notify-before window approves nothing, ``also_trust`` is refused rather
than ignored, and stopping (kill switch, dev-task cancel) revokes live
capabilities (audit M1).

The queue side (autonomy/approvals/service.py) runs against FakeSession, which
records each statement; the routes run as plain functions with fakes.
"""

from __future__ import annotations

import hashlib
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.sql.dml import Update

from life_graph.autonomy.approvals.capability import CapabilityStore
from life_graph.autonomy.approvals.durable_store import StoreUnavailableError
from life_graph.autonomy.approvals.service import ApprovalService, QueueConflictError
from life_graph.config import settings
from life_graph.core.tenant import tenant_scope
from tests.conftest import fake_request
from tests.unit.fakes import FakeSession, session_factory, sql

OWNER_KEY = "owner-key-0123456789"
SERVICE_KEY = "mcp-key-9876543210"
SERVICE_LABEL = f"service-key:{hashlib.sha256(SERVICE_KEY.encode()).hexdigest()[:8]}"


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setattr(settings, "api_key", None)
    monkeypatch.setattr(settings, "service_api_keys", f"{SERVICE_KEY},{OWNER_KEY}")
    monkeypatch.setattr(settings, "owner_api_keys", OWNER_KEY)
    monkeypatch.setattr(settings, "approvals_require_owner", False)


def _entry(entry_id="q1", requested_by=None):
    return SimpleNamespace(id=entry_id, status="pending", requested_by=requested_by)


def _updates(session) -> list[str]:
    return [sql(s) for s in session.statements if isinstance(s, Update)]


# ── 1. queue resolutions close the feed copy, in the same transaction ──


@pytest.mark.parametrize(
    ("decision", "feed_status"), [("approve", "approved"), ("reject", "rejected")]
)
async def test_resolving_in_the_queue_closes_the_feed_copy(decision, feed_status):
    # The copy (exists, then locked), the entry, the entry update, the linked
    # action lookup (none), then the copy update.
    session = FakeSession(["q1"], [("q1", {})], _entry(), None, [], None)
    service = ApprovalService(session_factory(session))

    await service.resolve("t1", "q1", decision, "looked fine", "owner")

    assert session.commits == 1  # one transaction for both stores
    feed_update = _updates(session)[-1]
    assert "UPDATE approvals" in feed_update
    assert "'autonomous_action'" in feed_update and "'q1'" in feed_update
    assert f"status='{feed_status}'" in feed_update.replace(" ", "")
    assert "resolved_by='owner'" in feed_update.replace(" ", "")
    assert "Resolved in autonomy queue" in feed_update
    # The copy is locked before the queue row (the feed side's order).
    assert "FOR UPDATE SKIP LOCKED" in sql(session.statements[1])
    assert "FOR UPDATE" in sql(session.statements[2])


@pytest.mark.parametrize(
    "locked",
    [
        [],  # another transaction holds the copy
        [("q1", {"execution": {"state": "started"}})],  # the feed is running it
    ],
)
async def test_the_queue_does_not_decide_what_the_feed_is_deciding(locked):
    session = FakeSession(["q1"], locked, _entry())
    service = ApprovalService(session_factory(session))

    with pytest.raises(QueueConflictError, match="approvals feed"):
        await service.resolve("t1", "q1", "reject", None, "owner")

    assert session.commits == 0
    assert _updates(session) == []


async def test_the_feed_resolving_its_own_copy_does_not_touch_it_again():
    session = FakeSession(_entry(), None, [], None)
    service = ApprovalService(session_factory(session))

    await service.resolve("t1", "q1", "approve", None, "owner", close_feed=False)

    assert not [u for u in _updates(session) if "UPDATE approvals" in u]
    assert "approvals.kind" not in sql(session.statements[0])


async def test_an_already_resolved_entry_is_a_conflict_not_a_404():
    from life_graph.autonomy.approvals.service import QueueAlreadyResolvedError

    session = FakeSession([], SimpleNamespace(id="q1", status="approved", requested_by=None))
    with pytest.raises(QueueAlreadyResolvedError) as exc:
        await ApprovalService(session_factory(session)).resolve("t1", "q1", "reject", None, "o")
    assert exc.value.status == "approved"
    assert "already resolved" in str(exc.value)  # what older callers match on


async def test_a_batch_closes_every_resolved_entrys_copy():
    entries = [_entry("q1"), _entry("q2")]
    # match, copies (exist / locked), entries under lock, then the writes.
    session = FakeSession(entries, ["q1"], [("q1", {})], entries, None)
    service = ApprovalService(session_factory(session))

    result = await service.batch_resolve("t1", {"approval_ids": ["q1", "q2"]}, "reject", None, "o")

    assert result["resolved_ids"] == ["q1", "q2"]
    assert session.commits == 1
    feed_update = _updates(session)[-1]
    assert "UPDATE approvals" in feed_update and "'rejected'" in feed_update
    assert "'q1'" in feed_update and "'q2'" in feed_update


async def test_a_batch_touching_a_copy_in_use_resolves_nothing():
    entries = [_entry("q1"), _entry("q2")]
    session = FakeSession(entries, ["q1"], [], entries)
    with pytest.raises(QueueConflictError):
        await ApprovalService(session_factory(session)).batch_resolve(
            "t1", {"approval_ids": ["q1", "q2"]}, "approve", None, "o"
        )
    assert session.commits == 0
    assert _updates(session) == []


# ── 2. a passed notify-before window approves nothing ──


async def test_a_passed_notify_before_window_is_handed_to_the_owner(monkeypatch):
    """It used to mark the entry approved ("Auto-approved after timeout") and
    run nothing: the action stayed pending for ever and the copy too."""
    engine = AsyncMock()
    monkeypatch.setattr("life_graph.runtime.get_notification_engine", lambda: engine)
    passed = SimpleNamespace(id="q1", tenant_id="t1", action_name="restart-api")
    session = FakeSession([passed], None)

    count = await ApprovalService(session_factory(session)).check_expirations()

    assert count == 1
    updates = _updates(session)
    assert len(updates) == 1  # the window, nothing else: no auto action, no copy
    assert "UPDATE approval_queue" in updates[0]
    assert "expires_at=NULL" in updates[0].replace(" ", "")
    assert "'approved'" not in updates[0] and "status=" not in updates[0].split("WHERE")[0]
    engine.create.assert_awaited_once()
    args, kwargs = engine.create.call_args
    assert args[0] == "t1" and "restart-api" in args[1]
    assert "Nothing ran" in kwargs["body"]


async def test_a_notification_failure_does_not_undo_the_window(monkeypatch):
    def boom():
        raise RuntimeError("no engine")

    monkeypatch.setattr("life_graph.runtime.get_notification_engine", boom)
    session = FakeSession([SimpleNamespace(id="q1", tenant_id="t1", action_name="x")], None)
    assert await ApprovalService(session_factory(session)).check_expirations() == 1
    assert session.commits == 1


# ── 1b. the queue routes hand an entry with a copy to the feed ──


def _route_service(monkeypatch, entries, copies):
    service = SimpleNamespace(
        match_pending=AsyncMock(return_value=entries),
        pending_feed_copies=AsyncMock(return_value=copies),
        resolve=AsyncMock(),
        batch_resolve=AsyncMock(
            side_effect=lambda **kw: {
                "resolved_count": len(kw["filter_criteria"]["approval_ids"] or []),
                "resolved_ids": list(kw["filter_criteria"]["approval_ids"] or []),
            }
        ),
    )
    monkeypatch.setattr("life_graph.runtime.get_approval_service", lambda: service)
    decided = AsyncMock(
        return_value={"id": "f1", "kind": "autonomous_action", "status": "approved"}
    )
    monkeypatch.setattr("life_graph.services.approvals.resolve_feed_copy", decided)
    return service, decided


async def test_approving_in_the_queue_runs_the_action_through_the_feed(monkeypatch):
    """Approving at /autonomy/approvals used to mark the entry approved and run
    nothing (only the feed's approve executes). Now it is decided through the
    copy, which runs the action under the at-most-once claim."""
    from life_graph.autonomy.approvals import router
    from life_graph.autonomy.approvals.schemas import ResolveRequest

    service, decided = _route_service(monkeypatch, [_entry("q1")], {"q1": "f1"})
    with tenant_scope("t1"):
        response = await router.resolve_approval(
            "q1", ResolveRequest(decision="approve", note="go"), fake_request(api_key=OWNER_KEY)
        )

    service.resolve.assert_not_awaited()
    decided.assert_awaited_once()
    _factory, tenant, feed_id, decision, note, who = decided.await_args.args
    assert (tenant, feed_id, decision, note, who) == ("t1", "f1", "approve", "go", "owner")
    assert response["data"] == {"id": "q1", "status": "approved"}


async def test_the_hand_off_keeps_the_self_approval_check(monkeypatch):
    from life_graph.autonomy.approvals import router
    from life_graph.autonomy.approvals.schemas import ResolveRequest

    _, decided = _route_service(monkeypatch, [_entry("q1", SERVICE_LABEL)], {"q1": "f1"})
    with tenant_scope("t1"), pytest.raises(HTTPException) as exc:
        await router.resolve_approval(
            "q1", ResolveRequest(decision="approve"), fake_request(api_key=SERVICE_KEY)
        )
    assert exc.value.status_code == 403
    decided.assert_not_awaited()


async def test_a_conflict_in_the_queue_is_409(monkeypatch):
    from life_graph.autonomy.approvals import router
    from life_graph.autonomy.approvals.schemas import ResolveRequest

    service, _ = _route_service(monkeypatch, [], {})
    service.resolve = AsyncMock(side_effect=QueueConflictError("being resolved"))
    with tenant_scope("t1"), pytest.raises(HTTPException) as exc:
        await router.resolve_approval(
            "q1", ResolveRequest(decision="reject"), fake_request(api_key=OWNER_KEY)
        )
    assert exc.value.status_code == 409


async def test_a_batch_splits_entries_with_a_copy_from_the_rest(monkeypatch):
    from life_graph.autonomy.approvals import router
    from life_graph.autonomy.approvals.schemas import BatchResolveRequest

    service, decided = _route_service(
        monkeypatch, [_entry("q1"), _entry("q2"), _entry("q3")], {"q2": "f2", "q3": "f3"}
    )
    decided.side_effect = [
        {"id": "f2", "kind": "autonomous_action", "status": "approved"},
        __import__("life_graph.services.approvals", fromlist=["x"]).ApprovalConflictError(
            "rejected in the autonomy queue"
        ),
    ]
    with tenant_scope("t1"):
        response = await router.batch_resolve(
            BatchResolveRequest(decision="approve", approval_ids=["q1", "q2", "q3"]),
            fake_request(api_key=OWNER_KEY),
        )

    assert service.batch_resolve.await_args.kwargs["filter_criteria"] == {"approval_ids": ["q1"]}
    data = response["data"]
    assert data["resolved_ids"] == ["q1", "q2"]
    assert data["failed"] == [
        {"id": "q3", "status_code": 409, "error": "Approval already rejected in the autonomy queue"}
    ]


# ── 3. also_trust is refused, not silently ignored ──


def test_also_trust_true_is_refused():
    from life_graph.autonomy.approvals.schemas import ResolveRequest

    with pytest.raises(ValidationError, match="trust/override"):
        ResolveRequest(decision="approve", also_trust=True)
    # Old clients that send false (or nothing) keep working.
    assert ResolveRequest(decision="approve", also_trust=False).also_trust is False


def test_the_service_no_longer_takes_also_trust():
    import inspect

    assert "also_trust" not in inspect.signature(ApprovalService.resolve).parameters


# ── 4. stopping revokes live capabilities ──


def _issue(store, tenant_id="t1", task_id=None):
    return store.issue(
        tenant_id=tenant_id,
        action_types=["transfer_money"],
        target_origins=["owner"],
        task_id=task_id,
    )


class _ConfigSession:
    def __init__(self):
        self.config = SimpleNamespace(autonomy_paused=False, autonomy_paused_at=None)
        self.commits = 0

    async def get(self, _model, _pk):
        return self.config

    async def commit(self):
        self.commits += 1


async def test_pausing_autonomy_leaves_no_live_capability(monkeypatch):
    from life_graph.autonomy.safety import router

    store = CapabilityStore()
    monkeypatch.setattr("life_graph.autonomy.approvals.capability.capability_store", store)
    mine = [_issue(store), _issue(store, task_id="task-7")]
    other_tenant = _issue(store, tenant_id="t2")
    session = _ConfigSession()

    response = await router.pause_kill_switch(session=session, tenant_id="t1")

    assert session.config.autonomy_paused is True
    assert response["data"]["capabilities_revoked"] == 2
    assert all(store.get(c.capability_id).revoked for c in mine)  # 0 live for t1
    assert store.get(other_tenant.capability_id).revoked is False


async def test_a_pause_with_the_store_down_still_pauses_and_says_so(monkeypatch):
    from life_graph.autonomy.safety import router

    class _Down:
        def revoke_all(self, **_kw):
            raise StoreUnavailableError("the authorization store is unavailable")

    monkeypatch.setattr("life_graph.autonomy.approvals.capability.capability_store", _Down())
    session = _ConfigSession()

    with pytest.raises(HTTPException) as exc:
        await router.pause_kill_switch(session=session, tenant_id="t1")

    assert exc.value.status_code == 503
    assert "Autonomy is paused" in exc.value.detail
    assert session.config.autonomy_paused is True and session.commits == 1


async def test_cancelling_a_dev_task_revokes_that_tasks_capabilities(monkeypatch):
    from life_graph.services.dev import tasks as dev_tasks

    store = CapabilityStore()
    monkeypatch.setattr("life_graph.autonomy.approvals.capability.capability_store", store)
    task_id = str(uuid.uuid4())
    mine = _issue(store, task_id=task_id)
    other = _issue(store, task_id="another-task")
    task = SimpleNamespace(status="queued", status_history=[], completed_at=None)
    session = FakeSession(task)

    state = await dev_tasks.request_cancel(session_factory(session), "t1", task_id)

    assert state == {"id": task_id, "status": "cancelled", "cancel": "done"}  # shape unchanged
    assert store.get(mine.capability_id).revoked is True
    assert store.get(other.capability_id).revoked is False


async def test_a_cancel_with_the_store_down_stands_and_the_route_says_so(monkeypatch):
    from life_graph.api import drivers
    from life_graph.services.dev import tasks as dev_tasks

    class _Down:
        def revoke_all(self, **_kw):
            raise StoreUnavailableError("the authorization store is unavailable")

    monkeypatch.setattr("life_graph.autonomy.approvals.capability.capability_store", _Down())
    task = SimpleNamespace(status="queued", status_history=[], completed_at=None)
    session = FakeSession(task)
    monkeypatch.setattr(drivers, "async_session", session_factory(session))

    with tenant_scope("t1"), pytest.raises(HTTPException) as exc:
        await drivers.cancel_dev_task(str(uuid.uuid4()))

    assert exc.value.status_code == 503
    assert "cancelled" in exc.value.detail and "could not be revoked" in exc.value.detail
    assert task.status == "cancelled" and session.commits == 1
    state = await dev_tasks.request_cancel(session_factory(session), "t1", str(uuid.uuid4()))
    assert state["capabilities_revoked"] is None and "unavailable" in state["revoke_error"]
