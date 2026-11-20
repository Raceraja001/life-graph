"""Kernel runs and the personal tools, under kernel_cloud_strip_personal_tools.

``kernel/process_manager.py::_run_agent`` cuts ``PERSONAL_TOOLS`` only on
Jarvis's general cloud route; every other persona -- admin, assistant, scout,
tutor, rex, scribe, swe-lead, seeded on the configured (cloud by default) agent
model -- keeps them on a cloud model. With
``kernel_cloud_strip_personal_tools`` on, the kernel applies drivers/local.py's
rule (#304) instead: every run that can leave the machine, counting the
fail-over chain, loses them. Off (the default) must be the previous behaviour
exactly; every case below runs under both.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from life_graph.core.task_context import set_task_context
from life_graph.kernel.process_manager import ProcessManager

NAMES = ["git_status", "web_get", "memory_search", "email_read", "calendar_events"]
PERSONAL = {"memory_search", "email_read", "calendar_events"}
LOCAL = "ollama_chat/qwen3:14b"
CLOUD = "gemini/gemini-3.6-flash"


class _FakeRegistry:
    tool_names = NAMES

    def get_tools(self):
        return [{"type": "function", "function": {"name": n}} for n in NAMES]


seen: dict = {}


async def _fake_run(self, messages, system_prompt=None, tools=None, **_kw):
    seen["tools"] = None if tools is None else {t["function"]["name"] for t in tools}
    seen["model"] = self.model
    yield 'data: {"type": "token", "content": "ok"}\n\n'
    yield 'data: {"type": "done", "model": "m"}\n\n'


async def _run(agent: str, model: str | None, message: str = "list my day") -> set[str]:
    root = uuid.uuid4()
    mgr = ProcessManager.__new__(ProcessManager)  # bypass __init__/DI
    set_task_context(task_id=root, tenant_id="t1", root_task_id=root, depth=0)

    async def no_memories(*_a, **_k):
        return ""

    persona = {"allowed_tools": list(NAMES), "model": model, "system_prompt": "x"}
    seen.clear()
    with (
        patch("life_graph.tools.registry.registry", _FakeRegistry()),
        patch("life_graph.agents.orchestrator.AgentOrchestrator.run", _fake_run),
        patch("life_graph.services.memory.context.memory_block", no_memories),
    ):
        await mgr._run_agent("t1", agent, {"message": message}, persona)
    return seen["tools"]


@pytest.fixture(params=[False, True], ids=["strip-off", "strip-on"])
def strip(request, monkeypatch) -> bool:
    """Every test runs with the setting off (default) and on."""
    from life_graph.config import settings

    monkeypatch.setattr(settings, "kernel_cloud_strip_personal_tools", request.param)
    return request.param


@pytest.fixture
def local_fallbacks(monkeypatch):
    """Fail-over stays local, so only the run's own model decides."""
    from life_graph.config import settings

    monkeypatch.setattr(settings, "llm_fallback_chain", "")
    monkeypatch.setattr(settings, "llm_paid_fallback_model", None)
    monkeypatch.setattr(settings, "lead_local_model", LOCAL)


def test_the_setting_is_off_by_default():
    from life_graph.config import Settings

    assert Settings.model_fields["kernel_cloud_strip_personal_tools"].default is False


# (persona, model, cloud run?)
CASES = [
    ("assistant", CLOUD, True),
    ("admin", CLOUD, True),
    ("scout", CLOUD, True),
    ("swe-lead", CLOUD, True),
    ("tutor", "openrouter/deepseek/deepseek-chat", True),
    ("assistant", LOCAL, False),
    ("admin", LOCAL, False),
    ("scout", "ollama/llama3.2", False),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("agent", "model", "cloud"), CASES)
async def test_personal_tools_follow_where_the_run_goes(
    strip, local_fallbacks, agent, model, cloud
):
    tools = await _run(agent, model)

    assert {"git_status", "web_get"} <= tools
    if strip and cloud:
        assert not tools & PERSONAL
    else:
        # Off: other personas keep them whatever the model (previous behaviour).
        assert tools >= PERSONAL


@pytest.mark.asyncio
async def test_a_cloud_fallback_makes_a_local_persona_a_cloud_run(strip, monkeypatch):
    """A local model that may fail over to a cloud one is not a local run."""
    from life_graph.config import settings

    monkeypatch.setattr(settings, "llm_fallback_chain", "gemini/gemini-3.5-flash-lite")
    monkeypatch.setattr(settings, "llm_paid_fallback_model", None)

    tools = await _run("admin", LOCAL)

    assert (not tools & PERSONAL) if strip else tools >= PERSONAL


@pytest.mark.asyncio
async def test_no_model_means_the_configured_default(strip, local_fallbacks, monkeypatch):
    # AgentOrchestrator reads a fresh Settings(), so the default is set by env.
    monkeypatch.setenv("LIFE_GRAPH_AGENT_LLM_MODEL", CLOUD)
    tools = await _run("admin", None)
    assert seen["model"] == CLOUD
    assert (not tools & PERSONAL) if strip else tools >= PERSONAL

    monkeypatch.setenv("LIFE_GRAPH_AGENT_LLM_MODEL", LOCAL)
    assert await _run("admin", None) >= PERSONAL
    assert seen["model"] == LOCAL


@pytest.mark.asyncio
async def test_jarvis_routes_are_unchanged(strip, local_fallbacks):
    """Jarvis, either way: a personal request on a cloud-configured Jarvis is
    pinned to the local model and keeps its personal tools; a general one on
    cloud loses them."""
    personal = await _run("jarvis", CLOUD, "personal: what's on my calendar?")
    assert seen["model"] == LOCAL
    assert {"memory_search", "email_read"} <= personal

    general = await _run("jarvis", CLOUD, "cloud: capital of Peru?")
    assert seen["model"] == CLOUD
    assert not general & PERSONAL


@pytest.mark.asyncio
async def test_jarvis_personal_route_with_cloud_fallbacks_stays_local(strip, monkeypatch):
    """Pinned to local models (only_models), so the cloud fallback chain does
    not make a personal request a cloud run."""
    from life_graph.config import settings

    monkeypatch.setattr(settings, "llm_fallback_chain", f"{LOCAL},gemini/gemini-3.5-flash-lite")
    monkeypatch.setattr(settings, "llm_paid_fallback_model", None)
    monkeypatch.setattr(settings, "lead_local_model", LOCAL)

    tools = await _run("jarvis", CLOUD, "personal: what's on my calendar?")

    assert {"memory_search", "email_read"} <= tools
