"""A 7-day cooldown held in a process dict is not a cooldown.

``RecallEngine._surfaced_memory_ids`` was the only record that a memory had
been surfaced. It is per-instance, so:

* a restart or deploy cleared it and every suppressed memory resurfaced;
* the ARQ worker and the web process each kept their own, so a memory
  suppressed in one resurfaced immediately from the other;
* multiple uvicorn workers each kept another copy again.

``settings.recall_cooldown_days`` defaults to 7. Nothing enforced it beyond
the life of one object. Redis now holds the durable record, keyed per tenant
with a TTL equal to the cooldown, and the dict stays as a local cache.

Redis being unavailable must fail OPEN: a missed cooldown resurfaces a
memory early, which is mildly annoying. A hard failure would break recall.
"""

from unittest.mock import MagicMock

import pytest

import life_graph.core.tenant as tenant_mod
import life_graph.services.recall as recall_mod
from life_graph.core.tenant import set_tenant_context
from life_graph.services.recall import RecallEngine


@pytest.fixture(autouse=True)
def _isolate_tenant_context():
    """Put the contextvar back exactly as it was.

    set_tenant_context() writes a module-level ContextVar with no unset. Left
    set, it leaks into every later test in the session — including the ones
    that assert behaviour when NO tenant context exists, which then fail only
    when the full suite runs.
    """
    token = tenant_mod._tenant_id_var.set("cooldown-tenant")
    user_token = tenant_mod._user_id_var.set("")
    try:
        yield
    finally:
        tenant_mod._tenant_id_var.reset(token)
        tenant_mod._user_id_var.reset(user_token)


class _FakeRedis:
    """Minimal stand-in with the setex/mget/pipeline surface recall uses."""

    def __init__(self):
        self.store: dict[str, str] = {}
        self.mget_calls = 0

    def pipeline(self):
        outer = self

        class _Pipe:
            def __init__(self):
                self._ops = []

            def setex(self, key, ttl, value):
                self._ops.append((key, ttl, value))

            async def execute(self):
                for key, _ttl, value in self._ops:
                    outer.store[key] = value

        return _Pipe()

    async def mget(self, keys):
        self.mget_calls += 1
        return [self.store.get(k) for k in keys]


def _engine():
    return RecallEngine(MagicMock(), MagicMock(), MagicMock())


@pytest.fixture
def redis(monkeypatch):
    set_tenant_context("cooldown-tenant")
    fake = _FakeRedis()
    monkeypatch.setattr(recall_mod, "get_redis", lambda: fake)
    return fake


@pytest.mark.asyncio
async def test_cooldown_survives_a_restart(redis):
    """The regression: a fresh engine must still honour the cooldown."""
    first = _engine()
    await first._remember_surfaced(["mem-1"])

    # A new process: empty _surfaced_memory_ids, same Redis.
    second = _engine()
    assert second._surfaced_memory_ids == {}

    kept = await second._apply_anti_annoyance([{"id": "mem-1", "tags": []}])
    assert kept == [], "a restart cleared the only record of the surfacing"


@pytest.mark.asyncio
async def test_cooldown_is_shared_across_processes(redis):
    """Web process suppresses it; the worker must suppress it too."""
    web, worker = _engine(), _engine()
    await web._remember_surfaced(["mem-2"])
    assert await worker._apply_anti_annoyance([{"id": "mem-2", "tags": []}]) == []


@pytest.mark.asyncio
async def test_a_memory_never_surfaced_is_not_suppressed(redis):
    engine = _engine()
    kept = await engine._apply_anti_annoyance([{"id": "fresh", "tags": []}])
    assert len(kept) == 1


@pytest.mark.asyncio
async def test_the_record_is_tenant_scoped(redis):
    engine = _engine()
    await engine._remember_surfaced(["shared-id"])
    set_tenant_context("other-tenant")
    kept = await engine._apply_anti_annoyance([{"id": "shared-id", "tags": []}])
    assert len(kept) == 1, "one tenant's cooldown must not suppress another's memory"


@pytest.mark.asyncio
async def test_the_ttl_matches_the_configured_cooldown(redis):
    captured = {}

    class _Pipe:
        def setex(self, key, ttl, value):
            captured["ttl"] = ttl

        async def execute(self):
            return None

    redis.pipeline = lambda: _Pipe()
    await _engine()._remember_surfaced(["mem-3"])
    assert captured["ttl"] == recall_mod._COOLDOWN_SECONDS


@pytest.mark.asyncio
async def test_one_round_trip_for_the_whole_batch(redis):
    """Per-candidate lookups would put a network call in a hot loop."""
    engine = _engine()
    cands = [{"id": f"m{i}", "tags": []} for i in range(25)]
    await engine._apply_anti_annoyance(cands)
    assert redis.mget_calls == 1


# ── Degraded mode ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_recall_still_works_without_redis(monkeypatch):
    set_tenant_context("cooldown-tenant")
    monkeypatch.setattr(recall_mod, "get_redis", lambda: None)
    engine = _engine()
    await engine._remember_surfaced(["mem-4"])  # must not raise
    kept = await engine._apply_anti_annoyance([{"id": "mem-4", "tags": []}])
    assert len(kept) == 1, "no Redis must fail open, not block recall"


@pytest.mark.asyncio
async def test_an_erroring_redis_fails_open(monkeypatch):
    set_tenant_context("cooldown-tenant")

    class _Broken:
        def pipeline(self):
            raise RuntimeError("redis down")

        async def mget(self, keys):
            raise RuntimeError("redis down")

    monkeypatch.setattr(recall_mod, "get_redis", lambda: _Broken())
    engine = _engine()
    await engine._remember_surfaced(["mem-5"])  # must not raise
    kept = await engine._apply_anti_annoyance([{"id": "mem-5", "tags": []}])
    assert len(kept) == 1


@pytest.mark.asyncio
async def test_in_process_cache_still_applies_without_redis(monkeypatch):
    """Within one process the old behaviour is unchanged."""
    from datetime import UTC, datetime

    set_tenant_context("cooldown-tenant")
    monkeypatch.setattr(recall_mod, "get_redis", lambda: None)
    engine = _engine()
    engine._surfaced_memory_ids["mem-6"] = datetime.now(UTC)
    assert await engine._apply_anti_annoyance([{"id": "mem-6", "tags": []}]) == []
