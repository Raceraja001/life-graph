"""The hourly watcher cron skips a tenant whose autonomy is paused (kill switch).

Before 2026-11-26 only origination checked the kill switch, after the
watchers had already run and routed their notifications. Now run_watchers
asks ``autonomy_stopped`` for each tenant first and runs none of a paused
tenant's watchers. A database error reading the flag skips the tenant too
(fail closed).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import life_graph.runtime as runtime
from life_graph.autonomy import kill_switch
from life_graph.watchers.app_uptime_watcher import AppUptimeWatcher
from life_graph.workers import tasks


@pytest.fixture(autouse=True)
def _fresh_cache():
    kill_switch._pause_cache.clear()
    yield
    kill_switch._pause_cache.clear()


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return [(r,) for r in self._rows]

    def scalars(self):
        return SimpleNamespace(all=lambda: self._rows)


def _wire(monkeypatch, tenants, paused):
    """A fake database with one enabled watcher per tenant, and recorders.

    The first query lists the tenants; every later one is the configs of the
    tenant whose context was set last (run_watchers sets it per tenant).
    """
    current = {"tid": None}
    asked = []

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def execute(self, stmt):
            if current["tid"] is None:
                return _Result(list(tenants))
            asked.append(current["tid"])
            config = SimpleNamespace(watcher_name=AppUptimeWatcher.name, config={})
            return _Result([config])

    monkeypatch.setattr(tasks, "async_session", _Session)
    monkeypatch.setattr(tasks, "set_tenant_context", lambda tid, *a: current.update(tid=tid))

    async def read(tenant_id):
        value = paused.get(tenant_id, False)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(kill_switch, "_pause_state", read)

    ran = []

    async def lifecycle(watcher_cls, tid, wconfig, watch_event):
        ran.append(tid)
        return [{"title": "down", "severity": "critical"}], None

    monkeypatch.setattr(tasks, "_run_lifecycle_watcher", lifecycle)

    announced = []

    async def announce(name, tid, events, ms, origination):
        announced.append(tid)

    monkeypatch.setattr(tasks, "_announce_watcher_events", announce)
    engine = SimpleNamespace(route_event=AsyncMock())
    monkeypatch.setattr(runtime, "get_watcher_notification_engine", lambda: engine)
    monkeypatch.setattr(runtime, "get_process_manager", lambda: SimpleNamespace(spawn=AsyncMock()))
    return SimpleNamespace(ran=ran, asked=asked, announced=announced, engine=engine)


def _notified(seen):
    return [c.args[0] for c in seen.engine.route_event.await_args_list]


@pytest.mark.asyncio
async def test_a_paused_tenants_watchers_do_not_run(monkeypatch):
    seen = _wire(monkeypatch, ["paused-t", "live-t"], {"paused-t": True})

    out = await tasks.run_watchers({})

    assert seen.ran == ["live-t"]
    assert seen.asked == ["live-t"]  # a paused tenant's configs are not even read
    assert seen.announced == ["live-t"]  # no WATCHER_COMPLETED, no origination
    assert _notified(seen) == ["live-t"]
    assert out["results"]["paused-t"] == {"events": 0, "skipped": "autonomy_paused"}
    assert out["results"]["live-t"] == {"events": 1}


@pytest.mark.asyncio
async def test_an_unreadable_pause_flag_skips_the_tenant(monkeypatch):
    seen = _wire(monkeypatch, ["flaky-t", "live-t"], {"flaky-t": RuntimeError("db down")})

    out = await tasks.run_watchers({})

    assert seen.ran == ["live-t"]
    assert _notified(seen) == ["live-t"]
    assert out["results"]["flaky-t"]["skipped"] == "autonomy_paused"


@pytest.mark.asyncio
async def test_a_tenant_with_no_config_row_still_runs(monkeypatch):
    """autonomy_stopped reads "no config row" as not paused, as before."""
    seen = _wire(monkeypatch, ["new-t"], {"new-t": None})

    await tasks.run_watchers({})

    assert seen.ran == ["new-t"]
    assert _notified(seen) == ["new-t"]
