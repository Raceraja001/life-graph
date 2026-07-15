"""Wiring test: the Governor gates driver dispatch BEFORE the money is spent.

The critical guarantee — an over-budget autonomous dispatch never reaches the
driver (no LLM call, no cost). The happy-path record() call is covered by
test_governor.py; here we lock the short-circuit.
"""

from __future__ import annotations

import uuid

import life_graph.drivers.dispatcher as disp_mod
from life_graph.core.budget import BudgetDecision
from life_graph.drivers.base import ContextPacket, DriverResult
from life_graph.drivers.dispatcher import TaskDispatcher


class _FakeSession:
    async def close(self):
        pass

    async def commit(self):
        pass

    async def rollback(self):
        pass


class _SpyDriver:
    name = "spy"

    def __init__(self):
        self.dispatched = False

    def cost_per_task(self) -> float:
        return 0.10

    async def dispatch(self, packet, workdir, timeout=300) -> DriverResult:
        self.dispatched = True
        return DriverResult(success=True, output="ran", cost_usd=0.10)


def _denied(**_kw):
    async def _f(*_a, **_k):
        return BudgetDecision(
            allowed=False, throttled=True,
            reason="monthly budget exhausted; autonomous spend denied",
            spent_usd=10.0, cap_usd=10.0, remaining_usd=0.0,
        )
    return _f


async def test_denied_dispatch_never_calls_driver(monkeypatch):
    driver = _SpyDriver()
    disp = TaskDispatcher(session_factory=lambda: _FakeSession(), event_bus=None)

    # Stub the pre-gate pipeline so we reach the budget gate deterministically.
    async def _no_wip(*_a, **_k):
        return None

    async def _packet(*_a, **_k):
        return ContextPacket(
            task_id=uuid.uuid4(), tenant_id="t1", task_type="code", instruction="do it"
        )

    async def _pick(*_a, **_k):
        return driver

    async def _emit(*_a, **_k):
        return None

    monkeypatch.setattr(disp, "_check_wip_limits", _no_wip)
    monkeypatch.setattr(disp._context_builder, "build_packet", _packet)
    monkeypatch.setattr(disp, "_select_driver", _pick)
    monkeypatch.setattr(disp, "_emit", _emit)
    # Governor denies the spend.
    monkeypatch.setattr(disp_mod.governor, "authorize", _denied())

    result = await disp.dispatch_task(
        tenant_id="t1", task_id=str(uuid.uuid4()), instruction="do it", task_type="code",
    )

    assert result.success is False
    assert result.metadata.get("budget_throttled") is True
    assert driver.dispatched is False  # the money was never spent


async def test_interactive_dispatch_reaches_driver_even_when_low(monkeypatch):
    """Interactive dispatches are authorized (allowed) and DO reach the driver."""
    driver = _SpyDriver()
    disp = TaskDispatcher(session_factory=lambda: _FakeSession(), event_bus=None)

    async def _no_wip(*_a, **_k):
        return None

    async def _packet(*_a, **_k):
        return ContextPacket(
            task_id=uuid.uuid4(), tenant_id="t1", task_type="code", instruction="do it"
        )

    async def _pick(*_a, **_k):
        return driver

    async def _emit(*_a, **_k):
        return None

    async def _allow(*_a, **_k):
        return BudgetDecision(
            allowed=True, throttled=True, reason="interactive allowed over cap",
            spent_usd=99.0, cap_usd=10.0, remaining_usd=0.0,
        )

    async def _record(*_a, **_k):
        return None

    monkeypatch.setattr(disp, "_check_wip_limits", _no_wip)
    monkeypatch.setattr(disp._context_builder, "build_packet", _packet)
    monkeypatch.setattr(disp, "_select_driver", _pick)
    monkeypatch.setattr(disp, "_emit", _emit)
    monkeypatch.setattr(disp, "_record_stats", _record)  # skip DB stats tail
    monkeypatch.setattr(disp_mod.governor, "authorize", _allow)
    monkeypatch.setattr(disp_mod.governor, "record", _record)

    result = await disp.dispatch_task(
        tenant_id="t1", task_id=str(uuid.uuid4()), instruction="do it",
        task_type="code", verify_chain=[], interactive=True,
    )

    assert driver.dispatched is True
    assert result.success is True
