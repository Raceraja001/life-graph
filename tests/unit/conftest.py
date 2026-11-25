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
