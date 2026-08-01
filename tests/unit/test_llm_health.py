"""Unit tests for LLMHealth — Redis-backed, fail-open."""

from __future__ import annotations

import pytest

from life_graph.services.llm_health import LLMHealth


class FakeRedis:
    """Minimal async Redis double: hashes + per-key expiry flag + wall clock."""

    def __init__(self, now: float = 1_000_000.0):
        self.h: dict[str, dict[str, str]] = {}
        self.expired: set[str] = set()
        self.now = now

    async def hset(self, key, mapping=None, **kw):
        self.h.setdefault(key, {})
        self.h[key].update({k: str(v) for k, v in (mapping or {}).items()})

    async def hgetall(self, key):
        return dict(self.h.get(key, {}))

    async def expire(self, key, ttl):
        return True

    async def keys(self, pattern):
        return [k for k in self.h if k.startswith("llm:health:")]


@pytest.fixture
def health(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr("life_graph.services.llm_health.get_redis", lambda: fake)
    h = LLMHealth(clock=lambda: fake.now)
    return h, fake


@pytest.mark.asyncio
async def test_record_success_sets_last_success_and_latency(health):
    h, fake = health
    await h.record_success("gemini/flash", latency_ms=120)
    rec = fake.h["llm:health:gemini/flash"]
    assert float(rec["last_success_at"]) == fake.now
    assert float(rec["avg_latency_ms"]) == pytest.approx(120, abs=1)
    assert rec.get("consecutive_failures", "0") == "0"


@pytest.mark.asyncio
async def test_429_sets_cooldown_and_in_cooldown_true(health):
    h, fake = health
    await h.record_failure("m1", "429")
    await h.set_cooldown("m1", 60)
    assert await h.in_cooldown("m1") is True
    fake.now += 61  # cooldown elapsed
    assert await h.in_cooldown("m1") is False


@pytest.mark.asyncio
async def test_in_cooldown_false_for_unknown_model(health):
    h, _ = health
    assert await h.in_cooldown("never-seen") is False


@pytest.mark.asyncio
async def test_fail_open_when_redis_unavailable(monkeypatch):
    monkeypatch.setattr("life_graph.services.llm_health.get_redis", lambda: None)
    h = LLMHealth()
    # No exceptions; in_cooldown False; records are no-ops.
    await h.record_success("m", 10)
    await h.record_failure("m", "429")
    await h.set_cooldown("m", 60)
    assert await h.in_cooldown("m") is False
    assert await h.snapshot() == []


@pytest.mark.asyncio
async def test_snapshot_shape(health):
    h, fake = health
    await h.record_success("m1", 100)
    await h.record_failure("m2", "429")
    await h.set_cooldown("m2", 60)
    snap = {r["model"]: r for r in await h.snapshot()}
    assert snap["m1"]["state"] == "up"
    assert snap["m2"]["state"] == "cooling"
    assert "last_error" in snap["m2"] and snap["m2"]["last_error"] == "429"
