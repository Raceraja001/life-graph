"""A personal run's delegated work stays on local models (core/personal_run.py).

Jarvis's personal route pins a personal conversation to local models, but
``delegate_to_persona`` used to start the worker as a fresh kernel task on the
worker's own model -- cloud included -- with the brief written from that
conversation. Now the parent's run carries a mark, the tool copies it onto the
child's input, and the child's ``_run_agent`` pins itself to local models or
refuses. Nothing here may construct a call to a cloud model.
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from life_graph.config import settings
from life_graph.core.personal_run import PERSONAL_INPUT_KEY, in_personal_run, personal_run_scope
from life_graph.services import lead
from life_graph.services.llm import resilient as rl

LOCAL = "ollama_chat/qwen3:14b"
LOCAL_2 = "ollama_chat/qwen3:4b"
CLOUD = "gemini/gemini-3.6-flash"
NAMES = ["web_search", "memory_search", "email_read", "delegate_to_persona"]
PERSONAL = {"memory_search", "email_read"}


@pytest.fixture(autouse=True)
def _chain(monkeypatch):
    """A chain that mixes local and cloud models, plus OmniRoute and a paid
    fallback: everything a personal run must never reach."""
    monkeypatch.setattr(settings, "lead_local_model", LOCAL)
    monkeypatch.setattr(settings, "llm_fallback_chain", f"{LOCAL_2},openrouter/x:free")
    monkeypatch.setattr(settings, "llm_paid_fallback_model", "anthropic/paid")
    monkeypatch.setattr(settings, "omniroute_api_key", "k")
    monkeypatch.setattr(settings, "omniroute_model", "openai/auto")
    monkeypatch.setattr(settings, "connector_local_model_prefixes", "")


# ── the tool: marks the child, refuses a cloud worker ─────────


@pytest.fixture
def delegation(monkeypatch):
    from life_graph.api import dependencies
    from life_graph.core.task_context import TaskContext, _task_context_var

    personas = {
        "admin": {"model": LOCAL, "allowed_tools": ["memory_search"]},
        "scout": {"model": CLOUD, "allowed_tools": ["web_search"]},
        "tutor": {"model": None, "allowed_tools": ["web_search"]},
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
    token = _task_context_var.set(TaskContext(task_id=uuid.uuid4(), tenant_id="t_personal"))
    yield SimpleNamespace(pm=pm, svc=svc)
    _task_context_var.reset(token)


async def _delegate(persona: str) -> dict:
    from life_graph.tools.delegate import delegate_to_persona

    return json.loads(await delegate_to_persona(persona, "check the bills", wait=False))


@pytest.mark.asyncio
async def test_a_personal_runs_child_is_marked_personal(delegation):
    with personal_run_scope(True):
        out = await _delegate("admin")
    assert out == {"task_id": "child", "status": "queued"}
    data = delegation.pm.spawn.await_args.kwargs["input_data"]
    assert data == {"message": "check the bills", PERSONAL_INPUT_KEY: True}


@pytest.mark.asyncio
async def test_jarvis_may_take_a_personal_task_whatever_its_model(delegation):
    """lead.route sends a marked Jarvis task to its local model."""
    with personal_run_scope(True):
        out = await _delegate("jarvis")
    assert out["status"] == "queued"
    assert delegation.pm.spawn.await_args.kwargs["input_data"][PERSONAL_INPUT_KEY] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("persona", ["scout", "tutor"])
async def test_a_personal_run_cannot_hand_work_to_a_cloud_worker(delegation, monkeypatch, persona):
    # tutor has no model of its own: the default one, cloud here.
    monkeypatch.setattr(settings, "agent_llm_model", CLOUD)
    with personal_run_scope(True):
        out = await _delegate(persona)
    assert "not a local model" in out["error"] and "personal conversation" in out["error"]
    delegation.pm.spawn.assert_not_called()


@pytest.mark.asyncio
async def test_a_failed_persona_lookup_refuses(delegation):
    delegation.svc.get_by_name.side_effect = RuntimeError("db down")
    with personal_run_scope(True):
        out = await _delegate("admin")
    assert "not a local model" in out["error"]
    delegation.pm.spawn.assert_not_called()


@pytest.mark.asyncio
async def test_a_general_run_delegates_as_before(delegation):
    out = await _delegate("scout")
    assert out["status"] == "queued"
    data = delegation.pm.spawn.await_args.kwargs["input_data"]
    assert data == {"message": "check the bills"}


# ── the child's run: pinned to local models, or refused ───────


class _FakeReg:
    tool_names = NAMES

    def get_tools(self):
        return [{"type": "function", "function": {"name": n}} for n in NAMES]


seen: dict = {}


async def _fake_run(self, messages, system_prompt=None, tools=None, **_kw):
    seen.update(
        model=self.model,
        tools=None if tools is None else {t["function"]["name"] for t in tools},
        pinned=rl._allowed_fallbacks.get(),
        personal=in_personal_run(),
    )
    yield 'data: {"type": "token", "content": "ok"}\n\n'


async def _run(agent: str, model: str | None, message: str = "check the bills", **extra):
    from life_graph.core.task_context import set_task_context
    from life_graph.kernel.process_manager import ProcessManager

    root = uuid.uuid4()
    mgr = ProcessManager.__new__(ProcessManager)
    set_task_context(task_id=root, tenant_id="t_personal", root_task_id=root, depth=1)

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
        return await mgr._run_agent("t_personal", agent, {"message": message, **extra}, persona)


@pytest.mark.asyncio
async def test_a_marked_child_on_a_local_model_is_pinned_to_local_models():
    await _run("admin", LOCAL, **{PERSONAL_INPUT_KEY: True})
    assert seen["model"] == LOCAL
    # Only the local models: not the cloud one in the chain, not OmniRoute,
    # not the paid fallback.
    assert seen["pinned"] == (LOCAL, LOCAL_2)
    # Pinned local, so it keeps its personal tools, and marks its own children.
    assert seen["tools"] >= PERSONAL and seen["personal"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("model", [CLOUD, "claude-cli", None])
async def test_a_marked_child_without_a_local_model_is_refused(monkeypatch, model):
    monkeypatch.setenv("LIFE_GRAPH_AGENT_LLM_MODEL", CLOUD)  # what None falls back to
    with pytest.raises(lead.LocalOnlyRefusedError, match="not a local model"):
        await _run("scout", model, **{PERSONAL_INPUT_KEY: True})
    assert seen == {}  # its model was never run


@pytest.mark.asyncio
async def test_a_marked_jarvis_task_takes_the_personal_route_even_if_asked_for_cloud():
    out = await _run("jarvis", CLOUD, "cloud: compare two phones", **{PERSONAL_INPUT_KEY: True})
    assert out["route"]["kind"] == "personal" and out["route"]["reason"] == lead.DELEGATED_REASON
    assert seen["model"] == LOCAL and seen["pinned"] == (LOCAL, LOCAL_2)
    assert seen["personal"] is True


@pytest.mark.asyncio
async def test_jarvis_marks_its_personal_runs_only():
    await _run("jarvis", CLOUD, "what bills are due?")
    assert seen["personal"] is True
    await _run("jarvis", CLOUD, "cloud: capital of Peru?")
    assert seen["personal"] is False and not seen["tools"] & PERSONAL


@pytest.mark.asyncio
async def test_an_unmarked_child_runs_on_its_own_model_as_before():
    await _run("scout", CLOUD)
    assert seen["model"] == CLOUD and seen["pinned"] is None and seen["personal"] is False


# ── the failure path: the local model is down ─────────────────


class _Health:
    async def in_cooldown(self, m):
        return False

    async def record_success(self, m, latency_ms):
        pass

    async def record_failure(self, m, kind):
        return 1

    async def set_cooldown(self, m, seconds):
        pass

    async def get(self, m):
        return {}


@pytest.mark.asyncio
async def test_local_models_down_fails_without_trying_a_cloud_model(monkeypatch):
    """The child's completion goes through ResilientLLM under the pin: with
    every local model failing, it gives up -- it never reaches the cloud model
    in the chain, OmniRoute or the paid fallback."""
    tried: list[str] = []

    async def down(*, model, messages, **_kw):
        tried.append(model)
        raise ConnectionError("ollama is down")

    monkeypatch.setattr(rl.litellm, "acompletion", down)
    monkeypatch.setattr(rl, "_over_quota", AsyncMock(return_value=False))
    monkeypatch.setattr(rl, "_count_request", AsyncMock())
    outcome: dict = {}

    async def run_through_llm(self, messages, system_prompt=None, tools=None, **_kw):
        try:
            await rl.ResilientLLM(health=_Health()).acompletion(messages=messages, model=self.model)
        except rl.ResilientLLMExhaustedError as exc:
            outcome["error"] = exc
        yield 'data: {"type": "token", "content": ""}\n\n'

    from life_graph.core.task_context import set_task_context
    from life_graph.kernel.process_manager import ProcessManager

    root = uuid.uuid4()
    set_task_context(task_id=root, tenant_id="t_personal", root_task_id=root, depth=1)

    async def no_memories(*_a, **_k):
        return ""

    with (
        patch("life_graph.tools.registry.registry", _FakeReg()),
        patch("life_graph.agents.orchestrator.AgentOrchestrator.run", run_through_llm),
        patch("life_graph.services.memory.context.memory_block", no_memories),
    ):
        await ProcessManager.__new__(ProcessManager)._run_agent(
            "t_personal",
            "admin",
            {"message": "check the bills", PERSONAL_INPUT_KEY: True},
            {"allowed_tools": list(NAMES), "model": LOCAL, "system_prompt": "x"},
        )

    assert "error" in outcome
    assert tried == [LOCAL, LOCAL_2]


def test_personal_pin_keeps_only_local_models():
    assert lead.personal_pin("admin", LOCAL) == [LOCAL, LOCAL_2]
    with pytest.raises(lead.LocalOnlyRefusedError):
        lead.personal_pin("scout", CLOUD)
    with pytest.raises(lead.LocalOnlyRefusedError):
        lead.personal_pin("scout", None)
