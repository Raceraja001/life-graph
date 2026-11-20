"""Autonomy trust boundaries (quality phase 2, batch 2a — P0).

Found while fixing H2 (#294), recorded in
docs/operations-log/2026-11-20-quality-phase2.md "Discovered during the batch":

1. ``POST /autonomy/auto-actions`` took the main ``command`` from any service
   key, and the classifier could auto-execute it as a host shell at L1-L3.
   The ``agent_id`` whose trust drove that came from the body, so a caller
   could borrow another agent's trust. Now a non-owner caller acts as itself
   (its server-derived label), its action always waits for approval, and the
   command is pinned by sha256 and re-checked before it runs.
2. ``POST /autonomy/trust/override`` took ``by`` from the body and was open to
   any key; now owner only, ``by`` is the server's.
3. ``POST /autonomy/levels/{id}/set``: owner only, ``set_by`` is the server's.
4. ``POST /autonomy/approvals/batch`` with no filter resolved every pending
   entry; now it needs a filter or ``all: true``.
5. The autonomy queue had no ``requested_by``: a caller could approve its own
   entry there (and through its mirror in the unified feed).
6. Other autonomy writes that loosen what runs on its own (safety rules,
   resuming after the kill switch, grading shadow runs, running a rollback)
   were open to any key; now owner only.

Only harmless commands are used; the executor is always a mock.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from life_graph.config import settings
from life_graph.core.tenant import tenant_scope
from tests.conftest import fake_request
from tests.unit.fakes import FakeResult, FakeSession

OWNER_KEY = "owner-key-0123456789"
SERVICE_KEY = "mcp-key-9876543210"
SERVICE_LABEL = f"service-key:{hashlib.sha256(SERVICE_KEY.encode()).hexdigest()[:8]}"


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setattr(settings, "api_key", None)
    monkeypatch.setattr(settings, "service_api_keys", f"{SERVICE_KEY},{OWNER_KEY}")
    monkeypatch.setattr(settings, "owner_api_keys", OWNER_KEY)
    monkeypatch.setattr(settings, "approvals_require_owner", False)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# ── 1. POST /autonomy/auto-actions ────────────────────────────


def _autofix_service(session):
    from life_graph.autonomy.pipeline.service import AutoFixService

    svc = AutoFixService.__new__(AutoFixService)
    svc._session_factory = lambda: session
    svc._executor = MagicMock()
    svc._executor.execute = AsyncMock(
        return_value=SimpleNamespace(exit_code=0, stdout="", stderr="", duration_ms=1)
    )
    svc._audit_service = AsyncMock()
    svc._level_service = None
    svc._project_locks = {}
    return svc


def _request(**kw):
    from life_graph.autonomy.pipeline.schemas import AutoFixRequest

    fields = {
        "agent_id": "cody",
        "project_id": "p1",
        "action_type": "fix_lint",
        "command": "echo noop",
    }
    fields.update(kw)
    return AutoFixRequest(**fields)


@pytest.fixture
def classified(monkeypatch):
    """The classifier says AUTO_EXECUTE (a trusted agent at L1+) unless told otherwise."""
    from life_graph.autonomy.safety import classifier as cls

    seen: dict = {"recommendation": cls.Recommendation.AUTO_EXECUTE}

    class _Classifier:
        def __init__(self, _session):
            pass

        async def classify(self, **kw):
            seen["agent_id"] = kw["agent_id"]
            return SimpleNamespace(
                risk_level=cls.RiskLevel.SAFE,
                recommendation=seen["recommendation"],
                autonomy_level="L3",
                matched_rule=None,
                reasoning="test",
            )

    monkeypatch.setattr(cls, "ActionClassifier", _Classifier)
    from life_graph.autonomy.pipeline import service as pipeline_service

    shadow = SimpleNamespace(intercept=AsyncMock(return_value=SimpleNamespace(shadow=False)))
    monkeypatch.setattr(pipeline_service, "shadow_service", shadow)
    seen["shadow"] = shadow
    return seen


def _routing_service():
    session = FakeSession()

    async def execute(_stmt, *_a, **_k):  # the re-read returns the row just added
        return FakeResult([session.added[0]])

    session.execute = execute
    svc = _autofix_service(session)
    svc._auto_execute = AsyncMock()
    svc._notify_before_execute = AsyncMock()
    svc._queue_for_approval = AsyncMock()
    svc._record_shadow = AsyncMock()
    return svc, session


def _service_key_caller():
    from life_graph.autonomy.pipeline.service import ApiCaller

    return ApiCaller(label=SERVICE_LABEL, is_owner=False)


async def test_a_service_key_command_is_queued_never_auto_executed(classified):
    svc, _ = _routing_service()
    result = await svc.process("t1", _request(), api_caller=_service_key_caller())

    assert result.routing == "queued_for_approval"
    svc._auto_execute.assert_not_awaited()
    svc._executor.execute.assert_not_awaited()
    svc._queue_for_approval.assert_awaited_once()
    assert svc._queue_for_approval.await_args.kwargs["requested_by"] == SERVICE_LABEL


async def test_a_service_key_command_never_takes_the_notify_then_auto_approve_path(classified):
    from life_graph.autonomy.safety.classifier import Recommendation

    classified["recommendation"] = Recommendation.NOTIFY_BEFORE
    svc, _ = _routing_service()
    result = await svc.process("t1", _request(), api_caller=_service_key_caller())

    assert result.routing == "queued_for_approval"
    svc._notify_before_execute.assert_not_awaited()


async def test_a_service_key_cannot_borrow_another_agents_trust(classified):
    from life_graph.autonomy.pipeline.service import REQUEST_KEY

    svc, session = _routing_service()
    await svc.process("t1", _request(agent_id="cody"), api_caller=_service_key_caller())

    # The classifier read the caller's own trust, not cody's.
    assert classified["agent_id"] == SERVICE_LABEL
    (action,) = session.added
    assert action.agent_id == SERVICE_LABEL
    # The name the body gave is kept, unverified, for the record.
    assert action.before_state[REQUEST_KEY] == {
        "requested_by": SERVICE_LABEL,
        "claimed_agent_id": "cody",
    }


async def test_the_owner_keeps_auto_execute_and_may_name_the_agent(classified):
    from life_graph.autonomy.pipeline.service import ApiCaller

    svc, session = _routing_service()
    result = await svc.process(
        "t1", _request(agent_id="cody"), api_caller=ApiCaller(label="owner", is_owner=True)
    )

    assert result.routing == "auto_executed"
    svc._auto_execute.assert_awaited_once()
    assert classified["agent_id"] == "cody"
    assert session.added[0].agent_id == "cody"


async def test_an_in_process_producer_keeps_auto_execute(classified):
    # services/action_proposal_bridge.py calls process() with no api_caller,
    # under the ops agent's own server-set agent_id.
    svc, session = _routing_service()
    result = await svc.process("t1", _request(agent_id="ops"))

    assert result.routing == "auto_executed"
    assert classified["agent_id"] == "ops"
    classified["shadow"].intercept.assert_awaited_once_with("t1", "ops")


async def test_every_command_is_pinned_at_creation(classified):
    from life_graph.autonomy.pipeline.service import COMMAND_APPROVAL_KEY

    svc, session = _routing_service()
    await svc.process("t1", _request(command="echo hello"), api_caller=_service_key_caller())

    pin = session.added[0].before_state[COMMAND_APPROVAL_KEY]
    assert pin["sha256"] == _sha("echo hello")
    assert pin["requested_by"] == SERVICE_LABEL


async def test_the_route_passes_the_server_derived_caller(monkeypatch):
    from life_graph.autonomy.pipeline import router

    seen = []

    async def process(tenant_id, request, *, rollback_approved_by=None, api_caller=None):
        seen.append(api_caller)
        raise RuntimeError("stop here")

    monkeypatch.setattr(
        "life_graph.runtime.get_autofix_service", lambda: SimpleNamespace(process=process)
    )
    for key in (SERVICE_KEY, OWNER_KEY):
        with tenant_scope("t1"), pytest.raises(RuntimeError):
            await router.trigger_auto_action(_request(), fake_request(api_key=key))

    assert (seen[0].label, seen[0].is_owner) == (SERVICE_LABEL, False)
    assert (seen[1].label, seen[1].is_owner) == ("owner", True)


def _pending_command(command: str, before_state):
    return MagicMock(
        id="a1",
        tenant_id="t1",
        kind="command",
        action_command=command,
        instruction=None,
        action_name="fix_lint",
        agent_id="ops",
        project_id="p1",
        risk_level="safe",
        status="pending",
        before_state=before_state,
    )


@pytest.fixture
def not_paused(monkeypatch):
    monkeypatch.setattr(
        "life_graph.autonomy.kill_switch.is_autonomy_paused", AsyncMock(return_value=False)
    )


@pytest.mark.parametrize("case", ["unpinned", "tampered"])
async def test_an_unpinned_or_changed_command_does_not_run(not_paused, case):
    from life_graph.autonomy.pipeline.service import COMMAND_NOT_PINNED

    before_state = None if case == "unpinned" else {"command_approval": {"sha256": _sha("true")}}
    session = FakeSession()
    svc = _autofix_service(session)

    status, exit_code = await svc._run_action("t1", _pending_command("echo pwned", before_state))

    assert (status, exit_code) == ("failure", 1)
    svc._executor.execute.assert_not_awaited()
    (stmt,) = session.statements
    assert stmt.compile().params["error_message"] == COMMAND_NOT_PINNED


async def test_a_pinned_command_runs(not_paused):
    svc = _autofix_service(FakeSession())
    pin = {"command_approval": {"sha256": _sha("true")}}

    status, _ = await svc._run_action("t1", _pending_command("true", pin))

    assert status == "success"
    svc._executor.execute.assert_awaited_once()
    assert svc._executor.execute.await_args.kwargs["command"] == "true"


# ── 2. POST /autonomy/trust/override ──────────────────────────


def _override_body(**kw):
    from life_graph.autonomy.trust.schemas import TrustOverrideRequest

    fields = {"agent_id": "cody", "action_type": "fix_lint", "score": 1.0, "reason": "trusted"}
    fields.update(kw)
    return TrustOverrideRequest(**fields)


async def test_a_service_key_cannot_override_trust(monkeypatch):
    from life_graph.autonomy.trust import router

    override = AsyncMock()
    monkeypatch.setattr(router, "TrustScoreService", lambda _s: SimpleNamespace(override=override))
    with pytest.raises(HTTPException) as exc:
        await router.override_trust(
            _override_body(by="owner"),
            fake_request(api_key=SERVICE_KEY),
            session=FakeSession(),
            tenant_id="t1",
        )
    assert exc.value.status_code == 403
    override.assert_not_awaited()


async def test_the_owner_overrides_trust_and_by_is_the_servers(monkeypatch):
    from life_graph.autonomy.trust import router

    override = AsyncMock(return_value=SimpleNamespace())
    monkeypatch.setattr(router, "TrustScoreService", lambda _s: SimpleNamespace(override=override))
    monkeypatch.setattr(router, "TrustScoreResponse", SimpleNamespace(model_validate=lambda s: {}))
    await router.override_trust(
        _override_body(by="someone-else"),
        fake_request(api_key=OWNER_KEY),
        session=FakeSession(),
        tenant_id="t1",
    )
    kwargs = override.await_args.kwargs
    assert kwargs["by"] == "owner"
    assert kwargs["reason"] == "trusted\n(client said: someone-else)"


# ── 3. POST /autonomy/levels/{id}/set ─────────────────────────


def _level_service(monkeypatch):
    from life_graph.autonomy.levels import router

    set_manual = AsyncMock(return_value=3)
    monkeypatch.setattr(
        "life_graph.runtime.get_autonomy_level_service",
        lambda: SimpleNamespace(set_manual=set_manual),
    )
    monkeypatch.setattr(router, "_level_payload", AsyncMock(return_value={}))
    return router, set_manual


async def test_a_service_key_cannot_set_an_autonomy_level(monkeypatch):
    from life_graph.autonomy.levels.schemas import SetLevelRequest

    router, set_manual = _level_service(monkeypatch)
    with tenant_scope("t1"), pytest.raises(HTTPException) as exc:
        await router.set_autonomy_level(
            "p1",
            SetLevelRequest(level=3, reason="go full auto", set_by="owner"),
            fake_request(api_key=SERVICE_KEY),
        )
    assert exc.value.status_code == 403
    set_manual.assert_not_awaited()


async def test_the_owner_sets_a_level_and_set_by_is_the_servers(monkeypatch):
    from life_graph.autonomy.levels.schemas import SetLevelRequest

    router, set_manual = _level_service(monkeypatch)
    with tenant_scope("t1"):
        await router.set_autonomy_level(
            "p1", SetLevelRequest(level=3, reason="go full auto"), fake_request(device_id="d-1")
        )
    assert set_manual.await_args.kwargs["by"] == "phone:d-1"


# ── 4. POST /autonomy/approvals/batch ─────────────────────────


def _batch_service(monkeypatch):
    batch = AsyncMock(return_value={"resolved_count": 0, "resolved_ids": []})
    monkeypatch.setattr(
        "life_graph.runtime.get_approval_service",
        lambda: SimpleNamespace(
            batch_resolve=batch,
            match_pending=AsyncMock(return_value=[]),
            pending_feed_copies=AsyncMock(return_value={}),
        ),
    )
    return batch


async def test_a_batch_with_no_filter_is_refused(monkeypatch):
    from life_graph.autonomy.approvals import router
    from life_graph.autonomy.approvals.schemas import BatchResolveRequest

    batch = _batch_service(monkeypatch)
    with tenant_scope("t1"), pytest.raises(HTTPException) as exc:
        await router.batch_resolve(
            BatchResolveRequest(decision="approve"), fake_request(api_key=OWNER_KEY)
        )
    assert exc.value.status_code == 422
    batch.assert_not_awaited()


async def test_all_true_resolves_every_pending_entry(monkeypatch):
    from life_graph.autonomy.approvals import router
    from life_graph.autonomy.approvals.schemas import BatchResolveRequest

    batch = _batch_service(monkeypatch)
    with tenant_scope("t1"):
        await router.batch_resolve(
            BatchResolveRequest(decision="reject", all=True), fake_request(api_key=OWNER_KEY)
        )
    batch.assert_awaited_once()


async def test_an_empty_id_list_resolves_nothing():
    from life_graph.autonomy.approvals.service import ApprovalService
    from tests.unit.fakes import sql

    session = FakeSession([])
    result = await ApprovalService(lambda: session).batch_resolve(
        "t1", {"approval_ids": []}, "approve", None, "owner"
    )
    assert result == {"resolved_count": 0, "resolved_ids": []}
    # The empty list became a filter (matching nothing), not "no filter".
    assert "approval_queue.id IN" in sql(session.statements[0])


# ── 5. requested_by and self-approval on the autonomy queue ───


def _entry(requested_by):
    return SimpleNamespace(id="q1", status="pending", requested_by=requested_by)


async def test_the_queue_records_who_asked():
    from life_graph.autonomy.approvals.service import ApprovalService

    session = FakeSession()
    await ApprovalService(lambda: session).create(
        "t1",
        {
            "agent_id": SERVICE_LABEL,
            "action_name": "fix_lint",
            "action_command": "echo noop",
            "requested_by": SERVICE_LABEL,
        },
    )
    assert session.added[0].requested_by == SERVICE_LABEL


def _real_approval_service(monkeypatch, *results):
    from life_graph.autonomy.approvals.service import ApprovalService

    session = FakeSession(*results)
    service = ApprovalService(lambda: session)
    monkeypatch.setattr("life_graph.runtime.get_approval_service", lambda: service)
    return session


async def test_a_caller_cannot_resolve_its_own_queue_entry(monkeypatch):
    from sqlalchemy.sql.dml import Update

    from life_graph.autonomy.approvals import router
    from life_graph.autonomy.approvals.schemas import ResolveRequest

    # Results in order: the router's feed-copy lookup (none), the service's
    # feed-copy lock (none), then the entry itself.
    session = _real_approval_service(monkeypatch, [], [], _entry(SERVICE_LABEL))
    with tenant_scope("t1"), pytest.raises(HTTPException) as exc:
        await router.resolve_approval(
            "q1", ResolveRequest(decision="approve"), fake_request(api_key=SERVICE_KEY)
        )
    assert exc.value.status_code == 403
    assert session.commits == 0
    assert not [s for s in session.statements if isinstance(s, Update)]  # lookups only


@pytest.mark.parametrize(
    ("requested_by", "request_kw"),
    [
        (SERVICE_LABEL, {"api_key": OWNER_KEY}),  # the owner is never refused
        ("service-key:other000", {"api_key": SERVICE_KEY}),  # someone else's entry
        (None, {"api_key": SERVICE_KEY}),  # not recorded: nothing refused
    ],
)
async def test_resolving_someone_elses_or_an_unrecorded_entry_is_allowed(
    monkeypatch, requested_by, request_kw
):
    from life_graph.autonomy.approvals import router
    from life_graph.autonomy.approvals.schemas import ResolveRequest

    # The router's feed-copy lookup, the service's feed-copy lock, the entry,
    # then the writes.
    session = _real_approval_service(monkeypatch, [], [], _entry(requested_by), [], [])
    with tenant_scope("t1"):
        await router.resolve_approval(
            "q1", ResolveRequest(decision="approve"), fake_request(**request_kw)
        )
    assert session.commits == 1


async def test_a_batch_that_includes_the_callers_own_entry_resolves_nothing(monkeypatch):
    from life_graph.autonomy.approvals import router
    from life_graph.autonomy.approvals.schemas import BatchResolveRequest

    session = _real_approval_service(monkeypatch, [_entry(None), _entry(SERVICE_LABEL)])
    with tenant_scope("t1"), pytest.raises(HTTPException) as exc:
        await router.batch_resolve(
            BatchResolveRequest(decision="approve", project_id="p1"),
            fake_request(api_key=SERVICE_KEY),
        )
    assert exc.value.status_code == 403
    assert session.commits == 0
    assert len(session.statements) == 1


async def test_the_feed_mirror_of_a_queue_entry_knows_who_asked():
    # An autonomous_action feed row points at its queue entry; approving it at
    # POST /approvals/{id}/approve must see the same requested_by.
    import uuid

    from life_graph.api import approvals as feed

    session = FakeSession(
        {"auto_action_id": "a1", "approval_id": "q1", "kind": "command"}, SERVICE_LABEL
    )
    assert await feed._requested_by(session, "t1", str(uuid.uuid4())) == SERVICE_LABEL


# ── 6. other autonomy routes that loosen what runs on its own ──


def _owner_only_calls():
    from life_graph.autonomy.audit import router as audit
    from life_graph.autonomy.pipeline import router as pipeline
    from life_graph.autonomy.safety import router as safety
    from life_graph.autonomy.shadow import router as shadow

    s = FakeSession()
    return {
        "create rule": lambda r: safety.create_rule(None, r, session=s, tenant_id="t1"),
        "update rule": lambda r: safety.update_rule("x", None, r, session=s, tenant_id="t1"),
        "delete rule": lambda r: safety.delete_rule("x", r, session=s, tenant_id="t1"),
        "seed rules": lambda r: safety.seed_defaults(r, session=s, tenant_id="t1"),
        "resume": lambda r: safety.resume_kill_switch(r, session=s, tenant_id="t1"),
        "grade": lambda r: shadow.grade_run("x", None, r, tenant_id="t1"),
        "rollback": lambda r: pipeline.rollback_action("x", r),
        "audit rollback": lambda r: audit.rollback_from_audit("x", r),
    }


@pytest.mark.parametrize("name", list(_owner_only_calls()))
async def test_a_service_key_cannot_loosen_autonomy(name):
    with tenant_scope("t1"), pytest.raises(HTTPException) as exc:
        await _owner_only_calls()[name](fake_request(api_key=SERVICE_KEY))
    assert exc.value.status_code == 403


async def test_any_caller_may_still_pull_the_kill_switch():
    from life_graph.autonomy.safety import router as safety
    from life_graph.models.db import TenantConfig

    config = SimpleNamespace(autonomy_paused=False, autonomy_paused_at=None)
    session = FakeSession(objects={(TenantConfig, "t1"): config})
    await safety.pause_kill_switch(session=session, tenant_id="t1")
    assert config.autonomy_paused is True
    assert isinstance(config.autonomy_paused_at, datetime)
    assert config.autonomy_paused_at.tzinfo is UTC
