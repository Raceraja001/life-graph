"""Jarvis's per-request model choice (services/lead.py) and how a run applies it
(kernel/process_manager._run_agent): personal work stays local, the rest may go
to the cloud without the personal tools."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from life_graph.services import lead

CLOUD = "claude-cli"
TOOLS = ["web_search", "research_web", "calendar_events", "bills_due", "delegate_to_persona"]


def _persona(model=CLOUD, tools=TOOLS):
    return {"name": "jarvis", "model": model, "allowed_tools": list(tools), "system_prompt": "J"}


@pytest.fixture(autouse=True)
def _local_chain(monkeypatch):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "lead_local_model", "")
    monkeypatch.setattr(settings, "agent_llm_model", "ollama_chat/qwen3:14b")
    monkeypatch.setattr(settings, "llm_fallback_chain", "ollama_chat/qwen3:4b,openrouter/x")
    monkeypatch.setattr(settings, "llm_paid_fallback_model", None)


@pytest.mark.parametrize(
    "message",
    [
        "What bills are due this week?",
        "when does my passport expire",
        "anything in my inbox from the bank?",
        "remind me what I said about the school fees",
        "call +91 98765 43210 about the plan",
    ],
)
def test_personal_requests_run_local_and_pinned(message):
    r = lead.route(_persona(), {"message": message})
    assert r.kind == "personal" and r.model == "ollama_chat/qwen3:14b"
    # Fails over only to local models, never to the cloud one in the chain.
    assert r.pinned == ["ollama_chat/qwen3:14b", "ollama_chat/qwen3:4b"]
    assert "calendar_events" in r.tools and "research_web" not in r.tools
    assert r.message == message  # not scrubbed: it stays on the machine


def test_general_requests_lose_the_personal_tools_and_are_scrubbed():
    history = [
        {"role": "user", "content": "compare free LLM tiers"},
        {"role": "assistant", "content": "write to me at a@b.co"},
    ]
    r = lead.route(
        _persona(), {"message": "Compare Groq and Cerebras free tiers", "history": history}
    )
    assert r.kind == "general" and r.model == CLOUD and r.pinned is None
    assert r.tools == ["web_search", "research_web"]
    assert r.history[1]["content"] == "write to me at «HIDDEN:email»"


def test_a_personal_earlier_turn_keeps_the_conversation_local():
    history = [{"role": "user", "content": "when is my next dentist appointment?"}]
    r = lead.route(_persona(), {"message": "and the one after that?", "history": history})
    assert r.kind == "personal" and r.reason.startswith("an earlier turn mentions")


def test_the_owner_can_switch():
    r = lead.route(_persona(), {"message": "personal: compare Groq and Cerebras"})
    assert r.kind == "personal" and r.message == "compare Groq and Cerebras"
    r = lead.route(_persona(), {"message": "cloud: summarise my bills"})
    # Cloud on request still gets no personal tools: it can only say so.
    assert r.kind == "general" and "bills_due" not in r.tools
    assert r.message == "summarise my bills"


def test_a_local_configured_model_changes_nothing(monkeypatch):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "llm_fallback_chain", "ollama_chat/qwen3:4b")
    r = lead.route(_persona(model="ollama_chat/qwen3:14b"), {"message": "my bills"})
    assert r.model == "ollama_chat/qwen3:14b" and r.tools == TOOLS and r.pinned is None


def test_local_but_failing_over_to_the_cloud_is_not_local():
    # The fixture's chain ends in a cloud model: a "local" persona could fail
    # over to it mid-run, so a personal request is pinned anyway.
    r = lead.route(_persona(model="ollama_chat/qwen3:14b"), {"message": "my bills"})
    assert r.kind == "personal" and r.pinned == ["ollama_chat/qwen3:14b", "ollama_chat/qwen3:4b"]


class _FakeOrchestrator:
    seen: dict = {}

    def __init__(self, model=None, temperature=None, max_tokens=None):
        self.model = model

    async def run(self, messages, system_prompt=None, tools=None):
        from life_graph.services.resilient_llm import _allowed_fallbacks

        _FakeOrchestrator.seen = {
            "model": self.model,
            "messages": messages,
            "system_prompt": system_prompt,
            "tools": sorted(t["function"]["name"] for t in tools or []),
            "pinned": _allowed_fallbacks.get(),
        }
        yield 'data: {"type": "token", "content": "ok"}'


class _FakeReg:
    tool_names = [*TOOLS, "run_command"]

    def get_tools(self):
        return [{"function": {"name": n}} for n in self.tool_names]


async def _run(agent, persona, message, tool_override=None):
    from life_graph.kernel import process_manager as pm_mod

    pm = pm_mod.ProcessManager.__new__(pm_mod.ProcessManager)
    with (
        patch("life_graph.tools.registry.registry", _FakeReg()),
        patch("life_graph.agents.orchestrator.AgentOrchestrator", _FakeOrchestrator),
        patch("life_graph.connectors.chat_context.context_for") as context_for,
    ):
        out = await pm._run_agent(
            "t1", agent, {"message": message}, persona, tool_override=tool_override
        )
    return out, _FakeOrchestrator.seen, context_for


@pytest.mark.asyncio
async def test_run_agent_keeps_personal_work_local():
    out, seen, context_for = await _run("jarvis", _persona(), "what bills are due?")
    assert seen["model"] == "ollama_chat/qwen3:14b"
    assert seen["pinned"] == ("ollama_chat/qwen3:14b", "ollama_chat/qwen3:4b")
    assert "bills_due" in seen["tools"] and "research_web" not in seen["tools"]
    assert out["route"]["kind"] == "personal"
    context_for.assert_not_called()  # local model: the tools read the data


@pytest.mark.asyncio
async def test_run_agent_sends_no_personal_data_to_the_cloud():
    out, seen, context_for = await _run(
        "jarvis", _persona(), "compare groq and cerebras", tool_override=TOOLS
    )
    assert seen["model"] == CLOUD and seen["pinned"] is None
    # Not even through an override.
    assert seen["tools"] == ["research_web", "web_search"]
    assert lead.GENERAL_NOTE in seen["system_prompt"]
    context_for.assert_not_called()  # no calendar or mail inline
    assert out["route"] == {"kind": "general", "reason": "nothing personal in it", "model": CLOUD}


@pytest.mark.asyncio
async def test_other_personas_are_untouched():
    out, seen, _ = await _run("scout", _persona(model="ollama_chat/qwen3:14b"), "my bills")
    assert seen["model"] == "ollama_chat/qwen3:14b" and "route" not in out
    assert "bills_due" in seen["tools"]
