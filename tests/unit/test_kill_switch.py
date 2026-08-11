# tests/unit/test_kill_switch.py
"""Unit tests for the autonomy kill-switch: is_autonomy_paused()'s fail-closed
cache behavior, and AutoFixService._run_action()'s guard (the single choke
point every execution path — classify-time auto-execute and post-approval
execute_pending — funnels through)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.sql.dml import Update

from life_graph.autonomy import kill_switch
from life_graph.autonomy.pipeline.executor import ExecutionResult
from life_graph.autonomy.pipeline.service import AutoFixService

# ── is_autonomy_paused() ────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_kill_switch_cache():
    kill_switch._pause_cache.clear()
    yield
    kill_switch._pause_cache.clear()


class _FakeConfigSession:
    def __init__(self, config):
        self._config = config

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def get(self, model, tenant_id):
        return self._config


@pytest.mark.asyncio
async def test_is_autonomy_paused_true_when_flag_set():
    config = SimpleNamespace(autonomy_paused=True)
    with patch(
        "life_graph.storage.database.async_session",
        return_value=_FakeConfigSession(config),
    ):
        assert await kill_switch.is_autonomy_paused("t1") is True


@pytest.mark.asyncio
async def test_is_autonomy_paused_false_when_flag_unset():
    config = SimpleNamespace(autonomy_paused=False)
    with patch(
        "life_graph.storage.database.async_session",
        return_value=_FakeConfigSession(config),
    ):
        assert await kill_switch.is_autonomy_paused("t1") is False


@pytest.mark.asyncio
async def test_is_autonomy_paused_fails_closed_on_missing_tenant_config():
    with patch(
        "life_graph.storage.database.async_session",
        return_value=_FakeConfigSession(None),
    ):
        assert await kill_switch.is_autonomy_paused("no-such-tenant") is True


@pytest.mark.asyncio
async def test_is_autonomy_paused_fails_closed_on_db_error():
    class _RaisingSession:
        async def __aenter__(self):
            raise RuntimeError("db unavailable")

        async def __aexit__(self, *exc_info):
            return False

    with patch(
        "life_graph.storage.database.async_session",
        return_value=_RaisingSession(),
    ):
        assert await kill_switch.is_autonomy_paused("t1") is True


@pytest.mark.asyncio
async def test_is_autonomy_paused_uses_cache_within_ttl():
    config = SimpleNamespace(autonomy_paused=False)
    session = _FakeConfigSession(config)
    with patch(
        "life_graph.storage.database.async_session", return_value=session
    ) as mock_session_factory:
        await kill_switch.is_autonomy_paused("t1")
        await kill_switch.is_autonomy_paused("t1")
    assert mock_session_factory.call_count == 1  # second call hit the cache


def test_invalidate_autonomy_pause_cache_drops_entry():
    kill_switch._pause_cache["t1"] = (999999999999.0, False)
    kill_switch.invalidate_autonomy_pause_cache("t1")
    assert "t1" not in kill_switch._pause_cache


# ── AutoFixService._run_action() guard ──────────────────────────


class _FakeResult:
    def __init__(self, action):
        self._action = action

    def scalar_one_or_none(self):
        return self._action

    def scalar_one(self):
        return self._action


class _FakeSession:
    def __init__(self, action):
        self._action = action

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def execute(self, stmt):
        if isinstance(stmt, Update):
            for key, value in stmt.compile().params.items():
                if hasattr(self._action, key):
                    setattr(self._action, key, value)
        return _FakeResult(self._action)

    async def commit(self):
        pass


def _make_service(action):
    svc = AutoFixService.__new__(AutoFixService)
    svc._session_factory = lambda: _FakeSession(action)
    svc._executor = MagicMock()
    svc._executor.execute = AsyncMock(
        return_value=ExecutionResult(exit_code=0, stdout="ok", stderr="", duration_ms=12.0)
    )
    svc._audit_service = AsyncMock()
    svc._level_service = None
    svc._project_locks = {}
    return svc


def _fake_pending_action():
    return MagicMock(
        id="a1",
        tenant_id="t1",
        status="pending",
        kind="command",
        action_command="echo hi",
        instruction=None,
        action_name="restart",
        rollback_command=None,
        trigger_type="manual",
        trigger_detail="restart",
        project_id="ambient",
        agent_id="ops",
        risk_level="moderate",
        approval_id=None,
        started_at=None,
        completed_at=None,
        created_at=datetime.now(UTC),
        exit_code=None,
        stdout=None,
        stderr=None,
        error_message=None,
        duration_ms=None,
    )


@pytest.mark.asyncio
async def test_run_action_blocked_when_paused():
    action = _fake_pending_action()
    svc = _make_service(action)

    with patch(
        "life_graph.autonomy.kill_switch.is_autonomy_paused", AsyncMock(return_value=True)
    ):
        status, exit_code = await svc._run_action("t1", action)

    svc._executor.execute.assert_not_awaited()
    assert status == "failure"
    assert exit_code == 1
    assert action.status == "failure"
    assert "kill-switch" in action.error_message
    svc._audit_service.log_auto_execute.assert_awaited_once()
    assert svc._audit_service.log_auto_execute.await_args.kwargs["result"] == "failure"


@pytest.mark.asyncio
async def test_run_action_proceeds_when_not_paused():
    action = _fake_pending_action()
    svc = _make_service(action)

    with patch(
        "life_graph.autonomy.kill_switch.is_autonomy_paused", AsyncMock(return_value=False)
    ):
        status, exit_code = await svc._run_action("t1", action)

    svc._executor.execute.assert_awaited_once()
    assert status == "success"
    assert exit_code == 0


@pytest.mark.asyncio
async def test_execute_pending_blocked_when_paused():
    """The kill-switch must also block the post-approval path, not just
    classify-time auto-execute -- execute_pending() never re-classifies, so
    _run_action is the only remaining choke point for approved actions."""
    action = _fake_pending_action()
    svc = _make_service(action)

    with (
        patch("life_graph.autonomy.pipeline.service.event_bus") as bus,
        patch(
            "life_graph.autonomy.kill_switch.is_autonomy_paused", AsyncMock(return_value=True)
        ),
    ):
        bus.emit = AsyncMock()
        resp = await svc.execute_pending("t1", "a1")

    svc._executor.execute.assert_not_awaited()
    assert resp.status == "failure"
