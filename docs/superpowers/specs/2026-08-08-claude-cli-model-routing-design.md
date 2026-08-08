# Claude CLI model routing — design

## Purpose

Let a persona's `model` be set to `claude-cli`, routing that persona's replies through the
already-proven CLI-shelling pattern (`life_graph/drivers/claude_code.py`, already used for
`cody`'s autonomous code-fix dispatch) instead of litellm/OpenRouter — selectable per
persona from the existing model picker, so Claude subscription quota is spent only where
deliberately chosen (e.g. `jarvis`), not globally.

Directly motivated: Jarvis's chat replies currently go through `ResilientLLM`/litellm
hardcoded to free/cheap OpenRouter models, and the earlier LLM-resilience work's own notes
already documented free-model latency and a weak model breaking delegation restraint under
a forceful prompt.

## Non-goals — read this section first, it's the scope-defining decision

**No tool-calling support for `claude-cli`-routed replies in this pass.**
`AgentOrchestrator.run()`'s tool loop (`life_graph/agents/orchestrator.py:108-234`) is
built entirely around litellm's OpenAI-shaped streaming deltas
(`chunk.choices[0].delta.tool_calls`, accumulated across chunks, iteratively re-invoked
with tool results appended). Replicating equivalent behavior against the Claude CLI's
one-shot JSON output (`claude -p ... --output-format json`) would mean parsing tool-call
intent out of CLI output, executing it, and re-invoking with results appended — a
materially larger, separate build, not a corner of this one.

**Concrete consequence:** a persona whose `model` is `claude-cli` cannot call *any* tool
during that turn — including `delegate_to_persona`. Setting Jarvis to `claude-cli` means
Jarvis loses delegation ability for replies generated that way. This is a real behavior
change, not a hidden gap — the model picker (see below) should make this legible.

- No incremental token streaming for `claude-cli` replies — the CLI returns one complete
  JSON blob per call, not a stream, so the reply arrives as a single chunk rather than
  token-by-token like every other model today.
- No change to `cody`'s existing use of `claude_code.py` — that path is untouched; this
  adds a second, independent caller of the same subprocess pattern.
- No new UI beyond the model picker entry — no separate settings page, no visible "no
  tools available" warning in this pass (see Open items).

## Architecture

```
Model picker (dashboard) -> persona.model = "claude-cli"
  -> life_graph/services/model_catalog.py: catalog includes {"id": "claude-cli", ...}
       (carried over the same way the two Gemini direct entries already are —
        zero new logic needed there, just one more FALLBACK_MODELS-style entry)

AgentOrchestrator.run() (life_graph/agents/orchestrator.py)
  if self.model == "claude-cli":
    skip the litellm iteration loop entirely
    -> life_graph/services/claude_cli_reply.py: run_claude_cli(prompt: str, timeout: float) -> ClaudeCliResult
         asyncio.create_subprocess_exec("claude", "-p", prompt, "--output-format", "json", ...)
         asyncio.wait_for(proc.communicate(), timeout=...)  [same pattern as claude_code.py:192-199]
         parse JSON, extract .get("result") as the reply text
    yield _sse({"type": "token", "content": <full reply text>})   # one chunk, not streamed
    yield _sse({"type": "usage", ...})
    yield _sse({"type": "done", "model": "claude-cli", ...})
  else:
    <existing litellm loop, unchanged>
```

## `dashboard/lib/model-options.ts` / `life_graph/services/model_catalog.py`

Add one entry to the non-OpenRouter carry-over list already used for the two Gemini direct
models (`model_catalog.py`'s `FALLBACK_MODELS`, the `not m["id"].startswith("openrouter/")`
filter already generically carries any such entry over on every successful fetch — no new
branching logic needed):

```python
{"id": "claude-cli", "name": "Claude CLI (subscription, no tool-calling)", "is_free": False},
```

The `(subscription, no tool-calling)` suffix in the display name is the only UI signal of
the Non-goals limitation for this pass — cheap, honest, no new UI component needed.

## `life_graph/services/claude_cli_reply.py` (new)

```python
async def run_claude_cli(prompt: str, timeout: float = 60.0) -> ClaudeCliResult:
    """Shell out to the Claude CLI for a one-shot, non-streaming, tool-free reply.

    Mirrors drivers/claude_code.py's subprocess pattern (same binary resolution,
    timeout handling, JSON parsing) but is a standalone caller, not a Driver —
    this is a model-routing path, not a task-dispatch path.
    """
```

Reuses `claude_code.py`'s exact subprocess mechanics: `asyncio.create_subprocess_exec`,
piped stdout/stderr, `asyncio.wait_for(proc.communicate(), timeout=timeout)`,
`proc.kill()` + drain on `TimeoutError`, `FileNotFoundError` handling for a missing
binary, generic `Exception` catch-all. Returns a small `ClaudeCliResult` (success, text,
error, duration_ms) — deliberately not reusing `DriverResult` itself (that type carries
task-dispatch-specific fields like `cost_usd`/`metadata` that don't apply here; a
smaller, purpose-built type is clearer than overloading an unrelated one).

**Prompt flattening:** build one string as `f"{role}: {content}"` per message (e.g.
`"user: what's the weather"`, `"assistant: I don't have that tool available"`), each on
its own line, with `system_prompt` (if set) prepended as its own unlabeled first block
followed by a blank line. Newline-joined, passed as the CLI's `-p` argument. No special
formatting beyond that for v1 — the CLI's own model does the actual reasoning about turn
structure from plain text.

## `life_graph/agents/orchestrator.py`

In `run()`, immediately after tools are resolved (`orchestrator.py:78-85`) and before the
`for iteration in range(self.MAX_ITERATIONS):` loop: an `if self.model == "claude-cli":`
branch that flattens `working_messages` into a prompt string, calls `run_claude_cli(...)`,
and yields the three SSE events shown in Architecture above, then `return`s — bypassing
the entire existing loop, which stays untouched for every other model value.

## Error handling

| Failure | Behavior |
|---|---|
| `claude` binary not found on the host | `run_claude_cli` catches `FileNotFoundError`, returns a failure result; orchestrator yields an `error` SSE event in the same shape the existing `ResilientLLMExhausted` path already uses (`orchestrator.py:291-304`) — the chat UI's existing error rendering handles it unchanged. |
| CLI call times out | Same as `claude_code.py`'s existing timeout handling — `proc.kill()`, drain, failure result, same `error` SSE event. |
| CLI exits non-zero / returns `is_error: true` in its JSON | Failure result with the CLI's own error text (mirrors `claude_code.py:212-221`'s success/error determination), same `error` SSE event. |
| Malformed/non-JSON CLI output on a zero exit code | Tolerated, not an error — mirrors `claude_code.py`'s own `_parse_output` behavior exactly: non-JSON stdout is treated as the literal reply text (`{"result": text}`), same as plain-text CLI output. A parse failure alone never fails the call; a non-zero exit code or an explicit `is_error: true` in the parsed JSON is what triggers the failure path below. |

## Testing

- Unit test for `run_claude_cli`: mock `asyncio.create_subprocess_exec` (check
  `tests/unit/` for however `claude_code.py`'s own tests mock this — match that
  convention exactly rather than inventing a new one). Cover: success (parses `result`
  correctly), timeout, `FileNotFoundError`, non-zero exit, malformed JSON output.
- Unit test for the orchestrator branch: assert that when `self.model == "claude-cli"`,
  `run()` yields exactly `token` → `usage` → `done` (no `tool_call` events possible),
  and that the litellm/`ResilientLLM` path is never invoked for this branch (mock
  `get_resilient_llm` and assert it's not called).
- Manual verification (per this repo's established pattern — no frontend test infra):
  set a test persona's model to `claude-cli` via the model picker, send a chat message,
  confirm a reply arrives (as one chunk, not streamed token-by-token) and that attempting
  something that would normally trigger a tool call instead just gets a plain text
  response with no tool invoked.

## Open items intentionally deferred

- Tool-calling support for `claude-cli` — the actual larger follow-up feature, out of
  scope per Non-goals above.
- A visible in-chat UI indicator (not just the model picker's suffixed label) when a
  reply was generated tool-free — worth revisiting if users are confused by the
  behavior change in practice.
- Budget/quota-awareness (tracking how much subscription usage `claude-cli`-routed
  personas consume) — ties to the broader budget-governance gap noted in earlier
  planning; not solved here.
