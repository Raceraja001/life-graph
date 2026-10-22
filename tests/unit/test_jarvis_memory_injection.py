"""Jarvis gets the owner's memories on a personal (local) run, never on a cloud run;
what changes per request sits just before the user's message, never in the
system prompt (so Ollama can reuse the cached start of the prompt)."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from life_graph.core.task_context import set_task_context
from life_graph.kernel.process_manager import ProcessManager

seen: dict = {}


async def _fake_run(self, messages, system_prompt=None, tools=None):
    seen["system_prompt"] = system_prompt or ""
    seen["messages"] = list(messages)
    seen["model"] = self.model
    yield 'data: {"type": "token", "content": "ok"}\n\n'
    yield 'data: {"type": "done", "model": "m"}\n\n'


async def _run(message: str, persona: dict) -> dict:
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
        result = await mgr._run_agent("t1", "jarvis", {"message": message}, persona)
    seen["calls"] = calls
    return result


def _note_before_user() -> str:
    *_, note, user = seen["messages"]
    assert user["role"] == "user" and note["role"] == "system"
    return note["content"]


@pytest.mark.asyncio
async def test_a_personal_request_starts_with_the_owners_memories():
    result = await _run("personal: when does my car insurance renew?", {"allowed_tools": None})
    note = _note_before_user()
    assert "MEMORY-MARKER" in note and "Current date and time" in note
    # The cached part of the prompt carries neither.
    assert "MEMORY-MARKER" not in seen["system_prompt"]
    assert "Current date and time" not in seen["system_prompt"]
    assert seen["calls"] == [("t1", "when does my car insurance renew?")]
    assert {"memory_s", "prepare_s", "first_token_s", "total_s"} <= set(result["timing"])


@pytest.mark.asyncio
async def test_a_cloud_request_never_sees_them():
    await _run(
        "cloud: what is the capital of Peru?", {"allowed_tools": None, "model": "openrouter/x/y"}
    )
    assert all("MEMORY-MARKER" not in str(m.get("content")) for m in seen["messages"])
    assert "MEMORY-MARKER" not in seen["system_prompt"]
    assert seen["calls"] == []
