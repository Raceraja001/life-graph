"""A personal run hands nothing to a cloud worker (core/personal_run.py).

``research_web`` sends its question to a cloud worker (services/web_research
-> services/workers.run_worker), protected only by the scrub, which misses
names and places. Jarvis's personal route on a cloud-configured Jarvis cut it,
but a marked child (pinned local), Jarvis's personal route on a local Jarvis,
and a run that became personal part-way through all kept it. Now the kernel
leaves CLOUD_WORKER_TOOLS out of a run that starts personal, and the tools
refuse by themselves while the run is marked.
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

# Imported before any test patches tools.registry.registry: the orchestrator
# binds the registry at import time.
import life_graph.agents.orchestrator  # noqa: F401
import life_graph.tools.web_search  # noqa: F401 - registers research_web
from life_graph.config import settings
from life_graph.core.personal_run import (
    CLOUD_WORKER_REFUSAL,
    PERSONAL_INPUT_KEY,
    in_personal_run,
    personal_run_scope,
)
from life_graph.services.lead import CLOUD_WORKER_TOOLS, resolve_run_tools
from life_graph.tools.registry import registry as real_registry

LOCAL = "ollama_chat/qwen3:14b"
CLOUD = "gemini/gemini-3.6-flash"
NAMES = ["web_search", "research_web", "memory_search", "email_read"]


@pytest.fixture(autouse=True)
def _chain(monkeypatch):
    monkeypatch.setattr(settings, "lead_local_model", LOCAL)
    monkeypatch.setattr(settings, "llm_fallback_chain", "")
    monkeypatch.setattr(settings, "llm_paid_fallback_model", None)
    monkeypatch.setattr(settings, "omniroute_api_key", "")
    monkeypatch.setattr(settings, "connector_local_model_prefixes", "")


@pytest.fixture
def research(monkeypatch):
    """The cloud worker behind research_web; never called on a personal run."""
    from life_graph.services import web_research

    fake = AsyncMock(return_value={"answer": "a", "sources": [], "pages_read": []})
    monkeypatch.setattr(web_research, "research", fake)
    return fake


# ── resolve_run_tools ─────────────────────────────────────────

_REG = SimpleNamespace(tool_names=NAMES)


@pytest.mark.parametrize(
    ("persona_tools", "override", "expected"),
    [
        (["web_search", "research_web"], None, ["web_search"]),
        (["web_search"], ["research_web", "memory_search"], ["memory_search"]),  # override can't
        (None, None, ["web_search", "memory_search", "email_read"]),  # "all tools" expands
    ],
)
def test_a_personal_run_gets_no_cloud_worker_tool(persona_tools, override, expected):
    got = resolve_run_tools(
        {"allowed_tools": persona_tools},
        override,
        cloud=False,
        temporary=False,
        personal=True,
        registry=_REG,
    )
    assert got == expected
    assert not set(got) & CLOUD_WORKER_TOOLS


def test_a_general_run_keeps_them():
    tools = ["web_search", "research_web"]
    got = resolve_run_tools({"allowed_tools": tools}, cloud=False, temporary=False)
    assert got == tools


# ── _run_agent: a run that starts personal ────────────────────


class _FakeReg:
    tool_names = NAMES

    def get_tools(self):
        return [{"type": "function", "function": {"name": n}} for n in NAMES]


seen: dict = {}


async def _fake_run(self, messages, system_prompt=None, tools=None, **_kw):
    seen["tools"] = None if tools is None else {t["function"]["name"] for t in tools}
    seen["model"] = self.model
    yield 'data: {"type": "token", "content": "ok"}\n\n'


async def _run(agent: str, model: str, message: str = "look into it", **extra):
    from life_graph.core.task_context import set_task_context
    from life_graph.kernel.process_manager import ProcessManager

    root = uuid.uuid4()
    set_task_context(task_id=root, tenant_id="t_pncw", root_task_id=root, depth=1)

    async def no_memories(*_a, **_k):
        return ""

    persona = {"allowed_tools": list(NAMES), "model": model, "system_prompt": "x"}
    seen.clear()
    with (
        patch("life_graph.tools.registry.registry", _FakeReg()),
        patch("life_graph.agents.orchestrator.AgentOrchestrator.run", _fake_run),
        patch("life_graph.services.memory.context.memory_block", no_memories),
        patch("life_graph.connectors.chat_context.context_for", AsyncMock(return_value="")),
    ):
        mgr = ProcessManager.__new__(ProcessManager)
        return await mgr._run_agent("t_pncw", agent, {"message": message, **extra}, persona)


@pytest.mark.asyncio
async def test_a_marked_child_gets_no_cloud_worker_tool():
    await _run("admin", LOCAL, **{PERSONAL_INPUT_KEY: True})
    assert seen["model"] == LOCAL
    assert "research_web" not in seen["tools"]
    assert {"web_search", "memory_search"} <= seen["tools"]


@pytest.mark.asyncio
async def test_jarvis_personal_route_on_a_local_jarvis_gets_no_cloud_worker_tool():
    """lead.route cuts research_web only when it moves Jarvis to the local
    model; a Jarvis already on one kept it."""
    out = await _run("jarvis", LOCAL, "what bills are due?")
    assert out["route"]["kind"] == "personal"
    assert "research_web" not in seen["tools"]


@pytest.mark.asyncio
async def test_general_and_unmarked_runs_keep_research_web():
    out = await _run("jarvis", LOCAL, "compare groq and cerebras")
    assert out["route"]["kind"] == "general" and "research_web" in seen["tools"]
    await _run("admin", LOCAL)
    assert "research_web" in seen["tools"]


# ── the tool itself: refuses while the run is marked ──────────


@pytest.mark.asyncio
@pytest.mark.parametrize("name", sorted(CLOUD_WORKER_TOOLS))
async def test_every_cloud_worker_tool_refuses_in_a_personal_run(research, name):
    with personal_run_scope(True):
        out = json.loads(await real_registry.execute(name, {"question": "who is Arun?"}))
    assert out == {"status": "error", "message": CLOUD_WORKER_REFUSAL}
    research.assert_not_called()


@pytest.mark.asyncio
async def test_research_web_works_outside_a_personal_run(research):
    out = json.loads(await real_registry.execute("research_web", {"question": "groq vs x"}))
    assert out["status"] == "ok"
    research.assert_awaited_once()


# ── mid-run: a run that becomes personal ──────────────────────


def _chunk(content=None, tool_calls=None):
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


def _call(index, name):
    args = json.dumps({"question": "q"}) if name == "research_web" else "{}"
    return SimpleNamespace(
        index=index, id=f"c{index}", function=SimpleNamespace(name=name, arguments=args)
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
    def __init__(self, turns):
        self.queue = list(turns)

    async def acompletion(self, **_kw):
        if self.queue:
            calls = [_call(i, n) for i, n in enumerate(self.queue.pop(0))]
            return _Stream([_chunk(tool_calls=calls)])
        return _Stream([_chunk(content="ok")])


@pytest.mark.asyncio
async def test_research_web_after_a_memory_read_is_refused(monkeypatch, research):
    from life_graph.agents import orchestrator as orch_mod
    from life_graph.api import dependencies

    results: list[tuple[str, dict]] = []

    async def execute(name, args):
        if name == "research_web":
            out = await real_registry.execute(name, args)  # the real tool
        else:
            out = json.dumps({"ok": True})
        results.append((name, json.loads(out)))
        return out

    turns = [["research_web"], ["memory_search"], ["research_web"]]
    llm = _LLM(turns)
    monkeypatch.setattr(dependencies, "get_resilient_llm", lambda: llm)
    # A fresh registry stand-in whose execute dispatches research_web to the
    # real tool (another test file may have left orch_mod.registry patched).
    monkeypatch.setattr(orch_mod, "registry", SimpleNamespace(execute=execute))
    orch = orch_mod.AgentOrchestrator(model=LOCAL)
    orch.condense = False
    orch.detect_stuck = False
    tools = [{"type": "function", "function": {"name": n}} for n in NAMES]
    async for _ in orch.run([{"role": "user", "content": "hi"}], tools=tools):
        pass

    assert [n for n, _ in results] == ["research_web", "memory_search", "research_web"]
    assert results[0][1]["status"] == "ok"  # before: allowed
    assert results[2][1] == {"status": "error", "message": CLOUD_WORKER_REFUSAL}
    research.assert_awaited_once()  # only the first call reached the worker
    assert in_personal_run() is False
