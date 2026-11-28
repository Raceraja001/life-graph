"""claude_code never sends personal memory to its cloud model (CHARTER invariant 7).

Before 2026-11-28 ``ClaudeCodeDriver._format_prompt`` added memories,
preferences and procedures to the prompt whenever the packet was not
private, although Claude always runs on a cloud model. It now follows the
codex/gemini rule (``cli_driver.build_prompt``): none of the three, ever.
The local driver, whose model runs on the machine, is unchanged.
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


@pytest.mark.asyncio
async def test_local_driver_still_gets_preferences_and_procedures(monkeypatch, tmp_path):
    captured: dict = {}

    async def _run(**kwargs):
        captured["system_prompt"] = kwargs.get("system_prompt")
        if False:
            yield  # pragma: no cover — makes this an async generator

    class _FakeOrchestrator:
        def run(self, **kwargs):
            return _run(**kwargs)

    monkeypatch.setattr("life_graph.agents.orchestrator.AgentOrchestrator", _FakeOrchestrator)
    await LocalDriver().dispatch(_packet(private=False), tmp_path)
    assert "PREF-SECRET" in captured["system_prompt"]
    assert "PROC-SECRET" in captured["system_prompt"]
