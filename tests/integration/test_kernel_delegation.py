"""Integration tests for delegation-tree tracking on spawned tasks
and the delegate_to_persona tool (added across Tasks 2, 3, 6)."""

import uuid

import pytest
import pytest_asyncio

import life_graph.tools.datetime_tool  # noqa: F401
from life_graph.api.dependencies import get_process_manager
from tests.integration.conftest import skip_on_db_error

TENANT_ID = "test_delegation_tenant"


class TestSpawnDelegationTree:
    """ProcessManager.spawn() root_task_id / depth / depth-cap behavior."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_spawn_without_parent_defaults_depth_zero(self):
        pm = get_process_manager()
        result = await pm.spawn(
            tenant_id=TENANT_ID,
            agent_name="chief",
            input_data={"message": "hello"},
        )
        task = await pm.get_task(TENANT_ID, result["task_id"])
        assert task is not None
        assert task.depth == 0
        assert task.root_task_id is None

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_spawn_with_parent_tracks_root_and_depth(self):
        pm = get_process_manager()
        root = await pm.spawn(
            tenant_id=TENANT_ID,
            agent_name="chief",
            input_data={"message": "root task"},
        )
        root_id = uuid.UUID(root["task_id"])

        child = await pm.spawn(
            tenant_id=TENANT_ID,
            agent_name="cody",
            input_data={"message": "child task"},
            parent_task_id=root_id,
            root_task_id=root_id,
            depth=1,
        )
        child_task = await pm.get_task(TENANT_ID, child["task_id"])
        assert child_task is not None
        assert child_task.parent_task_id == root_id
        assert child_task.root_task_id == root_id
        assert child_task.depth == 1

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_spawn_rejects_depth_past_cap(self):
        pm = get_process_manager()
        with pytest.raises(ValueError, match="Maximum delegation depth"):
            await pm.spawn(
                tenant_id=TENANT_ID,
                agent_name="cody",
                input_data={"message": "too deep"},
                depth=pm.MAX_DELEGATION_DEPTH + 1,
            )


from unittest.mock import AsyncMock, patch

from life_graph.kernel.process_manager import ProcessManager


class TestAllowedToolsEnforcement:
    """_run_agent() must filter tools by persona.allowed_tools."""

    @pytest.mark.asyncio
    async def test_run_agent_filters_tools_by_allowed_list(self):
        pm = ProcessManager(session_factory=None, persona_service=None)
        persona = {
            "model": "gemini/gemini-2.5-flash",
            "temperature": 0.5,
            "max_tokens": 1024,
            "system_prompt": "You are a test persona.",
            "allowed_tools": ["get_current_datetime"],
        }

        captured_kwargs = {}

        async def fake_run(self, messages, system_prompt=None, tools=None):
            captured_kwargs["tools"] = tools
            return
            yield  # pragma: no cover - makes this an async generator

        with patch(
            "life_graph.agents.orchestrator.AgentOrchestrator.run",
            fake_run,
        ):
            await pm._run_agent(
                "test_tenant",
                "test_persona",
                {"message": "hi"},
                persona,
            )

        tool_names = {t["function"]["name"] for t in captured_kwargs["tools"]}
        assert tool_names == {"get_current_datetime"}

    @pytest.mark.asyncio
    async def test_run_agent_passes_none_when_allowed_tools_unset(self):
        pm = ProcessManager(session_factory=None, persona_service=None)
        persona = {
            "model": "gemini/gemini-2.5-flash",
            "temperature": 0.5,
            "max_tokens": 1024,
            "system_prompt": "You are chief.",
            "allowed_tools": None,
        }

        captured_kwargs = {}

        async def fake_run(self, messages, system_prompt=None, tools=None):
            captured_kwargs["tools"] = tools
            return
            yield  # pragma: no cover

        with patch(
            "life_graph.agents.orchestrator.AgentOrchestrator.run",
            fake_run,
        ):
            await pm._run_agent(
                "test_tenant",
                "chief",
                {"message": "hi"},
                persona,
            )

        assert captured_kwargs["tools"] is None


import life_graph.tools.delegate  # noqa: F401 — ensure tool is registered for these tests
from life_graph.core.task_context import set_task_context
from life_graph.tools.registry import registry as tool_registry


class TestDelegateToPersonaTool:
    """The delegate_to_persona tool (life_graph/tools/delegate.py)."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_delegate_creates_linked_child_and_waits_for_result(self):
        pm = get_process_manager()
        root = await pm.spawn(
            tenant_id=TENANT_ID,
            agent_name="chief",
            input_data={"message": "root"},
        )
        root_id = root["task_id"]
        set_task_context(task_id=uuid.UUID(root_id), tenant_id=TENANT_ID)

        result_json = await tool_registry.execute(
            "delegate_to_persona",
            {
                "persona": "chief",
                "subtask": "say hello",
                "wait": True,
                "timeout_seconds": 5,
            },
        )
        import json

        result = json.loads(result_json)

        assert result["status"] in ("completed", "failed", "still_running")

        # Whatever the outcome, the child task must be correctly linked.
        tasks, _total, _has_more = await pm.list_tasks(TENANT_ID, agent_name="chief")
        child = next(
            (t for t in tasks if str(t.parent_task_id) == root_id),
            None,
        )
        assert child is not None
        assert str(child.root_task_id) == root_id
        assert child.depth == 1

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_delegate_to_unknown_persona_surfaces_error(self):
        pm = get_process_manager()
        root = await pm.spawn(
            tenant_id=TENANT_ID,
            agent_name="chief",
            input_data={"message": "root"},
        )
        set_task_context(
            task_id=uuid.UUID(root["task_id"]),
            tenant_id=TENANT_ID,
        )

        result_json = await tool_registry.execute(
            "delegate_to_persona",
            {"persona": "nonexistent_persona_xyz", "subtask": "do it"},
        )
        import json

        result = json.loads(result_json)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_delegate_outside_task_context_returns_error(self):
        # No set_task_context call — simulates a stray/direct call.
        from life_graph.core.task_context import _task_context_var

        token = _task_context_var.set(None)
        try:
            result_json = await tool_registry.execute(
                "delegate_to_persona",
                {"persona": "chief", "subtask": "do it"},
            )
            import json

            result = json.loads(result_json)
            assert "error" in result
            assert "task context" in result["error"].lower()
        finally:
            _task_context_var.reset(token)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_delegate_rejects_past_depth_cap(self):
        pm = get_process_manager()
        root = await pm.spawn(
            tenant_id=TENANT_ID,
            agent_name="chief",
            input_data={"message": "root"},
            depth=ProcessManager.MAX_DELEGATION_DEPTH,
        )
        set_task_context(
            task_id=uuid.UUID(root["task_id"]),
            tenant_id=TENANT_ID,
        )

        result_json = await tool_registry.execute(
            "delegate_to_persona",
            {"persona": "chief", "subtask": "one too deep"},
        )
        import json

        result = json.loads(result_json)
        assert "error" in result
        assert "delegation depth" in result["error"].lower()
