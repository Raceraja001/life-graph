from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_run_agent_uses_tool_override(monkeypatch):
    """When tool_override is given, only those tools are passed to the orchestrator."""
    from life_graph.kernel import process_manager as pm_mod

    pm = pm_mod.ProcessManager.__new__(pm_mod.ProcessManager)
    captured = {}

    class _FakeReg:
        def get_tools(self):
            return [
                {"function": {"name": n}} for n in ("inspect_system", "run_command", "git_status")
            ]

    async def fake_run(messages, system_prompt=None, tools=None):
        captured["tools"] = [t["function"]["name"] for t in (tools or [])]
        if False:
            yield ""
        return

    # Minimal persona with WRITE tools; override must win.
    persona = {
        "allowed_tools": ["run_command", "git_status"],
        "system_prompt": "x",
        "model": None,
        "temperature": 0.3,
        "max_tokens": 1024,
    }
    with (
        patch("life_graph.tools.registry.registry", _FakeReg()),
        patch("life_graph.agents.orchestrator.AgentOrchestrator") as orch_cls,
    ):
        orch_cls.return_value.run = fake_run
        await pm._run_agent(
            "t1",
            "ops",
            {"message": "go"},
            persona,
            tool_override=["inspect_system", "git_status"],
        )

    assert set(captured["tools"]) == {"inspect_system", "git_status"}  # run_command excluded
