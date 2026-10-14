"""The dispatcher hands each attempt's steps to the trajectory recorder (as a
driver:steps event) and keeps them out of the task's own result metadata.
"""

from __future__ import annotations

import uuid

import pytest

from life_graph.core.events import EventType
from life_graph.drivers.base import DriverResult
from life_graph.drivers.dispatcher import TaskDispatcher
from tests.unit.test_dispatcher_spec_first import _FakeSession, _wire

_STEPS = [
    {"seq": 1, "kind": "tool_call", "tool": "Read", "content": "{}"},
    {"seq": 2, "kind": "text", "content": "done"},
]


class _SteppingDriver:
    name = "stepper"

    def cost_per_task(self) -> float:
        return 0.0

    async def dispatch(self, packet, workdir, timeout=300) -> DriverResult:
        return DriverResult(
            success=True, output="done", metadata={"num_turns": 2, "steps": list(_STEPS)}
        )


@pytest.mark.asyncio
async def test_each_attempts_steps_are_emitted_and_kept_off_the_task_result(monkeypatch):
    disp = TaskDispatcher(session_factory=lambda: _FakeSession(), event_bus=None)
    _wire(disp, monkeypatch, _SteppingDriver())
    emitted = []

    async def _capture(event_type, payload):
        emitted.append((event_type, payload))

    monkeypatch.setattr(disp, "_emit", _capture)
    task_id = str(uuid.uuid4())

    result = await disp.dispatch_task(
        tenant_id="t1", task_id=task_id, instruction="Add a helper function", verify_chain=[]
    )

    steps_events = [p for t, p in emitted if t == EventType.DRIVER_STEPS]
    assert steps_events == [
        {"tenant_id": "t1", "task_id": task_id, "driver": "stepper", "attempt": 1, "steps": _STEPS}
    ]
    assert "steps" not in result.metadata
    assert result.metadata.get("num_turns") == 2  # the rest of the metadata survives


@pytest.mark.asyncio
async def test_a_driver_without_steps_emits_nothing(monkeypatch):
    class _Quiet(_SteppingDriver):
        async def dispatch(self, packet, workdir, timeout=300) -> DriverResult:
            return DriverResult(success=True, output="done")

    disp = TaskDispatcher(session_factory=lambda: _FakeSession(), event_bus=None)
    _wire(disp, monkeypatch, _Quiet())
    emitted = []

    async def _capture(event_type, payload):
        emitted.append(event_type)

    monkeypatch.setattr(disp, "_emit", _capture)
    await disp.dispatch_task(
        tenant_id="t1", task_id=str(uuid.uuid4()), instruction="x", verify_chain=[]
    )

    assert EventType.DRIVER_STEPS not in emitted


def test_each_tenant_gets_its_own_private_scratch_root():
    import os
    import stat
    from pathlib import Path

    from life_graph.drivers.dispatcher import tenant_scratch_root

    a, b = tenant_scratch_root("tenant-a"), tenant_scratch_root("tenant-b")
    assert a != b and Path(a).name == "tenant-a"
    assert stat.S_IMODE(os.stat(a).st_mode) == 0o700
    # A tenant id can never become a path that climbs out of the root.
    weird = Path(tenant_scratch_root("../../etc"))
    assert weird.parent == Path(a).parent and ".." not in weird.name.split("_")
