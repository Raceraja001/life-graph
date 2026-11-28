"""claude_code never sends personal memory to its cloud model (CHARTER invariant 7).

Before 2026-11-28 ``ClaudeCodeDriver._format_prompt`` added memories,
preferences and procedures to the prompt whenever the packet was not
private, although Claude always runs on a cloud model. It now follows the
codex/gemini rule (``cli_driver.build_prompt``): none of the three, ever.
The local driver gets the same rule when its resolved model is a cloud
model (``run_is_local``); on a local model it still receives preferences and
procedures.
"""

from __future__ import annotations

import uuid

import pytest

from life_graph.drivers.base import ContextPacket
from life_graph.drivers.claude_code import ClaudeCodeDriver
from life_graph.drivers.local import LocalDriver

SECRETS = ("MEMORY-SECRET", "PREF-SECRET", "PROC-SECRET")


def _packet(*, private: bool) -> ContextPacket:
    return ContextPacket(
        task_id=uuid.uuid4(),
        tenant_id="t1",
        task_type="code_change",
        instruction="Fix the failing parser test.",
        project_context={"name": "demo", "path": "/secret/path", "isolation": True},
        persona_system_prompt="You are code-fixer.",
        private=private,
        memories=[{"content": "MEMORY-SECRET", "trust_tier": "verified"}],
        preferences=[{"key": "PREF-SECRET"}],
        procedures=[{"name": "PROC-SECRET"}],
    )


@pytest.mark.parametrize("private", [False, True])
def test_claude_code_prompt_has_no_personal_data(private):
    prompt = ClaudeCodeDriver._format_prompt(_packet(private=private))
    assert prompt.startswith("You are code-fixer.")
    assert "Fix the failing parser test." in prompt
    assert '"name": "demo"' in prompt
    for secret in (*SECRETS, "/secret/path"):
        assert secret not in prompt
    for heading in ("Known procedures", "User preferences", "Untrusted data"):
        assert heading not in prompt


async def _local_system_prompt(monkeypatch, tmp_path, packet: ContextPacket) -> str:
    captured: dict = {}

    async def _run(**kwargs):
        captured["system_prompt"] = kwargs.get("system_prompt")
        if False:
            yield  # pragma: no cover — makes this an async generator

    class _FakeOrchestrator:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, **kwargs):
            return _run(**kwargs)

    monkeypatch.setattr("life_graph.agents.orchestrator.AgentOrchestrator", _FakeOrchestrator)
    await LocalDriver().dispatch(packet, tmp_path)
    return captured["system_prompt"]


@pytest.mark.asyncio
async def test_local_driver_on_a_local_model_still_gets_preferences_and_procedures(
    monkeypatch, tmp_path
):
    seen: list[str | None] = []

    def _local(model):
        seen.append(model)
        return True

    monkeypatch.setattr("life_graph.drivers.local.run_is_local", _local)
    packet = _packet(private=False)
    packet.persona_model = "ollama_chat/qwen3:14b"
    prompt = await _local_system_prompt(monkeypatch, tmp_path, packet)
    assert seen == ["ollama_chat/qwen3:14b"]
    assert "PREF-SECRET" in prompt and "PROC-SECRET" in prompt
    assert "MEMORY-SECRET" not in prompt  # this driver never renders memories


@pytest.mark.asyncio
async def test_local_driver_on_a_cloud_model_gets_no_personal_data(monkeypatch, tmp_path):
    monkeypatch.setattr("life_graph.drivers.local.run_is_local", lambda model: False)
    packet = _packet(private=False)
    packet.persona_model = "gemini/gemini-3.6-flash"
    prompt = await _local_system_prompt(monkeypatch, tmp_path, packet)
    assert "Fix the failing parser test." not in prompt  # the task is the user message
    assert "You are code-fixer." in prompt
    for secret in SECRETS:
        assert secret not in prompt
    for heading in ("User preferences", "Relevant procedures"):
        assert heading not in prompt


@pytest.mark.asyncio
async def test_local_driver_on_the_real_cloud_default_gets_no_personal_data(monkeypatch, tmp_path):
    """No stub: the default agent_llm_model is a cloud model, so it is cut."""
    from life_graph.config import settings

    monkeypatch.setattr(settings, "agent_llm_model", "gemini/gemini-3.6-flash")
    prompt = await _local_system_prompt(monkeypatch, tmp_path, _packet(private=False))
    for secret in SECRETS:
        assert secret not in prompt
