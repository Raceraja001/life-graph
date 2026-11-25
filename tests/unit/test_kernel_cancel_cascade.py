"""Kernel cancel cascades to delegated children (Phase 2 M2).

POST /kernel/tasks/{id}/cancel used to call ProcessManager.cancel, which
stopped only the one local asyncio task: delegated children kept running,
their capabilities stayed live, and cancel() always returned True. Now the
route marks the task and every open descendant cancelled through
DelegationEngine.cancel_task (which revokes capabilities), and stops each
run this process holds through ProcessManager.stop_local.

These are stub tests of that wiring; the database cascade itself is covered
in tests/integration/test_kernel_cancel_cascade_pg.py.
"""

from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from life_graph.api.kernel import cancel_task
from life_graph.core.tenant import tenant_scope
from life_graph.kernel.process_manager import ProcessManager
from life_graph.services.delegation import CapabilityRevokeError

TENANT = "t-cancel"


@pytest.fixture
def no_events(monkeypatch):
    emitted: list[tuple] = []

    async def emit(event_type, payload, source=None):
        emitted.append((event_type, payload))

    monkeypatch.setattr("life_graph.core.events.event_bus.emit", emit)
    return emitted


# ── ProcessManager.stop_local / cancel ──────────────────────────────


@pytest.mark.asyncio
async def test_stop_local_stops_a_held_run_and_says_so():
    pm = ProcessManager(session_factory=None, persona_service=None)
    tid = uuid.uuid4()
    run = asyncio.create_task(asyncio.sleep(3600))
    pm._running[tid] = run

    assert pm.stop_local(tid) is True
    await asyncio.sleep(0)
    assert run.cancelled()
    assert tid not in pm._running


@pytest.mark.asyncio
async def test_stop_local_is_false_when_not_held_or_already_done():
    pm = ProcessManager(session_factory=None, persona_service=None)
    assert pm.stop_local(uuid.uuid4()) is False

    finished = asyncio.create_task(asyncio.sleep(0))
    await finished
    tid = uuid.uuid4()
    pm._running[tid] = finished
    assert pm.stop_local(tid) is False


@pytest.mark.asyncio
async def test_cancel_returns_whether_it_stopped_a_local_run(no_events):
    pm = ProcessManager(session_factory=None, persona_service=None)
    written: list = []

    async def update(task_id, status, **kw):
        written.append((task_id, status))

    pm._update_task_status = update
    held = uuid.uuid4()
    pm._running[held] = asyncio.create_task(asyncio.sleep(3600))

    assert await pm.cancel(held, TENANT) is True
    not_held = uuid.uuid4()
    assert await pm.cancel(not_held, TENANT) is False
    # The row is marked cancelled either way.
    assert written == [(held, "cancelled"), (not_held, "cancelled")]


# ── the route ─────────────────────────────────────────────────────


class _PM:
    def __init__(self, task, held: set):
        self._task = task
        self.held = held
        self.stop_calls: list = []

    async def get_task(self, tenant_id, task_id):
        return self._task

    def stop_local(self, tid):
        self.stop_calls.append(tid)
        return tid in self.held

    async def cancel(self, *a, **k):  # the old path: must not be used
        raise AssertionError("route must cascade, not call pm.cancel")


class _Engine:
    """Stands in for DelegationEngine.cancel_task: reports the tree it stopped."""

    def __init__(self, descendants, error: Exception | None = None):
        self.descendants = descendants
        self.error = error
        self.calls: list = []

    async def cancel_task(self, task_id, tenant_id, reason="", *, stop_local=None):
        self.calls.append((task_id, tenant_id))
        for tid in (task_id, *self.descendants):
            stop_local(tid)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(id=task_id, status="cancelled")


def _row(status="running"):
    return SimpleNamespace(status=status, properties={})


@pytest.mark.asyncio
async def test_route_cancels_the_task_and_every_descendant(no_events):
    root, child, grandchild = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    pm = _PM(_row(), held={root, grandchild})
    engine = _Engine([child, grandchild])

    with tenant_scope(TENANT):
        out = await cancel_task(root, pm=pm, engine=engine)

    assert engine.calls == [(root, TENANT)]
    assert pm.stop_calls == [root, child, grandchild]
    assert out["data"]["status"] == "cancelled"
    assert out["data"]["cancelled_descendants"] == 2
    assert out["data"]["stopped_in_process"] == 2
    assert [p["task_id"] for _, p in no_events] == [str(root), str(child), str(grandchild)]


@pytest.mark.asyncio
async def test_route_cancels_a_queued_task_nobody_is_running(no_events):
    root = uuid.uuid4()
    pm = _PM(_row("queued"), held=set())
    engine = _Engine([])

    with tenant_scope(TENANT):
        out = await cancel_task(root, pm=pm, engine=engine)

    assert engine.calls == [(root, TENANT)]
    assert out["data"]["stopped_in_process"] == 0


@pytest.mark.asyncio
async def test_route_answers_503_when_capabilities_could_not_be_revoked(no_events):
    root, child = uuid.uuid4(), uuid.uuid4()
    err = CapabilityRevokeError(SimpleNamespace(id=root), RuntimeError("store down"))
    pm = _PM(_row(), held={root, child})
    engine = _Engine([child], error=err)

    with tenant_scope(TENANT), pytest.raises(HTTPException) as exc:
        await cancel_task(root, pm=pm, engine=engine)

    assert exc.value.status_code == 503
    assert "could not be revoked" in exc.value.detail
    # Stopped first, even though the revocation failed.
    assert pm.stop_calls == [root, child]


@pytest.mark.asyncio
async def test_route_still_refuses_a_finished_task(no_events):
    pm = _PM(_row("completed"), held=set())
    engine = _Engine([])

    with tenant_scope(TENANT), pytest.raises(HTTPException) as exc:
        await cancel_task(uuid.uuid4(), pm=pm, engine=engine)

    assert exc.value.status_code == 409
    assert engine.calls == []
