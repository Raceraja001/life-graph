"""Unit tests for ResilientLLM ordered failover."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import life_graph.services.resilient_llm as rl
from life_graph.services.resilient_llm import ResilientLLM, ResilientLLMExhausted


def _resp(text="ok"):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


class FakeHealth:
    def __init__(self, cooling=None):
        self.cooling = set(cooling or [])
        self.success = []
        self.failure = []
        self.cooldowns = {}

    async def in_cooldown(self, m):
        return m in self.cooling

    async def cooldown_until(self, m):
        return self.cooldowns.get(m, 0)

    async def record_success(self, m, latency_ms):
        self.success.append(m)

    async def record_failure(self, m, kind):
        self.failure.append((m, kind))

    async def set_cooldown(self, m, seconds):
        self.cooldowns[m] = seconds
        self.cooling.add(m)


@pytest.fixture(autouse=True)
def _chain(monkeypatch):
    # primary "A" + fallback chain [B, C]
    monkeypatch.setattr(rl.settings, "llm_fallback_chain", "B,C", raising=False)
    monkeypatch.setattr(rl.settings, "llm_model_cheap", "A", raising=False)
    monkeypatch.setattr(rl.settings, "llm_cooldown_429_seconds", 60, raising=False)
    monkeypatch.setattr(rl.settings, "llm_cooldown_error_seconds", 30, raising=False)


@pytest.mark.asyncio
async def test_first_model_success(monkeypatch):
    call = AsyncMock(return_value=_resp("hi"))
    monkeypatch.setattr(rl.litellm, "acompletion", call)
    h = FakeHealth()
    out = await ResilientLLM(health=h).chat([{"role": "user", "content": "q"}])
    assert out == "hi"
    assert call.call_args.kwargs["model"] == "A"  # primary tried first
    assert h.success == ["A"]


@pytest.mark.asyncio
async def test_429_benches_and_falls_over(monkeypatch):
    call = AsyncMock(side_effect=[rl.litellm.RateLimitError("rate", "prov", "A"), _resp("hi")])
    monkeypatch.setattr(rl.litellm, "acompletion", call)
    h = FakeHealth()
    out = await ResilientLLM(health=h).chat([{"role": "user", "content": "q"}])
    assert out == "hi"
    assert h.failure[0] == ("A", "429")
    assert "A" in h.cooldowns and h.cooldowns["A"] == 60  # 429 cooldown
    assert h.success == ["B"]  # second model served


@pytest.mark.asyncio
async def test_cooling_model_skipped(monkeypatch):
    call = AsyncMock(return_value=_resp("hi"))
    monkeypatch.setattr(rl.litellm, "acompletion", call)
    h = FakeHealth(cooling={"A"})
    await ResilientLLM(health=h).chat([{"role": "user", "content": "q"}])
    assert call.call_args.kwargs["model"] == "B"  # A skipped (cooling)


@pytest.mark.asyncio
async def test_all_fail_raises_exhausted(monkeypatch):
    call = AsyncMock(side_effect=rl.litellm.APIError(500, "boom", "prov", "m"))
    monkeypatch.setattr(rl.litellm, "acompletion", call)
    h = FakeHealth()
    with pytest.raises(ResilientLLMExhausted):
        await ResilientLLM(health=h).chat([{"role": "user", "content": "q"}])
    assert len(h.failure) >= 3  # A, B, C all recorded


@pytest.mark.asyncio
async def test_all_cooling_tries_least_recently_failed(monkeypatch):
    # A,B,C all cooling; the final retry should still make ONE live attempt.
    call = AsyncMock(return_value=_resp("hi"))
    monkeypatch.setattr(rl.litellm, "acompletion", call)
    h = FakeHealth(cooling={"A", "B", "C"})
    h.cooldowns = {"A": 100, "B": 10, "C": 50}  # B soonest to recover
    out = await ResilientLLM(health=h).chat([{"role": "user", "content": "q"}])
    assert out == "hi"
    assert call.await_count == 1  # exactly one forced attempt
