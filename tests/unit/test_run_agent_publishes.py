"""_run_agent must publish each orchestrator event to the session bus."""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from life_graph.core.task_context import set_task_context
from life_graph.kernel.process_manager import ProcessManager
from life_graph.services.chat_stream import get_chat_stream_bus


async def _fake_run(self, messages, system_prompt=None, tools=None):
    yield 'data: {"type": "token", "content": "he"}\n\n'
    yield 'data: {"type": "token", "content": "llo"}\n\n'
    yield 'data: {"type": "done", "model": "m"}\n\n'


@pytest.mark.asyncio
async def test_run_agent_publishes_events_to_bus():
    root = uuid.uuid4()
    mgr = ProcessManager.__new__(ProcessManager)  # bypass __init__/DI
    set_task_context(task_id=root, tenant_id="t1", root_task_id=root, depth=0)

    with patch("life_graph.agents.orchestrator.AgentOrchestrator.run", _fake_run):
        result = await mgr._run_agent(
            "t1", "jarvis", {"message": "hi"}, {"allowed_tools": None}
        )

    assert result["response"] == "hello"
    published = list(get_chat_stream_bus()._buffers[str(root)])
    types = [p["event"]["type"] for p in published]
    assert types == ["token", "token", "done"]
    assert all(p["agent_name"] == "jarvis" and p["depth"] == 0 for p in published)
