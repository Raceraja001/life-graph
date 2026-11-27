"""Phase 4b: the gate before every automatic action (kill switch, D4 share, Governor)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from life_graph.drivers import accounts_hook
from life_graph.services.dev import automation_gate as gate


@pytest.fixture
def world(monkeypatch):
    state = {"paused": False, "preview": None, "allowed": True, "authorized": []}

    async def stopped(_t):
        return state["paused"]

    async def preview(driver, tenant_id, *, unattended, account_id=None):
        state["preview_args"] = (driver, unattended, account_id)
        return state["preview"]

    async def authorize(tenant_id, category, estimated_usd=0.0, *, interactive=False):
        state["authorized"].append(interactive)
        return SimpleNamespace(allowed=state["allowed"], reason="monthly budget exhausted")

    monkeypatch.setattr(gate, "autonomy_stopped", stopped)
    monkeypatch.setattr(accounts_hook, "preview", preview)
    monkeypatch.setattr(gate.governor, "authorize", authorize)
    return state


async def test_open_when_nothing_refuses(world):
    assert await gate.blockers("t1") == []
    assert world["authorized"] == [False]  # always as an unattended spend


async def test_the_kill_switch_refuses_first(world):
    world["paused"] = True
    assert await gate.blockers("t1", driver="codex") == ["Autonomy is paused (kill switch)."]
    assert world["authorized"] == []


async def test_the_subscription_share_refuses_for_the_pinned_account(world):
    world["preview"] = {"state": "over_budget", "budget": {"reason": "over 90% of the window"}}
    out = await gate.blockers("t1", driver="codex", account_id="acc-1")
    assert out and "subscription share" in out[0]
    assert world["preview_args"] == ("codex", True, "acc-1")
    world["preview"] = {"state": "cooling"}
    assert "cooling down" in (await gate.blockers("t1", driver="codex"))[0]
    world["preview"] = {"state": "error"}
    assert "could not be read" in (await gate.blockers("t1", driver="codex"))[0]  # fail closed


async def test_a_subscription_run_skips_the_dollar_cap(world):
    world["preview"] = {"state": "selected", "kind": "subscription"}
    world["allowed"] = False
    assert await gate.blockers("t1", driver="codex") == []
    assert world["authorized"] == []


async def test_the_governor_refuses_an_api_billed_run(world):
    world["preview"] = {"state": "selected", "kind": "api_key"}
    world["allowed"] = False
    assert await gate.blockers("t1", driver="codex") == ["Budget: monthly budget exhausted."]
