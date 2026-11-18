"""DevTaskRunner's own rules, without a database (claim and run are injected)."""

from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest

from life_graph.services.dev import runner as runner_mod
from life_graph.services.dev.runner import DevTaskRunner


def _task(interactive=True):
    return SimpleNamespace(id=uuid.uuid4(), title="t", properties={"interactive": interactive})


class Queue:
    """A fake claim: hands out tasks, honouring allow_unattended like the real one."""

    def __init__(self, tasks):
        self.tasks = list(tasks)
        self.calls: list[dict] = []

    async def __call__(self, _sf, **kw):
        self.calls.append(kw)
        for t in self.tasks:
            if kw.get("allow_unattended", True) or t.properties["interactive"]:
                self.tasks.remove(t)
                return t
        return None


class Gate:
    """A fake run that blocks until released."""

    def __init__(self):
        self.started: list[str] = []
        self.release = asyncio.Event()

    async def __call__(self, _sf, task):
        self.started.append(str(task.id))
        await self.release.wait()


async def test_never_more_than_max_concurrency():
    gate = Gate()
    r = DevTaskRunner(
        None,
        claim=Queue([_task() for _ in range(5)]),
        run_task=gate,
        max_concurrency=2,
        listen=False,
    )
    assert await r.fill() == 2
    await asyncio.sleep(0)
    assert len(gate.started) == 2 and len(r.running) == 2
    assert await r.fill() == 0  # full: does not even claim
    gate.release.set()
    await r.run_until_idle()
    assert len(gate.started) == 5


async def test_at_most_one_unattended_task_at_a_time():
    gate = Gate()
    queue = Queue([_task(False), _task(False), _task(True)])
    r = DevTaskRunner(None, claim=queue, run_task=gate, max_concurrency=3, listen=False)
    await r.fill()
    await asyncio.sleep(0)
    # One unattended + the interactive one; the second unattended waits.
    assert len(r.running) == 2
    assert queue.calls[-1]["allow_unattended"] is False
    gate.release.set()
    await r.run_until_idle()
    assert len(gate.started) == 3


async def test_a_cancel_it_asked_for_is_recorded_and_swallowed(monkeypatch):
    marked = []

    async def mark(self, tid):
        marked.append(tid)

    monkeypatch.setattr(DevTaskRunner, "_mark_cancelled", mark)
    gate = Gate()
    task = _task()
    r = DevTaskRunner(None, claim=Queue([task]), run_task=gate, listen=False)
    await r.fill()
    await asyncio.sleep(0)
    tid = str(task.id)
    r._cancelling.add(tid)
    run = r._running[tid]
    run.cancel()
    await asyncio.gather(run, return_exceptions=True)
    assert marked == [tid]
    assert run.cancelled() is False  # ended quietly, not as a cancelled task
    assert r.running == []


async def test_a_shutdown_cancel_leaves_the_row_for_recovery(monkeypatch):
    marked = []

    async def mark(self, tid):
        marked.append(tid)

    monkeypatch.setattr(DevTaskRunner, "_mark_cancelled", mark)
    r = DevTaskRunner(None, claim=Queue([_task()]), run_task=Gate(), listen=False)
    await r.fill()
    await asyncio.sleep(0)
    await r.stop(drain_seconds=0)
    assert marked == []  # stays "running"; fail_interrupted recovers it


async def test_stop_drains_before_cancelling():
    gate = Gate()
    r = DevTaskRunner(None, claim=Queue([_task()]), run_task=gate, listen=False)
    await r.fill()
    await asyncio.sleep(0)

    async def finish_soon():
        await asyncio.sleep(0.05)
        gate.release.set()

    asyncio.get_running_loop().create_task(finish_soon())
    await r.stop(drain_seconds=5)
    assert r.running == []


async def test_a_crashing_task_does_not_take_the_runner_down():
    async def boom(_sf, _task):
        raise RuntimeError("driver exploded")

    r = DevTaskRunner(None, claim=Queue([_task(), _task()]), run_task=boom, listen=False)
    await r.run_until_idle()
    assert r.running == []


async def test_notify_wakes_the_runner_in_this_process():
    r = DevTaskRunner(None, claim=Queue([]), run_task=Gate(), listen=False)
    runner_mod.set_local_runner(r)
    try:
        await runner_mod.notify_runner()
        await runner_mod.notify_runner(cancel=True)
        assert r._wake.is_set() and r._cancel_wake.is_set()
    finally:
        runner_mod.set_local_runner(None)


@pytest.mark.parametrize(
    ("lease", "stale"),
    [(None, True), ({}, True), ({"heartbeat_at": "garbage"}, True)],
)
def test_a_missing_or_broken_lease_is_stale(lease, stale):
    assert runner_mod.lease_is_stale(lease) is stale


def test_a_fresh_lease_is_alive():
    from datetime import UTC, datetime

    assert runner_mod.lease_is_stale({"heartbeat_at": datetime.now(UTC).isoformat()}) is False


async def test_stop_drains_while_run_forever_is_running(monkeypatch):
    """stop() wakes the main loop; its exit must not cancel what stop() drains."""
    monkeypatch.setattr("life_graph.services.dev.tasks.QUEUE_POLL_SECONDS", 0.01)
    gate = Gate()
    done = []

    async def run(_sf, task):
        await gate(_sf, task)
        done.append(str(task.id))

    r = DevTaskRunner(None, claim=Queue([_task()]), run_task=run, listen=False)
    r.heartbeat = _noop  # no DB
    r.check_cancels = _noop_list
    forever = asyncio.get_running_loop().create_task(r.run_forever())
    for _ in range(100):
        if r.running:
            break
        await asyncio.sleep(0.01)

    async def finish_soon():
        await asyncio.sleep(0.2)
        gate.release.set()

    asyncio.get_running_loop().create_task(finish_soon())
    await r.stop(drain_seconds=5)
    forever.cancel()
    await asyncio.gather(forever, return_exceptions=True)
    assert len(done) == 1  # it finished; it was not cut off


async def _noop():
    return None


async def _noop_list():
    return []
