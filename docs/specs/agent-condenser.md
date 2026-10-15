# Long Runs: Context Condenser, Stuck Detection, Honest Outcomes — Feature Spec

> **Status: Built and shown live (2026-10-15).** The user asked for a
> detailed plan and then to build it without waiting ("create a detailed plan
> and then, you can work on it and complete. don't expect me").
>
> - **Code:**
>   - `agents/condenser.py`;
>   - `agents/stuck.py`;
>   - the orchestrator's events and `stop_reason`;
>   - `LocalDriver` outcomes;
>   - failure causes `stuck` and `out_of_rounds`.
> - **Tests:** unit tests plus mocked-model end-to-end tests
>   (`tests/unit/test_agent_condenser.py`, `tests/unit/test_long_runs.py`).
>   CI is green.
>
> **What the live trials showed** (qwen3-coder:30b, node-todo fixture):
> 1. **Trial 1 made no tool calls** and answered in prose, yet was reported
>    as a success. The verifiers caught it. **Added:** a coding run with no
>    tool calls now fails with `stop_reason=no_action`, and the error says
>    whether the tool calls were written out as text.
> 2. **Trial 2 made three real tool calls**, then Ollama stalled ("Timeout
>    on reading data from socket") and the run hit 1,200 s. It was correctly
>    reported as `success=False, stop_reason=timeout`; before this change it
>    would have been a success.
>
> **Shown live on 2026-10-15** (qwen3:14b, which fits the GPU; the 30B
> model kept stalling WSL). Every mechanism fired:
>
> | Window | What happened |
> |---|---|
> | 8k, run 1 | mask ×2, summary ×2, a loop nudge, then a `stuck` stop, reported as `success=False` |
> | 8k, run 2 | 40 tool calls, 9 condensations across every layer, and a `no_progress` nudge |
> | 32k | finished in 40 s with no condensing needed |
>
> The trials led to three fixes:
> 1. **Masking now keeps the newest read of each file** while it still fits.
>    Edits failed once a file's only copy was masked, because the model had
>    to guess the exact text to replace.
> 2. **A coding run where no edit landed now fails** with `no_change`. Every
>    `code_edit` was refused and the run was still reported as a success.
> 3. **A kept tail that is itself over budget gets its older results masked.**
>    One turn can make many parallel calls: a 32-message tail stayed at
>    4,785 tokens against a 2,304 budget even with the middle dropped.
>
> **Still a model-quality limit:** qwen3:14b often fails to reproduce exact
> text for `code_edit`, and once claimed a test it never wrote. The
> acceptance verifier caught it, which is what the verifiers are for.
>
> **Prior art.** The ideas come from OpenHands' "condenser" and "stuck
> detector" (MIT licence). Ideas are not copyrighted. No code was copied:
> everything here is written for Life Graph's own orchestrator, message
> format and step recording.

## Why

The local driver runs up to 40 tool rounds on a local model. Three things go
wrong on long runs, and the first two are invisible today.

1. **The front of the conversation silently disappears.** Ollama serves
   every model with `OLLAMA_CONTEXT_LENGTH=32768`. When a prompt is longer,
   it drops tokens from the **start**, which holds the system prompt and the
   task. A run that reads a few large files therefore keeps working but no
   longer knows what it was asked to do, or which rules it must follow. Every
   tool result stays in the conversation forever. A single page of
   `code_read` is about 2–8k characters, so a 20-round coding run passes 32k
   tokens easily.
2. **Loops burn the whole budget.** A model that calls the same tool with the
   same arguments and gets the same error keeps doing it until the
   40-iteration cap or the 1,200-second timeout. Nothing notices or tells it
   to change course.
3. **Failures are reported as successes.** `LocalDriver` counts only events
   of type `error`. The orchestrator reports failure as `partial_error`
   ("All models are currently unavailable", "Internal error"), or as `done`
   with `"warning": "Max tool-calling iterations reached."`. So a run that
   died or ran out of rounds is returned as `success=True` with whatever text
   streamed. The trust scores, failure-cause stats and merge decisions that
   read driver results are all fed that wrong signal.

## Design

### 1. Honest outcomes (`drivers/local.py`)
- `partial_error` counts as an error, like `error`.
- `done` carrying a `warning` (the iteration cap) fails the run with
  `stop_reason="max_iterations"`.
- A `stuck` stop (below) fails the run with `stop_reason="stuck"`.
- The driver result's `metadata.stop_reason` is set to one of `completed`,
  `error`, `timeout`, `max_iterations` or `stuck`, so failure causes can count
  them.
- `services/failure_causes.py` gains the causes `stuck` ("Stuck in a loop")
  and `out_of_rounds` ("Ran out of tool rounds").

### 2. Stuck detection (`agents/stuck.py`, pure)
A `StuckDetector` watches the stream of tool calls and their results. It
looks at a normalised signature of each call: the tool name plus canonical
JSON of its arguments, and a hash of the result.

| Pattern | Rule |
|---|---|
| `repeat` | The same call with the same result, `REPEAT_LIMIT=3` times in a row |
| `error_repeat` | The same call returning an error, 3 times in a row, regardless of the exact error text |
| `ping_pong` | Two calls alternating A, B, A, B, A, B with unchanged results (6 steps) |
| `no_progress` | `NO_PROGRESS_LIMIT=12` calls in a row whose results are all identical to ones already seen in this run, so nothing new was learned |

**Response, in two strikes:**
1. **First detection:** a corrective user message is added to the
   conversation, saying "You have called X with the same arguments 3 times
   and got the same result. Do something different: …, or stop and say what
   is blocking you." A `stuck` event with `action: "nudged"` is recorded.
2. **A second detection of any pattern:** the run ends with a `stuck` event
   (`action: "stopped"`) and a `done` event whose `stop_reason` is `stuck`. A
   stuck run is cheaper than one that runs out the clock, and the step
   record shows why it stopped.

### 3. Context condenser (`agents/condenser.py`)
Before each model call after the first, the conversation is measured. If it
is over budget, it is condensed in layers, cheapest first.

- **Measuring:** `litellm.token_counter` when it is available, otherwise
  characters ÷ 3.5. A ±15% error is fine because the budget leaves headroom.
- **Budget:** `context_tokens × 0.8 − max_tokens`. `context_tokens` comes from
  the setting `agent_context_tokens` (default 32768, matching
  `OLLAMA_CONTEXT_LENGTH`), with a per-model override through
  `agent_context_tokens_by_model` (JSON).
- **Always kept, verbatim:**
  - the system prompt;
  - the first user message (the task);
  - the last `KEEP_RECENT_TURNS=4` assistant turns, each with its tool
    results.
- **Protocol safety:** the condensed list must still be a valid
  chat-completions conversation. An assistant message with `tool_calls` is
  never separated from its `tool` results, and the kept tail never begins
  with an orphaned `tool` message.

**Layers:**
1. **Masking old observations.** Tool results older than the kept tail are
   replaced in place with a stub such as `[earlier result elided: code_read
   life_graph/x.py, 6,240 chars. Call the tool again if you need it]`. The
   `tool_call_id` is kept, so the protocol stays valid, and the model still
   sees *what* it did.
2. **Summarising the middle.** If the conversation is still over budget, the
   span between the task and the kept tail is replaced by one user message,
   `[Summary of the work so far]`. A side call to the same model writes it,
   under the headings **Done so far**, **Files read / changed**, **Current
   state**, **Open problems / next step**. The prompt says to keep exact file
   paths, function names and error messages. The call is capped at 800
   tokens, and the summary is redacted (`services/redaction.py`) before it
   enters the conversation.
3. **Truncating.** If summarising fails or is still over budget, the middle
   is dropped and replaced by a note that it was dropped. Losing the middle
   is better than Ollama silently losing the beginning.

Each condensation emits a `condensed` event (`layer`, `before_tokens`,
`after_tokens`, `messages_before`, `messages_after`), which the step
recorder stores. A run's trajectory therefore shows where and how its memory
was cut.

**Capping single results.** A tool result over `MAX_RESULT_CHARS=12000`
keeps its head and tail, with a marker in the middle saying how much was cut,
when it is appended. One huge output (a log, a big diff) cannot fill the
window by itself.

**Where it runs.** In `AgentOrchestrator.run`, for every non-`claude-cli`
model.
- Chat personas with 8 rounds rarely reach the budget, so for them it is
  a no-op.
- The local driver is where it matters. With condensation in place its
  round cap rises from 40 to 60: rounds were capped partly because the
  context could not hold more.

### 4. Settings

| Setting | Default | Meaning |
|---|---|---|
| `agent_condenser_enabled` | `true` | Master switch |
| `agent_context_tokens` | `32768` | Model context the budget is computed from |
| `agent_context_tokens_by_model` | `{}` | e.g. `{"ollama_chat/qwen3-coder:30b": 65536}` if Ollama is given more |
| `agent_stuck_detection` | `true` | Master switch for stuck detection |

## Verification
- **Unit tests (pure):**
  - each stuck pattern fires, and an ordinary varied run never does;
  - the condenser keeps the system prompt, the task and the tail;
  - every assistant `tool_calls` message keeps all its results, and no
    `tool` message is orphaned;
  - masking alone gets under budget when it can;
  - a summary failure falls back to truncation;
  - the output fits the budget;
  - capping a result keeps its head and tail.
- **Orchestrator tests with a mocked model:**
  - a model repeating one failing call is nudged, then stopped, and emits
    `stuck` and then `done` with `stop_reason=stuck`;
  - a long run sends a request under budget to the model and emits
    `condensed`.
- **Driver tests:**
  - `partial_error` gives `success=False`;
  - the iteration cap gives `stop_reason=max_iterations`.
- **Live trial:**
  - the local driver on the node-todo fixture, with a deliberately small
    `agent_context_tokens` that forces condensation;
  - the task must still finish with its verifiers passing, and the
    trajectory must show `condensed` steps;
  - with the real 32k budget, a 20+ round run must never send a prompt over
    budget.

## Out of scope
- **OpenCode and Claude Code** manage their own context; this changes only
  Life Graph's orchestrator.
- **Retrieval of masked results** (a "recall earlier result" tool). The
  stub tells the model to call the tool again, which is enough for files.
