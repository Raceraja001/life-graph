# Free-Model Resilience — never hard-fail on a rate-limited backend

> **Date:** 2026-07-31
> **Status:** Approved design — ready for implementation planning
> **Scope:** new `services/resilient_llm.py` + `services/llm_health.py`, `config.py` (chain +
> cooldowns), a choke-point change to `services/llm_client.py`, migration of the direct
> `litellm.acompletion` call sites, a `GET /api/v1/health/models` endpoint, and a mobile
> "Model health" card. Deployed at `brain.raceraja001.in`.
> **Roadmap:** final workstream (chat → notifications → reactive UI → chat distillation → **resilience**).

## Problem

Life Graph leans on free LLM tiers (Gemini Flash, OpenRouter/DeepSeek, Groq) to stay cheap. But
almost every LLM call targets a **single configured model**: the six `litellm.acompletion(...)`
sites (extraction, agents, consolidation, the multi-model advisor, research, the dependency
watcher) and the hybrid `LMStudioClient` (synthesis, sessions, failure-mining, second-opinion).
When that one model rate-limits (429 — the everyday free-tier reality) or errors, the call fails
and the feature silently degrades to a rule/local tier, even when another free backend would have
answered fine. There is no ordered failover and no visibility into which backend is currently
healthy.

## Decisions (locked with user)

- **Reactive failover, quota-free.** No proactive probing (that would burn the same free quota we
  want for real work). Health is learned from *actual* call outcomes.
- **All call sites, via one choke point.** Every completion routes through a new `ResilientLLM.chat`;
  migration is mechanical and behavior-preserving on the happy path.
- **Ordered chain with cooldowns.** Try the caller's requested/tier model first, then free
  alternates; a model that 429s or errors is benched for a cooldown and the next serves the request.
- **Shared health record in Redis.** App and worker call LLMs in separate processes; Redis (already
  a dependency) unifies the record. No DB migration.
- **Lightweight visibility.** A `GET /health/models` endpoint + a small "Model health" card on the
  mobile **settings** page (diagnostic, not daily).
- **Preserve model *choice*.** The wrapper adds resilience + recording only; it never overrides a
  caller's deliberate model (e.g. an expensive-tier call still tries expensive first). The
  multi-model advisor keeps its intentional per-opinion diversity.

## Non-goals (v1)

- No proactive/scheduled probing; no cron; no probe requests.
- No per-tenant health (model health is global infrastructure state).
- No adoption of LiteLLM's `Router` object — a thin, transparent wrapper we fully control instead.
- No change to *which* model any feature prefers; only failover + recording are added.
- No persistence of health beyond Redis TTL (it's live operational state, not history).
- No embeddings failover (embeddings stay local via LM Studio; out of scope).
- No automatic quota accounting (free tiers don't expose reliable remaining-quota; we record 429s
  as the observable rate-limit signal, not a quota number).

## Architecture

```
any caller ── ResilientLLM.chat(messages, *, model=<caller's choice|None>, tier="cheap"|"expensive", **opts)
   chain = dedupe([ model or tier_default, *settings.llm_fallback_chain ])
   for m in chain:
       if health.in_cooldown(m):  continue                 # benched after a recent failure
       t0 = now
       try:
           resp = await litellm.acompletion(model=m, messages=…, **opts)
           health.record_success(m, latency=now-t0);  return resp   # first success wins
       except RateLimitError (429):
           health.record_failure(m, "429"); health.set_cooldown(m, Retry-After or COOLDOWN_429); continue
       except (Timeout, APIError, APIConnectionError, …):
           health.record_failure(m, kind);  health.set_cooldown(m, COOLDOWN_ERROR); continue
   # every model skipped (all cooling) or failed:
   #   try the least-recently-failed model ONCE more (don't give up without a live attempt);
   #   if that fails, raise ResilientLLMExhausted → caller's EXISTING degradation runs.

  LMStudioClient.chat ── cloud attempt now delegates to ResilientLLM.chat;
                          local LM Studio stays the terminal fallback (when reachable).

  health record (Redis)  hash per model: last_success_at, last_failure_at, last_error,
                          consecutive_failures, cooldown_until, avg_latency_ms  (TTL ~1h)
        │
        ▼
  GET /api/v1/health/models → [{model, state: up|cooling|down, last_seen, last_error, avg_latency_ms}]
        │
        ▼  mobile Settings "Model health" card (colored dot per backend)
```

## Components

### 1. `ResilientLLM` (`services/resilient_llm.py`)

- `async def acompletion(self, *, messages, model=None, tier="cheap", **kwargs) -> ModelResponse`:
  the loop above — the **core**, a resilient drop-in for `litellm.acompletion` that returns the
  **raw LiteLLM response object** (so the six direct call sites keep parsing `response.usage`,
  `response._hidden_params` cost, and `response.choices` exactly as they do today). Raises
  `ResilientLLMExhausted` (a new exception) only when every attempt (including the final
  least-recently-failed retry) fails.
- `async def chat(self, messages, *, model=None, tier="cheap", temperature=0.3, max_tokens=1024,
  response_format=None, **kwargs) -> str`:
  a thin convenience wrapping `acompletion` and returning `response.choices[0].message.content or ""`
  — for text-only callers (`LMStudioClient`'s cloud path, synthesis). Callers catch
  `ResilientLLMExhausted` and run their existing fallback (extraction → rules/nlp; synthesis →
  rule-based answer).
- **Chain assembly:** `[caller_model_or_tier_default] + settings.llm_fallback_chain`, de-duplicated
  preserving order. `tier="cheap"` default = `settings.llm_model_cheap`; `tier="expensive"` =
  `settings.llm_model_expensive`. A caller passing an explicit `model` puts it at the head.
- **Cooldown skip:** consult `LLMHealth.in_cooldown(model)` before each attempt.
- **Error classification:** distinguish 429 (rate limit → longer cooldown, honor `Retry-After`
  header when present) from other errors (timeout/connection/API → shorter cooldown). Use LiteLLM's
  exception types (`litellm.RateLimitError`, etc.) with a permissive fallback on the message.
- Singleton via a DI provider (`get_resilient_llm()` in `api/dependencies.py`), holding an
  `LLMHealth` instance.

### 2. `LLMHealth` (`services/llm_health.py`) — Redis-backed record

- Keyed `llm:health:{model}` → hash: `last_success_at`, `last_failure_at`, `last_error`
  (`"429"|"timeout"|"error"`), `consecutive_failures`, `cooldown_until` (epoch), `avg_latency_ms`
  (EMA). Each key `EXPIRE`d (~1h) so a long-idle model naturally drops to "unknown".
- Methods: `record_success(model, latency_ms)`, `record_failure(model, kind)`,
  `set_cooldown(model, seconds)`, `in_cooldown(model) -> bool`, `snapshot() -> list[dict]` (for the
  endpoint). Uses `storage/redis.py::get_redis()`; **if Redis is unavailable, all methods no-op /
  return "not cooling"** so resilience still works without a health record (fail-open).
- Global, not tenant-scoped. Reads/writes are best-effort (never raise into the LLM path).

### 3. Config (`config.py`)

- `llm_fallback_chain: str` (comma-separated LiteLLM ids, ordered) — default derived from existing
  settings, e.g. `"gemini/gemini-2.0-flash,openrouter/deepseek/deepseek-chat"`; `LIFE_GRAPH_`-prefixed
  override. A `llm_fallback_chain_list` property parses it.
- `llm_cooldown_429_seconds: int = 60`, `llm_cooldown_error_seconds: int = 30`,
  `llm_health_ttl_seconds: int = 3600`.
- Local LM Studio is appended to the effective chain **only when configured/reachable** (existing
  `use_hybrid_llm`/lm_studio settings gate it); on the VM the chain is cloud-only and the terminal is
  the caller's rule/local degradation.

### 4. Call-site migration (the "all call sites" work)

- **Choke point — `services/llm_client.py`:** `LMStudioClient._cloud_chat` currently calls a single
  `openrouter_model`. Repoint it to `ResilientLLM.chat(...)` (passing the caller's `model` through as
  the primary). This makes **every** `.chat` caller resilient in one change: `synthesis.py`,
  `api/sessions.py`, `services/failure_mining.py`, `services/second_opinion.py`, and the
  local-extraction path in `extraction/llm.py`. Local LM Studio remains `LMStudioClient`'s terminal
  fallback when the resilient cloud chain is exhausted.
- **Direct `litellm.acompletion` sites (6) → `ResilientLLM.acompletion`:** `extraction/llm.py:222`
  (`_extract_cloud`), `agents/orchestrator.py:119`, `jobs/consolidation.py:321`,
  `services/research_engine.py:422`, `watchers/dependency_watcher.py:115`, and
  `services/multi_model_advisor.py:313`. Each swaps `litellm.acompletion(...)` for
  `resilient.acompletion(...)` with its existing `model=` as the primary and **identical downstream
  handling** — the wrapper returns the raw response object, so `response.usage`, cost, `.choices`,
  and `response_format`/other kwargs all pass through unchanged.
- **Advisor diversity preserved (the delicate one):** `multi_model_advisor` fans out across
  `advisor_models` for *diverse opinions*, passing per-instance `api_key`/`api_base`, wrapping each
  call in `asyncio.wait_for(timeout)`, and returning a fabricated `ModelResponse` on failure. The
  fan-out stays; each opinion call becomes `resilient.acompletion(model=<opinion model>,
  api_key=…, api_base=…, timeout=…)` (the wrapper forwards `api_key`/`api_base` via `**kwargs` and
  applies the per-call timeout inside its attempt loop). If the chain is exhausted
  (`ResilientLLMExhausted`), the advisor keeps its existing fabricated-`ModelResponse` fallback for
  that opinion. This site needs individual care in its own task.

### 5. Status endpoint + mobile card

- **`GET /api/v1/health/models`** (new route, e.g. `api/health.py` or the existing health router):
  returns `LLMHealth.snapshot()` mapped to `[{model, state, last_seen, last_error, avg_latency_ms}]`
  where `state` = `up` (recent success, not cooling), `cooling` (cooldown_until in the future),
  `down` (only failures recently), or `unknown` (no record / TTL expired). No tenant scoping.
- **Mobile "Model health" card** — mobile has no settings page today, so add a minimal new route
  `dashboard/app/(mobile)/m/settings/page.tsx` reached via a small gear link in the mobile shell
  header (keeps this diagnostic off the daily home surface). The card is a compact list — colored dot
  (green up / amber cooling / red down / grey unknown) + model short name + "last seen 2m ago" +
  last error. A `useModelHealth()` hook (polling ~30s; operational, low-frequency). Read-only.

## Failure handling

| Case | Behaviour |
|---|---|
| Primary model 429s | Benched for `Retry-After` or 60s; the next chain model serves the request; both outcomes recorded |
| Transient error/timeout | Benched 30s; next model serves; recorded |
| All models cooling | Try the least-recently-failed one anyway (one live attempt) rather than giving up blind |
| Every attempt fails | Raise `ResilientLLMExhausted`; caller runs its existing degradation (rules/nlp or rule-based answer) — never a hard 500 to the user |
| Redis down | Health methods fail-open (no cooldowns, no records); failover still tries models in order |
| Caller requested an explicit model | That model is the primary (tried first); chain is only the fallback tail — deliberate choices honored |
| Local LM Studio unreachable (VM) | Simply not in the effective chain; terminal is the rule/local degradation |
| Endpoint read with no records yet | Models report `state: "unknown"` — honest, not a fake "up" |

## Verification

1. **Unit** (`tests/unit`, mocked `litellm.acompletion` + a fake/mocked Redis):
   - First model succeeds → returned; `record_success` called; no cooldown.
   - First model raises 429 → cooldown set (honoring `Retry-After`), second model used and returned,
     both outcomes recorded.
   - A model in cooldown is skipped.
   - All models fail → `ResilientLLMExhausted` raised; health reflects the failures.
   - "All cooling → try least-recently-failed once" path exercised.
   - Redis unavailable → methods no-op, failover still returns the first working model (fail-open).
   - `LLMHealth.snapshot()` returns the documented shape; `state` derivation (up/cooling/down/unknown).
   - `LMStudioClient._cloud_chat` now delegates to `ResilientLLM` (asserted via a mock) and still
     falls back to local on exhaustion.
2. **Integration** (`tests/integration`, httpx ASGITransport):
   - `GET /api/v1/health/models` returns 200 and the list shape; valid request never 422.
   - A representative migrated caller (e.g. extraction) still returns correctly when the primary is
     mocked to 429 and a fallback succeeds.
3. **Live E2E (batched with deploy):** on the VM, force a 429 (or wait for the free tier to rate-limit)
   → confirm the request is served by the next backend, the "Model health" card shows the primary as
   `cooling` and the fallback as `up`, and the card recovers to `up` after the cooldown. Confirm no
   feature hard-errors while a backend is rate-limited.
