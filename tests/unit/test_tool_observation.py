"""Unit tests for tool-exhaust observation sampling logic."""

from __future__ import annotations

from life_graph.services.tool_observation import ToolObservationHook


def _hook(rng_value=0.99, daily_cap=500, sample_rate=0.10):
    return ToolObservationHook(
        daily_cap=daily_cap, sample_rate=sample_rate, rng=lambda: rng_value
    )


def test_low_signal_classification():
    assert ToolObservationHook.is_low_signal({"exit_status": "ok"}) is True
    assert ToolObservationHook.is_low_signal(
        {"exit_status": "ok", "project_id": "p1"}
    ) is False
    assert ToolObservationHook.is_low_signal({"exit_status": "error"}) is False


def test_high_signal_always_stored_even_over_cap():
    h = _hook(rng_value=0.99)  # rng would drop a sampled low-signal
    assert h.should_store(count_today=10_000, low_signal=False) is True


def test_low_signal_stored_under_cap():
    h = _hook()
    assert h.should_store(count_today=10, low_signal=True) is True


def test_low_signal_sampled_over_cap():
    # Over cap: keep only when rng < sample_rate.
    keep = _hook(rng_value=0.05, sample_rate=0.10)
    drop = _hook(rng_value=0.50, sample_rate=0.10)
    assert keep.should_store(count_today=600, low_signal=True) is True
    assert drop.should_store(count_today=600, low_signal=True) is False


async def test_call_is_noop_without_tenant_context():
    # No tenant context set → must not touch the DB (session_factory unused).
    called = {"n": 0}

    def boom_factory():
        called["n"] += 1
        raise AssertionError("should not open a session")

    h = ToolObservationHook(session_factory=boom_factory)
    await h({"tool": "x", "exit_status": "ok"})
    assert called["n"] == 0
