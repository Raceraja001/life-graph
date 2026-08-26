# LLM Resilient Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the bug that let a streaming LLM failure bypass `ResilientLLM`'s
failover entirely (today's production "Internal error" root cause), then make
the fallback chain itself smarter: health-ranked ordering, escalating backoff
for chronically broken models, and one guaranteed paid last-resort model.

**Architecture:** All changes are in-place extensions of the existing
`ResilientLLM`/`LLMHealth` pair in `life_graph/services/` — no new service,
no new storage. `LLMHealth` already records `consecutive_failures` and
`avg_latency_ms` per model in Redis; this plan makes `ResilientLLM` actually
use that data, and closes the gap where streaming calls skip its protection.

**Tech Stack:** Python 3.11, `litellm.acompletion`, Redis-backed health hash
(`life_graph/services/llm_health.py`), `pytest` + `pytest-asyncio` with hand-rolled
fakes (`FakeHealth`, `FakeRedis`) — no Postgres or Redis needed for any test
in this plan.

## Global Constraints

- Design spec: `docs/superpowers/specs/2026-08-08-llm-resilient-fallback-design.md`
  (committed `3ac001e`) — every task below implements one section of it.
- Cooldown backoff formula: `min(base_seconds * 2 ** (consecutive_failures - 1),
  llm_cooldown_max_seconds)`, where `base_seconds` is the existing
  `llm_cooldown_429_seconds` (60) or `llm_cooldown_error_seconds` (30)
  depending on failure kind. `llm_cooldown_max_seconds` defaults to `900`
  (15 minutes). A provider's explicit `Retry-After` header (429 only) is
  used as-is, never multiplied.
- Current Gemini model ids to use: primary `gemini/gemini-3.6-flash`,
  fallback `gemini/gemini-3.5-flash-lite` (Gemini 2.5/2.0 are both blocked
  for new API keys ahead of Google's Oct 16, 2026 shutdown — confirmed via
  production logs and web search on 2026-08-08).
- Paid last-resort model: `openrouter/deepseek/deepseek-chat`, configured via
  new setting `llm_paid_fallback_model: str | None = None` (`None` by
  default — only set explicitly in `.env.production`, never assumed).
- Ranking sort key for the free fallback pool: ascending
  `(consecutive_failures, avg_latency_ms if known else -1)` — a model with no
  history yet sorts as best-case. Ties preserve the original
  `llm_fallback_chain` list order (stable sort).
- The paid last-resort model is **never** part of the ranked pool — it's
  always appended as the final chain entry, regardless of its own health
  data.
- Ruff: line-length 100, double quotes (`ruff check life_graph/`,
  `ruff format life_graph/`) — run before each commit.
- Test command: run from the repo root using the project's venv Python
  explicitly (this dev environment has multiple Python installs on PATH) —
  `/c/Python314/python.exe -m pytest tests/unit/test_resilient_llm.py -v`
  (swap the file per task). All tests in this plan are unit tests — no
  Postgres or Redis needs to be running; `LLMHealth`'s tests use a hand-rolled
  `FakeRedis`, and `ResilientLLM`'s tests use a hand-rolled `FakeHealth`
  (both already exist in the repo — see each task).
- Every existing test in a modified file must still pass after each task —
  each task's steps include a full-file regression run before commit.

---

### Task 1: Fix the streaming bypass bug (critical — root cause of today's incident)

**Files:**
- Modify: `life_graph/services/resilient_llm.py:1-16` (imports), `:89-94` (`_attempt`)
- Test: `tests/unit/test_resilient_llm.py`

**Interfaces:**
- Consumes: nothing new — uses the existing `ResilientLLM(health: LLMHealth | None)`
  constructor and `ResilientLLM.acompletion(*, messages, model=None, tier="cheap", **kwargs)`
  signature, unchanged.
- Produces: `_attempt()`'s behavior for `kwargs.get("stream")` truthy now
  validates the call (pulls the first chunk) before returning, inside its
  caller's existing try/except — later tasks build on this same method
  without needing to know its internals, only that streaming failures now
  correctly reach `acompletion()`'s except block like non-streaming ones
  always have.

The current `_attempt()` (`resilient_llm.py:89-94`):

```python
    async def _attempt(self, model: str, messages: list[dict], kwargs: dict) -> Any:
        """Make one live call to `model`, recording success health on return."""
        t0 = time.monotonic()
        resp = await litellm.acompletion(model=model, messages=messages, **kwargs)
        await self._health.record_success(model, (time.monotonic() - t0) * 1000)
        return resp
```

The bug: with `stream=True`, `litellm.acompletion()` returns a lazy stream
wrapper almost instantly — no real HTTP request has been made yet. This
method calls `record_success` and returns that unvalidated wrapper as if the
call succeeded. The real request only fires later, when the caller
(`AgentOrchestrator.run()`) does `async for chunk in response:` — completely
outside this method's (and its caller `acompletion()`'s) try/except, so a
connect-time failure never fails over to the next model in the chain.

- [ ] **Step 1: Write the failing regression test**

Add this near the top of `tests/unit/test_resilient_llm.py`, right after the
existing `_resp()` helper function:

```python
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
```

Then add these three tests at the end of the file:

```python
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
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_resilient_llm.py -v -k streaming`
Expected: all 3 FAIL — `test_streaming_first_chunk_failure_falls_over` and
`test_streaming_empty_stream_treated_as_failure` fail because `_attempt()`
returns the broken/empty stream as a "success" instead of failing over (the
`async for chunk in resp` in the test will itself raise, since nothing
catches it); `test_streaming_success_rechains_first_chunk` currently passes
by coincidence (no bug on the happy path) — that's fine, it becomes a
guard against a regression in Step 3's fix.

- [ ] **Step 3: Implement the fix**

In `life_graph/services/resilient_llm.py`, change the imports block (top of
file) from:

```python
from __future__ import annotations

import logging
import os
import time
from typing import Any

import litellm
```

to:

```python
from __future__ import annotations

import logging
import os
import time
from collections.abc import AsyncGenerator
from typing import Any

import litellm
```

Then replace `_attempt()` (`resilient_llm.py:89-94`):

```python
    async def _attempt(self, model: str, messages: list[dict], kwargs: dict) -> Any:
        """Make one live call to `model`, recording success health on return."""
        t0 = time.monotonic()
        resp = await litellm.acompletion(model=model, messages=messages, **kwargs)
        await self._health.record_success(model, (time.monotonic() - t0) * 1000)
        return resp
```

with:

```python
    async def _attempt(self, model: str, messages: list[dict], kwargs: dict) -> Any:
        """Make one live call to `model`, recording success health on return.

        For streaming calls, `litellm.acompletion` returns a lazy stream
        wrapper that makes no real network call until first iterated — so the
        first chunk is pulled here, inside this method (and thus inside the
        caller's try/except in `acompletion()`), to catch connect/first-byte
        failures (bad model id, auth, deprecated model, etc.) as an ordinary
        failure that fails over, instead of letting them surface later,
        unprotected, when the orchestrator iterates the stream itself.
        """
        t0 = time.monotonic()
        resp = await litellm.acompletion(model=model, messages=messages, **kwargs)
        if kwargs.get("stream"):
            first_chunk = await resp.__anext__()
            await self._health.record_success(model, (time.monotonic() - t0) * 1000)
            return _rechain(first_chunk, resp)
        await self._health.record_success(model, (time.monotonic() - t0) * 1000)
        return resp
```

Then add this module-level helper function right after the `ResilientLLM`
class (below its last method, before `_safe_cooldown`):

```python
async def _rechain(first_chunk: Any, rest: Any) -> AsyncGenerator[Any, None]:
    """Re-yield an already-fetched first chunk, then delegate to the rest of the stream."""
    yield first_chunk
    async for chunk in rest:
        yield chunk
```

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_resilient_llm.py -v -k streaming`
Expected: all 3 PASS.

- [ ] **Step 5: Run the full file to confirm no regressions**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_resilient_llm.py -v`
Expected: all tests PASS (the non-streaming tests never set `stream=True`,
so `kwargs.get("stream")` is falsy for them and they hit the unchanged
non-streaming branch).

- [ ] **Step 6: Commit**

```bash
git add life_graph/services/resilient_llm.py tests/unit/test_resilient_llm.py
git commit -m "fix: validate streaming LLM calls inside ResilientLLM's failover

Streaming completions returned a lazy, unvalidated stream wrapper as an
immediate 'success' — the real HTTP request only fired when the caller
iterated it, bypassing failover entirely. Root cause of the 2026-08-08
production incident (a 404 for a deprecated Gemini model reached the
orchestrator's weak same-model retry instead of failing over)."
```

---

### Task 2: Fix dead Gemini model defaults

**Files:**
- Modify: `life_graph/config.py:164`, `:167`
- Modify: `life_graph/agents/orchestrator.py:39`
- Test: `tests/unit/test_config_model_defaults.py` (new file)

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `Settings().agent_llm_model == "gemini/gemini-3.6-flash"`,
  `Settings().agent_fallback_model == "gemini/gemini-3.5-flash-lite"`,
  `AgentOrchestrator().FALLBACK_MODEL == "gemini/gemini-3.5-flash-lite"` —
  no other task depends on these exact values, but every task in this plan
  assumes the fallback chain models are otherwise reachable in production
  (this task is what makes that true).

Google is blocking `gemini-2.5-flash` and `gemini-2.0-flash` for new API
keys ahead of an October 2026 shutdown (confirmed via production logs and
web search on 2026-08-08 — see the design doc's Background section). The
production `.env.production` was already hand-patched to unblock the live
system before this plan existed; this task fixes the code defaults so a
fresh deploy or local dev setup doesn't regress to the dead models.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_config_model_defaults.py`:

```python
"""Regression test: agent LLM model defaults must not point at Gemini model
ids blocked for new API keys (gemini-2.5-flash and gemini-2.0-flash both
return 404 as of 2026-08-08, ahead of Google's Oct 16, 2026 shutdown)."""

from __future__ import annotations

from life_graph.agents.orchestrator import AgentOrchestrator
from life_graph.config import Settings


def test_agent_llm_model_default_is_current():
    assert Settings().agent_llm_model == "gemini/gemini-3.6-flash"


def test_agent_fallback_model_default_is_current():
    assert Settings().agent_fallback_model == "gemini/gemini-3.5-flash-lite"


def test_orchestrator_fallback_model_class_default_is_current():
    orch = AgentOrchestrator()
    assert orch.FALLBACK_MODEL == "gemini/gemini-3.5-flash-lite"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_config_model_defaults.py -v`
Expected: all 3 FAIL (current values are `gemini-2.5-flash` / `gemini-2.0-flash`).

- [ ] **Step 3: Implement the fix**

In `life_graph/config.py`, change line 164 from:

```python
    agent_llm_model: str = "gemini/gemini-2.5-flash"
```

to:

```python
    agent_llm_model: str = "gemini/gemini-3.6-flash"
```

And line 167 from:

```python
    agent_fallback_model: str = "gemini/gemini-2.0-flash"
```

to:

```python
    agent_fallback_model: str = "gemini/gemini-3.5-flash-lite"
```

In `life_graph/agents/orchestrator.py`, change line 39 from:

```python
    FALLBACK_MODEL: str = "gemini/gemini-2.0-flash"  # overridden in __init__ from config
```

to:

```python
    FALLBACK_MODEL: str = "gemini/gemini-3.5-flash-lite"  # overridden in __init__ from config
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_config_model_defaults.py -v`
Expected: all 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add life_graph/config.py life_graph/agents/orchestrator.py tests/unit/test_config_model_defaults.py
git commit -m "fix: update dead Gemini model defaults (2.5/2.0-flash are blocked for new keys)"
```

---

### Task 3: LLMHealth interface additions

**Files:**
- Modify: `life_graph/services/llm_health.py:70-76` (`record_failure`)
- Modify: `life_graph/services/llm_health.py` (new `get()` method, add after `cooldown_until`, before `snapshot`)
- Test: `tests/unit/test_llm_health.py`

**Interfaces:**
- Consumes: nothing from Tasks 1-2.
- Produces: `LLMHealth.record_failure(model: str, kind: str) -> int` (was
  `-> None`) — returns the model's updated consecutive-failure count.
  `LLMHealth.get(model: str) -> dict[str, str]` — returns the model's raw
  health record (empty dict if unknown or Redis is down). Task 4 consumes
  the `record_failure` return value; Task 5 consumes `get()`.

- [ ] **Step 1: Write the failing tests**

Add these to `tests/unit/test_llm_health.py`, after the existing
`test_record_success_sets_last_success_and_latency` test:

```python
@pytest.mark.asyncio
async def test_record_failure_returns_incrementing_count(health):
    h, _ = health
    assert await h.record_failure("m1", "error") == 1
    assert await h.record_failure("m1", "error") == 2
    assert await h.record_failure("m1", "error") == 3


@pytest.mark.asyncio
async def test_record_failure_count_resets_after_success(health):
    h, _ = health
    await h.record_failure("m1", "error")
    await h.record_failure("m1", "error")
    await h.record_success("m1", 50)
    assert await h.record_failure("m1", "error") == 1


@pytest.mark.asyncio
async def test_record_failure_returns_one_when_redis_unavailable(monkeypatch):
    monkeypatch.setattr("life_graph.services.llm_health.get_redis", lambda: None)
    h = LLMHealth()
    assert await h.record_failure("m", "error") == 1


@pytest.mark.asyncio
async def test_get_returns_raw_record(health):
    h, _ = health
    await h.record_success("m1", 120)
    rec = await h.get("m1")
    assert float(rec["avg_latency_ms"]) == pytest.approx(120, abs=1)


@pytest.mark.asyncio
async def test_get_returns_empty_dict_for_unknown_model(health):
    h, _ = health
    assert await h.get("never-seen") == {}


@pytest.mark.asyncio
async def test_get_returns_empty_dict_when_redis_unavailable(monkeypatch):
    monkeypatch.setattr("life_graph.services.llm_health.get_redis", lambda: None)
    h = LLMHealth()
    assert await h.get("m") == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_llm_health.py -v`
Expected: the new `record_failure`-return-value tests FAIL (`None != 1`
etc.); the new `get()` tests FAIL with `AttributeError: 'LLMHealth' object
has no attribute 'get'`.

- [ ] **Step 3: Implement the fix**

In `life_graph/services/llm_health.py`, change `record_failure`
(`llm_health.py:70-76`) from:

```python
    async def record_failure(self, model: str, kind: str) -> None:
        prev = await self._read(model)
        fails = int(prev.get("consecutive_failures", 0) or 0) + 1
        await self._write(
            model,
            {"last_failure_at": self._clock(), "last_error": kind, "consecutive_failures": fails},
        )
```

to:

```python
    async def record_failure(self, model: str, kind: str) -> int:
        """Record a failure and return the model's updated consecutive-failure count."""
        prev = await self._read(model)
        fails = int(prev.get("consecutive_failures", 0) or 0) + 1
        await self._write(
            model,
            {"last_failure_at": self._clock(), "last_error": kind, "consecutive_failures": fails},
        )
        return fails
```

Then add a new `get()` method right after `cooldown_until` and before
`snapshot`:

```python
    async def get(self, model: str) -> dict[str, str]:
        """Return a model's raw health record (empty dict if unknown or Redis is down)."""
        return await self._read(model)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_llm_health.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add life_graph/services/llm_health.py tests/unit/test_llm_health.py
git commit -m "feat: LLMHealth.record_failure returns count, add get() accessor

Both are prerequisites for ResilientLLM's upcoming exponential backoff
and health-ranked fallback ordering — no behavior change to LLMHealth
itself."
```

---

### Task 4: Exponential backoff for chronically failing models

**Files:**
- Modify: `life_graph/config.py` (new setting, add to the "Resilient LLM
  failover" section right after `llm_health_ttl_seconds` at line 128)
- Modify: `life_graph/services/resilient_llm.py:112-121` (the failure branch inside `acompletion`)
- Test: `tests/unit/test_resilient_llm.py`

**Interfaces:**
- Consumes: `LLMHealth.record_failure(model, kind) -> int` from Task 3.
- Produces: cooldown durations that escalate `base_seconds * 2 **
  (consecutive_failures - 1)`, capped at `settings.llm_cooldown_max_seconds`
  (new setting, default `900`), and reset to `base_seconds` the moment a
  model succeeds again (via `record_failure`'s count resetting on
  `record_success` — already true, from Task 3). No other task depends on
  this task's internals.

- [ ] **Step 1: Write the failing tests**

First, update `FakeHealth` in `tests/unit/test_resilient_llm.py` — its
`record_failure` currently returns `None`, but the real `LLMHealth` (Task 3)
now returns an `int`, and the production code this task adds will use that
return value. Replace the existing `FakeHealth` class with:

```python
class FakeHealth:
    def __init__(self, cooling=None):
        self.cooling = set(cooling or [])
        self.success = []
        self.failure = []
        self.cooldowns = {}
        self._consecutive = {}
        self._latency = {}

    async def in_cooldown(self, m):
        return m in self.cooling

    async def cooldown_until(self, m):
        return self.cooldowns.get(m, 0)

    async def record_success(self, m, latency_ms):
        self.success.append(m)
        self._consecutive[m] = 0
        self._latency[m] = latency_ms

    async def record_failure(self, m, kind):
        self.failure.append((m, kind))
        self._consecutive[m] = self._consecutive.get(m, 0) + 1
        return self._consecutive[m]

    async def set_cooldown(self, m, seconds):
        self.cooldowns[m] = seconds
        self.cooling.add(m)

    async def get(self, m):
        return {
            "consecutive_failures": self._consecutive.get(m, 0),
            "avg_latency_ms": self._latency.get(m),
        }
```

(This adds `_consecutive`/`_latency` tracking and the `get()` method that
Task 5 will also need — `FakeHealth` is a hand-rolled double for the whole
`LLMHealth` interface, so it must track everything `ResilientLLM` reads,
not just what the current task's tests happen to check.)

Then add these tests at the end of the file:

```python
@pytest.mark.asyncio
async def test_error_cooldown_escalates_with_consecutive_failures(monkeypatch):
    fail_a = rl.litellm.APIError(500, "boom", "prov", "A")
    call = AsyncMock(side_effect=[fail_a, _resp("hi"), fail_a, _resp("hi"), fail_a, _resp("hi")])
    monkeypatch.setattr(rl.litellm, "acompletion", call)
    h = FakeHealth()
    llm = ResilientLLM(health=h)

    await llm.chat([{"role": "user", "content": "q"}])
    assert h.cooldowns["A"] == 30  # 1st failure: base error cooldown

    h.cooling.discard("A")  # simulate the cooldown period elapsing
    await llm.chat([{"role": "user", "content": "q"}])
    assert h.cooldowns["A"] == 60  # 2nd consecutive failure: doubled

    h.cooling.discard("A")
    await llm.chat([{"role": "user", "content": "q"}])
    assert h.cooldowns["A"] == 120  # 3rd consecutive failure: doubled again


@pytest.mark.asyncio
async def test_error_cooldown_caps_at_max(monkeypatch):
    monkeypatch.setattr(rl.settings, "llm_cooldown_max_seconds", 100, raising=False)
    fail_a = rl.litellm.APIError(500, "boom", "prov", "A")
    call = AsyncMock(side_effect=[fail_a, _resp("hi")])
    monkeypatch.setattr(rl.litellm, "acompletion", call)
    h = FakeHealth()
    h._consecutive["A"] = 9  # A has already failed 9 times in a row (uncapped: 30*2**9=15360s)
    llm = ResilientLLM(health=h)

    await llm.chat([{"role": "user", "content": "q"}])
    assert h.cooldowns["A"] == 100  # capped, not 30 * 2**9


@pytest.mark.asyncio
async def test_error_cooldown_resets_to_base_after_success(monkeypatch):
    fail_a = rl.litellm.APIError(500, "boom", "prov", "A")
    call = AsyncMock(side_effect=[fail_a, _resp("hi"), _resp("hi"), fail_a, _resp("hi")])
    monkeypatch.setattr(rl.litellm, "acompletion", call)
    h = FakeHealth()
    llm = ResilientLLM(health=h)

    await llm.chat([{"role": "user", "content": "q"}])  # A fails (1st), B succeeds
    assert h.cooldowns["A"] == 30
    h.cooling.discard("A")

    await llm.chat([{"role": "user", "content": "q"}])  # A succeeds this round
    assert h.success == ["B", "A"]

    await llm.chat([{"role": "user", "content": "q"}])  # A fails again -> count reset to 1
    assert h.cooldowns["A"] == 30  # back to base, not 60


@pytest.mark.asyncio
async def test_429_retry_after_header_used_as_is_not_multiplied(monkeypatch):
    err = rl.litellm.RateLimitError("rate", "prov", "A")
    err.response = SimpleNamespace(headers={"retry-after": "45"})
    call = AsyncMock(side_effect=[err, _resp("hi")])
    monkeypatch.setattr(rl.litellm, "acompletion", call)
    h = FakeHealth()
    h._consecutive["A"] = 4  # even with prior failures, an explicit Retry-After wins as-is

    await ResilientLLM(health=h).chat([{"role": "user", "content": "q"}])
    assert h.cooldowns["A"] == 45
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_resilient_llm.py -v -k "cooldown or retry_after"`
Expected: all 4 new tests FAIL (`AttributeError: 'Settings' object has no
attribute 'llm_cooldown_max_seconds'`, since it doesn't exist until Step 3).

- [ ] **Step 3: Implement the fix**

In `life_graph/config.py`, in the "Resilient LLM failover" section, change:

```python
    # ── Resilient LLM failover ────────────────────
    llm_fallback_chain: str = "openrouter/deepseek/deepseek-chat,gemini/gemini-2.0-flash"
    llm_cooldown_429_seconds: int = 60
    llm_cooldown_error_seconds: int = 30
    llm_health_ttl_seconds: int = 3600
```

to:

```python
    # ── Resilient LLM failover ────────────────────
    llm_fallback_chain: str = "openrouter/deepseek/deepseek-chat,gemini/gemini-2.0-flash"
    llm_cooldown_429_seconds: int = 60
    llm_cooldown_error_seconds: int = 30
    llm_cooldown_max_seconds: int = 900
    llm_health_ttl_seconds: int = 3600
```

In `life_graph/services/resilient_llm.py`, change the failure branch inside
`acompletion()` (`resilient_llm.py:112-121`) from:

```python
            try:
                return await self._attempt(m, messages, kwargs)
            except Exception as exc:  # noqa: BLE001 - classify + fail over
                kind = _classify(exc)
                await self._health.record_failure(m, kind)
                cd = (
                    _retry_after(exc) or settings.llm_cooldown_429_seconds
                    if kind == "429"
                    else settings.llm_cooldown_error_seconds
                )
                await self._health.set_cooldown(m, cd)
                logger.warning("Model %s failed (%s); benched %ss", m, kind, cd)
```

to:

```python
            try:
                return await self._attempt(m, messages, kwargs)
            except Exception as exc:  # noqa: BLE001 - classify + fail over
                kind = _classify(exc)
                fails = await self._health.record_failure(m, kind)
                retry_after = _retry_after(exc) if kind == "429" else None
                if retry_after is not None:
                    cd = retry_after
                else:
                    base = (
                        settings.llm_cooldown_429_seconds
                        if kind == "429"
                        else settings.llm_cooldown_error_seconds
                    )
                    cd = min(base * 2 ** (fails - 1), settings.llm_cooldown_max_seconds)
                await self._health.set_cooldown(m, cd)
                logger.warning(
                    "Model %s failed (%s); benched %ss (failure #%d)", m, kind, cd, fails
                )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_resilient_llm.py -v -k "cooldown or retry_after"`
Expected: all 4 PASS.

- [ ] **Step 5: Run the full file to confirm no regressions**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_resilient_llm.py -v`
Expected: all tests PASS, including `test_429_benches_and_falls_over` (a
single first-time failure still benches for exactly the base 60s/30s, since
`2 ** (1 - 1) == 1`).

- [ ] **Step 6: Commit**

```bash
git add life_graph/config.py life_graph/services/resilient_llm.py tests/unit/test_resilient_llm.py
git commit -m "feat: exponential backoff for chronically failing LLM models

A model stuck broken (like the dead Gemini key on 2026-08-08) previously
got retried at a flat 30s/60s cooldown forever. Cooldown now escalates
30s -> 60s -> 120s -> ... capped at 15 minutes, resetting to base the
next time the model succeeds. An explicit Retry-After header is still
respected as-is, never multiplied."
```

---

### Task 5: Health-ranked fallback pool

**Files:**
- Modify: `life_graph/services/resilient_llm.py:80-87` (replace `_chain`), `:104` (its call site in `acompletion`)
- Test: `tests/unit/test_resilient_llm.py`

**Interfaces:**
- Consumes: `LLMHealth.get(model) -> dict[str, str]` from Task 3.
- Produces: `ResilientLLM._primary(model, tier) -> str` (replaces the
  primary-resolution half of the old `_chain`) and `async
  ResilientLLM._rank_fallbacks(primary: str) -> list[str]` (de-duped,
  health-sorted fallback pool, excluding `primary`). Task 6 consumes both to
  build the final chain with the paid model appended.

- [ ] **Step 1: Write the failing tests**

Add these to `tests/unit/test_resilient_llm.py`, at the end of the file:

```python
@pytest.mark.asyncio
async def test_fallback_pool_ranked_by_fewest_failures_then_latency(monkeypatch):
    call = AsyncMock(
        side_effect=[rl.litellm.APIError(500, "boom", "prov", "A"), _resp("hi")]
    )
    monkeypatch.setattr(rl.litellm, "acompletion", call)
    h = FakeHealth()
    # B has 2 consecutive failures recorded (not currently cooling); C is clean.
    # B would be faster if it weren't unreliable -- failure count wins first.
    h._consecutive["B"] = 2
    h._latency["B"] = 10.0
    h._latency["C"] = 50.0

    out = await ResilientLLM(health=h).chat([{"role": "user", "content": "q"}])
    assert out == "hi"
    assert h.success == ["C"]  # C tried before B: fewer consecutive failures wins


@pytest.mark.asyncio
async def test_fallback_pool_unknown_model_gets_fair_first_try(monkeypatch):
    call = AsyncMock(
        side_effect=[rl.litellm.APIError(500, "boom", "prov", "A"), _resp("hi")]
    )
    monkeypatch.setattr(rl.litellm, "acompletion", call)
    h = FakeHealth()
    h._latency["B"] = 200.0  # B has a proven (nonzero-latency) track record; C has none

    out = await ResilientLLM(health=h).chat([{"role": "user", "content": "q"}])
    assert out == "hi"
    assert h.success == ["C"]  # unseen C sorts ahead of B's recorded latency


@pytest.mark.asyncio
async def test_fallback_pool_ties_preserve_env_order(monkeypatch):
    call = AsyncMock(
        side_effect=[rl.litellm.APIError(500, "boom", "prov", "A"), _resp("hi")]
    )
    monkeypatch.setattr(rl.litellm, "acompletion", call)
    h = FakeHealth()  # no health data for B or C at all -> tie -> original "B,C" order wins

    out = await ResilientLLM(health=h).chat([{"role": "user", "content": "q"}])
    assert out == "hi"
    assert h.success == ["B"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_resilient_llm.py -v -k fallback_pool`
Expected: `test_fallback_pool_ranked_by_fewest_failures_then_latency` and
`test_fallback_pool_unknown_model_gets_fair_first_try` FAIL (`h.success ==
["B"]`, since ranking doesn't exist yet and the `.env`-order fallback `B` is
tried before `C`); `test_fallback_pool_ties_preserve_env_order` currently
PASSes by coincidence (it becomes a guard against a regression in Step 3).

- [ ] **Step 3: Implement the fix**

In `life_graph/services/resilient_llm.py`, replace `_chain`
(`resilient_llm.py:80-87`):

```python
    def _chain(self, model: str | None, tier: str) -> list[str]:
        """Build the de-duped attempt order: caller's model/tier default, then fallbacks."""
        primary = model or (
            settings.llm_model_expensive if tier == "expensive" else settings.llm_model_cheap
        )
        chain = [primary, *settings.llm_fallback_chain_list]
        seen: set[str] = set()
        return [m for m in chain if m and not (m in seen or seen.add(m))]
```

with:

```python
    def _primary(self, model: str | None, tier: str) -> str:
        """Resolve the caller's model/tier choice into the primary model id."""
        return model or (
            settings.llm_model_expensive if tier == "expensive" else settings.llm_model_cheap
        )

    async def _rank_fallbacks(self, primary: str) -> list[str]:
        """De-dupe the configured fallback pool against `primary`, then sort it by
        health: fewest consecutive failures first, then lowest average latency.
        A model with no recorded history yet sorts as best-case (fair first
        try) rather than being buried behind models with a real track record.
        Ties preserve the pool's original `.env` list order (stable sort).
        """
        seen: set[str] = {primary}
        pool = [
            m for m in settings.llm_fallback_chain_list if m and not (m in seen or seen.add(m))
        ]

        async def _rank_key(m: str) -> tuple[int, float]:
            rec = await self._health.get(m)
            fails = int(rec.get("consecutive_failures", 0) or 0)
            latency = rec.get("avg_latency_ms")
            return (fails, float(latency) if latency else -1.0)

        keyed = [(await _rank_key(m), m) for m in pool]
        keyed.sort(key=lambda pair: pair[0])
        return [m for _, m in keyed]
```

Then change its call site in `acompletion()` (`resilient_llm.py:104`) from:

```python
        chain = self._chain(model, tier)
```

to:

```python
        primary = self._primary(model, tier)
        chain = [primary, *await self._rank_fallbacks(primary)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_resilient_llm.py -v -k fallback_pool`
Expected: all 3 PASS.

- [ ] **Step 5: Run the full file to confirm no regressions**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_resilient_llm.py -v`
Expected: all tests PASS — every prior test uses a `FakeHealth` with no
health data set for the models it cares about, so ranking ties out to the
original `.env` order and prior assertions on which model gets tried hold
unchanged.

- [ ] **Step 6: Commit**

```bash
git add life_graph/services/resilient_llm.py tests/unit/test_resilient_llm.py
git commit -m "feat: rank the free fallback pool by recorded health

Fallback order was a fixed .env list with no signal about which models
are actually working right now. Sorted by (consecutive_failures,
avg_latency_ms) using LLMHealth data already being recorded; unseen
models get a fair first try, ties keep the original .env order."
```

---

### Task 6: Guaranteed paid last-resort model

**Files:**
- Modify: `life_graph/config.py` (new setting, add to the "Resilient LLM
  failover" section right after `llm_cooldown_max_seconds` from Task 4)
- Modify: `life_graph/services/resilient_llm.py:104-111` (chain construction and skip loop in `acompletion`)
- Test: `tests/unit/test_resilient_llm.py`

**Interfaces:**
- Consumes: `ResilientLLM._primary()` and `ResilientLLM._rank_fallbacks()` from Task 5.
- Produces: the final `chain` list `acompletion()` iterates now always ends
  with `settings.llm_paid_fallback_model` when configured (`None` by
  default). No other task depends on this.

- [ ] **Step 1: Write the failing tests**

Add these to `tests/unit/test_resilient_llm.py`, at the end of the file:

```python
@pytest.mark.asyncio
async def test_paid_fallback_tried_last_after_all_free_models_fail(monkeypatch):
    monkeypatch.setattr(rl.settings, "llm_paid_fallback_model", "PAID", raising=False)
    call = AsyncMock(
        side_effect=[
            rl.litellm.APIError(500, "boom", "prov", "A"),
            rl.litellm.APIError(500, "boom", "prov", "B"),
            rl.litellm.APIError(500, "boom", "prov", "C"),
            _resp("hi"),
        ]
    )
    monkeypatch.setattr(rl.litellm, "acompletion", call)
    h = FakeHealth()

    out = await ResilientLLM(health=h).chat([{"role": "user", "content": "q"}])
    assert out == "hi"
    assert call.call_args.kwargs["model"] == "PAID"
    assert h.success == ["PAID"]


@pytest.mark.asyncio
async def test_paid_fallback_never_reordered_ahead_of_primary(monkeypatch):
    monkeypatch.setattr(rl.settings, "llm_paid_fallback_model", "PAID", raising=False)
    call = AsyncMock(return_value=_resp("hi"))
    monkeypatch.setattr(rl.litellm, "acompletion", call)
    h = FakeHealth()
    # PAID would rank ahead of everything on health data alone (fast, zero
    # failures) if it were part of the ranked pool -- it must not be, since
    # it's cost, not health, that decides when it's used.
    h._latency["PAID"] = 1.0

    out = await ResilientLLM(health=h).chat([{"role": "user", "content": "q"}])
    assert out == "hi"
    assert call.call_args.kwargs["model"] == "A"  # primary still tried first


@pytest.mark.asyncio
async def test_no_paid_fallback_configured_exhausts_as_before(monkeypatch):
    monkeypatch.setattr(rl.settings, "llm_paid_fallback_model", None, raising=False)
    call = AsyncMock(side_effect=rl.litellm.APIError(500, "boom", "prov", "m"))
    monkeypatch.setattr(rl.litellm, "acompletion", call)
    h = FakeHealth()

    with pytest.raises(ResilientLLMExhausted):
        await ResilientLLM(health=h).chat([{"role": "user", "content": "q"}])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_resilient_llm.py -v -k paid_fallback`
Expected: `test_paid_fallback_tried_last_after_all_free_models_fail` FAILS
(raises `ResilientLLMExhausted` instead of returning "hi", since "PAID"
isn't added to the chain yet). The other two currently PASS by coincidence
(no paid-model logic exists yet to break them) — they become regression
guards after Step 3.

- [ ] **Step 3: Implement the fix**

In `life_graph/config.py`, in the "Resilient LLM failover" section, change:

```python
    llm_cooldown_max_seconds: int = 900
    llm_health_ttl_seconds: int = 3600
```

to:

```python
    llm_cooldown_max_seconds: int = 900
    llm_health_ttl_seconds: int = 3600
    llm_paid_fallback_model: str | None = None
```

In `life_graph/services/resilient_llm.py`, change the start of
`acompletion()` (`resilient_llm.py:104-111`) from:

```python
        primary = self._primary(model, tier)
        chain = [primary, *await self._rank_fallbacks(primary)]
        skipped: list[str] = []
        for m in chain:
            if await self._health.in_cooldown(m):
                skipped.append(m)
                continue
            try:
                return await self._attempt(m, messages, kwargs)
```

to:

```python
        primary = self._primary(model, tier)
        chain = [primary, *await self._rank_fallbacks(primary)]
        if settings.llm_paid_fallback_model and settings.llm_paid_fallback_model not in chain:
            chain.append(settings.llm_paid_fallback_model)
        skipped: list[str] = []
        for m in chain:
            if await self._health.in_cooldown(m):
                skipped.append(m)
                continue
            if m == settings.llm_paid_fallback_model:
                logger.warning("Falling back to paid model %s", m)
            try:
                return await self._attempt(m, messages, kwargs)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_resilient_llm.py -v -k paid_fallback`
Expected: all 3 PASS.

- [ ] **Step 5: Run the full file to confirm no regressions**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_resilient_llm.py -v`
Expected: all tests PASS — every prior test relies on `rl.settings`'s real
`llm_paid_fallback_model` default of `None` (set in Step 3), so the paid
branch never activates for them.

- [ ] **Step 6: Run the complete unit suite**

Run: `/c/Python314/python.exe -m pytest tests/unit/ -v`
Expected: all tests PASS — final check across every file touched by this
plan (`test_resilient_llm.py`, `test_llm_health.py`,
`test_config_model_defaults.py`) plus everything else in `tests/unit/`.

- [ ] **Step 7: Commit**

```bash
git add life_graph/config.py life_graph/services/resilient_llm.py tests/unit/test_resilient_llm.py
git commit -m "feat: guaranteed paid last-resort model in the fallback chain

Appends settings.llm_paid_fallback_model (opt-in, None by default) as the
final chain entry, never reordered into the ranked free pool -- only
reached once every free candidate has failed or is cooling. Fixes the
class of incident where the entire free tier is congested at once
(observed on 2026-08-08: two free OpenRouter fallbacks 429'd
simultaneously)."
```

---

## Deployment note (not a plan task — handled after merge, same as prior features)

Once this branch is merged, production deployment follows the established
pattern from this session's push-to-talk feature: SSH to the VM, `git pull`,
rebuild the `app`/`worker` images, recreate the containers. The one new
production-only step this plan requires: add
`LIFE_GRAPH_LLM_PAID_FALLBACK_MODEL=openrouter/deepseek/deepseek-chat` to
`.env.production` before recreating containers (local dev and any other
non-production environment should leave this unset, per the Global
Constraints). Verify afterward via `docker logs life_graph_app` (look for
`"Model %s failed"` entries showing escalating cooldowns, and no more
"Unrecoverable agent error" for connect-time failures) and a real chat
message in the browser.
