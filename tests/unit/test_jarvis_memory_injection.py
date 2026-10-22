"""Jarvis gets the owner's memories on a personal (local) run, never on a cloud run."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from life_graph.core.task_context import set_task_context
from life_graph.kernel.process_manager import ProcessManager

seen: dict = {}


async def _fake_run(self, messages, system_prompt=None, tools=None):
    seen["system_prompt"] = system_prompt or ""
    seen["model"] = self.model
    yield 'data: {"type": "token", "content": "ok"}\n\n'
    yield 'data: {"type": "done", "model": "m"}\n\n'


async def _run(message: str, persona: dict) -> None:
    root = uuid.uuid4()
    mgr = ProcessManager.__new__(ProcessManager)  # bypass __init__/DI
    set_task_context(task_id=root, tenant_id="t1", root_task_id=root, depth=0)
    calls = []

    async def fake_block(tenant_id, msg, history=None):
        calls.append((tenant_id, msg))
        return "## What you remember about the owner\n- MEMORY-MARKER"

    with (
        patch("life_graph.agents.orchestrator.AgentOrchestrator.run", _fake_run),
        patch("life_graph.services.memory_context.memory_block", fake_block),
    ):
        await mgr._run_agent("t1", "jarvis", {"message": message}, persona)
    seen["calls"] = calls


@pytest.mark.asyncio
async def test_a_personal_request_starts_with_the_owners_memories():
    await _run("personal: when does my car insurance renew?", {"allowed_tools": None})
    assert "MEMORY-MARKER" in seen["system_prompt"]
    assert seen["calls"] == [("t1", "when does my car insurance renew?")]


@pytest.mark.asyncio
async def test_a_cloud_request_never_sees_them():
    await _run(
        "cloud: what is the capital of Peru?", {"allowed_tools": None, "model": "openrouter/x/y"}
    )
    assert "MEMORY-MARKER" not in seen["system_prompt"]
    assert seen["calls"] == []
