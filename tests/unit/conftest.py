"""Unit-test defaults."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _kill_switch_no_config_row(request, monkeypatch):
    """The kill switch reads TenantConfig; unit tests have no database.

    Without this, every gate that asks autonomy_stopped() (scheduler, watchers,
    delegation, dev-runner claims, errand approvals; 2026-11-25) would fail
    closed on the missing database and refuse. A unit test's tenant is an
    unprovisioned one: no config row, which the kill switch reads as "not
    paused" for those gates and as paused for the auto-fix gate, exactly as a
    real unprovisioned tenant. A test that sets the state itself patches
    kill_switch._pause_state after this runs; a module that tests the real
    reader sets ``REAL_KILL_SWITCH = True``.
    """
    if getattr(request.module, "REAL_KILL_SWITCH", False):
        return
    from life_graph.autonomy import kill_switch

    async def no_config_row(tenant_id):
        return None

    monkeypatch.setattr(kill_switch, "_pause_state", no_config_row)


@pytest.fixture(autouse=True)
def _no_dev_task_event_writes(request, monkeypatch):
    """Dev-task events stay in memory; unit tests have no database.

    Dispatcher, runner and runtime tests call task_events.emit() with real
    task ids. That starts a background writer on the shared (session-scoped)
    event loop, which then tried to reach the real database and logged
    "Dropped a dev task event" / "Could not write ... dev task event(s)"
    seconds later -- inside whichever test happened to be running. Tests that
    assert on caplog then failed at random under xdist (2026-11-25:
    test_exception_logging, CI failed at least twice).

    Here the writer's database step is a no-op, and a writer started by this
    test is cancelled when it ends, so nothing crosses into the next test. A
    module that tests the real writer sets ``REAL_TASK_EVENTS = True``.
    """
    if getattr(request.module, "REAL_TASK_EVENTS", False):
        yield
        return
    from life_graph.services.dev import task_events

    async def no_write(batch):
        return None

    monkeypatch.setattr(task_events, "_write", no_write)
    before = task_events._consumer
    yield
    started = task_events._consumer
    if started is not None and started is not before and not started.done():
        started.cancel()
    task_events._queue = None
    task_events._consumer = None
