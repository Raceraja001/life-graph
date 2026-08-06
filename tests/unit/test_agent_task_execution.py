"""Unit tests for Phase B2 Task 3: ``_run_action`` agent_task execution.

Covers the EXECUTION side of open-ended agent work: when ``AutoFixService.
_run_action`` runs an ``AutoAction`` with ``kind == "agent_task"``, it must
dispatch through ``TaskDispatcher.dispatch_task`` (LocalDriver →
AgentOrchestrator, Governor budget gate, verifier chain) instead of the
command-path ``CommandExecutor``, and adapt the returned ``DriverResult``
into the same ``(exit_code, stdout, stderr, duration_ms)`` shape the command
path already persists onto the ``AutoAction``. The ``kind == "command"``
path must be completely unaffected — see
``test_run_action_command_path_unchanged``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.sql.dml import Update

from life_graph.autonomy.pipeline.executor import ExecutionResult
from life_graph.autonomy.pipeline.service import DEFAULT_AGENT_TASK_COST_CAP, AutoFixService
from life_graph.drivers.base import DriverResult


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

    Mirrors ``tests/unit/test_agent_task_routing.py``'s ``_FakeSession``:
    each test in this module only ever touches one ``AutoAction``, so WHERE
    clauses are ignored — UPDATE statements apply to (and SELECTs return)
    whatever row is currently in the box.
    """

    def __init__(self, box):
        self._box = box

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def commit(self):
        pass

    async def execute(self, stmt):
        action = self._box["action"]
        if isinstance(stmt, Update):
            for key, value in stmt.compile().params.items():
                if hasattr(action, key):
                    setattr(action, key, value)
        return _FakeResult(action)


def make_auto_action(
    *,
    kind: str = "command",
    instruction: str | None = None,
    action_command: str | None = "echo hi",
    agent_id: str = "ops",
    project_id: str = "ambient",
):
    """Build a bare object with the attributes ``_run_action`` reads/writes.

    A plain object (not MagicMock) so unset attributes fail loudly instead of
    silently returning a MagicMock — the audit-log call only reads
    attributes ``_run_action`` explicitly sets or takes from the action.
    """
    return MagicMock(
        id="a1",
        tenant_id="t1",
        kind=kind,
        instruction=instruction,
        action_command=action_command,
        action_name="cody_fix" if kind == "agent_task" else "restart",
        agent_id=agent_id,
        project_id=project_id,
        risk_level="moderate",
        started_at=None,
        completed_at=None,
        exit_code=None,
        stdout=None,
        stderr=None,
        duration_ms=None,
        status="pending",
    )


def _make_service(dispatcher):
    """Build a bare ``AutoFixService`` wired to ``dispatcher`` and a
    ``_FakeSession`` that mutates whatever ``AutoAction`` object
    ``_run_action`` is called with.

    The real ``_run_action`` persists via an ``UPDATE ... WHERE id ==``
    statement, not by mutating the in-memory object directly — so the fake
    session needs a live reference to that exact object to fake persistence
    onto it. The tests construct the ``AutoAction`` (via ``make_auto_action``)
    *after* the fixture runs, so ``_run_action`` itself is wrapped to seed the
    box with whichever action it's called with, right before delegating to
    the real implementation.
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
    svc._level_service = None
    svc._project_locks = {}
    svc._dispatcher = dispatcher

    real_run_action = AutoFixService._run_action

    async def _run_action_seeding(self, tenant_id, auto_action, timeout_seconds=60):
        box["action"] = auto_action
        return await real_run_action(self, tenant_id, auto_action, timeout_seconds)

    svc._run_action = _run_action_seeding.__get__(svc, AutoFixService)

    return svc


@pytest.fixture
def agent_task_service_with_dispatcher():
    """``AutoFixService`` wired to a mock dispatcher that succeeds."""
    disp = MagicMock()
    disp.dispatch_task = AsyncMock(
        return_value=DriverResult(
            success=True, output="done", cost_usd=0.4, duration_ms=1200,
        )
    )
    return _make_service(disp), disp


@pytest.fixture
def agent_task_service_with_dispatcher_failing():
    """``AutoFixService`` wired to a mock dispatcher that fails."""
    disp = MagicMock()
    disp.dispatch_task = AsyncMock(
        return_value=DriverResult(
            success=False, error="verify failed", cost_usd=0.2, duration_ms=800,
        )
    )
    return _make_service(disp), disp


@pytest.mark.asyncio
async def test_run_action_agent_task_dispatches(agent_task_service_with_dispatcher):
    svc, disp = agent_task_service_with_dispatcher
    auto = make_auto_action(
        kind="agent_task", instruction="Fix test X", action_command=None,
        agent_id="cody", project_id="ambient",
    )
    await svc._run_action("t1", auto, timeout_seconds=60)

    disp.dispatch_task.assert_awaited_once()
    kwargs = disp.dispatch_task.call_args.kwargs
    assert kwargs["instruction"] == "Fix test X"
    assert kwargs["persona_name"] == "cody"
    assert kwargs["interactive"] is False
    assert kwargs["task_id"] == "a1"
    assert kwargs["project_id"] == "ambient"
    assert kwargs["task_type"] == "general"
    assert kwargs["verify_chain"] == ["build_ok", "lint_clean"]
    assert kwargs["cost_cap_usd"] == DEFAULT_AGENT_TASK_COST_CAP

    assert auto.status == "success"
    assert auto.exit_code == 0
    assert auto.stdout == "done"
    assert auto.stderr == ""
    assert auto.duration_ms == 1200


@pytest.mark.asyncio
async def test_run_action_agent_task_failure_maps_exit_code_1(
    agent_task_service_with_dispatcher_failing,
):
    svc, disp = agent_task_service_with_dispatcher_failing
    auto = make_auto_action(kind="agent_task", instruction="X", action_command=None, agent_id="cody")
    await svc._run_action("t1", auto, timeout_seconds=60)

    assert auto.status == "failure"
    assert auto.exit_code == 1
    assert auto.stderr == "verify failed"


@pytest.mark.asyncio
async def test_run_action_command_path_unchanged(agent_task_service_with_dispatcher):
    svc, disp = agent_task_service_with_dispatcher
    auto = make_auto_action(kind="command", action_command="echo hi", instruction=None)
    await svc._run_action("t1", auto, timeout_seconds=60)

    disp.dispatch_task.assert_not_awaited()  # command path uses CommandExecutor
    svc._executor.execute.assert_awaited_once()
    assert auto.status == "success"
    assert auto.exit_code == 0
    assert auto.stdout == "ok"


@pytest.mark.asyncio
async def test_driver_result_to_fields_adapter():
    """Direct unit test of the adapter's mapping rules."""
    ok = DriverResult(success=True, output="hello", duration_ms=42)
    assert AutoFixService._driver_result_to_fields(ok) == (0, "hello", "", 42)

    bad = DriverResult(success=False, output="partial", error="boom", duration_ms=7)
    assert AutoFixService._driver_result_to_fields(bad) == (1, "partial", "boom", 7)

    bad_no_error = DriverResult(success=False, output="", duration_ms=3)
    assert AutoFixService._driver_result_to_fields(bad_no_error) == (1, "", "", 3)
