# LLM resilient fallback — design

## Purpose

Fix the chain of issues that caused Jarvis chat to return "Internal error" / "All
models are currently unavailable" in production on 2026-08-08:

1. Streaming LLM calls silently bypass `ResilientLLM`'s failover — the one bug
   directly responsible for today's "Internal error" (a 404 from a deprecated
   Gemini model never reached the fallback chain at all).
2. The free-model fallback pool is a hand-ordered `.env` list with no signal
   about which models are actually healthy right now.
3. A chronically broken model (dead API key, deprecated model id) gets retried
   at full frequency forever — flat 30s cooldown, no escalation.
4. There's no guaranteed capacity when the entire free tier is congested at
   once (OpenRouter free-pool 429s on two fallbacks simultaneously, also
   observed today).
5. `config.py`'s hardcoded model defaults (`gemini-2.5-flash`,
   `gemini-2.0-flash`) are already past Google's new-key cutoff ahead of the
   Oct 16, 2026 shutdown — the production `.env` override unblocks today, but
   the code defaults will bite the next fresh deploy or local dev setup.

## Non-goals

- No new load-balancing service, no external routing layer — everything below
  extends the existing `ResilientLLM` class in place.
- No change to which providers are integrated (Gemini, OpenRouter) — this is
  about ordering, backoff, and one guaranteed paid fallback, not adding new
  providers.
- No fix for genuine mid-stream failures (a connection that drops after
  several tokens have already been streamed to the user) — only the
  connect/first-byte failure class, which is what actually happened today and
  what's safely recoverable without confusing/duplicating a partially-sent
  reply.
- No UI change — this is entirely backend reliability plumbing.

## Background: root cause of today's incident

Two distinct bugs stacked on 2026-08-08, confirmed via production logs
(`docker logs life_graph_app`) and source inspection:

**Bug A — missing Gemini key (now fixed operationally).** `GEMINI_API_KEY` was
never set in `.env.production`. Every agent run's primary model call failed
with a `403 PERMISSION_DENIED` at the `litellm.acompletion()` await itself —
which *is* inside `ResilientLLM._attempt()`'s try/except, so this case
correctly failed over to the free OpenRouter fallback chain. Roughly 9 of 12
agent runs in a 6-hour window succeeded this way, entirely on
`openrouter/openai/gpt-oss-20b:free` — Gemini was dead weight in the chain the
whole time, invisibly.

**Bug B — streaming bypasses ResilientLLM (the real bug).** After adding a
valid `GEMINI_API_KEY`, calls started reaching Google — which returned
`404 Not Found: "model models/gemini-2.5-flash is no longer available to new
users"` (confirmed via web search: Gemini 2.5 is being sunset, new API keys
are already blocked from it ahead of the Oct 16, 2026 shutdown). This error
did **not** appear via the `life_graph.services.resilient_llm` logger (no
"Model X failed" line, no cooldown set) — it surfaced only via
`life_graph.agents.orchestrator`'s own generic exception handler
(`orchestrator.py:301-319`), which retries the *same* model once and then
gives up with `"Internal error: NotFoundError"`.

Root cause: `ResilientLLM._attempt()` (`resilient_llm.py:99-103`) does
`resp = await litellm.acompletion(model=model, messages=messages, **kwargs)`.
With `stream=True`, `litellm.acompletion()` returns a lazy
`CustomStreamWrapper` almost immediately — the real HTTP request isn't made
until the wrapper is first iterated. So `_attempt()` calls
`record_success()` and returns the (unvalidated) wrapper as a "successful"
result. The real request — and the 404 — only happens later, inside
`orchestrator.run()`'s `async for chunk in response:` loop
(`orchestrator.py:139`), completely outside `ResilientLLM`'s protection: no
classification, no cooldown, no failover to the next model in the chain.

This means the ranking/backoff/paid-fallback work below would not have
caught today's actual failure on its own — Bug A's failure mode (caught
inside `_attempt()`) already worked correctly. Bug B is the piece that has to
be fixed for the rest of this design to matter for this failure class.

## Architecture

```
ResilientLLM.acompletion(model=primary, tier=..., stream=True, ...)
  chain = [primary] + rank(fallback_pool) + [paid_last_resort]   # paid never reordered into the pool
  for m in chain:
    skip if in_cooldown(m)
    try:
      resp = await litellm.acompletion(model=m, stream=True, ...)
      if streaming:
        first_chunk = await resp.__anext__()      # <-- NEW: validates the call
                                                    #     inside this try/except
        return _rechain(first_chunk, resp)         # re-yields first_chunk, then resp
      record_success(m, latency=time_to_first_chunk)
      return resp
    except Exception as exc:
      fails = record_failure(m, kind)              # returns updated consecutive_failures
      cooldown = backoff(kind, fails)               # NEW: exponential, capped
      set_cooldown(m, cooldown)
  # all failed/cooling -> one forced attempt on soonest-to-recover (existing) -> ResilientLLMExhausted
```

`orchestrator.run()` is unchanged apart from now reliably receiving either a
working stream or a `ResilientLLMExhausted` — its existing
`except ResilientLLMExhausted` branch (the clean "all models unavailable"
message) already does the right thing; it just wasn't being reached before.

## Component changes

### `life_graph/services/resilient_llm.py`

- **`_attempt()`**: when `kwargs.get("stream")` is true, after
  `litellm.acompletion()` returns the wrapper, immediately
  `await resp.__anext__()` inside the same try block. On success, wrap it in
  a small async generator that yields the already-fetched first chunk, then
  delegates to the rest of `resp`, and return that. On `StopAsyncIteration`
  (an empty stream — zero chunks), treat it as a failure the same as any
  other exception, so it fails over rather than returning a
  turn with no content. `record_success`'s latency is now measured as
  time-to-first-chunk instead of time-to-lazy-object.
- **`_chain()` → becomes async, and pool-aware**: replace the current
  `[primary, *fallback_list]` construction with
  `[primary, *(await self._rank_fallbacks(fallback_list)), *([paid] if paid else [])]`.
- **New `_rank_fallbacks(pool: list[str]) -> list[str]`**: reads each
  candidate's `LLMHealth` record, sorts ascending by
  `(consecutive_failures, avg_latency_ms if avg_latency_ms is not None else -1)`
  — a model with no history yet (both fields absent) sorts as best-case, so
  new entries in the chain get a fair first try instead of being buried behind
  models with a real latency history. Stable sort, so ties preserve the
  `.env` list's original relative order (keeps the fallback deterministic
  when health data is flat, e.g. right after a Redis flush).
- **Exponential backoff**: in the failure branch, cooldown becomes
  `base_seconds * 2 ** (consecutive_failures - 1)`, capped at
  `settings.llm_cooldown_max_seconds`. `base_seconds` keeps today's existing
  per-kind logic (`llm_cooldown_429_seconds` / Retry-After for 429s,
  `llm_cooldown_error_seconds` for everything else). Resets naturally to
  `base_seconds` next time the model succeeds, since `record_success` already
  zeroes `consecutive_failures`.
- **Paid fallback logging**: a `logger.warning("Falling back to paid model
  %s", paid_model)` right before attempting it — the only new observability
  surface this design adds, since `/api/v1/health/models` already exposes
  the underlying per-model state for anyone who wants to look.

### `life_graph/services/llm_health.py`

- **`record_failure()`**: change return type from `None` to `int`, returning
  the just-incremented `consecutive_failures` value, so `resilient_llm.py`
  can compute backoff without a second Redis round-trip. No storage schema
  change — the field already exists and is already written.

### `life_graph/config.py`

- Fix dead defaults: `agent_llm_model` `"gemini/gemini-2.5-flash"` →
  `"gemini/gemini-3.6-flash"`; `agent_fallback_model`
  `"gemini/gemini-2.0-flash"` → `"gemini/gemini-3.5-flash-lite"`.
- `life_graph/agents/orchestrator.py`'s `FALLBACK_MODEL` class attribute
  (`"gemini/gemini-2.0-flash"`, already documented as "overridden from
  config" in `__init__`) gets the same value for consistency, though it's
  only a fallback for the attribute default, not live behavior.
- New: `llm_paid_fallback_model: str | None = None` — `None` by default so
  local dev and any future non-production deployment never silently spends
  money; set explicitly via `LIFE_GRAPH_LLM_PAID_FALLBACK_MODEL` only in
  `.env.production`.
- New: `llm_cooldown_max_seconds: int = 900` (15 minutes) — the backoff cap.

### `.env.production`

- `LIFE_GRAPH_AGENT_LLM_MODEL=gemini/gemini-3.6-flash` and
  `LIFE_GRAPH_AGENT_FALLBACK_MODEL=gemini/gemini-3.5-flash-lite` (already
  applied operationally ahead of this plan, to unblock production
  immediately — this design makes them the actual code defaults too).
- New: `LIFE_GRAPH_LLM_PAID_FALLBACK_MODEL=openrouter/deepseek/deepseek-chat`.

## Error handling

| Failure | Behavior |
|---|---|
| Redis unavailable | `LLMHealth` fails open (already true today): `in_cooldown` reads as false, health lookups return empty. Ranking collapses to the `.env` list's original order (all-equal sort keys); backoff collapses to flat `base_seconds` (consecutive_failures always reads 0). No new fragility introduced. |
| A model with no health history yet | Sorts as best-case in `_rank_fallbacks` (fair first try), consistent with today's behavior of just trying whatever's next in the list. |
| Streaming call's first-chunk fetch raises | Caught inside `_attempt()`'s try/except exactly like a non-streaming failure — classified, cooldown set, fails over to the next candidate in chain. This is the fix for today's bug. |
| Streaming call's first chunk succeeds but a later chunk fails | Out of scope (see Non-goals) — surfaces to `orchestrator.run()`'s existing single-retry-then-"Internal error" path, unchanged from today. Rare in practice (network blip after a working connection) and unsafe to silently retry on a different model once partial content may have streamed to the user. |
| Every free model (primary + pool) fails or is cooling, no paid model configured | Existing behavior: one forced attempt on the soonest-to-recover, then `ResilientLLMExhausted` → orchestrator's clean "All models are currently unavailable" message. |
| Every free model fails or is cooling, paid model configured | Paid model is attempted (logged at WARNING), same success/failure handling as any other candidate. Only exhausts if the paid model *also* fails. |
| A model stuck broken for hours (like today's dead Gemini key) | Cooldown escalates 30s → 60s → 120s → ... capped at 15 min, instead of retrying at full frequency forever. Resets to 30s base the moment it recovers. |

## Testing

All unit-testable with mocks — no Postgres/Redis needed, matching the
existing pattern in `tests/unit/`.

- **Regression test for Bug B**: mock `litellm.acompletion` to return a fake
  async generator whose first `__anext__()` raises (simulating the 404).
  Assert `ResilientLLM.acompletion()` fails over to the next model in the
  chain instead of returning the broken stream — this test would have caught
  today's incident.
- **Ranking**: seed a fake `LLMHealth` with distinct
  `consecutive_failures`/`avg_latency_ms` per model; assert
  `_rank_fallbacks()` orders them correctly, and that an unseen model sorts
  ahead of ones with recorded failures.
- **Backoff**: call `record_failure` repeatedly for one model; assert the
  cooldown set on each subsequent failure grows (30 → 60 → 120 → ...),
  caps at `llm_cooldown_max_seconds`, and resets to base after a
  `record_success`.
- **Paid fallback placement**: assert it's always the last chain entry
  regardless of its own health data, and that `acompletion()` only reaches it
  once every free candidate has failed or is cooling.
- **Empty-stream handling**: mock a stream that raises `StopAsyncIteration`
  on the first `__anext__()`; assert this is treated as a failure (fails
  over), not a silent empty success.

## Open items intentionally deferred

- True mid-stream recovery (switching models after content has already
  started streaming to the user) — explicitly out of scope; today's failure
  class doesn't need it and it's meaningfully harder to do safely.
- A dashboard/UI surface for the health snapshot — `/api/v1/health/models`
  already exists and is sufficient for now; a visual status card is a
  separate, smaller follow-up if it turns out to be useful.
- Alerting when the paid fallback fires repeatedly (would indicate the free
  tier is chronically insufficient, not just occasionally congested) — the
  new WARNING log line is enough to grep for now; a real alert can follow if
  it turns out to matter in practice.
