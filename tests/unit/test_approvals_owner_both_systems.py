"""P0 (audit 2026-11-19, follow-up to H3): owner identity on BOTH approval systems.

#278 made the unified feed (``POST /approvals/{id}/approve|reject``) take who
decided from the server's view of the caller. The autonomy queue
(``POST /autonomy/approvals/{id}/resolve`` and ``/autonomy/approvals/batch``)
still wrote ``resolved_by`` straight from the request body and ignored
``approvals_require_owner``, so any service key — the MCP server's, a hook's —
could resolve a queued shell command in the owner's name, even with
enforcement on. Both routers now share api/approval_identity.py.

Separately, and whatever the setting: a non-owner caller that started a dev
task (``POST /drivers/tasks``, which MCP's start_dev_task calls) may not
approve that task's plan/PR/merge/deploy (self-approval guard).

And a startup/system signal says whether enforcement is on and whether the
owner could still get in (counts only).
"""

from __future__ import annotations

import logging
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from life_graph.api import approval_identity as ident
from life_graph.api import approvals as feed
from life_graph.autonomy.approvals import router as queue
from life_graph.autonomy.approvals.schemas import BatchResolveRequest, ResolveRequest
from life_graph.config import settings
from life_graph.core.tenant import tenant_scope
from life_graph.services import approvals as approvals_mod
from life_graph.services import owner_enforcement

OWNER_KEY = "owner-key-0123456789"
SERVICE_KEY = "mcp-key-9876543210"
OTHER_KEY = "hook-key-5555555555"


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setattr(settings, "api_key", None)
    monkeypatch.setattr(settings, "service_api_keys", f"{SERVICE_KEY},{OTHER_KEY},{OWNER_KEY}")
    monkeypatch.setattr(settings, "owner_api_keys", OWNER_KEY)
    monkeypatch.setattr(settings, "approvals_require_owner", False)
    with tenant_scope("t"):
        yield


def _request(key: str | None = None, device_id: str | None = None) -> Request:
    headers = [(b"authorization", f"Bearer {key}".encode())] if key else []
    request = Request(
        {"type": "http", "method": "POST", "path": "/x", "headers": headers, "query_string": b""}
    )
    if device_id:
        request.state.device_id = device_id
    return request


def _label(key: str) -> str:
    return ident.resolver(_request(key))


# ── autonomy queue: who resolved comes from the caller, not the body ──────


@pytest.fixture
def queue_calls(monkeypatch):
    """Capture what the autonomy router hands its service; no database."""
    calls: list[dict] = []

    class _Service:
        # No entry here has a feed copy, so the router resolves in the queue.
        async def match_pending(self, tenant_id, filter_criteria):
            return []

        async def pending_feed_copies(self, tenant_id, entry_ids):
            return {}

        async def resolve(self, **kw):
            calls.append({"op": "resolve", **kw})

        async def batch_resolve(self, **kw):
            calls.append({"op": "batch", **kw})
            return {"resolved_count": 1, "resolved_ids": ["a"]}

    import life_graph.runtime as runtime

    monkeypatch.setattr(runtime, "get_approval_service", lambda: _Service())
    return calls


async def _queue_resolve(request, **body):
    body.setdefault("decision", "approve")
    return await queue.resolve_approval("a1", ResolveRequest(**body), request)


async def _queue_batch(request, **body):
    body.setdefault("decision", "approve")
    body.setdefault("approval_ids", ["a1"])
    return await queue.batch_resolve(BatchResolveRequest(**body), request)


@pytest.mark.parametrize("route", [_queue_resolve, _queue_batch])
async def test_queue_ignores_resolved_by_in_the_body(queue_calls, route):
    await route(_request(SERVICE_KEY), resolved_by="owner", note="fine")

    call = queue_calls[0]
    assert call["resolved_by"] == _label(SERVICE_KEY)
    assert call["resolved_by"] != "owner" and SERVICE_KEY not in call["resolved_by"]
    assert call["note"] == "fine\n(client said: owner)"


@pytest.mark.parametrize("route", [_queue_resolve, _queue_batch])
async def test_queue_records_the_owner_key_and_a_paired_phone(queue_calls, route):
    await route(_request(OWNER_KEY), resolved_by="someone else")
    await route(_request(device_id="d-9"))

    assert [c["resolved_by"] for c in queue_calls] == ["owner", "phone:d-9"]
    assert queue_calls[1]["note"] is None


def test_queue_body_without_resolved_by_is_accepted():
    """Old clients send it (life-graph-ui sends the tenant id); new ones need not."""
    assert ResolveRequest(decision="approve").resolved_by is None
    assert BatchResolveRequest(decision="reject").resolved_by is None
    assert ResolveRequest(decision="approve", resolved_by="default").resolved_by == "default"


@pytest.mark.parametrize("route", [_queue_resolve, _queue_batch])
async def test_queue_off_by_default_a_service_key_may_still_resolve(queue_calls, route):
    await route(_request(SERVICE_KEY), decision="reject")
    assert [c["decision"] for c in queue_calls] == ["reject"]


@pytest.mark.parametrize("route", [_queue_resolve, _queue_batch])
async def test_queue_enforced_a_non_owner_key_is_refused(monkeypatch, queue_calls, route):
    monkeypatch.setattr(settings, "approvals_require_owner", True)

    with pytest.raises(HTTPException) as info:
        await route(_request(SERVICE_KEY), resolved_by="owner")

    assert info.value.status_code == 403
    assert queue_calls == []


@pytest.mark.parametrize("route", [_queue_resolve, _queue_batch])
async def test_queue_enforced_owner_key_and_paired_phone_may_resolve(
    monkeypatch, queue_calls, route
):
    monkeypatch.setattr(settings, "approvals_require_owner", True)

    await route(_request(OWNER_KEY))
    await route(_request(device_id="d-9"))

    assert [c["resolved_by"] for c in queue_calls] == ["owner", "phone:d-9"]


# ── unified feed: self-approval guard (any setting) ──────────────────────


@pytest.fixture
def feed_calls(monkeypatch):
    calls: list[dict] = []
    requested: dict[str, str | None] = {"by": None}

    async def fake_resolve(self, tenant_id, approval_id, decision, note=None, resolved_by=None):
        calls.append({"decision": decision, "resolved_by": resolved_by})
        return {"id": approval_id, "kind": "driver_merge", "status": decision + "d"}

    async def fake_requested_by(_session, _tenant, _id):
        return requested["by"]

    async def no_emit(*_a, **_k):
        return None

    class _Session:
        async def commit(self):
            pass

        async def rollback(self):
            pass

    monkeypatch.setattr(approvals_mod.ApprovalService, "resolve", fake_resolve)
    monkeypatch.setattr(feed, "_requested_by", fake_requested_by)
    monkeypatch.setattr(feed.event_bus, "emit", no_emit)
    return calls, requested, _Session()


async def _feed(route, request, session):
    return await route(str(uuid.uuid4()), request, None, "t", session)


@pytest.mark.parametrize("enforced", [False, True])
async def test_an_agent_cannot_approve_the_task_it_started(monkeypatch, feed_calls, enforced):
    calls, requested, session = feed_calls
    monkeypatch.setattr(settings, "approvals_require_owner", enforced)
    requested["by"] = _label(SERVICE_KEY)  # the MCP key started the dev task

    with pytest.raises(HTTPException) as info:
        await _feed(feed.approve_approval, _request(SERVICE_KEY), session)

    assert info.value.status_code == 403
    assert calls == []


async def test_with_enforcement_off_another_service_key_may_approve(feed_calls):
    calls, requested, session = feed_calls
    requested["by"] = _label(SERVICE_KEY)

    await _feed(feed.approve_approval, _request(OTHER_KEY), session)

    assert calls[0]["resolved_by"] == _label(OTHER_KEY)  # which key approved is recorded


async def test_an_agent_may_still_withdraw_its_own_request(feed_calls):
    calls, requested, session = feed_calls
    requested["by"] = _label(SERVICE_KEY)

    await _feed(feed.reject_approval, _request(SERVICE_KEY), session)

    assert [c["decision"] for c in calls] == ["reject"]


async def test_the_owner_approves_work_the_owner_started(feed_calls):
    calls, requested, session = feed_calls
    requested["by"] = "owner"
    await _feed(feed.approve_approval, _request(OWNER_KEY), session)

    requested["by"] = "phone:d-9"
    await _feed(feed.approve_approval, _request(device_id="d-9"), session)

    assert [c["resolved_by"] for c in calls] == ["owner", "phone:d-9"]


async def test_no_recorded_requester_means_no_self_approval_refusal(feed_calls):
    calls, requested, session = feed_calls
    requested["by"] = None
    await _feed(feed.approve_approval, _request(SERVICE_KEY), session)
    assert len(calls) == 1


class _Rows:
    """A session whose execute() answers from a queue of scalar results."""

    def __init__(self, *results):
        self._results = list(results)

    async def execute(self, _stmt):
        value = self._results.pop(0)
        return SimpleNamespace(scalar_one_or_none=lambda: value)


async def test_requested_by_is_read_from_the_approvals_task():
    task = str(uuid.uuid4())
    session = _Rows({"task_id": task}, {"requested_by": "service-key:abcd1234"})
    assert await feed._requested_by(session, "t", str(uuid.uuid4())) == "service-key:abcd1234"


async def test_a_task_fanned_out_from_a_plan_inherits_the_plans_requester():
    plan = str(uuid.uuid4())
    session = _Rows(
        {"task_id": str(uuid.uuid4())},
        {"origin": "plan_approval", "plan_task_id": plan},
        {"requested_by": "service-key:abcd1234"},
    )
    assert await feed._requested_by(session, "t", str(uuid.uuid4())) == "service-key:abcd1234"


async def test_an_approval_without_a_task_has_no_requester():
    assert await feed._requested_by(_Rows({"kind": "x"}), "t", str(uuid.uuid4())) is None
    assert await feed._requested_by(_Rows(None), "t", str(uuid.uuid4())) is None
    assert await feed._requested_by(_Rows(), "t", "not-a-uuid") is None


async def test_starting_a_dev_task_records_who_asked(monkeypatch):
    from life_graph.api import dependencies, drivers
    from life_graph.services.dev import tasks as dev_tasks

    seen: dict = {}

    class _Registry:
        async def get_by_id(self, _t, _p):
            return {"id": str(uuid.uuid4()), "name": "p", "is_active": True}

    class _Personas:
        async def get_by_name(self, _t, _n):
            return {"driver": "opencode", "is_active": True}

    async def fake_create(_factory, _tenant, **kw):
        seen.update(kw)
        return {"id": "t1"}

    monkeypatch.setattr(dependencies, "get_project_registry", lambda: _Registry())
    monkeypatch.setattr(dependencies, "get_persona_service", lambda: _Personas())
    monkeypatch.setattr(dev_tasks, "create_dev_task", fake_create)

    body = drivers.DevTaskCreate(instruction="fix the thing", project_id="p")
    await drivers.create_dev_task(body, _request(SERVICE_KEY))

    assert seen["properties"] == {"requested_by": _label(SERVICE_KEY)}


# ── safe-enablement evidence (counts only) ────────────────────────────────


def test_status_reports_counts_never_keys(monkeypatch):
    monkeypatch.setattr(settings, "approvals_require_owner", True)
    report = owner_enforcement.status(paired_devices=1)

    assert report["approvals_require_owner"] is True
    assert report["owner_keys_configured"] == 1
    assert report["non_owner_service_keys"] == 2
    assert report["owner_keys_not_accepted"] == 0
    assert report["lockout_risk"] is False
    text = repr(report)
    assert OWNER_KEY not in text and SERVICE_KEY not in text


async def test_startup_warns_when_enforcement_would_lock_everyone_out(monkeypatch, caplog):
    monkeypatch.setattr(settings, "approvals_require_owner", True)
    monkeypatch.setattr(settings, "owner_api_keys", "")

    async def no_devices(_session):
        return 0

    monkeypatch.setattr(owner_enforcement, "paired_device_count", no_devices)

    class _Factory:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *_a):
            return False

    with caplog.at_level(logging.WARNING, logger=owner_enforcement.__name__):
        report = await owner_enforcement.check_at_startup(lambda: _Factory())

    assert report["lockout_risk"] is True
    assert any("approvals_require_owner is on" in r.message for r in caplog.records)


async def test_startup_is_quiet_when_enforcement_is_off(monkeypatch, caplog):
    monkeypatch.setattr(settings, "owner_api_keys", "")

    def boom():
        raise AssertionError("no database query when enforcement is off")

    with caplog.at_level(logging.WARNING, logger=owner_enforcement.__name__):
        report = await owner_enforcement.check_at_startup(boom)

    assert report["lockout_risk"] is False
    assert not caplog.records
