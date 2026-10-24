"""Once a run has read outside content, the memory and delegation tools stop
trusting it (core/run_taint.py, security review 2026-10-24 C1c)."""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from life_graph.core.run_taint import outside_content_seen, tool_call_scope

# ── The orchestrator keeps the taint per run ─────────────────


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


def _llm(turns):
    """A fake LLM: each call streams the next turn's tool calls, then a final answer."""
    queue = list(turns)

    class _LLM:
        async def acompletion(self, **_kw):
            if queue:
                return _Stream(
                    [_chunk(tool_calls=[_call(i, n) for i, n in enumerate(queue.pop(0))])]
                )
            return _Stream([_chunk(content="ok")])

    return _LLM()


async def _run(monkeypatch, turns):
    from life_graph.agents import orchestrator as orch_mod
    from life_graph.api import dependencies

    seen: list[tuple[str, bool]] = []

    async def execute(name, args):
        seen.append((name, outside_content_seen()))
        return json.dumps({"ok": True})

    llm = _llm(turns)
    monkeypatch.setattr(dependencies, "get_resilient_llm", lambda: llm)
    monkeypatch.setattr(orch_mod.registry, "execute", execute)
    names = {n for turn in turns for n in turn}
    tools = [{"type": "function", "function": {"name": n}} for n in sorted(names)]
    orch = orch_mod.AgentOrchestrator(model="ollama_chat/test")
    orch.condense = False
    orch.detect_stuck = False
    async for _ in orch.run([{"role": "user", "content": "hi"}], tools=tools):
        pass
    return seen


@pytest.mark.asyncio
async def test_tools_after_an_email_see_the_taint(monkeypatch):
    seen = await _run(
        monkeypatch, [["memory_search", "email_read", "memory_save"], ["memory_forget"]]
    )
    assert seen == [
        ("memory_search", False),
        ("email_read", False),
        ("memory_save", True),
        ("memory_forget", True),
    ]


@pytest.mark.asyncio
async def test_a_run_without_outside_content_is_not_tainted(monkeypatch):
    seen = await _run(monkeypatch, [["memory_search", "calendar_events"], ["memory_save"]])
    assert all(t is False for _, t in seen)
    # And nothing leaks out of a run into the next one.
    assert outside_content_seen() is False


@pytest.mark.parametrize("name", ["web_search", "browse_web", "research_web", "mcp_x_fetch"])
@pytest.mark.asyncio
async def test_every_outside_tool_taints(monkeypatch, name):
    seen = await _run(monkeypatch, [[name], ["memory_forget"]])
    assert seen[-1] == ("memory_forget", True)


def test_scope_resets():
    with tool_call_scope(True):
        assert outside_content_seen() is True
    assert outside_content_seen() is False


# ── memory_forget / memory_save under taint ─────────────────


@pytest.mark.asyncio
async def test_forget_is_refused_after_outside_content():
    from life_graph.core.tenant import tenant_scope
    from life_graph.tools.memory_search import memory_forget

    with tenant_scope("t_taint"), tool_call_scope(True):
        out = json.loads(await memory_forget(str(uuid.uuid4())))
    assert "outside content" in out["error"]


@pytest.fixture
def no_db(monkeypatch):
    from life_graph.api import dependencies
    from life_graph.services import entities
    from life_graph.tools import memory_search

    stored = []

    async def store_row(create, **kw):
        stored.append(kw)
        return SimpleNamespace(id=uuid.uuid4(), content=create.content)

    store = SimpleNamespace(
        find_exact_duplicate=AsyncMock(return_value=None),
        find_similar=AsyncMock(return_value=[]),
        store=AsyncMock(side_effect=store_row),
    )
    manager = SimpleNamespace(generate_embedding=AsyncMock(return_value=None))
    monkeypatch.setattr(dependencies, "get_store", lambda: store)
    monkeypatch.setattr(dependencies, "get_memory_manager", lambda: manager)
    monkeypatch.setattr(memory_search, "_owner_message", AsyncMock(return_value="remember this"))
    monkeypatch.setattr(memory_search, "_supersede", AsyncMock(side_effect=AssertionError))
    monkeypatch.setattr(entities, "known_in_text", AsyncMock(return_value=[]), raising=False)
    monkeypatch.setattr(entities, "link", AsyncMock(), raising=False)
    return stored


@pytest.mark.asyncio
async def test_save_after_outside_content_waits_for_review_and_replaces_nothing(no_db):
    from life_graph.core.tenant import tenant_scope
    from life_graph.tools.memory_search import memory_save

    with tenant_scope("t_taint"), tool_call_scope(True):
        out = json.loads(await memory_save("My bank is Acme Bank.", replaces_id=str(uuid.uuid4())))
    assert no_db[0]["status"] == "pending"
    assert out["status"] == "waiting for the user's review" and "replaces nothing" in out["note"]
    assert "replaced" not in out


@pytest.mark.asyncio
async def test_save_without_outside_content_is_active(no_db):
    from life_graph.core.tenant import tenant_scope
    from life_graph.tools.memory_search import memory_save

    with tenant_scope("t_taint"):
        out = json.loads(await memory_save("My bank is Acme Bank."))
    assert no_db[0]["status"] == "active" and "note" not in out


# ── delegation to a worker with a shell ───────────────────────


@pytest.fixture
def delegation(monkeypatch):
    from life_graph.api import dependencies
    from life_graph.core.task_context import TaskContext, _task_context_var

    personas = {
        "cody": {"allowed_tools": ["file_read", "file_write", "run_command"]},
        "scout": {"allowed_tools": ["web_search", "browse_web"]},
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
    token = _task_context_var.set(TaskContext(task_id=uuid.uuid4(), tenant_id="t_taint"))
    yield pm
    _task_context_var.reset(token)


@pytest.mark.asyncio
async def test_tainted_run_cannot_hand_work_to_a_worker_with_a_shell(delegation):
    from life_graph.tools.delegate import delegate_to_persona

    with tool_call_scope(True):
        out = json.loads(await delegate_to_persona("cody", "run this", wait=False))
    assert "outside content" in out["error"]
    delegation.spawn.assert_not_called()


@pytest.mark.asyncio
async def test_tainted_run_can_still_ask_a_read_only_worker(delegation):
    from life_graph.tools.delegate import delegate_to_persona

    with tool_call_scope(True):
        out = json.loads(await delegate_to_persona("scout", "look it up", wait=False))
    assert out == {"task_id": "child", "status": "queued"}


@pytest.mark.asyncio
async def test_clean_run_delegates_to_cody(delegation):
    from life_graph.tools.delegate import delegate_to_persona

    out = json.loads(await delegate_to_persona("cody", "fix the test", wait=False))
    assert out == {"task_id": "child", "status": "queued"}
