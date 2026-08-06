from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from life_graph.drivers.base import ContextPacket
from life_graph.drivers.local import LocalDriver


async def _fake_run(**kwargs):
    """Minimal async generator standing in for AgentOrchestrator.run."""
    captured["system_prompt"] = kwargs.get("system_prompt")
    if False:
        yield  # pragma: no cover — makes this an async generator


captured: dict = {}


@pytest.mark.asyncio
async def test_dispatch_tells_the_model_its_workdir(monkeypatch, tmp_path):
    captured.clear()

    class _FakeOrchestrator:
        def run(self, **kwargs):
            return _fake_run(**kwargs)

    monkeypatch.setattr(
        "life_graph.agents.orchestrator.AgentOrchestrator", _FakeOrchestrator
    )

    packet = ContextPacket(
        task_id=uuid.uuid4(), tenant_id="t1", task_type="code",
        instruction="fix it",
    )
    driver = LocalDriver()
    workdir = tmp_path / "wt_abc123"
    workdir.mkdir()

    await driver.dispatch(packet, workdir)

    assert str(workdir) in captured["system_prompt"]
