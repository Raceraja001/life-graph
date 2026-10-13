# Agent Observability — Watch, Study and Run the Agents — Feature Spec

> **Status: In progress (2026-10-13).** Builds on step recording (`c410413`:
> `drivers/steps.py`, `services/trajectories.py`, table `agent_run_steps`).
> Backend in this repo; pages in the separate `life-graph-ui` app (Luminaux
> template, `src/pages/lg/`).

## Why

Two goals, stated 2026-10-13:

1. **Study**: understand how agents think, work and fail, from full recordings
   of every run.
2. **Run the system unattended**: see what agents did, what they spent, and
   what is broken, without reading logs or querying the database.

On 2026-10-13 each of the following cost real time to find by hand:
- a plan-only prompt that told the agent to implement;
- a spec cut to 4,000 characters;
- a preview server claiming another worktree's tasks;
- a stale backend process;
- an exhausted budget;
- a local model sending empty tool arguments.

Every page here would have shown its share of those problems at a glance.

## Pages

| # | Page (route) | Shows | Backend |
|---|---|---|---|
| 1 | **Run Replay** (`/dev-tasks/:id`) | The run as a timeline: text, thinking, each tool call with its input, each result (errors red), attempts side by side, verifier verdicts, approvals with reviewer notes, PR, merge, cost. | `GET /kernel/drivers/tasks/{id}` (+ approval notes and verification), `GET …/steps` |
| 2 | **Plan Board** (`/plans`, `/plans/:id`) | Plans list; one plan: spec, acceptance criteria with conformance status, its tasks as a pipeline (queued → running → PR → merged) and why the gate holds each one. | `GET /kernel/drivers/plans`, `GET /kernel/drivers/plans/{id}` |
| 3 | **Agent Scorecards** (`/agents/scorecards`) | Per driver and model: runs, success, bounce rate, merged, cost per merged PR, trust against the auto-merge bar, top failure causes. | `GET /kernel/drivers/scorecards?days=` |
| 4 | **Failure Explorer** (`/agents/failures`) | Failed runs grouped by cause (deterministic rules over error, verification and steps), each linking to its replay. | `GET /kernel/drivers/failures?days=` |
| 5 | **Spend & Budget** (`/budget`) | Month-to-date against the cap, by category, top-spending tasks, projection to month end, soft/hard thresholds. | `GET /kernel/observability/budget` |
| 6 | **System Health** (`/system`) | Startup subsystems, dev-task runner (lock holder pid, queue depth, running), drivers available, Ollama models loaded and their VRAM use. | `GET /kernel/observability/system` |
| 7 | **Agents Console** (`/agents`) | Each persona: model, tools, and **tools it lists that are not registered** (red); "Test" runs a probe through chat and shows its tool calls. | `GET /kernel/observability/agents`; probe uses `POST /kernel/chat/stream` |
| 8 | **Decision Gaps** (`/decisions/gaps`) | Topics discussed often with no recorded decision; record one in place. | `GET /kernel/observability/decision-gaps`; record via `POST /memories/` |

Navigation (life-graph-ui `src/data/menu.ts`):
- **Agents** gets Plans, Scorecards, Failures and Agents console.
- **System** gets Budget and System health.
- **Judgment** gets Decision gaps.
- Dev task cards link to their replay.

## Design

### Failure causes (`services/failure_causes.py`)

These are deterministic rules, with no LLM (invariant 1). Each failed task
gets exactly one primary cause, checked in this order:

| Cause key | Rule |
|---|---|
| `budget_exhausted` | error starts with `budget:` |
| `sandbox_unavailable` | error contains `sandbox unavailable` |
| `interrupted` | error starts with `Interrupted` |
| `timeout` | error contains `timed out` |
| `plan_not_run` | error starts with `Not run:` (an earlier plan task stopped) |
| `plan_no_spec` | error mentions `no '## Spec'` |
| `plan_wrote_files` | a `no_diff_in_plan` verdict failed |
| `model_unavailable` | an `error` step or the error says models are unavailable |
| `empty_tool_args` | a `tool_call` step with `{}`/`null` input followed by a failing result |
| `tool_error` | any failing `tool_result` step |
| `verification_failed` | a failed verifier verdict (sub-cause = the verifier names) |
| `cancelled` | status `cancelled` |
| `other` | none of the above |

A cause is a string key with a label, not an enum (invariant 2).

### Scorecards

The scorecard groups dev tasks from the last `days` (default 30) by
`(driver, model)`:
- `driver` and `model` come from the task's result metadata, falling back
  to its persona;
- `runs` and `succeeded` count dev tasks that reached `completed`;
- `bounced` counts runs whose verification has 2 attempts;
- `merged` uses `stage == merged`;
- `cost_usd` is summed, and `cost_per_merged` is that sum divided by
  `merged`;
- `causes` holds the top three failure causes.

Trust is shown next to the auto-merge bar (`AUTO_PR_MERGE_RATE`) using the
existing `auto_merge_status`.

### Plans

- **Plan:** a dev task with `task_type == "plan"`.
- **Children:** the tasks whose `properties.plan_group_id` matches the group
  that the plan's approved `driver_plan` approval wrote into its payload. A
  re-filed approval counts too: its `refiled_from` links back.
- **Gate state:** each child's gate state (`ready` / `wait` / `blocked`)
  comes from the existing `_plan_gate`.
- **Criteria:** from `acceptance.parse_criteria(spec)`, joined with the
  stored conformance report.

### System

The system endpoint reports:
- **Subsystems:** the startup report, which `/health` already builds;
- **Runner:** the advisory-lock holder pid from `pg_locks` (key `RUNNER_LOCK_KEY`), plus whether this process holds it;
- **Queue:** `queued` and `running` dev-task counts;
- **Drivers:** each registered driver and whether it is `available()`;
- **Ollama:** `GET /api/ps` on the configured Ollama base (loaded models with `size_vram`) and `/api/tags` (installed); when Ollama is unreachable, the endpoint returns an `error` field instead of failing.

### Agents console

The tool check runs per persona:
- **`allowed_tools`:** each name is marked registered or not against
  `registry.tool_names` (connector tools included, the same way startup
  registers them);
- **Model:** `model` is listed, and claude-cli personas get the note that
  they run without tools.

### Decision gaps

1. **Count entities:** count active memories per entity (`properties.entities`),
   case-folded, over the last 90 days.
2. **Find gaps:** a gap is an entity mentioned in at least 4 memories where
   none of those memories has `fact_type == "decision"`.
3. **Rank:** gaps are ranked by mention count, and each carries its most
   recent three memories for context.

This is deterministic SQL with no LLM. Recording a decision posts a normal
memory (tag `decision`), which goes through the usual dedup and review.

### Replay additions to existing endpoints

- `GET /kernel/drivers/tasks/{id}` approvals gain `note` (`resolution_note`),
  `resolved_at` and `resolved_by`.
- `GET /kernel/drivers/tasks/{id}` also gains its `verification` attempts
  (the summary `get_dev_task` already computes).

## Non-goals (this round)

- **Live streaming while a run is in progress.** Steps arrive when each
  attempt ends; the replay polls while a task is running.
- **Editing the budget cap from the UI.** The cap is an env setting; the page
  says how to change it.
- **Cross-tenant views.**

## Tasks

1. **Backend: replay additions.** Approval notes and verification on task
   detail.
2. **Backend: `failure_causes.py`.** The classifier, with unit tests.
3. **Backend: plans, scorecards and failures endpoints.** Tests included.
4. **Backend: `api/observability.py`.** Budget, system, agents and
   decision-gaps endpoints, with tests.
5. **UI: API bindings and types.** In `lifegraph.ts`.
6. **UI: pages 1–8.** Plus navigation and the dev-task card link.
7. **UI: Playwright smoke tests.** One per new page.
8. **`gen_state.py --html`.** Then a final pass in a real browser, on desktop
   and phone.
