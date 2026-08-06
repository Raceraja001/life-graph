import uuid
from unittest.mock import AsyncMock, patch

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


@pytest.mark.asyncio
async def test_retry_preserves_tool_override(monkeypatch):
    """A retried run must keep the SAME tool_override, not fall back to the
    persona's own (possibly write-capable) allowed_tools.

    Without this, an ordinary transient failure on a scheduled read-only
    ops run (any non-timeout exception, default max_retries=3) would
    silently re-spawn the retry with full write-tool access.
    """
    from life_graph.kernel import process_manager as pm_mod

    pm = pm_mod.ProcessManager.__new__(pm_mod.ProcessManager)

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def execute(self, *args, **kwargs):
            return None

        async def commit(self):
            return None

    pm._session_factory = lambda: _FakeSession()

    captured = {}

    async def fake_spawn(*args, **kwargs):
        captured["tool_override"] = kwargs.get("tool_override")
        return {"task_id": "retry-task", "agent_name": "ops", "status": "queued"}

    pm.spawn = fake_spawn
    monkeypatch.setattr(pm_mod.asyncio, "sleep", AsyncMock())

    readonly = ["inspect_system", "git_status"]
    await pm._retry_task(
        uuid.uuid4(),
        "t1",
        "ops",
        {"message": "go"},
        retry_count=0,
        tool_override=readonly,
    )

    assert captured["tool_override"] == readonly


@pytest.mark.asyncio
async def test_fail_task_forwards_tool_override_into_retry(monkeypatch):
    """_fail_task must pass tool_override through to _retry_task on the
    retry-eligible path (retry_count < max_retries, not timed out)."""
    from life_graph.kernel import process_manager as pm_mod

    pm = pm_mod.ProcessManager.__new__(pm_mod.ProcessManager)

    class _FakeTask:
        retry_count = 0
        max_retries = 3
        input = {"message": "go"}

    class _FakeResult:
        def scalar_one_or_none(self):
            return _FakeTask()

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def execute(self, *args, **kwargs):
            return _FakeResult()

        async def commit(self):
            return None

    pm._session_factory = lambda: _FakeSession()

    captured = {}

    async def fake_retry_task(*args, **kwargs):
        captured["tool_override"] = kwargs.get("tool_override")

    pm._retry_task = fake_retry_task

    with patch("life_graph.kernel.process_manager.event_bus") as bus:
        bus.emit = AsyncMock()
        readonly = ["inspect_system", "git_status"]
        await pm._fail_task(
            uuid.uuid4(),
            "t1",
            "ops",
            "boom",
            tool_override=readonly,
        )

    assert captured["tool_override"] == readonly
