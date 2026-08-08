"""Unit tests for ResilientLLM ordered failover."""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import life_graph.services.resilient_llm as rl
from life_graph.services.resilient_llm import ResilientLLM, ResilientLLMExhausted


def _resp(text="ok"):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


class FakeStream:
    """Minimal async-iterator stand-in for litellm's CustomStreamWrapper.

    Real streaming calls make no network request until first iterated —
    this fake mirrors that: `raise_on_first` simulates a connect/first-byte
    failure (e.g. a 404 for a deprecated model), surfacing only on the
    first `__anext__()`, exactly like the real bug this fake exists to
    reproduce.
    """

    def __init__(self, chunks=None, raise_on_first=None):
        self._chunks = iter(chunks or [])
        self._raise_on_first = raise_on_first
        self._first_call = True

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._first_call and self._raise_on_first is not None:
            self._first_call = False
            raise self._raise_on_first
        self._first_call = False
        try:
            return next(self._chunks)
        except StopIteration:
            raise StopAsyncIteration from None


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


def test_bridge_sets_env_from_settings_when_unset(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_BASE", raising=False)
    monkeypatch.setattr(rl.settings, "openrouter_api_key", "sk-or-test", raising=False)
    monkeypatch.setattr(
        rl.settings, "openrouter_url", "https://openrouter.ai/api/v1", raising=False
    )

    rl._bridge_provider_credentials()

    assert os.environ["OPENROUTER_API_KEY"] == "sk-or-test"
    assert os.environ["OPENROUTER_API_BASE"] == "https://openrouter.ai/api/v1"


def test_bridge_does_not_overwrite_existing_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "pre-existing-key")
    monkeypatch.setenv("OPENROUTER_API_BASE", "https://pre-existing.example/v1")
    monkeypatch.setattr(rl.settings, "openrouter_api_key", "sk-or-should-not-win", raising=False)
    monkeypatch.setattr(
        rl.settings, "openrouter_url", "https://should-not-win.example", raising=False
    )

    rl._bridge_provider_credentials()

    assert os.environ["OPENROUTER_API_KEY"] == "pre-existing-key"
    assert os.environ["OPENROUTER_API_BASE"] == "https://pre-existing.example/v1"


def test_bridge_noop_when_settings_empty(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_BASE", raising=False)
    monkeypatch.setattr(rl.settings, "openrouter_api_key", "", raising=False)
    monkeypatch.setattr(rl.settings, "openrouter_url", "", raising=False)

    rl._bridge_provider_credentials()

    assert "OPENROUTER_API_KEY" not in os.environ
    assert "OPENROUTER_API_BASE" not in os.environ


@pytest.mark.asyncio
async def test_streaming_first_chunk_failure_falls_over(monkeypatch):
    """Regression test for the 2026-08-08 incident: a streaming call that
    fails on its first chunk (e.g. a 404 for a deprecated model) must fail
    over to the next model in the chain, not silently return a broken
    stream to the caller."""
    bad_stream = FakeStream(raise_on_first=rl.litellm.APIError(404, "not found", "prov", "A"))
    good_stream = FakeStream(chunks=["chunk1", "chunk2"])
    call = AsyncMock(side_effect=[bad_stream, good_stream])
    monkeypatch.setattr(rl.litellm, "acompletion", call)
    h = FakeHealth()

    resp = await ResilientLLM(health=h).acompletion(
        messages=[{"role": "user", "content": "q"}], stream=True
    )
    collected = [chunk async for chunk in resp]

    assert collected == ["chunk1", "chunk2"]
    assert h.failure[0][0] == "A"  # first model recorded as failed
    assert h.success == ["B"]  # second model served the stream


@pytest.mark.asyncio
async def test_streaming_success_rechains_first_chunk(monkeypatch):
    """A working stream must yield every chunk exactly once — the first
    chunk (fetched during validation) must not be lost or duplicated."""
    stream = FakeStream(chunks=["a", "b", "c"])
    call = AsyncMock(return_value=stream)
    monkeypatch.setattr(rl.litellm, "acompletion", call)
    h = FakeHealth()

    resp = await ResilientLLM(health=h).acompletion(
        messages=[{"role": "user", "content": "q"}], stream=True
    )
    collected = [chunk async for chunk in resp]

    assert collected == ["a", "b", "c"]
    assert h.success == ["A"]


@pytest.mark.asyncio
async def test_streaming_empty_stream_treated_as_failure(monkeypatch):
    """A stream with zero chunks (StopAsyncIteration on the very first
    pull) must count as a failure and fail over, not a silent empty
    success."""
    empty_stream = FakeStream(chunks=[])
    good_stream = FakeStream(chunks=["hi"])
    call = AsyncMock(side_effect=[empty_stream, good_stream])
    monkeypatch.setattr(rl.litellm, "acompletion", call)
    h = FakeHealth()

    resp = await ResilientLLM(health=h).acompletion(
        messages=[{"role": "user", "content": "q"}], stream=True
    )
    collected = [chunk async for chunk in resp]

    assert collected == ["hi"]
    assert h.failure[0][0] == "A"
    assert h.success == ["B"]
