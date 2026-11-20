"""Autonomy actions: an API request's rollback_command ran as host shell.

Found while fixing H2 (audit 2026-11-19). ``POST /autonomy/auto-actions``
stored ``rollback_command`` from any caller's body, and
``POST /auto-actions/{id}/rollback`` (and ``/audit/{id}/rollback``) ran it
through ``CommandExecutor`` (``create_subprocess_shell``) with no classifier
pass and no approval. Now only an owner-verified caller may attach one (403
otherwise), its sha256 is pinned in ``AutoAction.before_state`` at creation,
and rollback runs it only while that pin matches.

Only harmless commands are used; the executor is a mock.
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
from tests.unit.fakes import FakeSession

OWNER_KEY = "owner-key-0123456789"
SERVICE_KEY = "mcp-key-9876543210"


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setattr(settings, "api_key", None)
    monkeypatch.setattr(settings, "service_api_keys", f"{SERVICE_KEY},{OWNER_KEY}")
    monkeypatch.setattr(settings, "owner_api_keys", OWNER_KEY)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _autofix_service(session):
    from life_graph.autonomy.pipeline.service import AutoFixService

    svc = AutoFixService.__new__(AutoFixService)
    svc._session_factory = lambda: session
    svc._executor = MagicMock()
    svc._executor.execute = AsyncMock(
        return_value=SimpleNamespace(exit_code=0, stdout="", stderr="")
    )
    svc._audit_service = AsyncMock()
    svc._project_locks = {}
    return svc


def _request(**kw):
    from life_graph.autonomy.pipeline.schemas import AutoFixRequest

    return AutoFixRequest(
        agent_id="agent-x", project_id="p1", action_type="fix_lint", command="echo noop", **kw
    )


async def test_a_non_owner_cannot_attach_a_rollback_command():
    from life_graph.autonomy.pipeline.service import RollbackNotApprovedError

    session = FakeSession()
    with pytest.raises(RollbackNotApprovedError):
        await _autofix_service(session).process("t1", _request(rollback_command="echo undo"))
    assert session.added == []


async def test_the_route_refuses_a_rollback_command_from_a_service_key(monkeypatch):
    from life_graph.autonomy.pipeline import router

    service = _autofix_service(FakeSession())
    monkeypatch.setattr("life_graph.runtime.get_autofix_service", lambda: service)
    with tenant_scope("t1"), pytest.raises(HTTPException) as exc:
        await router.trigger_auto_action(
            _request(rollback_command="echo undo"), fake_request(api_key=SERVICE_KEY)
        )
    assert exc.value.status_code == 403


async def test_the_route_passes_the_owner_as_the_rollback_approver(monkeypatch):
    from life_graph.autonomy.pipeline import router

    seen = {}

    async def process(tenant_id, request, *, rollback_approved_by=None, api_caller=None):
        seen["by"] = rollback_approved_by
        seen["caller"] = api_caller
        raise RuntimeError("stop here")

    monkeypatch.setattr(
        "life_graph.runtime.get_autofix_service", lambda: SimpleNamespace(process=process)
    )
    with tenant_scope("t1"), pytest.raises(RuntimeError):
        await router.trigger_auto_action(
            _request(rollback_command="echo undo"), fake_request(api_key=OWNER_KEY)
        )
    assert seen["by"] == "owner:api_key"
    assert seen["caller"].label == "owner" and seen["caller"].is_owner


async def test_the_owner_attaches_a_rollback_command_and_it_is_pinned(monkeypatch):
    from life_graph.autonomy.pipeline.service import ROLLBACK_APPROVAL_KEY
    from life_graph.autonomy.safety import classifier as cls

    class _Classifier:
        def __init__(self, _session):
            pass

        async def classify(self, **_k):
            return SimpleNamespace(
                risk_level=cls.RiskLevel.MODERATE,
                recommendation=cls.Recommendation.QUEUE_FOR_APPROVAL,
                autonomy_level="L0",
                matched_rule=None,
                reasoning="test",
            )

    from tests.unit.fakes import FakeResult

    monkeypatch.setattr(cls, "ActionClassifier", _Classifier)
    session = FakeSession()
    svc = _autofix_service(session)
    svc._queue_for_approval = AsyncMock()

    async def execute(_stmt, *_a, **_k):  # the re-read returns the row just added
        return FakeResult([session.added[0]])

    session.execute = execute
    await svc.process(
        "t1", _request(rollback_command="echo undo"), rollback_approved_by="owner:api_key"
    )
    (action,) = session.added
    pin = action.before_state[ROLLBACK_APPROVAL_KEY]
    assert pin["sha256"] == _sha("echo undo")
    assert pin["approved_by"] == "owner:api_key"
    assert action.is_reversible is True


def _executed_action(rollback_command: str, before_state):
    from life_graph.autonomy.models import AutoAction

    return AutoAction(
        id="a1",
        tenant_id="t1",
        agent_id="agent-x",
        project_id="p1",
        action_name="fix_lint",
        action_command="echo noop",
        trigger_type="manual",
        trigger_detail="test",
        status="success",
        is_reversible=True,
        rollback_command=rollback_command,
        before_state=before_state,
        created_at=datetime.now(UTC),
    )


@pytest.mark.parametrize("case", ["unpinned", "tampered"])
async def test_an_unpinned_or_tampered_rollback_does_not_run(case):
    from life_graph.autonomy.pipeline.service import RollbackNotApprovedError

    # unpinned: created before this change. tampered: approved as "echo undo",
    # the row now says something else.
    before_state = (
        None
        if case == "unpinned"
        else {"rollback_approval": {"sha256": _sha("echo undo"), "approved_by": "owner:api_key"}}
    )
    action = _executed_action("echo pwned", before_state)
    svc = _autofix_service(FakeSession(action))
    with pytest.raises(RollbackNotApprovedError):
        await svc.rollback("t1", "a1")
    svc._executor.execute.assert_not_awaited()


async def test_a_pinned_rollback_runs():
    pin = {"rollback_approval": {"sha256": _sha("echo undo")}}
    action = _executed_action("echo undo", pin)
    svc = _autofix_service(FakeSession(action))
    await svc.rollback("t1", "a1")
    svc._executor.execute.assert_awaited_once()
    assert svc._executor.execute.await_args.kwargs["command"] == "echo undo"
