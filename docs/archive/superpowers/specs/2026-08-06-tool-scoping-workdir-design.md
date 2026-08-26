# Tool-Scoping & Real-Workdir Fixes for Agent-Task Dispatch — Design

**Status:** Approved design, ready for implementation plan.
**Date:** 2026-08-06
**Builds on:** [[autonomous-action-roles-b2-feature]] — merged to local master @ `5b9ca53`. That branch's final review found `LocalDriver` now correctly scopes tools to a persona's `allowed_tools`, but two things surfaced as a result: persona `allowed_tools` don't match any registered tool name (so scoping makes cody's runs *safe but functionally inert*), and the dispatcher's scratch workdir has no association with a real repo (so `build_ok`/`lint_clean` verify nothing).

## Goal

Close three residual gaps from the B2 final review so an approved cody `agent_task` can
actually do useful work, in an isolated workspace, verified against the files it really
changed — without weakening any safety invariant B2 established (always-queue, tool
scoping on both dispatch and bounce-retry).

## Key findings (verified against master @ `5b9ca53`)

- **Persona `allowed_tools` reference names that don't exist.** The tool registry
  (`life_graph/tools/*.py`) registers exactly: `run_command`, `git_status`, `git_log`,
  `git_diff`, `git_branch`, `inspect_system`, `web_search`, `browse_web`, `browser_agent`,
  `calculator`, `get_current_datetime`, `delegate_to_persona`. `kernel/personas.py`'s
  12 built-in personas reference `"terminal"`, `"git"`, `"file_read"`, `"file_write"`,
  `"docker"`, `"ssh"`, `"memory_search"` — none of which are registered names. This is
  pre-existing and system-wide (`kernel/process_manager.py`'s identical scoping filter
  already applies it in interactive chat), not introduced by B2.
- **Every existing tool takes an LLM-supplied absolute path, unsandboxed.**
  `run_command(command, working_directory=None)` defaults to the user's home directory;
  `git_status(repo_path)` etc. require an absolute path with no default. Nothing threads
  a "current project" concept into tool execution today — the model has to already know
  (from its system prompt / context) where to point these paths.
- **`ContextPacket.project_context`** (`drivers/context.py::_load_project`) is populated
  from a real `Project` DB row (`name`, `path`, `description`, `language`, `framework`,
  ...) when `project_id` resolves to one — but the row's `path` is only ever surfaced to
  `LocalDriver` as raw JSON dumped into the system prompt; nothing tells the model "this is
  your working directory," and nothing propagates it into `run_command`'s
  `working_directory` default or `git_status`'s `repo_path`.
- **`ClaudeCodeDriver._resolve_workdir`** already supports git-worktree isolation
  (`project_context.get("isolation")` → `git worktree add --detach`) — this exists today,
  is just never turned on by any caller (`_load_project` never sets `"isolation"`).
- **`_verify_build_ok`/`_verify_lint_clean`** (`services/verifiers.py`) operate on the
  *entire* `workdir` tree (`workdir.rglob("*.py")`, `ruff check <workdir>`) — not scoped to
  changed files. Pointing `workdir` at a real repo without diff-scoping would make
  `lint_clean` fail on every run against this repo's ~834 pre-existing ruff errors,
  regardless of what cody actually changed. `_verify_diff_within_scope` already has the
  needed pattern (`git diff --name-only HEAD`, run inside `workdir`) to build a diff-scoped
  variant from.
- **`AMBIENT_PROJECT_ID = "ambient"`** (`autonomy/safety/ambient_rules.py`,
  `services/action_proposal_bridge.py`) is used for `AutoAction.project_id` and
  `AutonomyLevelService`'s trust-scoping key — a free-form string, not a DB foreign key.
  It is **not** the same value as the `project_id` UUID `dispatch_task` needs for workdir
  resolution. These two can and should stay decoupled: `AutoAction.project_id` keeps
  meaning "ambient" for trust/WIP-limit purposes; a *separate* lookup resolves the real
  repo `Project` row specifically for the dispatch-time workdir.
- **`ClaudeCodeDriver` invokes the `claude` CLI as a subprocess** — it does not use
  `life_graph`'s Python tool registry at all. A persona's `allowed_tools` (registry names)
  therefore cannot filter what the CLI itself can do; the CLI has its own tool vocabulary
  and its own `--allowedTools`/`--disallowedTools` flags for headless-mode restriction.

## Decisions (locked with the developer)

1. **Build `file_read`/`file_write` now; leave `memory_search` for later.** `memory_search`
   wires into the hybrid vector/graph search subsystem — separate, larger effort.
2. **`file_read`/`file_write` follow the existing trust model exactly**: LLM-supplied
   absolute path, no sandboxing. Consistent with `run_command`/`git_*` (which already grant
   full host access to any persona that has them) — a differently-scoped file tool would be
   a new, inconsistent trust model, not a real safety improvement.
3. **Repo association via a named `Project` lookup**, not a new settings var. A well-known
   constant name, `AMBIENT_REPO_PROJECT_NAME = "life-graph"`, is looked up per-tenant by
   `_run_action`'s agent_task branch (the caller, before it invokes `dispatch_task` — the
   lookup does not live inside `dispatch_task` itself) using the existing `Project`
   table/registration flow. Unregistered = today's safe-inert behavior (no path, scratch
   temp dir) — nothing breaks for a tenant that hasn't set this up.
4. **Isolated git worktree, not the live checkout.** Cody's `agent_task` dispatches get
   their own throwaway worktree off the real repo (mirrors `ClaudeCodeDriver`'s existing,
   currently-dormant isolation logic). Verified against real code; can't corrupt the
   developer's own working directory mid-edit.
5. **New diff-scoped verifier names (`build_ok_diff`, `lint_clean_diff`)**, not a change to
   the existing `build_ok`/`lint_clean` semantics — `uzhavu-ops`/`dependency-updater`'s
   existing verify chains are untouched.
6. **`ClaudeCodeDriver` gets real tool-scoping via the CLI's own flags**, translated from a
   persona's `allowed_tools` through a small mapping table — not merely documented as
   unscoped. Only matters today for `uzhavu-ops`/`dependency-updater` (the only personas
   that pin `driver: claude_code`); cody rides `LocalDriver`.

## Architecture

```
Persona tool names (personas.py)         Tool registry (life_graph/tools/*.py)
  "run_command"        ─────────────────▶  run_command            (existing)
  "git_status/.../branch" ───────────────▶  git_status, git_log, ...  (existing)
  "file_read"           ─────────────────▶  file_read               (NEW: tools/filesystem.py)
  "file_write"          ─────────────────▶  file_write               (NEW: tools/filesystem.py)
  "docker", "ssh"        (dropped — redundant with run_command; not built)
  "memory_search"         (left aspirational, deferred)

_run_action (autonomy/pipeline/service.py), agent_task branch:
  AutoAction.project_id stays "ambient" — trust/WIP scoping unchanged
  NEW, done here (not inside dispatch_task): look up
    Project(name="life-graph", tenant_id=...) — if found:
        real_project_uuid → dispatch_task(..., project_id=real_project_uuid, persona_name="cody", ...)
        → build_packet(project_id=real_project_uuid, ...)
        → packet.project_context = {name, path, ...}  (real repo path)
        → resolve_workdir(packet, scratch, isolation=True)   [shared helper,
             extracted from ClaudeCodeDriver._resolve_workdir]
        → git worktree add --detach <scratch>/wt_xxx  (off the real repo)
        → SAME resolved workdir passed to:
              driver.dispatch(packet, workdir, ...)     — LocalDriver tells the LLM
                                                           "your working directory is X"
              verifier_chain.run_chain(["build_ok_diff","lint_clean_diff"], workdir, ctx)
        → worktree removed after the run (mirrors ClaudeCodeDriver's existing cleanup)
     if NOT found: today's behavior — scratch temp dir, no isolation, verifiers vacuous
        (unchanged fallback, nothing regresses for an unconfigured tenant)

ClaudeCodeDriver (uzhavu-ops, dependency-updater only):
  packet.allowed_tools → translate to CLI's own tool names → --allowedTools flag
  packet.persona_system_prompt → prepended to the CLI prompt
```

## Components

- **`life_graph/tools/filesystem.py`** (new) — `file_read`, `file_write`, registered via
  `@tool(...)`, matching the existing module style (`terminal.py`, `git.py`): docstring,
  safety constants (max read size), structured JSON-ish return, logged.
- **`life_graph/kernel/personas.py`** — reconcile every `allowed_tools` list against real
  registered names (see mapping above); no other persona fields change.
- **`life_graph/kernel/ambient.py`** — `AMBIENT_ACTION_READONLY_TOOLS` comment updated now
  that `file_read` is real; new `AMBIENT_REPO_PROJECT_NAME` constant.
- **`life_graph/drivers/context.py` / `drivers/base.py`** — extract a shared
  `resolve_workdir(packet, scratch, isolation=False) -> tuple[Path, Path | None]` helper
  (the logic already in `ClaudeCodeDriver._resolve_workdir`, made reusable); `ContextPacket`
  gains nothing new here (path/isolation already flow through `project_context`).
- **`life_graph/drivers/dispatcher.py`** — `dispatch_task`'s agent_task-aware caller (the
  autonomy pipeline) resolves the real `Project` by name, passes its UUID for packet-building
  only; `dispatch_task` itself calls the shared `resolve_workdir` once and passes the same
  `workdir` to both `driver.dispatch()` and `verifier_chain.run_chain()`; worktree cleanup
  in a `finally`.
- **`life_graph/drivers/local.py`** — surfaces the resolved workdir explicitly in the system
  prompt (not just buried in the `project_context` JSON dump).
- **`life_graph/drivers/claude_code.py`** — new mapping table (registry tool name →
  Claude Code CLI tool name), builds `--allowedTools`/`--disallowedTools` from
  `packet.allowed_tools`; uses `packet.persona_system_prompt` in the rendered prompt.
- **`life_graph/services/verifiers.py`** — `_verify_build_ok_diff`, `_verify_lint_clean_diff`
  added alongside (not replacing) the existing whole-tree verifiers, reusing
  `_verify_diff_within_scope`'s `git diff --name-only HEAD` pattern to scope the file list.
- **`life_graph/autonomy/pipeline/service.py`** — `_run_action`'s agent_task branch: resolve
  the real project (if any), pass its UUID to `dispatch_task` for packet/workdir purposes
  (never overwriting `AutoAction.project_id`), pass `verify_chain=["build_ok_diff",
  "lint_clean_diff"]` instead of the whole-tree names.

## Error handling / fallback behavior

- No `Project` row named `AMBIENT_REPO_PROJECT_NAME` for the tenant → today's exact
  behavior (scratch temp dir, no isolation, vacuous verifiers) — a deliberate, safe default
  for any tenant that hasn't registered a repo.
- Worktree creation fails (e.g. `git worktree add` errors) → fall back to the scratch
  temp dir, same as `ClaudeCodeDriver._resolve_workdir` already does today, logged as a
  warning — never raises out of `dispatch_task`.
- `claude` CLI's actual flag names/semantics for tool restriction should be confirmed
  against the installed CLI version during implementation (documented assumption, not a
  runtime dependency verified by this design).

## Testing

- Unit tests for `file_read`/`file_write` (success, missing file, oversized read).
- Unit tests for the persona `allowed_tools` reconciliation (each persona's resolved tool
  set matches the intended registry names — regression guard against a future typo
  reintroducing this exact bug class).
- Unit tests for the shared `resolve_workdir` helper (isolation on/off, project path
  present/absent, worktree-creation failure fallback).
- Unit tests for `build_ok_diff`/`lint_clean_diff` (only checks files in `git diff
  --name-only HEAD`, ignores whole-tree pre-existing issues outside that diff).
- Integration-style test extending the existing agent_task E2E: with a real `Project` row
  registered, a mocked worktree/dispatch confirms the workdir threaded through to both the
  driver call and the verifier chain is the same path.

## Out of scope (explicitly deferred)

- Building `memory_search`.
- `docker`/`ssh` tools.
- Governor budget realism for `LocalDriver.cost_per_task()` (still hardcoded `0.0`).
- Any change to `uzhavu-ops`/`dependency-updater`'s existing verify chains or behavior
  beyond the `ClaudeCodeDriver` tool-scoping fix (item 6) that also benefits them.
