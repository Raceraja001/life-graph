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
                "test_tenant", "test_persona",
                {"message": "hi"}, persona,
            )

        tool_names = {
            t["function"]["name"] for t in captured_kwargs["tools"]
        }
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
                "test_tenant", "chief",
                {"message": "hi"}, persona,
            )

        assert captured_kwargs["tools"] is None
