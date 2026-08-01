# Free-Model Resilience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route every LLM completion through one resilient wrapper that tries the caller's model first, then an ordered chain of free alternates (benching any backend that 429s/errors for a cooldown), recording outcomes to a shared Redis health record surfaced on a mobile "Model health" card — so features never hard-fail while a free backend is rate-limited.

**Architecture:** A `ResilientLLM` service exposes `acompletion()` (a drop-in for `litellm.acompletion` returning the raw response) and a `chat()` text convenience. It consults an `LLMHealth` Redis record for cooldowns and records every outcome. `LMStudioClient`'s cloud path delegates to it (covering all `.chat` callers); the six direct `litellm.acompletion` sites swap to `resilient.acompletion`. A new `GET /api/v1/health/models` endpoint + a mobile settings card show live health.

**Tech Stack:** Python 3.11+, LiteLLM (already a dep), Redis (`redis.asyncio` via `storage/redis.py`), FastAPI, pytest (`httpx.AsyncClient` + `ASGITransport`, `conftest.py` mocks pgvector), Next.js 16 / React 19 dashboard, `@tanstack/react-query` v5.

## Global Constraints

- **Branch:** `feat/llm-resilience`, already checked out (worktree `scratchpad/hotfix-wt`), off `origin/master` (`d829b61`). Commit after each task with trailer exactly: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **Reactive only — no probing.** Health is recorded from real call outcomes; never issue a request solely to check health.
- **Behavior-preserving migrations.** A migrated call site keeps its own model choice as the primary (passed as `model=`), its downstream response handling, and its existing degradation. The wrapper only adds failover + recording.
- **Fail-open on Redis.** Every `LLMHealth` method is best-effort: if `get_redis()` is `None` or a Redis op raises, treat as "not cooling"/no-op and never raise into the LLM path.
- **Model health is global**, not tenant-scoped (infrastructure state). No DB migration (Redis only).
- **Never hard-fail the user.** When every model is exhausted, `acompletion`/`chat` raise `ResilientLLMExhausted`; callers catch it and run their existing fallback (extraction → rules/nlp; synthesis → rule-based answer). No new user-facing 500s.
- **Ruff:** line-length 100, double quotes; type hints + docstrings on public APIs. Run `ruff check life_graph/ tests/ && ruff format life_graph/ tests/` before backend commits; **commit only the files the task changed** — do not commit repo-wide format drift on pre-existing files.
- **Backend test gate:** `pytest tests/unit/ -v` (no DB — pgvector mocked) for unit tasks; `pytest tests/integration/ -v` for the endpoint. Tests never accept 422 for valid input.
- **Frontend:** no JS test runner. Gate = `npm run build` clean + `npm run lint` zero NEW problems, from `dashboard/`. No new npm dependency. No `@typescript-eslint/no-explicit-any` (repo treats as ERROR). Design tokens only.
- **No new secrets.** Free-tier keys already live in the VM `.env.production`.

## File Structure

**Task 1 — LLMHealth (Redis record)**: Create `life_graph/services/llm_health.py`, `tests/unit/test_llm_health.py`.
**Task 2 — ResilientLLM core + config + DI**: Create `life_graph/services/resilient_llm.py`, `tests/unit/test_resilient_llm.py`; modify `life_graph/config.py`, `life_graph/api/dependencies.py`.
**Task 3 — Choke point (LMStudioClient)**: Modify `life_graph/services/llm_client.py`; test `tests/unit/test_llm_client_resilient.py`.
**Task 4 — Migrate 5 direct acompletion sites**: Modify `extraction/llm.py`, `agents/orchestrator.py`, `jobs/consolidation.py`, `services/research_engine.py`, `watchers/dependency_watcher.py`; test `tests/unit/test_extraction_failover.py`.
**Task 5 — Advisor migration (delicate)**: Modify `life_graph/services/multi_model_advisor.py`; test `tests/unit/test_advisor_resilient.py`.
**Task 6 — Status endpoint**: Create `life_graph/api/model_health.py`; modify `life_graph/main.py` (register router); test `tests/integration/test_model_health_endpoint.py`.
**Task 7 — Mobile card**: Create `dashboard/app/(mobile)/m/settings/page.tsx`; modify `dashboard/lib/api.ts`, `dashboard/lib/mobile-api.ts`, `dashboard/components/mobile/mobile-shell.tsx` (gear link).

---

### Task 1: `LLMHealth` — Redis-backed health record

A best-effort, fail-open record of each model's recent outcomes + cooldown.

**Files:** Create `life_graph/services/llm_health.py`, `tests/unit/test_llm_health.py`.

**Interfaces:**
- Consumes: `life_graph.storage.redis.get_redis() -> aioredis.Redis | None`.
- Produces: `class LLMHealth` with `async record_success(model, latency_ms)`, `async record_failure(model, kind)`, `async set_cooldown(model, seconds)`, `async in_cooldown(model) -> bool`, `async snapshot() -> list[dict]`. Key format `llm:health:{model}`. `kind ∈ {"429","timeout","error"}`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_llm_health.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/unit/test_llm_health.py -v`
Expected: FAIL — `ModuleNotFoundError: life_graph.services.llm_health`.

- [ ] **Step 3: Implement**

Create `life_graph/services/llm_health.py`:

```python
"""LLMHealth — a best-effort, fail-open record of free-LLM backend health.

Written from real call outcomes (never a probe). Stored in Redis so the API and
worker processes share one view. Every method degrades to a no-op / "not cooling"
when Redis is unavailable, so the resilience path never breaks on a Redis fault.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from life_graph.config import settings
from life_graph.storage.redis import get_redis

logger = logging.getLogger(__name__)

_KEY = "llm:health:{model}"
_EMA_ALPHA = 0.3  # weight of the newest latency sample


class LLMHealth:
    """Per-model health hash in Redis; all ops best-effort."""

    def __init__(self, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.time

    def _key(self, model: str) -> str:
        return _KEY.format(model=model)

    async def _read(self, model: str) -> dict[str, str]:
        r = get_redis()
        if r is None:
            return {}
        try:
            return await r.hgetall(self._key(model))
        except Exception:  # pragma: no cover - fail-open
            logger.debug("LLMHealth read failed for %s", model, exc_info=True)
            return {}

    async def _write(self, model: str, mapping: dict[str, Any]) -> None:
        r = get_redis()
        if r is None:
            return
        try:
            await r.hset(self._key(model), mapping={k: str(v) for k, v in mapping.items()})
            await r.expire(self._key(model), settings.llm_health_ttl_seconds)
        except Exception:  # pragma: no cover - fail-open
            logger.debug("LLMHealth write failed for %s", model, exc_info=True)

    async def record_success(self, model: str, latency_ms: float) -> None:
        prev = await self._read(model)
        prev_lat = float(prev.get("avg_latency_ms", latency_ms) or latency_ms)
        ema = _EMA_ALPHA * latency_ms + (1 - _EMA_ALPHA) * prev_lat
        await self._write(
            model,
            {
                "last_success_at": self._clock(),
                "avg_latency_ms": round(ema, 1),
                "consecutive_failures": 0,
                "cooldown_until": 0,
            },
        )

    async def record_failure(self, model: str, kind: str) -> None:
        prev = await self._read(model)
        fails = int(prev.get("consecutive_failures", 0) or 0) + 1
        await self._write(
            model,
            {"last_failure_at": self._clock(), "last_error": kind, "consecutive_failures": fails},
        )

    async def set_cooldown(self, model: str, seconds: float) -> None:
        await self._write(model, {"cooldown_until": self._clock() + seconds})

    async def in_cooldown(self, model: str) -> bool:
        rec = await self._read(model)
        try:
            return float(rec.get("cooldown_until", 0) or 0) > self._clock()
        except (TypeError, ValueError):  # pragma: no cover
            return False

    async def cooldown_until(self, model: str) -> float:
        rec = await self._read(model)
        try:
            return float(rec.get("cooldown_until", 0) or 0)
        except (TypeError, ValueError):  # pragma: no cover
            return 0.0

    async def snapshot(self) -> list[dict]:
        r = get_redis()
        if r is None:
            return []
        try:
            keys = await r.keys("llm:health:*")
        except Exception:  # pragma: no cover - fail-open
            return []
        out: list[dict] = []
        now = self._clock()
        for key in keys:
            model = (key.decode() if isinstance(key, bytes) else key).removeprefix("llm:health:")
            rec = await self._read(model)
            if not rec:
                continue
            cooldown_until = float(rec.get("cooldown_until", 0) or 0)
            last_success = float(rec.get("last_success_at", 0) or 0)
            last_failure = float(rec.get("last_failure_at", 0) or 0)
            if cooldown_until > now:
                state = "cooling"
            elif last_success >= last_failure and last_success > 0:
                state = "up"
            elif last_failure > 0:
                state = "down"
            else:
                state = "unknown"
            out.append(
                {
                    "model": model,
                    "state": state,
                    "last_success_at": last_success or None,
                    "last_failure_at": last_failure or None,
                    "last_error": rec.get("last_error"),
                    "avg_latency_ms": float(rec.get("avg_latency_ms", 0) or 0) or None,
                    "cooldown_until": cooldown_until or None,
                }
            )
        return out
```

- [ ] **Step 4: Run to verify pass** — `pytest tests/unit/test_llm_health.py -v` → all pass.
- [ ] **Step 5: Lint + commit**

```bash
ruff check life_graph/services/llm_health.py tests/unit/test_llm_health.py && ruff format life_graph/services/llm_health.py tests/unit/test_llm_health.py
git add life_graph/services/llm_health.py tests/unit/test_llm_health.py
git commit -m "feat(resilience): LLMHealth — fail-open Redis backend-health record

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `ResilientLLM` core + config + DI

The ordered-failover wrapper: `acompletion()` (raw response) + `chat()` (text), cooldown skip, error classification, health recording.

**Files:** Create `life_graph/services/resilient_llm.py`, `tests/unit/test_resilient_llm.py`; modify `life_graph/config.py`, `life_graph/api/dependencies.py`.

**Interfaces:**
- Consumes: `litellm.acompletion`, `litellm` exception types, `LLMHealth` (Task 1), settings.
- Produces:
  - `class ResilientLLMExhausted(Exception)`
  - `class ResilientLLM(health: LLMHealth | None = None)` with
    `async acompletion(self, *, messages, model=None, tier="cheap", timeout=None, **kwargs) -> Any`
    (raw LiteLLM response) and
    `async chat(self, messages, *, model=None, tier="cheap", temperature=0.3, max_tokens=1024, response_format=None, **kwargs) -> str`.
  - `get_resilient_llm()` singleton in `api/dependencies.py`.
  - config: `settings.llm_fallback_chain`, `llm_fallback_chain_list`, `llm_cooldown_429_seconds`, `llm_cooldown_error_seconds`, `llm_health_ttl_seconds`.

- [ ] **Step 1: Add config**

In `life_graph/config.py`, near the LLM settings (~line 109, after `advisor_models`), add:

```python
    # ── Resilient LLM failover ────────────────────
    llm_fallback_chain: str = "gemini/gemini-2.0-flash,openrouter/deepseek/deepseek-chat"
    llm_cooldown_429_seconds: int = 60
    llm_cooldown_error_seconds: int = 30
    llm_health_ttl_seconds: int = 3600
```

And near the other `@property` list accessors (~line 223), add:

```python
    @property
    def llm_fallback_chain_list(self) -> list[str]:
        return [m.strip() for m in self.llm_fallback_chain.split(",") if m.strip()]
```

- [ ] **Step 2: Write the failing tests**

Create `tests/unit/test_resilient_llm.py`:

```python
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
    call = AsyncMock(side_effect=[rl.litellm.RateLimitError("rate", "A", "prov"), _resp("hi")])
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
    call = AsyncMock(side_effect=rl.litellm.APIError("boom", "m", "prov"))
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
```

Note: LiteLLM exception constructors vary by version. If `rl.litellm.RateLimitError(...)`/`APIError(...)` signatures differ, construct them however the installed litellm requires (import and check), or subclass minimal stand-ins in the test — the point is that `acompletion` raises the real `litellm.RateLimitError` / a generic error and the wrapper classifies them. Adjust the test constructors to the installed version; do not change the wrapper's classification logic to fit a wrong constructor.

- [ ] **Step 3: Run to verify failure** — `pytest tests/unit/test_resilient_llm.py -v` → FAIL (module missing).

- [ ] **Step 4: Implement**

Create `life_graph/services/resilient_llm.py`:

```python
"""ResilientLLM — ordered free-model failover with cooldowns + health recording.

Every completion tries the caller's model first, then the configured free
fallback chain, skipping any model currently in cooldown. A 429 benches a model
for `llm_cooldown_429_seconds` (or its Retry-After); other errors for
`llm_cooldown_error_seconds`. Health is recorded to LLMHealth from real outcomes
— never a probe. When every model is exhausted (or all cooling and the one forced
retry also fails) it raises ResilientLLMExhausted; callers run their own fallback.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import litellm

from life_graph.config import settings
from life_graph.services.llm_health import LLMHealth

logger = logging.getLogger(__name__)


class ResilientLLMExhausted(Exception):
    """Raised when every model in the chain failed or is unavailable."""


def _classify(exc: Exception) -> str:
    if isinstance(exc, litellm.RateLimitError):
        return "429"
    if isinstance(exc, (litellm.Timeout,)) or exc.__class__.__name__ in {"Timeout", "APITimeoutError"}:
        return "timeout"
    return "error"


def _retry_after(exc: Exception) -> float | None:
    headers = getattr(exc, "response", None)
    try:
        ra = getattr(headers, "headers", {}).get("retry-after") if headers else None
        return float(ra) if ra else None
    except (TypeError, ValueError):
        return None


class ResilientLLM:
    def __init__(self, health: LLMHealth | None = None) -> None:
        self._health = health or LLMHealth()

    def _chain(self, model: str | None, tier: str) -> list[str]:
        primary = model or (
            settings.llm_model_expensive if tier == "expensive" else settings.llm_model_cheap
        )
        chain = [primary, *settings.llm_fallback_chain_list]
        seen: set[str] = set()
        return [m for m in chain if m and not (m in seen or seen.add(m))]

    async def _attempt(self, model: str, messages: list[dict], kwargs: dict) -> Any:
        t0 = time.monotonic()
        resp = await litellm.acompletion(model=model, messages=messages, **kwargs)
        await self._health.record_success(model, (time.monotonic() - t0) * 1000)
        return resp

    async def acompletion(
        self, *, messages: list[dict], model: str | None = None, tier: str = "cheap", **kwargs: Any
    ) -> Any:
        chain = self._chain(model, tier)
        skipped: list[str] = []
        for m in chain:
            if await self._health.in_cooldown(m):
                skipped.append(m)
                continue
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

        # Every model failed or was skipped. If some were only SKIPPED (cooling),
        # force ONE live attempt on the one soonest to recover — don't give up blind.
        if skipped:
            cooldowns = {mm: await _safe_cooldown(self._health, mm) for mm in skipped}
            forced = min(cooldowns, key=cooldowns.get)
            try:
                return await self._attempt(forced, messages, kwargs)
            except Exception as exc:  # noqa: BLE001
                await self._health.record_failure(forced, _classify(exc))
        raise ResilientLLMExhausted(f"All models exhausted: {chain}")

    async def chat(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        tier: str = "cheap",
        temperature: float = 0.3,
        max_tokens: int = 1024,
        response_format: dict | None = None,
        **kwargs: Any,
    ) -> str:
        opts: dict[str, Any] = {"temperature": temperature, "max_tokens": max_tokens, **kwargs}
        if response_format:
            opts["response_format"] = response_format
        resp = await self.acompletion(messages=messages, model=model, tier=tier, **opts)
        return resp.choices[0].message.content or ""


async def _safe_cooldown(health: LLMHealth, model: str) -> float:
    try:
        return await health.cooldown_until(model)
    except Exception:  # pragma: no cover
        return 0.0
```

Note: `_safe_cooldown` is the module-level async helper shown at the bottom of the file; the cooldowns are resolved into a plain dict first (the comprehension above) so `min(key=...)` operates on concrete floats, not coroutines. Verify `litellm.RateLimitError` / `litellm.Timeout` exist in the installed version (`python -c "import litellm; print(litellm.RateLimitError, litellm.Timeout)"`); if a name differs, adjust `_classify` to the real names and note it.

- [ ] **Step 5: Add the DI provider**

In `life_graph/api/dependencies.py`, near `get_lm_client` (~line 44), add:

```python
@lru_cache(maxsize=1)
def get_resilient_llm():
    """Singleton resilient LLM wrapper (shared health record)."""
    from life_graph.services.resilient_llm import ResilientLLM

    return ResilientLLM()
```

(Confirm `lru_cache` is imported in the file — it is, used by other providers.)

- [ ] **Step 6: Run tests + lint + commit**

```bash
python -c "import litellm; print(litellm.RateLimitError, litellm.Timeout)"   # confirm exception names
pytest tests/unit/test_resilient_llm.py -v
ruff check life_graph/services/resilient_llm.py life_graph/config.py life_graph/api/dependencies.py tests/unit/test_resilient_llm.py && ruff format life_graph/services/resilient_llm.py tests/unit/test_resilient_llm.py
git add life_graph/services/resilient_llm.py tests/unit/test_resilient_llm.py life_graph/config.py life_graph/api/dependencies.py
git commit -m "feat(resilience): ResilientLLM ordered-failover wrapper + config + DI

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Choke point — route `LMStudioClient` cloud path through `ResilientLLM`

Repoint `LMStudioClient._cloud_chat` to the resilient wrapper so all `.chat` callers (synthesis, sessions, failure-mining, second-opinion, local-extraction path) gain failover in one change; keep local LM Studio as the terminal fallback.

**Files:** Modify `life_graph/services/llm_client.py`; create `tests/unit/test_llm_client_resilient.py`.

**Interfaces:** Consumes `ResilientLLM` (Task 2). `LMStudioClient.chat`'s external signature is unchanged.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_llm_client_resilient.py`:

```python
"""LMStudioClient cloud path now delegates to ResilientLLM."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

import life_graph.services.llm_client as lc
from life_graph.services.llm_client import LMStudioClient
from life_graph.services.resilient_llm import ResilientLLMExhausted


@pytest.mark.asyncio
async def test_cloud_chat_uses_resilient(monkeypatch):
    monkeypatch.setattr(lc.settings, "use_hybrid_llm", True, raising=False)
    monkeypatch.setattr(lc.settings, "openrouter_api_key", "k", raising=False)
    resilient = AsyncMock()
    resilient.chat = AsyncMock(return_value="cloud-answer")
    monkeypatch.setattr(lc, "get_resilient_llm", lambda: resilient)
    out = await LMStudioClient().chat([{"role": "user", "content": "q"}])
    assert out == "cloud-answer"
    resilient.chat.assert_awaited()


@pytest.mark.asyncio
async def test_falls_back_to_local_on_exhaustion(monkeypatch):
    monkeypatch.setattr(lc.settings, "use_hybrid_llm", True, raising=False)
    monkeypatch.setattr(lc.settings, "openrouter_api_key", "k", raising=False)
    resilient = AsyncMock()
    resilient.chat = AsyncMock(side_effect=ResilientLLMExhausted("x"))
    monkeypatch.setattr(lc, "get_resilient_llm", lambda: resilient)
    client = LMStudioClient()
    client._local_chat = AsyncMock(return_value="local-answer")  # type: ignore[method-assign]
    out = await client.chat([{"role": "user", "content": "q"}])
    assert out == "local-answer"
```

- [ ] **Step 2: Run → FAIL** (`get_resilient_llm` not imported in llm_client; cloud path still uses openrouter directly).

- [ ] **Step 3: Implement**

In `life_graph/services/llm_client.py`:
- Import at top: `from life_graph.api.dependencies import get_resilient_llm` — **but** that risks a circular import (dependencies imports many services). Instead import lazily inside `_cloud_chat`. Add no top-level import.
- Replace the body of `chat` (lines ~92-98) so cloud exhaustion cleanly falls to local:

```python
        if self._use_cloud:
            try:
                return await self._cloud_chat(messages, model, temperature, max_tokens, response_format)
            except Exception:
                logger.warning("Resilient cloud chat exhausted, falling back to local LLM", exc_info=True)
        return await self._local_chat(messages, model, temperature, max_tokens, response_format)
```

- Replace `_cloud_chat` (lines ~100-128) to delegate to the resilient wrapper (it raises `ResilientLLMExhausted` on total failure, caught above):

```python
    async def _cloud_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None,
        temperature: float,
        max_tokens: int,
        response_format: dict | None,
    ) -> str:
        """Chat via the resilient cloud chain (OpenRouter/Gemini/... with failover)."""
        from life_graph.api.dependencies import get_resilient_llm

        return await get_resilient_llm().chat(
            messages,
            model=model,  # None → wrapper picks the tier default
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )
```

- Leave `_local_chat`, `embed`, `embed_batch`, `list_models` unchanged.

- [ ] **Step 4: Run → PASS** (`pytest tests/unit/test_llm_client_resilient.py -v`).
- [ ] **Step 5: Lint + commit** (files: `llm_client.py`, `test_llm_client_resilient.py`; message `feat(resilience): route LMStudioClient cloud path through ResilientLLM` + trailer).

---

### Task 4: Migrate the 5 direct `acompletion` sites

Swap `litellm.acompletion(...)` → `resilient.acompletion(...)` at five sites, keeping each site's model as the primary and its downstream response handling identical.

**Files:** Modify `extraction/llm.py`, `agents/orchestrator.py`, `jobs/consolidation.py`, `services/research_engine.py`, `watchers/dependency_watcher.py`; create `tests/unit/test_extraction_failover.py`.

**Interfaces:** Consumes `ResilientLLM.acompletion(messages=…, model=…, **kwargs) -> raw response` (Task 2).

- [ ] **Step 1: Migrate each site (5 edits)**

For EACH site below, replace the `litellm.acompletion(...)` call with `await get_resilient_llm().acompletion(...)`, keeping every argument the same EXCEPT that positional/`model=` stays as the site's model and messages move to `messages=`. Import the provider lazily where the site currently does `import litellm` (replace that import with `from life_graph.api.dependencies import get_resilient_llm`, unless `litellm` is used elsewhere in the file — then keep both). The response object and all downstream handling (`.usage`, `._hidden_params`, `.choices`, parsing) are UNCHANGED because `acompletion` returns the raw response.

  - `life_graph/extraction/llm.py:222` (`_extract_cloud`): becomes
    ```python
    from life_graph.api.dependencies import get_resilient_llm
    ...
    response = await get_resilient_llm().acompletion(
        messages=messages,
        model=self._model,
        max_tokens=self._max_tokens,
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    ```
    Keep the surrounding `try/except Exception: return []` — but note total failover exhaustion now raises `ResilientLLMExhausted`, which the existing `except Exception` already catches (→ returns `[]`, i.e. the rules/nlp tier runs). Leave the cost/usage tracking below it unchanged.
  - `life_graph/agents/orchestrator.py:119`: same swap (`messages=…, model=<existing>, **existing kwargs`). Preserve its response handling.
  - `life_graph/jobs/consolidation.py:321`: same swap.
  - `life_graph/services/research_engine.py:422`: same swap.
  - `life_graph/watchers/dependency_watcher.py:115`: same swap.

  For each, read the existing call first and forward its exact kwargs. Do NOT change temperatures, max_tokens, response_format, or parsing.

- [ ] **Step 2: Write a failover test (extraction as representative)**

Create `tests/unit/test_extraction_failover.py`:

```python
"""Extraction's cloud path fails over via ResilientLLM instead of hard-failing."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import life_graph.extraction.llm as ex


@pytest.mark.asyncio
async def test_extract_cloud_uses_resilient(monkeypatch):
    # A response whose JSON content yields zero facts is fine; we assert the
    # resilient wrapper is what gets called (not litellm directly).
    resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"facts": []}'))],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
        _hidden_params={},
    )
    resilient = AsyncMock()
    resilient.acompletion = AsyncMock(return_value=resp)
    monkeypatch.setattr(ex, "get_resilient_llm", lambda: resilient)

    extractor = ex.LLMExtractor(model="gemini/gemini-2.0-flash")
    facts = await extractor._extract_cloud("some text")
    resilient.acompletion.assert_awaited()
    assert resilient.acompletion.call_args.kwargs["model"] == "gemini/gemini-2.0-flash"
    assert facts == []
```

Adjust `LLMExtractor` construction/attribute names to the real class (read `extraction/llm.py` first — the class name and `_model`/`_max_tokens` fields). If the local path is what a bare `LLMExtractor` uses, target `_extract_cloud` directly as shown.

- [ ] **Step 3: Run the new test + the full unit suite**

Run: `pytest tests/unit/test_extraction_failover.py tests/unit/ -q`
Expected: new test passes; no regressions in the existing suite.

- [ ] **Step 4: Lint + commit** (the 5 modified files + the test; message `feat(resilience): route 5 direct LLM call sites through ResilientLLM` + trailer).

---

### Task 5: Advisor migration (delicate)

`multi_model_advisor` fans out diverse opinions with per-instance `api_key`/`api_base`, an `asyncio.wait_for` timeout, and a fabricated `ModelResponse` on failure. Route each opinion through `resilient.acompletion` while preserving all of that.

**Files:** Modify `life_graph/services/multi_model_advisor.py`; create `tests/unit/test_advisor_resilient.py`.

- [ ] **Step 1: Read the call site + surrounding method**

Read `life_graph/services/multi_model_advisor.py` around lines 300-345 (the `litellm.acompletion` inside `asyncio.wait_for`, the `except asyncio.TimeoutError` branch returning a fabricated `ModelResponse`, and how `model`, `self._api_key`, `self._api_base`, `self._timeout` are used).

- [ ] **Step 2: Migrate the opinion call**

Replace the `litellm.acompletion(...)` inside `asyncio.wait_for(...)` with `get_resilient_llm().acompletion(...)`, forwarding the opinion's `model` as the primary and passing `api_key=self._api_key, api_base=self._api_base` through as kwargs (the wrapper forwards `**kwargs` to `litellm.acompletion`). Keep the `asyncio.wait_for(..., timeout=self._timeout)` wrapper as-is around the call, and keep the existing `except asyncio.TimeoutError` fabricated-`ModelResponse` fallback. Add an `except ResilientLLMExhausted:` branch that returns the SAME fabricated-`ModelResponse` fallback the timeout branch uses (extract that fallback into a small local helper if it reduces duplication, or return an equivalent `ModelResponse`). Import `get_resilient_llm` (lazily) and `ResilientLLMExhausted`.

Concretely (adapt to the real surrounding code):

```python
from life_graph.api.dependencies import get_resilient_llm
from life_graph.services.resilient_llm import ResilientLLMExhausted
...
        t0 = time.monotonic()
        try:
            response = await asyncio.wait_for(
                get_resilient_llm().acompletion(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": question},
                    ],
                    model=model,
                    api_key=self._api_key,
                    api_base=self._api_base,
                    response_format={"type": "json_object"},
                    temperature=0.3,
                ),
                timeout=self._timeout,
            )
        except (asyncio.TimeoutError, ResilientLLMExhausted):
            latency = int((time.monotonic() - t0) * 1000)
            logger.warning("Advisor model %s unavailable after %dms", model, latency)
            return ModelResponse(model=model, ...)  # the existing fabricated fallback, unchanged
```

Preserve the rest of the method (parsing the response into the advisor's opinion shape) unchanged.

- [ ] **Step 3: Write the test**

Create `tests/unit/test_advisor_resilient.py` asserting: (a) a successful opinion call routes through `resilient.acompletion` with the opinion's `model` and forwards `api_key`/`api_base`; (b) when `resilient.acompletion` raises `ResilientLLMExhausted`, the advisor returns its fabricated fallback `ModelResponse` (not an exception). Mock `get_resilient_llm` and read the real method to shape the assertions.

- [ ] **Step 4: Run test + suite; lint + commit** (files: `multi_model_advisor.py`, `test_advisor_resilient.py`; message `feat(resilience): resilient advisor opinions, preserving diversity + fallback` + trailer).

---

### Task 6: Status endpoint `GET /api/v1/health/models`

**Files:** Create `life_graph/api/model_health.py`; modify `life_graph/main.py` (register router); create `tests/integration/test_model_health_endpoint.py`.

**Interfaces:** Consumes `LLMHealth.snapshot()` (Task 1) via `get_resilient_llm()._health` or a fresh `LLMHealth()`.

- [ ] **Step 1: Write the router**

Create `life_graph/api/model_health.py`:

```python
"""Read-only free-LLM backend health for the status card."""
from __future__ import annotations

from fastapi import APIRouter

from life_graph.api.responses import success_response
from life_graph.services.llm_health import LLMHealth

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/models")
async def model_health():
    """Return each known free-LLM backend's current health state."""
    return success_response(await LLMHealth().snapshot())
```

Confirm the `success_response` import path matches the codebase (other routers use `from life_graph.api.responses import success_response`). If the app mounts routers under `/api/v1`, this yields `GET /api/v1/health/models`.

- [ ] **Step 2: Register in `main.py`**

In `life_graph/main.py`, where other routers are `include_router`'d, add (matching the existing prefix convention — read how neighbors are included and mirror it):

```python
    from life_graph.api import model_health
    app.include_router(model_health.router, prefix="/api/v1")
```

(If routers there are imported at top and included without an inline import, follow that pattern instead.)

- [ ] **Step 3: Write the integration test**

Create `tests/integration/test_model_health_endpoint.py` (reuse the `client`/header fixtures from a sibling integration test):

```python
import pytest


@pytest.mark.asyncio
async def test_model_health_returns_list(client, tenant_headers):
    resp = await client.get("/api/v1/health/models", headers=tenant_headers)
    assert resp.status_code != 422
    if resp.status_code == 200:
        assert isinstance(resp.json()["data"], list)  # possibly empty when Redis has no records
```

Match the real fixture names used by sibling `tests/integration/*` files.

- [ ] **Step 4: Run test + import check + lint + commit**

```bash
python -c "import life_graph.main"
pytest tests/integration/test_model_health_endpoint.py -v   # skip acceptable if the suite needs a DB that's down
```
Commit files: `api/model_health.py`, `main.py`, the test; message `feat(resilience): GET /health/models status endpoint` + trailer.

---

### Task 7: Mobile "Model health" card

**Files:** Create `dashboard/app/(mobile)/m/settings/page.tsx`; modify `dashboard/lib/api.ts`, `dashboard/lib/mobile-api.ts`, `dashboard/components/mobile/mobile-shell.tsx`.

- [ ] **Step 1: API client + hook**

In `dashboard/lib/api.ts`, add a `health` group (or extend an existing one):

```ts
  health: {
    models: () => GET<any>("/health/models"),
  },
```

In `dashboard/lib/mobile-api.ts`, add:

```ts
export function useModelHealth() {
  return useQuery({
    queryKey: ["model-health"],
    queryFn: () => api.health.models().then((r) => r.data ?? []),
    refetchInterval: 30_000,
  });
}
```

(`useQuery`, `api` are already imported in this file.)

- [ ] **Step 2: Settings page with the card**

Create `dashboard/app/(mobile)/m/settings/page.tsx` — a client component rendering `useModelHealth()` as a compact list. Each row: a colored dot (`up`→`var(--success)`, `cooling`→`var(--warning)`, `down`→`var(--danger)`, `unknown`→`var(--text-subtle)`), the model short name (last path segment), a relative "last seen" (from `last_success_at`), and `last_error` if present. Reuse `LoadingCard`/`EmptyCard`/`ErrorCard` from `@/components/mobile/parts`. Empty state: "No model activity recorded yet." Use design tokens only; no `any` on the row type (define a small `ModelHealthVM` interface).

- [ ] **Step 3: Gear link in the shell header**

In `dashboard/components/mobile/mobile-shell.tsx`, add a small gear icon (`Settings` from `lucide-react`) linking (`next/link`) to `/m/settings` in the header row (read the header markup first; place it at the trailing edge). Keep it subtle (icon-only, `var(--text-subtle)`).

- [ ] **Step 4: Build + lint**

From `dashboard/`: `npm run build` (clean) + `npm run lint` (zero new problems vs baseline).

- [ ] **Step 5: Manual verification + commit**

Self-verify the wiring (hook → endpoint → card; gear → route). Live tap→data is deferred to the batched E2E. Commit the 4 files; message `feat(resilience): mobile Model health card + settings route` + trailer.

---

## Final verification (whole branch)

1. `pytest tests/unit/ -v` green (new: llm_health, resilient_llm, llm_client_resilient, extraction_failover, advisor_resilient); `pytest tests/integration/test_model_health_endpoint.py -v` (green or DB-skip).
2. `ruff check life_graph/` clean on new/changed lines; `python -c "import life_graph.main"` imports.
3. `npm run build` + `npm run lint` clean from `dashboard/`.
4. Trace one path end-to-end by reading: a caller → `ResilientLLM.acompletion` → primary 429 → `LLMHealth.set_cooldown` + record → next model success → record → (endpoint) `snapshot()` shows primary `cooling`, fallback `up` → mobile card renders the dots.
5. Confirm every migrated site still parses its response the same way (no downstream change) and still degrades (extraction→[], synthesis→rule-based) on `ResilientLLMExhausted`.

## Notes for the batch merge

Off `origin/master` (`d829b61`); independent of PRs #15–#19. No migration (Redis-only), so no alembic collision. `config.py`, `api/dependencies.py`, `main.py`, and `dashboard/lib/api.ts`/`mobile-api.ts`/`mobile-shell.tsx` are shared-ish files that other open PRs also touch — additive changes here; re-run build/tests after each merge.
