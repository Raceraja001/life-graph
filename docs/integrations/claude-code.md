# Claude Code integration

Life Graph has a strong memory engine and, until now, no capture surface for coding work.
This adapter closes that: Claude Code's lifecycle hooks post the developer's work into the
Capture Spine, and session start injects proactive recall back into the model's context.

- **Code:** `life_graph/integrations/claude_code/`
- **Installer:** `life-graph hooks install | uninstall | status`
- **Plugin:** `integrations/claude-code-plugin/`
- **Tests:** `tests/unit/test_claude_code_hook.py`, `tests/unit/test_hook_installer.py`

---

## Install

```bash
life-graph hooks install          # merges into ~/.claude/settings.json
life-graph hooks status           # what is wired, where captures go
life-graph hooks uninstall        # removes only our entries
```

Then **restart Claude Code** (or open a new session) — hooks are read at session start.

The installed command is `<current python> -m life_graph.integrations.claude_code.hook`.
`hooks install` bakes in `sys.executable`, so the hook inherits the virtualenv you ran the
CLI from; a bare `python3` would not have `life_graph` or `httpx` importable. Re-running
`install` replaces the entry in place, which also upgrades a stale interpreter path.

Useful flags:

| Flag | Effect |
|---|---|
| `--dry-run` | Print the resulting settings JSON; write nothing, back up nothing |
| `--settings <path>` | Operate on another settings file (use this for experiments) |
| `--python <path>` | Pin a specific interpreter in the hook command |

### Safety of the settings edit

`~/.claude/settings.json` is the developer's file. Every operation is a deep merge:

- Top-level keys (`theme`, `statusLine`, `autoCompact*`, …) are untouched.
- Existing entries in each event array are preserved; ours is appended, never substituted.
- Our entries are recognised by the marker `life_graph.integrations.claude_code.hook`
  inside the entry's `command`. No extra keys are added to the entry, so nothing depends on
  Claude Code preserving fields its schema does not know about.
- A timestamped backup is written before any write, matching the existing
  `settings.json.bak.20260822135550` convention.
- Install is idempotent — running it twice never duplicates an entry.
- `uninstall` removes only our entries and drops the arrays it emptied, restoring the
  original file.
- A settings file that does not parse is reported and **never** overwritten.

### As a plugin instead

```bash
claude --plugin-dir /path/to/life-graph/integrations/claude-code-plugin
```

`integrations/claude-code-plugin/` holds `.claude-plugin/plugin.json` and
`hooks/hooks.json`, which point at `${CLAUDE_PLUGIN_ROOT}/hooks/life-graph-hook.sh`. That
shim resolves the repo root from its own location, prefers the repo's `.venv/bin/python`,
and puts the repo on `PYTHONPATH` so the plugin works from a plain checkout. In plugin mode
`${CLAUDE_PLUGIN_DATA}` is set, so hook state lives under the plugin's own data directory
rather than `~/.life-graph/`.

---

## What is captured

| Hook event | Surface | Trust tier | Content |
|---|---|---|---|
| `UserPromptSubmit` | `cli` | **SELF** | The prompt you typed — injected turns are dropped |
| `PostToolUse` | `tool_exhaust` | **VERIFIED** | `tool:<name> status:ok <ms>ms args:<summary>` |
| `PostToolUseFailure` | `tool_exhaust` | **VERIFIED** | same, `status:error`, plus the error |
| `Stop` | `assistant_message` | **VERIFIED** | The assistant's closing message |
| `SubagentStop` | `assistant_message` | **VERIFIED** | The subagent's closing message |
| `SessionStart` | — | — | *reads* — injects recall, captures nothing |
| `SessionEnd` | — | — | flushes the offline spool |

### Trail versus content

`tool_exhaust` is an activity trail, and `capture_no_extract_surfaces` (default
`tool_exhaust`) keeps the capture spine from extracting it. Without that, every tool call
became several LLM-written "facts" about shell commands — 4,831 of 5,067 memories on one
instance, all pending, all of it flowing back in through `SessionStart` recall.

Two consequences shape the table above:

* `Stop` moved off `tool_exhaust` onto its own `assistant_message` surface. A closing
  message is a conclusion, the one thing on this path worth remembering, and leaving it on
  a non-extracted surface would have discarded it silently.
* `UserPromptSubmit` drops turns Claude Code *injects* rather than ones you type —
  `<task-notification>`, `<local-command-stdout>`, `<command-name>`, `<command-message>`.
  Each background task otherwise taught the spine that "The task with ID 'blwug1frp' has
  been completed". Matched at the start of the prompt only, so quoting a tag mid-sentence
  still counts as you speaking.

`modality` is always `text`. `capture_processors` early-returns on every other modality, so
a `structured` event would be stored but never processed into memory.

### Surfaces are trust discriminators, not labels

`life_graph/core/trust.py` maps surface → `TrustTier` and is **default-deny**: any surface
not in `_SURFACE_TIER` resolves to `EXTERNAL` and gets prompt-fenced as untrusted data. A
plausible-looking `claude_code` surface would therefore have quietly demoted everything this
integration captures. We reuse the existing rows instead, which already carry the right
semantics — `cli` for the developer typing, `tool_exhaust` for deterministic observation of
our own work, `assistant_message` for an agent's own conclusions. `tests/unit/test_claude_code_hook.py` asserts both tiers against
`classify_surface` directly; that is the regression that matters.

### Session-start recall

`SessionStart` builds a context fingerprint from `cwd` — project name (directory basename)
and git branch (read straight out of `.git/HEAD`, falling back to a 0.5 s `git` call only
for worktrees/submodules) — POSTs it to `/api/v1/search/recall`, and renders the result as
compact markdown:

```markdown
## Recalled from Life Graph

**Who you are working with**
- Prefers cheap models (Gemini Flash, DeepSeek).

**Past decisions**
- Chose Apache AGE over Neo4j to stay inside Postgres.

**Open intentions**
- [high] Ship the hooks adapter
```

It is emitted as `additionalContext` inside `hookSpecificOutput`, capped at 5 items per
section and 240 characters per item — this text is charged on every subsequent turn of the
session, so raw JSON would cost several times as many tokens to say the same thing. When
recall returns nothing, the hook emits nothing at all, so a cold Life Graph is invisible.

Recall is **skipped when `source == "compact"`**: that fires when context is being
compacted, not started, and re-injecting would fight the compaction that triggered it.

---

## Sampling policy

Ported verbatim from `life_graph/services/tool_observation.py`, but enforced **client-side**
so a throttled event never makes an HTTP call at all. That matters concretely: the default
plan allows 60 req/min and `event_bus.emit` is awaited in-request, so an unsampled hook on
every tool call would exhaust the quota within seconds of normal agent work.

- `DAILY_CAP = 500`, `LOW_SIGNAL_SAMPLE_RATE = 0.10`.
- **Low-signal** = succeeded *and* not tied to a project. A Claude Code hook has no kernel
  project id, so all successful tool calls are low-signal — they are exactly what the cap
  throttles.
- **High-signal** (failures; `Stop`/`SubagentStop` conclusions) always sends and never
  consumes the budget.
- Below the cap everything sends; above it, low-signal events send at 10%.

A hook is a fresh process per event and several run in parallel, so the counter lives in
`<state>/daily_count.json` and is read-modify-written under an advisory file lock. It is
scoped to the UTC day and resets on rollover. If the counter file is unwritable the policy
fails **open** (sends) — a broken counter must not become a silent capture outage.

`tests/unit/test_claude_code_hook.py` asserts the constants and `is_low_signal` against the
backend service directly, so the two cannot drift.

---

## Privacy posture

**What leaves the machine** — only the rows in the table above, addressed to
`LIFE_GRAPH_API_URL` (default `http://localhost:8080`, i.e. nothing leaves the machine at
all in the default self-hosted setup). Each payload carries `surface`, `content`,
`modality: "text"`, and a `properties` bag with `session_id`, `cwd`, project name,
`hook_event`, and the optional `prompt_id` / `permission_mode` / `agent_id` / `agent_type`.

**What does not leave** — file contents, tool *results*, the transcript, environment
variables. Tool arguments leave only as a redacted 200-character summary
(`life_graph.core.redaction.summarize_args`), never verbatim.

**Redaction** — every payload passes through `life_graph.core.redaction.redact_secrets`,
applied to the content *and* recursively to every string in `properties`. It catches
`api_key`/`secret`/`token`/`password`-shaped key–value pairs, `Authorization:` headers and
bearer tokens, and the literal shapes of AWS (`AKIA…`), OpenAI (`sk-…`), GitHub (`ghp_…`),
Slack (`xox…`) and JWT credentials. It is best-effort pattern matching, tuned to avoid
storing credentials — not a guarantee against every exfiltration shape.

**Truncation** — content is clipped to 8000 characters with an explicit `… [+N chars]`
marker.

**Local state** — `~/.life-graph/claude-code/` (or `${CLAUDE_PLUGIN_DATA}/life-graph/`):
`spool.db` (undelivered captures), `daily_count.json` (the sampler), and `hook.log` only
when debugging is on.

---

## Failure posture

A dead or slow Life Graph must never break Claude Code. Concretely:

- Every path is wrapped; the process **always exits 0**. Exit 2 would *block* the
  developer's action and is never used anywhere in this code.
- Hard timeouts: **2 s** on captures, **5 s** on the session-start recall, 0.5 s on the git
  branch lookup, 3 s total on the `SessionEnd` spool flush.
- Nothing is written to stdout except deliberate hook JSON — stray output corrupts the
  contract. Debug output goes to a file, never stdout.
- `UserPromptSubmit` never sets `updatedPrompt`. Rewriting the developer's prompt is not
  this integration's business.
- Delivery triage reuses the desktop agent's `SendStatus`: 2xx sent, 5xx/network transient →
  spooled to SQLite and retried at `SessionEnd`, 401/403 and other 4xx dropped (a bad key or
  a rejected payload must not retry forever).

## Turning it off

```bash
life-graph hooks uninstall              # remove the entries entirely
export LIFE_GRAPH_HOOK_DISABLED=1       # keep them wired, make every event a no-op
```

## Configuration

All plain environment variables — the hook is a short-lived subprocess and deliberately does
not load `life_graph.config`.

| Variable | Default | Meaning |
|---|---|---|
| `LIFE_GRAPH_API_URL` | `http://localhost:8080` | Backend base URL |
| `LIFE_GRAPH_TENANT_ID` | `personal` | Sent as `X-Tenant-ID` (required by `TenantMiddleware`) |
| `LIFE_GRAPH_API_KEY` | — | Sent as `Authorization: Bearer …` when set |
| `LIFE_GRAPH_HOOK_DISABLED` | — | `1` makes every event a no-op |
| `LIFE_GRAPH_HOOK_DEBUG` | — | `1` appends JSONL to `<state>/hook.log` |
| `LIFE_GRAPH_HOOK_STATE_DIR` | `~/.life-graph/claude-code` | Spool + counter + log location |
| `LIFE_GRAPH_HOOK_CAPTURE_TIMEOUT` | `2.0` | Seconds |
| `LIFE_GRAPH_HOOK_RECALL_TIMEOUT` | `5.0` | Seconds |
| `LIFE_GRAPH_HOOK_DAILY_CAP` | `500` | Low-signal captures per UTC day |
| `LIFE_GRAPH_HOOK_SAMPLE_RATE` | `0.10` | Low-signal rate above the cap |
| `LIFE_GRAPH_HOOK_MAX_CONTENT` | `8000` | Content character cap |

---

## Verified hook contract

The published summary of the hook I/O contract had several wrong field names, so the schema
below was read out of the **zod input schemas embedded in the Claude Code 2.1.241
executable** (`~/.local/share/claude/versions/2.1.241`) rather than from prose. Confirmed
absent from the binary entirely: `session_start_mode`, `session_end_mode`, `compaction_mode`,
`tool_output`.

Hook JSON arrives on **stdin**. Common fields on every event:

```
session_id, transcript_path, cwd,
prompt_id?, permission_mode?, agent_id?, agent_type?, effort?, hook_event_name
```

`prompt_id` is a *common* field (a UUID correlating a prompt with every event until the next
one), not a `UserPromptSubmit`-specific one. `agent_id` is present only inside a subagent.

Per event:

| Event | Extra fields | Correction |
|---|---|---|
| `SessionStart` | `source` (`startup\|resume\|clear\|compact\|fork`), `agent_type?`, `model?`, `session_title?` | not `session_start_mode` |
| `SessionEnd` | `reason` (`clear\|resume\|logout\|prompt_input_exit\|other`) | not `session_end_mode` |
| `UserPromptSubmit` | `prompt`, `source?`, `session_title?` | **not `user_prompt`** |
| `PreToolUse` | `tool_name`, `tool_input`, `tool_use_id` | — |
| `PostToolUse` | `tool_name`, `tool_input`, `tool_response`, `tool_use_id`, `duration_ms?` | **not `tool_result`**; `duration_ms` is real |
| `PostToolUseFailure` | `tool_name`, `tool_input`, `tool_use_id`, `error`, `is_interrupt?`, `duration_ms?` | a **separate event** — `PostToolUse` does not fire on failure |
| `Stop` | `stop_hook_active`, `last_assistant_message?`, `background_tasks?`, `session_crons?` | `last_assistant_message` confirmed real |
| `SubagentStop` | `stop_hook_active`, `agent_id`, `agent_transcript_path`, `agent_type`, `last_assistant_message?` | — |
| `PreCompact` | `trigger` (`manual\|auto`), `custom_instructions` | not `compaction_mode` |

`PostToolUseFailure` is the reason this adapter wires an event the original brief did not
list: without it, tool errors — the single highest-signal observation available — would
never be captured at all, and `is_low_signal` would classify literally everything as noise.

Output on **stdout**, exit 0:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "…"
  },
  "systemMessage": "…"
}
```

`additionalContext` nests **inside** `hookSpecificOutput`; `systemMessage` is **top-level**.
Exit 2 blocks the action (never used here); any other nonzero is a non-blocking error.
Hooks matching the same event run in parallel.

Settings entry shape: `hooks.<Event>` is an array of `{ matcher?, hooks: [{ type, command,
timeout?, statusMessage? }] }`. An absent `matcher` means "all", and `UserPromptSubmit` and
`Stop` do not support one at all — so this integration omits `matcher` everywhere.
