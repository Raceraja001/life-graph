"""A run that touches the owner's data becomes personal for the rest of it.

core/personal_run.py: Jarvis's personal route marks its run from the start,
but a general run -- Jarvis on a local model, or any local persona with the
personal tools -- could read a memory or a mail and then hand a brief built
from it to a cloud worker. The orchestrator now sets the mark from the first
PERSONAL_TOOLS call on (the way it sets the taint), so a later
``delegate_to_persona`` carries ``PERSONAL_INPUT_KEY`` and the child is pinned
local or refused. The run's own model is not changed.
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from life_graph.config import settings
from life_graph.core.personal_run import PERSONAL_INPUT_KEY, in_personal_run, personal_run_scope
from life_graph.services.lead import PERSONAL_TOOLS

LOCAL = "ollama_chat/qwen3:14b"
CLOUD = "gemini/gemini-3.6-flash"


def _chunk(content=None, tool_calls=None):
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


def _call(index, name):
    return SimpleNamespace(
        index=index, id=f"c{index}", function=SimpleNamespace(name=name, arguments="{}")
    )


class _Stream:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)


class _LLM:
    """Streams each turn's tool calls, then a final answer; records models."""

    def __init__(self, turns):
        self.queue = list(turns)
        self.models: list[str] = []

    async def acompletion(self, *, model=None, **_kw):
        self.models.append(model)
        if self.queue:
            calls = [_call(i, n) for i, n in enumerate(self.queue.pop(0))]
            return _Stream([_chunk(tool_calls=calls)])
        return _Stream([_chunk(content="ok")])


async def _run(monkeypatch, turns, execute, model=LOCAL):
    from life_graph.agents import orchestrator as orch_mod
    from life_graph.api import dependencies

    llm = _LLM(turns)
    monkeypatch.setattr(dependencies, "get_resilient_llm", lambda: llm)
    monkeypatch.setattr(orch_mod.registry, "execute", execute)
    names = sorted({n for turn in turns for n in turn})
    tools = [{"type": "function", "function": {"name": n}} for n in names]
    orch = orch_mod.AgentOrchestrator(model=model)
    orch.condense = False
    orch.detect_stuck = False
    async for _ in orch.run([{"role": "user", "content": "hi"}], tools=tools):
        pass
    return llm


def _recorder():
    seen: list[tuple[str, bool]] = []

    async def execute(name, args):
        seen.append((name, in_personal_run()))
        return json.dumps({"ok": True})

    return seen, execute


@pytest.mark.asyncio
async def test_tools_after_a_personal_tool_see_the_mark(monkeypatch):
    seen, execute = _recorder()
    llm = await _run(
        monkeypatch,
        [["web_search", "memory_search", "web_search"], ["delegate_to_persona"]],
        execute,
    )
    assert seen == [
        ("web_search", False),
        ("memory_search", False),  # the mark is for what comes after it
        ("web_search", True),
        ("delegate_to_persona", True),
    ]
    # The run's own model never changed.
    assert set(llm.models) == {LOCAL}
    # Nothing leaks out of the run.
    assert in_personal_run() is False


@pytest.mark.asyncio
async def test_a_run_without_personal_tools_stays_unmarked(monkeypatch):
    seen, execute = _recorder()
    await _run(monkeypatch, [["web_search", "browse_web"], ["delegate_to_persona"]], execute)
    assert all(mark is False for _, mark in seen)


@pytest.mark.asyncio
async def test_a_failed_personal_tool_still_marks(monkeypatch):
    seen: list[tuple[str, bool]] = []

    async def execute(name, args):
        seen.append((name, in_personal_run()))
        if name == "email_read":
            raise KeyError(name)  # the orchestrator's "Unknown tool" path
        return json.dumps({"ok": True})

    await _run(monkeypatch, [["email_read"], ["delegate_to_persona"]], execute)
    assert seen[-1] == ("delegate_to_persona", True)


@pytest.mark.asyncio
async def test_a_disallowed_personal_tool_does_not_mark(monkeypatch):
    """Blocked before it ran, so it read nothing."""
    from life_graph.agents import orchestrator as orch_mod
    from life_graph.api import dependencies

    seen, execute = _recorder()
    llm = _LLM([["memory_search"], ["delegate_to_persona"]])
    monkeypatch.setattr(dependencies, "get_resilient_llm", lambda: llm)
    monkeypatch.setattr(orch_mod.registry, "execute", execute)
    orch = orch_mod.AgentOrchestrator(model=LOCAL)
    orch.condense = False
    orch.detect_stuck = False
    tools = [{"type": "function", "function": {"name": "delegate_to_persona"}}]
    async for _ in orch.run([{"role": "user", "content": "hi"}], tools=tools):
        pass
    assert seen == [("delegate_to_persona", False)]


@pytest.mark.asyncio
async def test_a_run_started_personal_is_personal_from_its_first_tool(monkeypatch):
    seen, execute = _recorder()
    with personal_run_scope(True):
        await _run(monkeypatch, [["web_search"]], execute)
    assert seen == [("web_search", True)]


@pytest.mark.parametrize("name", sorted(PERSONAL_TOOLS - {"delegate_to_persona"}))
@pytest.mark.asyncio
async def test_every_personal_tool_marks(monkeypatch, name):
    seen, execute = _recorder()
    await _run(monkeypatch, [[name], ["delegate_to_persona"]], execute)
    assert seen[-1] == ("delegate_to_persona", True)


@pytest.mark.asyncio
async def test_a_delegation_marks_the_run_too(monkeypatch):
    """delegate_to_persona is in PERSONAL_TOOLS: a worker's report may carry
    what it read, so the run's next delegation is personal (fail closed)."""
    seen, execute = _recorder()
    await _run(monkeypatch, [["delegate_to_persona"], ["delegate_to_persona"]], execute)
    assert seen == [("delegate_to_persona", False), ("delegate_to_persona", True)]


# ── end to end: the orchestrator's mark reaches the child ─────


@pytest.fixture
def delegation(monkeypatch):
    from life_graph.api import dependencies
    from life_graph.core.task_context import TaskContext, _task_context_var

    personas = {
        "admin": {"model": LOCAL, "allowed_tools": ["memory_search"]},
        "scout": {"model": CLOUD, "allowed_tools": ["web_search"]},
    }
    svc = SimpleNamespace(get_by_name=AsyncMock(side_effect=lambda t, n: personas.get(n)))
    pm = SimpleNamespace(
        get_task=AsyncMock(
            return_value=SimpleNamespace(root_task_id=None, id=uuid.uuid4(), depth=0)
        ),
        spawn=AsyncMock(return_value={"task_id": "child"}),
    )
    monkeypatch.setattr(dependencies, "get_persona_service", lambda: svc)
    monkeypatch.setattr(dependencies, "get_process_manager", lambda: pm)
    monkeypatch.setattr(settings, "connector_local_model_prefixes", "")
    token = _task_context_var.set(TaskContext(task_id=uuid.uuid4(), tenant_id="t_ptu"))
    yield pm
    _task_context_var.reset(token)


def _delegating_execute(persona: str, results: list):
    from life_graph.tools.delegate import delegate_to_persona

    async def execute(name, args):
        if name == "delegate_to_persona":
            out = await delegate_to_persona(persona, "follow up on that", wait=False)
            results.append(json.loads(out))
            return out
        return json.dumps({"ok": True})

    return execute


@pytest.mark.asyncio
async def test_after_a_memory_read_a_cloud_worker_is_refused(monkeypatch, delegation):
    results: list = []
    await _run(
        monkeypatch,
        [["memory_search"], ["delegate_to_persona"]],
        _delegating_execute("scout", results),
    )
    assert "not a local model" in results[0]["error"]
    delegation.spawn.assert_not_called()


@pytest.mark.asyncio
async def test_after_a_memory_read_a_local_worker_gets_a_marked_task(monkeypatch, delegation):
    results: list = []
    await _run(
        monkeypatch,
        [["memory_search"], ["delegate_to_persona"]],
        _delegating_execute("admin", results),
    )
    assert results[0]["status"] == "queued"
    data = delegation.spawn.await_args.kwargs["input_data"]
    assert data[PERSONAL_INPUT_KEY] is True


@pytest.mark.asyncio
async def test_without_a_personal_tool_a_cloud_worker_is_still_allowed(monkeypatch, delegation):
    results: list = []
    await _run(
        monkeypatch,
        [["web_search"], ["delegate_to_persona"]],
        _delegating_execute("scout", results),
    )
    assert results[0]["status"] == "queued"
    assert PERSONAL_INPUT_KEY not in delegation.spawn.await_args.kwargs["input_data"]
