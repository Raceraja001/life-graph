# Splitting `AgentOrchestrator.run()` — plan (audit M15)

Status: **plan only**, 2026-11-20. Not done in the p2-boundaries batch on
purpose: `run()` is the loop every chat turn, kernel task and dispatched dev
task goes through, and that batch already moved the tool-allowlist rule
(M14) and the session/memory boundaries (M12). One risky change at a time.

`life_graph/agents/orchestrator.py:71-564`: one async generator, ~494 lines,
complexity 35 (ruff C901 limit 15), 142 statements (PLR0915 limit 50). It is
in the ruff per-file baseline in `pyproject.toml`; delete that entry when this
lands.

## What it does today, in order

1. Resolve tools (`tools` or the whole registry) and `allowed_tool_names`, the
   execution-time enforcement set.
2. Build `working_messages` (system prompt + messages).
3. `claude-cli` short path: flatten to one prompt, no tools, emit
   token/usage/done or partial_error/done, return.
4. Per-run state: token count, retry count, `StuckDetector`, condenser budget,
   `outside_seen` taint.
5. Loop up to `MAX_ITERATIONS`:
   1. condense the window (iteration > 0) and emit `condensed`;
   2. one streamed completion: emit `token`s, accumulate tool calls (with the
      Ollama index-0 remap);
   3. no tool calls: ask `keep_going` (nudge and continue) or emit usage/done
      `completed` and return;
   4. append the assistant message with normalised tool calls;
   5. execute each call: parse args, emit `tool_call`, refuse names outside
      `allowed_tool_names`, run inside `audience_for_model` +
      `tool_call_scope(outside_seen)`, update taint, emit `tool_result`, append
      the capped result, feed the stuck detector;
   6. stuck: first time nudge, second time emit stuck/usage/done `stuck`;
   7. errors: `ResilientLLMExhaustedError` → partial_error/done `error`; any
      other → one retry with `status`, then partial_error/done `error`.
6. Max iterations: usage/done `max_iterations`.

## Target shape

Keep `run()` as the public async generator and its exact event stream; move
the phases into private methods/helpers that return data, so the generator
only sequences and yields:

| New unit | Takes | Returns / yields |
|---|---|---|
| `_resolve_tools(tools)` | tools arg | `(resolved_tools, allowed_names)` |
| `_run_claude_cli(working_messages)` | messages | async gen of the 3-5 events (moved as is) |
| `_RunState` dataclass | — | tokens, retry count, detector, budget, outside_seen |
| `_condense(working, state)` | — | optional `condensed` event dict |
| `_stream_completion(working, kwargs)` | — | async gen of `token` events, then a final `_Turn(content, tool_calls)` (pure accumulation incl. the index remap, unit-testable without a model) |
| `_normalise_tool_calls(acc, iteration)` | accumulator | assistant `tool_calls` list (blank-id fix, `_valid_json_args`) |
| `_execute_tool_call(tc, state)` | one call | async gen of `tool_call`/`tool_result`, returns the tool message; enforcement check stays here, as the single gate |
| `_stuck_outcome(stuck, detector)` | — | nudge message or terminal events |
| `_done(state, stop_reason, **extra)` | — | the usage+done pair every exit emits |

The `_done` helper alone removes five copies of the usage/done pair, and makes
"every exit ends with exactly one `done`" a property of one function.

## Safety invariants to pin before moving anything

Write these as tests first (several exist in
`tests/unit/test_orchestrator_tool_enforcement.py` and
`test_orchestrator_claude_cli_routing.py`; add the rest), run them on the
unsplit code, then split:

1. A tool name the model emits that is not in `allowed_tool_names` is refused
   and never reaches `registry.execute` (enforcement point).
2. Tools run inside `audience_for_model(self.model)` and
   `tool_call_scope(outside_seen)`; taint is sticky for the rest of the run
   and set even when the tool call fails.
3. Event sequence per exit path (completed, nudged-then-completed, stuck,
   exhausted, unknown-error-retried, unknown-error-final, max_iterations,
   claude-cli success/failure): a golden list of `type` values with a fake
   streaming LLM.
4. No message is inserted between an assistant tool call and its tool
   results (the stuck nudge comes after all results of a turn).
5. Ollama index-0 parallel calls become separate calls with valid JSON args.

## Order of work (one PR each)

1. Golden event-sequence tests (above), no code change.
2. Extract `_done` and `_stream_completion` + `_normalise_tool_calls` (pure,
   most of the complexity); tests unchanged and green.
3. Extract `_execute_tool_call` and the stuck handling.
4. Extract the claude-cli path and `_RunState`; drop the ruff baseline entry.
5. Re-run the agent benchmark (12-task OpenCode/qwen3-coder and gpt-oss sets)
   and compare pass counts and median latency with the pre-split run before
   release.
