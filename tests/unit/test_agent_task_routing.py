"""Unit tests for Phase B2 routing: ``kind == "agent_task"`` always queues.

Covers decision B2-D2 — open-ended agent work never auto-executes, no matter
what the safety classifier recommends — and confirms the existing B1
command-kind routing (auto-execute when the classifier says so) is
unaffected by the override.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.sql.dml import Update

from life_graph.autonomy.pipeline.executor import ExecutionResult
from life_graph.autonomy.pipeline.schemas import AutoFixRequest
from life_graph.autonomy.pipeline.service import AutoFixService
from life_graph.autonomy.safety.classifier import ClassificationResult, Recommendation, RiskLevel


class _FakeResult:
    """Stand-in for a SQLAlchemy Result — both scalar accessors return the row."""

    def __init__(self, obj):
        self._obj = obj

    def scalar_one(self):
        return self._obj

    def scalar_one_or_none(self):
        return self._obj


class _FakeSession:
    """Async-context-manager session backed by a single-row box.

    Mirrors ``tests/unit/test_execute_pending.py``'s ``_FakeSession``: each
    test in this module only ever creates one ``AutoAction``, so WHERE
    clauses are ignored — UPDATE statements are applied to (and SELECTs
    return) whatever row is currently in the box.
    """

    def __init__(self, box):
        self._box = box

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    def add(self, obj):
        self._box["action"] = obj

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass

    async def execute(self, stmt):
        action = self._box["action"]
        if isinstance(stmt, Update):
            for key, value in stmt.compile().params.items():
                if hasattr(action, key):
                    setattr(action, key, value)
        return _FakeResult(action)


@pytest.fixture
def agent_task_autofix_service():
    """Build an ``AutoFixService`` whose classifier always recommends
    AUTO_EXECUTE, so the two tests can prove agent_task overrides it while
    command-kind is unaffected.
    """
    box: dict = {"action": None}
    session = _FakeSession(box)

    svc = AutoFixService.__new__(AutoFixService)
    svc._session_factory = lambda: session
    svc._executor = MagicMock()
    svc._executor.execute = AsyncMock(
        return_value=ExecutionResult(exit_code=0, stdout="ok", stderr="", duration_ms=5.0)
    )
    svc._audit_service = AsyncMock()
    svc._approval_service = AsyncMock()
    svc._approval_service.create = AsyncMock(return_value=MagicMock(id="appr-1"))
    svc._level_service = None
    svc._project_locks = {}

    classification = ClassificationResult(
        risk_level=RiskLevel.SAFE,
        recommendation=Recommendation.AUTO_EXECUTE,
        matched_rule=None,
        trust_score=1.0,
        autonomy_level="L1",
        reasoning={},
    )
    fake_classifier = MagicMock()
    fake_classifier.classify = AsyncMock(return_value=classification)

    mocks = {
        "executor": svc._executor,
        "approval_service": svc._approval_service,
        "audit_service": svc._audit_service,
    }

    with (
        patch(
            "life_graph.autonomy.safety.classifier.ActionClassifier",
            return_value=fake_classifier,
        ),
        patch("life_graph.autonomy.pipeline.service.shadow_service") as shadow_mock,
        patch("life_graph.autonomy.pipeline.service.event_bus") as bus_mock,
    ):
        shadow_mock.intercept = AsyncMock(return_value=MagicMock(shadow=False, enrollment_id=None))
        bus_mock.emit = AsyncMock()

        def _tracking_add(obj):
            mocks["saved_auto_action"] = obj
            box["action"] = obj

        session.add = _tracking_add

        yield svc, mocks


@pytest.mark.asyncio
async def test_agent_task_always_queues_even_when_classifier_says_auto(
    agent_task_autofix_service,
):
    svc, mocks = agent_task_autofix_service  # fixture: classifier -> AUTO_EXECUTE
    req = AutoFixRequest(
        agent_id="cody",
        project_id="ambient",
        action_type="cody_fix",
        kind="agent_task",
        instruction="Fix failing test X",
    )
    resp = await svc.process("t1", req)
    assert resp.routing == "queued_for_approval"
    # the executor / dispatcher must NOT have run
    mocks["executor"].execute.assert_not_called()
    # persisted kind + instruction
    saved = mocks["saved_auto_action"]
    assert saved.kind == "agent_task"
    assert saved.instruction == "Fix failing test X"
    assert saved.action_command is None


@pytest.mark.asyncio
async def test_command_action_routing_unchanged(agent_task_autofix_service):
    svc, mocks = agent_task_autofix_service  # classifier -> AUTO_EXECUTE
    req = AutoFixRequest(
        agent_id="ops",
        project_id="ambient",
        action_type="restart",
        command="docker restart x",
    )  # kind defaults 'command'
    resp = await svc.process("t1", req)
    assert resp.routing == "auto_executed"  # B1 behavior preserved
    mocks["executor"].execute.assert_called_once()
    saved = mocks["saved_auto_action"]
    assert saved.kind == "command"
    assert saved.instruction is None
    assert saved.action_command == "docker restart x"
