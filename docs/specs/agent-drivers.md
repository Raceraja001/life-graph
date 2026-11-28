# Agent Drivers — Rent the Muscle, Own the Nervous System — Feature Spec

> **Status: Built.** Implemented in `life_graph/drivers/dispatcher.py`. The [2026-11-27 autonomy-policy amendment](#amendment-2026-11-27--autonomy-policy-owner-decision-d2) is built too (migration `064_autonomy_policies`). [Phase 4b](#phase-4b-2026-11-27-dependencies-parallel-plans-pr-feedback-loop-arena) (dependencies, parallel plans, PR feedback loop, arena) is built too (migration `066_dev_task_groups_pr_watches`), off by default. This document records the design as it was specified; for what the code actually does now, see [docs/STATE.md](../STATE.md) — it is generated from the code.

> _Historical banner (July 2026); the line above and docs/STATE.md are current._ ✅ **STATUS: MOSTLY IMPLEMENTED (July 2026).** Migration `021_agent_drivers.py`; package `life_graph/drivers/` (base protocol, registry, local driver, dispatcher with WIP limits + bounce-once, context packets); `services/verifiers.py`, `services/results_loop.py`; API `api/drivers.py`. **Still pending**: second-opinion reviewer pass; seed personas (`uzhavu-ops`, `dependency-updater`); watcher-finding → task origination. See [CHARTER.md](../../CHARTER.md#current-frontier) for what is genuinely still open. **Do not rebuild what exists.**

> **Purpose**: Turn Life Graph from "one orchestrator loop with 10 tools" into an agent workforce — by wrapping best-in-class external agents (Claude Code headless, Codex CLI, browser-use) as interchangeable **drivers**, arming every dispatch with a **context packet** no external agent has, gating every result through a **verifier chain**, and feeding every outcome back into memory, trust, and calibration. Life Graph never competes with frontier executors; it employs them.
>
> **Strategy ref**: `docs/design/07_strategic_direction_2026-07.md` (D2). Rule of `.comms/context/strategic-decision.md` applies: wrap existing tools, don't rebuild them.
>
> **Existing code leveraged**: `kernel/process_manager.py` (task lifecycle), `kernel/personas.py` + `agent_personas` table (custom agents as configuration), `kernel/chief_router.py` (routing), `kernel/scheduler.py` (standing pipelines), `autonomy/` (safety classifier, trust calculator, approval queue, audit — Era 8, built), `agents/orchestrator.py` (becomes the `local` driver), `services/context.py` + `api/agent.py` (context building seed), `kernel/project_registry.py` (project map), `services/preference_store.py` (era 4), `core/metrics.py` + `tenant_usage` (cost tracking).
>
> **Depends on**: `capture-spine.md` Phase 1 (results report through the spine). Feeds `judgment-engine.md` (every task is an implicit prediction: estimated vs actual).
>
> **Multi-tenant**: All data scoped by `tenant_id`.

---

## Requirements

### Story 1: AgentDriver Protocol & Registry

As the **kernel**, I want a uniform driver interface so that any external or local agent can execute a task interchangeably, selected by capability, cost, and trust — the way the tool registry abstracts tools, one level up.

#### Acceptance Criteria

- GIVEN a driver implements the protocol WHEN it registers THEN it declares: `name`, `capabilities` (e.g. `["code", "test", "review"]`), `cost_class` (`free|cheap|frontier`), `supports_workdir` (can it operate on a project checkout), `max_concurrency`
- GIVEN a task with `task_type="code_fix"` and a target project WHEN the dispatcher selects a driver THEN selection order is: persona's pinned driver if set → cheapest driver whose capabilities cover the task type and whose recent success rate for this task_type ≥ 0.6 → fallback chain
- GIVEN the `claude_code` driver executes WHEN dispatch runs THEN it invokes Claude Code headless (`claude -p "<packet>" --output-format json`) with `cwd` set to the project path (or an isolated worktree when `isolation=true`), captures the JSON result, and normalizes it to a `DriverResult{artifacts[], summary, raw_cost, duration_ms, exit_status}`
- GIVEN the `local` driver executes WHEN dispatch runs THEN the existing `AgentOrchestrator` tool loop handles it (cheap/small/private tasks; LM Studio for anything that must not leave the machine)
- GIVEN a driver crashes or times out WHEN the failure is recorded THEN the task is retried per existing ProcessManager retry policy on the **next** driver in the fallback chain, and the failure counts against the failed driver's success rate
- GIVEN I `GET /api/v1/kernel/drivers` THEN I see registered drivers with capabilities, cost class, rolling 30-day success rate and mean cost per task_type
- GIVEN a driver binary is missing (e.g. Claude Code not installed on this host) WHEN registry initialization runs THEN the driver registers as `unavailable` with a reason, and selection skips it (graceful degradation, same pattern as the era-4 advisor's missing API keys)

---

### Story 2: Context Packets — the unfair advantage

As a **user**, I want every dispatched task to carry a context packet assembled from my substrate — relevant memories, preferences, procedures, project map, and judgment profile — so that a rented frontier agent starts every task knowing what only my system knows.

#### Acceptance Criteria

- GIVEN a task is dispatched WHEN the packet builder runs THEN the packet contains, in order: (1) task spec + acceptance criteria, (2) project context from the project registry (language, framework, conventions, key paths), (3) top-k relevant memories (semantic search on task description, k≤10), (4) applicable preferences (era-4 store, filtered by task domain), (5) applicable procedures (from the `procedures` table) if any match the task type, (6) judgment profile facts when available ("estimates in this domain run 2.8×; pad accordingly"), (7) output contract (artifact format + verifier expectations)
- GIVEN the packet is assembled WHEN size is computed THEN it fits a configurable token budget (default 6k tokens): sections are truncated in reverse priority order (memories trimmed before acceptance criteria, never the reverse)
- GIVEN the packet is sent WHEN the task record is stored THEN the packet snapshot is persisted in `agent_tasks.input.context_packet` — reproducibility and Time-Machine forensics ("what did the agent know when it did this")
- GIVEN the existing `/api/v1/agent/context` endpoint WHEN this ships THEN packet building extends that service (`services/context.py`) rather than duplicating it; the endpoint gains `?task_type=&project_id=` parameters
- GIVEN a task is privacy-flagged (`properties.private=true`) WHEN the packet is built THEN memory/preference sections are included only for `local` driver dispatch and stripped for external drivers
- *Amended 2026-11-28 (cross-project leak, dev task `c545707e`):* GIVEN a task is dispatched for project P WHEN the memories section is built THEN it holds only memories attributed to P — by `properties.project_id`, `project`/`project_name`, a path in `cwd`/`repo_path`/`project_path` under P's registry path, `repo` ending in P's name, or a `project:<name>` (or legacy bare-name skill) tag — and none whose attribution names any other project. Memories with no project attribution are left out of a project's packet; a packet with no project gets only unattributed memories. A project missing from the tenant's registry gets no memories. Fail-closed, no setting. Enforced in `drivers/context.py` (`memory_in_scope`, with a matching SQL pre-filter so the top-k is drawn from in-scope rows); other memory consumers (recall, search, brief, Jarvis) are unchanged. Before this, `_load_memories` took the tenant's top-10 memories by importance with no project filter, so a race-app task was handed apptx-v2's git-conflict items in its untrusted-data block. Tests: `tests/unit/test_packet_project_scope.py`.
- *Amended 2026-11-28 (personal data, [CHARTER invariant 7](../../CHARTER.md#7-personal-data-stays-on-the-machine)):* GIVEN a task is dispatched to a driver whose model runs in the cloud (`claude_code`, `codex`, `gemini`, `cloud`) WHEN its prompt is built THEN it holds no memories, preferences or procedures, whatever `properties.private` says — only the persona's system prompt, the task, the project metadata (minus `path`/`isolation`) and the code in the worktree leave the machine. `claude_code` (`ClaudeCodeDriver._format_prompt`) now follows the rule `codex`/`gemini` already had (`drivers/cli_driver.py::build_prompt`); the `cloud` driver empties the three packet fields before its loop; `opencode` never rendered them. `local` follows the same rule by its resolved model: when `persona_model` (or the default `agent_llm_model`) is not local by `connectors.locality.run_is_local` — the check that already cuts personal tools for a cloud run, failover chain included — preferences and procedures are left out; on a local model it still receives both (it never renders memories). Before this, `local` added them whatever the model. No opt-in setting. Before this, a non-private `claude_code` packet sent all three to Anthropic. The packet builder still assembles them (the dispatch record and `local` use them). Tests: `tests/unit/test_claude_code_prompt_privacy.py`.

---

### Story 3: Verifier Chain — machine-checked definition of done

As a **user**, I want every task type to have a machine-checkable definition of done, run automatically before anything reaches me, so that the swarm produces verified work instead of homework.

#### Acceptance Criteria

- GIVEN a task type is registered WHEN its verifier chain is defined THEN it is data, not code: an ordered list like `["tests_pass", "lint_clean", "diff_within_scope"]` stored on the persona/task-type config
- GIVEN built-in verifiers ship WHEN Phase 3 lands THEN at minimum: `tests_pass` (pytest/vitest in project), `lint_clean` (ruff/eslint), `build_ok`, `diff_within_scope` (changed files ⊆ declared scope), `citations_present` (review findings cite file:line), `style_conforms` (content: rules distilled from correction history), `claims_evidenced` (content: factual claims checked against era-4 evidence store, flag-not-block)
- GIVEN a verifier chain runs WHEN any verifier fails THEN the result is bounced back to the **same driver once** with the failure report appended to the packet ("fix these specific failures"); a second failure marks the task `needs_human` and enters the approval queue with the failure report attached
- GIVEN all verifiers pass WHEN the autonomy gate runs THEN the existing Era-8 machinery decides the landing: trust level for this (persona, task_type) determines auto-land vs approval queue — this spec adds **no new approval UI**, it reuses `autonomy/approvals`
- GIVEN a second-opinion review is configured (`reviewer_model != generator_model`) WHEN verification runs THEN a cheap dissenting model reviews the artifact before the human gate (same forced-contrarian pattern as the judgment engine's advisor)
- GIVEN verification completes WHEN results are recorded THEN a `verification_runs` row stores per-verifier pass/fail + evidence, and the whole run reports through the capture spine as an observation

---

### Story 4: Results Loop — every task teaches the system

As the **system**, I want every completed task to flow back into the substrate — capture spine observations, trust score updates, cost metering, and implicit predictions for calibration — so that the swarm gets cheaper and more trusted the more it runs.

#### Acceptance Criteria

- GIVEN a task completes (any terminal state) WHEN the results processor runs THEN an observation enters the capture spine: `{task_id, task_type, driver, duration_ms, cost, verifier_results, landing}` — this is the Apprentice's and Judgment Engine's raw material
- GIVEN the task carried a time/effort estimate WHEN it resolves THEN an implicit prediction is created and immediately resolved in the judgment engine (`resolution_source="kernel_task"`) — swarm volume feeds calibration with zero manual input
- GIVEN a task lands successfully WHEN trust updates run THEN the existing `autonomy/trust/calculator.py` records the success for (persona, task_type); failures likewise — no new trust logic
- GIVEN costs accrue WHEN a task completes THEN `tenant_usage.llm_cost_usd` and per-driver counters update; `GET /api/v1/kernel/drivers/stats` exposes **verified tasks landed per cost unit per week** — the swarm's single success metric (D2)
- GIVEN the same task_type + project trajectory succeeds 3+ times WHEN consolidation runs THEN the capture spine's existing `PROCEDURE_CANDIDATE` path fires (Apprentice contract; consumption out of scope here)

---

### Story 5: Custom Agents as Configuration

As a **user**, I want to create a new custom agent (Uzhavu ops agent, blog-draft agent, dependency-update agent) in minutes by writing a row, not a codebase — persona + driver + tools + verifier chain + context profile.

#### Acceptance Criteria

- GIVEN the `agent_personas` table (built) WHEN this spec lands THEN it gains columns: `driver` (nullable pin), `verifier_chain` (JSONB), `context_profile` (JSONB: which packet sections + filters), `task_types` (TEXT[])
- GIVEN I `POST /api/v1/kernel/personas` with `{name: "uzhavu-ops", driver: "claude_code", task_types: ["deploy_check", "incident_fix"], tools: [...], verifier_chain: ["build_ok", "health_endpoint_green"], context_profile: {domains: ["uzhavu", "infra"]}}` THEN the agent is fully operational on next dispatch — zero code
- GIVEN ChiefRouter classifies an intent WHEN a persona's `task_types`/`intent_pattern` matches THEN routing to that persona uses its pinned driver and verifier chain automatically
- GIVEN a persona has no pinned driver WHEN dispatch runs THEN Story 1 selection applies (cheapest capable trusted driver)
- GIVEN personas multiply WHEN I `GET /api/v1/kernel/personas?task_type=review` THEN I can list agents by what they do, with their rolling success rates

---

### Story 6: Standing Pipelines — work that originates without the user

As a **user**, I want recurring agent work to originate from schedules and watchers — not from me typing requests — so the swarm runs my operations while I sleep.

#### Acceptance Criteria

- GIVEN the scheduler (built) WHEN I create a schedule with `agent_name="dependency-updater"` and cron `0 21 * * 0` THEN weekly: the dependency watcher's findings become tasks → driver produces upgrade PRs per project → verifiers run project tests → results land in the approval queue (or auto-land at sufficient trust)
- GIVEN a watcher fires an actionable finding (`WATCHER_COMPLETED` with `properties.actionable=true`) WHEN pipeline rules match THEN a task is spawned automatically with the finding embedded in the packet (watcher → work, no human relay)
- GIVEN the three launch pipelines WHEN Phase 5 completes THEN these run standing: (1) **dependency updates** (weekly, per registered project), (2) **code review** (on push observation for registered projects: review agent + `citations_present` verifier), (3) **content pipeline** (weekly: research engine → draft with style preferences → dissent critique → approval queue)
- GIVEN pipelines run unattended WHEN concurrency is evaluated THEN per-project WIP limit (default 2) and per-tenant concurrent-task limit (default 5) are enforced by the dispatcher; excess work queues rather than parallelizing into chaos
- GIVEN a pipeline fails 3 consecutive runs WHEN the scheduler evaluates it THEN the existing auto-disable rule applies and a notification fires (built behavior, inherited)

---

## Design

### Architecture Overview

```mermaid
flowchart TD
    subgraph Origin["Work origination"]
        U[User request via ChiefRouter]
        S[Scheduler cron]
        W[Watcher findings]
    end

    subgraph Dispatch["Dispatch (kernel)"]
        PM[ProcessManager<br/>agent_tasks]
        SEL[Driver selection<br/>capability × cost × trust]
        CP[Context Packet Builder<br/>services/context.py]
    end

    subgraph Drivers["Drivers (rented muscle)"]
        D1[claude_code<br/>headless subprocess]
        D2[codex]
        D3[browser_use]
        D4[local<br/>AgentOrchestrator + LM Studio]
    end

    subgraph Gate["Verification & landing"]
        V[Verifier chain<br/>data-defined per task_type]
        R2[Second-opinion review<br/>dissenting model]
        A8[autonomy/ Era 8<br/>trust → auto-land | approval queue]
    end

    subgraph Learn["Results loop"]
        CS[Capture spine observation]
        J[Judgment: implicit prediction resolved]
        T[Trust calculator update]
        C[Cost metering<br/>verified-tasks-per-₹ metric]
    end

    U & S & W --> PM --> SEL
    CP --> SEL
    SEL --> D1 & D2 & D3 & D4
    D1 & D2 & D3 & D4 --> V --> R2 --> A8
    A8 --> CS & J & T & C
    CS -. PROCEDURE_CANDIDATE .-> Learn
```

Key design decisions:

1. **Drivers are subprocess wrappers, not frameworks.** No CrewAI/LangGraph dependency for execution — the externals *are* the agents. The protocol is ~5 methods; a new driver is an afternoon.
2. **Verifier chains are data.** Adding a task type = registering verifiers + a persona row. Code only for new verifier *kinds*.
3. **No new approval/trust/audit machinery.** Era 8 built it; this spec routes through it. Any temptation to add a second approval path is a bug.
4. **One bounce rule.** A failed verification returns to the driver once with specifics; twice → human. Infinite fix loops burn money silently — hard cap.
   *Amended 2026-11-27 (owner decision D2, see [Amendment: autonomy policy](#amendment-2026-11-27--autonomy-policy-owner-decision-d2)):* the one bounce stays the default. The owner may enable a **bounded** number of extra automatic rounds (verify-fix, review-fix), each budget- and kill-switch-gated and recorded as a verification attempt. Rounds never approve: decision 3's single approval path is unchanged.
5. **Privacy split is structural.** External drivers never receive memory/preference sections on private-flagged tasks; the local driver exists precisely for this. *(2026-11-28: drivers on a cloud model never receive memories, preferences or procedures at all, private or not — see Story 2 and CHARTER invariant 7.)*

### Data Models

```sql
-- Migration 021_agent_drivers.py

ALTER TABLE agent_personas
    ADD COLUMN driver          VARCHAR(32),
    ADD COLUMN verifier_chain  JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN context_profile JSONB NOT NULL DEFAULT '{}',
    ADD COLUMN task_types      TEXT[] NOT NULL DEFAULT '{}';

CREATE TABLE driver_stats (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       VARCHAR(64) NOT NULL,
    driver          VARCHAR(32) NOT NULL,
    task_type       VARCHAR(64) NOT NULL,
    window_start    DATE NOT NULL,
    dispatched      INTEGER NOT NULL DEFAULT 0,
    verified_landed INTEGER NOT NULL DEFAULT 0,
    failed          INTEGER NOT NULL DEFAULT 0,
    total_cost_usd  FLOAT NOT NULL DEFAULT 0,
    total_duration_ms BIGINT NOT NULL DEFAULT 0,
    UNIQUE (tenant_id, driver, task_type, window_start)
);

CREATE TABLE verification_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       VARCHAR(64) NOT NULL,
    task_id         UUID NOT NULL,              -- FK agent_tasks
    attempt         INTEGER NOT NULL DEFAULT 1, -- 1 = first pass, 2 = after bounce
    passed          BOOLEAN NOT NULL,
    results         JSONB NOT NULL,             -- [{"verifier": "tests_pass", "passed": true, "evidence": "..."}]
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_verification_task ON verification_runs (task_id);
```

(`agent_tasks` needs no schema change — packet snapshot and driver name live in its existing `input`/`output` JSONB.)

### API Contracts

```
GET /api/v1/kernel/drivers
→ 200 [ { "name": "claude_code", "capabilities": ["code","test","review"],
          "cost_class": "frontier", "available": true,
          "stats_30d": {"dispatched": 41, "verified_landed": 36, "success_rate": 0.88,
                        "mean_cost_usd": 0.31, "landed_per_usd": 2.8} },
        { "name": "local", "capabilities": ["triage","extract","summarize"],
          "cost_class": "free", "available": true, ... } ]

GET /api/v1/kernel/drivers/stats?window=30d
→ 200 { "verified_landed_per_usd_week": [...weekly series...], "by_task_type": {...} }

POST /api/v1/kernel/tasks   (existing endpoint — payload gains optional fields)
{ "agent_name": "uzhavu-ops", "task_type": "incident_fix",
  "input": {"description": "worker queue stuck on VPS", "project_id": "…"},
  "priority": "high", "properties": {"private": false, "isolation": true} }
→ 201  (dispatch, verification, landing all downstream-automatic)

GET /api/v1/agent/context?task_type=code_fix&project_id=…   (extended existing endpoint)
→ 200 { "packet": { "spec": …, "project": …, "memories": […], "preferences": […],
                    "procedures": […], "judgment_profile": …, "output_contract": … },
        "token_estimate": 4180 }
```

### Core Implementation

```python
# life_graph/drivers/base.py
"""AgentDriver protocol — the tool registry pattern, one level up."""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class DriverResult:
    exit_status: str                    # ok|failed|timeout
    summary: str
    artifacts: list[dict] = field(default_factory=list)  # [{"kind": "diff|file|text|pr", "ref": ...}]
    raw_cost_usd: float = 0.0
    duration_ms: int = 0
    raw: dict = field(default_factory=dict)


class AgentDriver(Protocol):
    name: str
    capabilities: list[str]
    cost_class: str                     # free|cheap|frontier
    supports_workdir: bool
    max_concurrency: int

    async def available(self) -> tuple[bool, str]: ...
    async def dispatch(self, packet: str, *, workdir: str | None,
                       timeout_s: int) -> DriverResult: ...
```

```python
# life_graph/drivers/claude_code.py
"""Claude Code headless driver. Wrap, don't rebuild (strategic-decision.md)."""

import asyncio, json, time


class ClaudeCodeDriver:
    name = "claude_code"
    capabilities = ["code", "test", "review", "refactor", "docs"]
    cost_class = "frontier"
    supports_workdir = True
    max_concurrency = 2

    async def dispatch(self, packet: str, *, workdir: str | None, timeout_s: int) -> DriverResult:
        started = time.monotonic()
        proc = await asyncio.create_subprocess_exec(
            "claude", "-p", packet, "--output-format", "json",
            cwd=workdir, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except asyncio.TimeoutError:
            proc.kill()
            return DriverResult(exit_status="timeout", summary="claude_code timed out")
        data = json.loads(out or b"{}")
        return DriverResult(
            exit_status="ok" if proc.returncode == 0 else "failed",
            summary=data.get("result", "")[:2000],
            raw_cost_usd=float(data.get("total_cost_usd") or 0.0),
            duration_ms=int((time.monotonic() - started) * 1000),
            raw=data,
        )
```

```python
# life_graph/services/verifiers.py
"""Verifier chain — definition of done as data. One bounce, then human."""

VERIFIERS = {}  # name -> async callable(task, artifacts, project) -> VerifierOutcome

def verifier(name: str):
    def wrap(fn):
        VERIFIERS[name] = fn
        return fn
    return wrap


@verifier("tests_pass")
async def tests_pass(task, artifacts, project):
    # subprocess pytest/vitest per project.framework — evidence = tail of failures
    ...

@verifier("citations_present")
async def citations_present(task, artifacts, project):
    # review artifacts must cite file:line for every finding
    ...

@verifier("style_conforms")
async def style_conforms(task, artifacts, project):
    # content: rules distilled from corrections table (capture-spine Story 3)
    ...


class VerifierChain:
    async def run(self, task, artifacts) -> VerificationRun:
        results = []
        for name in task.verifier_chain:
            outcome = await VERIFIERS[name](task, artifacts, task.project)
            results.append(outcome)
            if not outcome.passed and outcome.blocking:
                break
        run = await self._store(task, results)
        if not run.passed and task.attempt == 1:
            await self._bounce_once(task, run)      # re-dispatch with failure report
        elif not run.passed:
            await self._to_approval_queue(task, run)  # autonomy/approvals (Era 8)
        else:
            await self._autonomy_gate(task, run)      # trust decides landing
        return run
```

```python
# life_graph/drivers/dispatcher.py — selection: persona pin → cheapest capable trusted → fallback
# life_graph/services/results_loop.py — capture-spine observation + implicit judgment
#   prediction + trust update + driver_stats upsert, subscribed to TASK_COMPLETED/TASK_FAILED
```

### Dependencies & Integrations

| Integrates with | How |
|---|---|
| `kernel/process_manager.py` | Dispatch replaces the direct orchestrator call with driver selection; retries → fallback chain |
| `kernel/personas.py` | Personas gain driver/verifier_chain/context_profile/task_types (Story 5) |
| `autonomy/` (Era 8, built) | Verified results route through safety classifier → trust → approval queue → audit; **no new gate code** |
| `agents/orchestrator.py` | Registered unchanged as the `local` driver |
| `services/context.py` + `api/agent.py` | Packet builder extends the existing context service/endpoint |
| `capture-spine.md` | Results loop reports observations; `PROCEDURE_CANDIDATE` inherited |
| `judgment-engine.md` | Implicit predictions per estimated task, resolved on completion |
| `kernel/scheduler.py` + `watchers/` | Standing pipelines (Story 6) |

### New EventType Additions

```python
# In life_graph/core/events.py — add to EventType enum:
DRIVER_DISPATCHED = "driver:dispatched"
DRIVER_RESULT = "driver:result"
VERIFICATION_PASSED = "verification:passed"
VERIFICATION_FAILED = "verification:failed"
TASK_BOUNCED = "verification:bounced"
PIPELINE_TASK_ORIGINATED = "pipeline:task:originated"
```

### New Environment Variables

```bash
LIFE_GRAPH_DRIVERS_ENABLED=true
LIFE_GRAPH_DRIVER_CLAUDE_CODE_BIN=claude
LIFE_GRAPH_DRIVER_CODEX_BIN=codex
LIFE_GRAPH_DRIVER_DEFAULT_TIMEOUT_S=900
LIFE_GRAPH_CONTEXT_PACKET_TOKEN_BUDGET=6000
LIFE_GRAPH_WIP_LIMIT_PER_PROJECT=2
LIFE_GRAPH_CONCURRENT_TASKS_PER_TENANT=5
```

### Error Handling

- Driver unavailable at dispatch → next in fallback chain; all unavailable → task `needs_human` with reason
- Malformed driver JSON output → `exit_status=failed`, raw stdout preserved in `output.raw` for debugging
- Verifier crash (not failure) → treated as inconclusive: chain continues, crash logged, task cannot auto-land (conservative)
- Workdir isolation: `isolation=true` tasks run in a git worktree; worktree cleanup on terminal state; dirty worktree on failure is preserved 7 days for forensics
- Cost runaway guard: per-task cost cap (designed as $2; the setting is `per_task_spend_cap_usd`, see STATE.md) — driver processes killed past cap, task marked failed

### Security Considerations

- External drivers execute with project-scoped workdirs only — never `$HOME`, never the Life Graph repo itself without an explicit persona permission
- Private-flagged tasks strip memory/preference packet sections for external drivers (Story 2); enforced in the packet builder, not by driver goodwill
- Era-8 safety classifier runs on task **intent** before dispatch (existing) and on **artifacts** before landing — destructive-action patterns route to the approval queue regardless of trust level
- Driver subprocess env is allow-listed (no ambient API keys beyond what the driver itself needs).
  True since 2026-11-18 (`drivers/host_exec.py`; containers: `services/dev/task_runtime.py`);
  before that host-run drivers inherited the API process's whole environment.

### Cost Model

| Item | Estimate |
|---|---|
| Dependency PRs (4 projects, weekly, frontier driver) | ~₹120/mo |
| Code review on push (~30/mo, cheap reviewer model) | ~₹40/mo |
| Content pipeline (4/mo: research + draft + critique) | ~₹80/mo |
| Triage/extraction (local driver) | ₹0 |
| **Metric that matters** | verified tasks landed per ₹ per week, trending up |

---

## Tasks

### Phase 1: Driver Protocol + Two Drivers (~2 days)
- [x] `drivers/base.py` protocol + `drivers/registry.py` (availability probing, stats surface)
- [x] `drivers/claude_code.py` (headless subprocess, JSON parse, worktree isolation option)
- [x] `drivers/local.py` wrapping `AgentOrchestrator`
- [x] Migration `021_agent_drivers.py`; `GET /kernel/drivers` endpoint; new EventTypes

### Phase 2: Context Packets (~1.5 days)
- [ ] Extend `services/context.py`: packet sections, token budget with priority truncation, privacy stripping
- [ ] Packet snapshot into `agent_tasks.input`; extend `/api/v1/agent/context` params
- [ ] Judgment-profile section stub (activates when judgment engine ships)

### Phase 3: Verifier Chain (~2 days)
- [x] `services/verifiers.py`: registry decorator + built-ins (tests_pass, lint_clean, build_ok, diff_within_scope, citations_present, style_conforms, claims_evidenced)
- [ ] One-bounce rule; wire into `autonomy/pipeline/executor.py`; `verification_runs` storage
- [ ] Second-opinion reviewer pass (dissenting cheap model)

### Phase 4: Dispatch + Results Loop (~1.5 days)
- [x] `drivers/dispatcher.py`: selection (pin → cheapest capable trusted → fallback), WIP/concurrency limits, cost cap
- [x] `services/results_loop.py`: capture-spine observation, implicit judgment prediction, trust update, `driver_stats` upsert
- [ ] Persona columns live: create `uzhavu-ops` and `dependency-updater` personas as rows (proof of Story 5)

### Phase 5: Standing Pipelines (~1.5 days)
- [ ] Watcher-finding → task origination rules; scheduler-originated tasks
- [ ] Launch the three pipelines: dependency updates, code review on push, content pipeline
- [ ] `GET /kernel/drivers/stats` with verified-per-₹ weekly series

### Phase 6: Tests & Docs (~1 day)
- [ ] Integration tests: driver fallback, packet privacy stripping, bounce-once, autonomy-gate routing, WIP limits (mock drivers — no real subprocess in CI)
- [ ] Update KNOWLEDGE.md (drivers section, new tables/events), .env.example, OpenAPI examples

**Total: ~9.5 days**


---

## Amendment 2026-11-27 — Autonomy policy (owner decision D2)

> **Status: Built** (branch `race/autonomy-policy`). Code: `services/dev/autonomy_policy.py`,
> `services/dev/review_stages.py`, `services/dev/risk_report.py`, `drivers/review_stages.py`
> (dispatcher mixin), `autonomy/policy/router.py`; migration `064_autonomy_policies`.
> Context: race-app becomes life-graph's frontend and its own autonomy pipeline (race-app
> `docs/specs/AUTONOMY.md`, `TEAMWORK.md` §1–2) is replaced by these features
> (race-app `docs/specs/LIFE_GRAPH_MIGRATION.md`, Phase 2).

### Decision

A task may get **bounded, budget-gated, owner-enabled** automatic rounds — verify-fix and
review-fix now; nudges, stall retries and PR-feedback rounds later — each recorded as a
verification attempt. **The approval path stays single**: rounds never approve, and the
owner's auto-approval conditions can only **narrow** `change_policy.auto_gate`.
**Default 0 rounds = today's one-bounce behaviour, unchanged.**

### Rationale

- *Why amend decision 4 at all.* One bounce was a cost guard ("infinite fix loops burn money
  silently"), not a quality rule. A cap the owner sets explicitly, per project, with the budget
  governor, the per-task cost cap and the kill switch checked before every round, keeps that
  guarantee: loops stay finite (`MAX_FIX_ROUNDS = 3`), and spend stays visible and bounded.
  race-app's local engine showed that one or two more targeted rounds turn many needs-human
  escalations (a test still failing after the first fix; a reviewer's concrete objection) into
  finished work without a person.
- *Why rounds never approve* (decision 3, CHARTER invariants 1 and 5). A round only produces
  a new attempt that must pass the same verifier chain; it is recorded in `verification_runs`
  like the bounce (attempt 3, 4, …). Whether anything lands unattended is still decided by
  `auto_gate` alone.
- *Why a reviewer can only veto* (invariant 1). race-app's `requireReviewApproved` becomes
  `require_no_reviewer_objection`: some reviewer looked and none objected. An LLM's "ok" adds
  nothing to the trust the change already needs; a stage that could not run counts against
  auto-approval, never for it.
- *Why conditions only narrow* (invariant 5). The owner's conditions are asked *after* auto_gate's
  own rules (protected paths, size, proof checks, trust per kind of change) passed, and can only
  add refusal reasons. Global and project conditions are evaluated separately and both must hold.
  An unreadable or corrupt policy refuses. Merges and deploys keep their existing human rules
  (`auto_merge` is still a separate opt-in; `deploy_on_merge` is never trust-approved).

### Story 7: Owner auto-approval conditions (narrow `auto_gate` only)

- GIVEN no `autonomy_policies` row for the tenant WHEN auto_gate runs THEN its answer is exactly
  what it was before this amendment (no query result adds a reason).
- GIVEN a policy WHEN auto_gate's own rules refuse THEN that refusal is returned unchanged and the
  policy is not consulted.
- GIVEN auto_gate's own rules pass WHEN any owner condition fails THEN auto_gate returns
  `(False, "owner policy: <reason>; <reason>…", record)` — the same `(allowed, reason, record)`
  shape, so the approval note, the auto-open/merge logs and the night-shift "why waiting" all
  show the owner's reason.
- Conditions (each off by default): `max_changed_lines`, `max_files`, `paths_allowed` (every changed
  file matches one glob), `paths_forbidden` (none matches), `require_verification_passed` (payload
  `verified` true, at least one check, no unverifiable check), `require_no_reviewer_objection`,
  `risk_tolerance` (`any` | `warnings` = no block finding | `none` = no finding; a missing or
  incomplete risk report refuses). Globs are `fnmatch` (`*` also crosses `/`), as `protected_paths`.
- GIVEN `daily_auto_approval_cap: N` (global) WHEN N tasks were already opened or merged
  unattended since UTC midnight, across all projects, THEN auto-approval is refused
  ("daily auto-approval cap reached (N of N today)"). Counted per task (auto-open + auto-merge of
  one task = 1), excluding the task being decided; `0` = no auto-approval; uncountable → refuse.
- GIVEN any policy row WHEN the kill switch is paused (or unreadable) THEN auto-approval is refused.
- GIVEN a `human` review stage in the global or the project list THEN the task is never
  auto-approved.

### Story 8: Review stages (veto-only)

- GIVEN `review_stages` (≤ 4, unique names, each `{name, reviewer, focus}`) WHEN a task's verifier
  chain passes THEN the stages run in order in the second-opinion position, **replacing** the
  single default review; with no stages the default review runs exactly as before.
- Reviewers: `human` (stop the chain; the task lands for a person and is never auto-approved;
  later stages are recorded `skipped`), `pr_agent` (PR-Agent on the real diff with the focus as
  extra instructions), `model:<id>` (one veto-only LLM pass on that model only, no paid fallback,
  code only). Driver-backed reviewers come with the Phase 3 drivers.
- GIVEN a stage objects AND review-fix rounds remain AND `_round_allowed` THEN the objection goes
  back to the author as a failed check (`review:<stage>`), the verifier chain re-runs (recorded
  as the next attempt), then **that** stage reviews again. GIVEN no round is left or allowed THEN
  it routes to a person exactly as today's dissent (`driver_second_opinion_dissent`, task
  `needs_human`, error `Review stage dissent: review stage '<name>': <concern>`).
- GIVEN a review-fix round's driver run or re-verification fails THEN the task needs a person
  (`driver_verification_failed` entry).
- GIVEN a stage cannot run (tool missing, model down, unreadable answer) THEN it is recorded
  `unavailable`, the chain continues, the task is not failed, and auto-approval is refused.
- `review_fix_rounds` is a per-task total across stages (not per stage): the strictest reading of
  "bounded".
- Every result is stored, in order, on the task (`properties.review_stages`); the PR approval
  payload carries the latest verdict per stage (`payload.autonomy.review_stages`).

### Story 9: Verify-fix rounds

- GIVEN `verify_fix_rounds = 0` (default) WHEN verification fails THEN the one bounce runs and a
  second failure escalates — identical attempts, events, error text, metadata and approval entry
  to before.
- GIVEN `verify_fix_rounds = N > 0` WHEN the bounce's re-check still fails THEN up to N more rounds
  run, each with the **latest** failing verifier output, each recorded as attempt 3, 4, …; a round
  that passes lands like a successful bounce; out of rounds → needs_human with the last failure
  (`Verification failed after the bounce and N verify-fix round(s) — needs human review`; the
  approval entry says "after one bounce and N verify-fix round(s)").
- Before each extra round `_round_allowed` checks, fail-closed: kill switch not paused, the run's
  spend below its per-task cost cap, and the Governor allows the driver's estimated spend
  (interactive / local-model runs bypass the monthly cap exactly as the first dispatch does).
  Extra rounds book their spend with the Governor. A round whose *driver run* fails ends the
  rounds (they fix checks; stall retries are a later, separate round kind).

### Story 10: Risk report

- GIVEN a task lands a change WHEN Step 6b runs (before the landing commit) THEN a risk report is
  built from the worktree diff and stored on the task (`properties.risk_report`), and its counts go
  into the PR approval payload (`payload.autonomy.risk = {block, warn, complete}`).
- Findings on **added** lines: `secret_pattern` (block; the high-confidence shapes of
  `no_secrets_in_diff`), `high_entropy_string` (block; warn in tests/fixtures or next to
  sha/hash/digest/integrity) — ≥ 20 chars, ≥ 2 digits, letters, ≥ 3 character classes, Shannon
  entropy ≥ 3.5 bits/char, not a UUID — `hex_string` (warn; ≥ 32 hex chars), `secret_assignment`
  (warn; a literal assigned to password/api_key/secret/token…, placeholders excepted). On the
  change: `protected_path`, `out_of_scope` (non-test file the instruction does not name, when it
  names any) and `large_deletion` (deleted file, or > 200 lines removed) — all warn. Lock files,
  minified/map/svg/snapshot files are not scanned for entropy.
- A finding names file, line, rule and a shape ("28-char string, 4.3 bits/char"), never the
  value. ≤ 100 findings stored (`truncated` says so). An empty diff while files changed is stored
  `complete: false`, which `risk_tolerance` refuses.
- New opt-in verifier `no_high_entropy_in_diff` (a project's `required_checks` or a persona's
  chain): fails on `block` findings in added lines (tracked diff + untracked files). Not in the
  default chain or the always-on checks, so existing dispatches are unchanged.

### Story 11: Review panel on risky diffs (2026-11-28, shadow first)

> Added 2026-11-28, step 6 of the router/council decision (race-app
> `docs/research/2026-11-28-router-council/04-decision.md`). Code: `services/dev/review_panel.py`,
> hook `AutonomyRoundsMixin._review_panel` in `drivers/review_stages.py` (runs right after the
> risk report, before the landing commit). The idea (independent proposers, no vote) is from
> the Mixture-of-Agents study (togethercomputer/MoA, Apache-2.0); no code was ported.

- Settings: `driver_review_panel_mode` = `off` (default) | `shadow` | `enforce`;
  `driver_review_panel_models` (default `ollama_chat/qwen3:14b,ollama_chat/qwen3-coder:30b`);
  `driver_review_panel_timeout_seconds` (300, per member); `driver_review_panel_min_lines` (150).
- GIVEN mode is not `off` WHEN a change lands THEN the panel runs only if the diff is **risky**:
  the risk report has a warn or block finding, or is missing/incomplete; the diff touches a
  protected path (`change_policy.protected_hits`, defaults plus the project's globs); or it changes
  more than `driver_review_panel_min_lines` lines (added + removed). Otherwise
  `properties.review_panel` is `{"verdict": "skipped", "reason": "not risky"}`.
- Each member reviews the real diff **in parallel and blind to the others**, prompted with the
  task instruction and the diff only (no memories, preferences or procedures), focused on
  correctness, security and scope, and answers `objection` | `approve` | `not_reviewed` with a
  reason. Each call runs under `only_models([model])` (no failover). Only `ollama/` and
  `ollama_chat/` ids run: any other id is **refused** (never called) and counts as
  `not_reviewed`. A timeout, error or unreadable answer is `not_reviewed`, never a pass.
- Combine (deterministic, no chairman, no majority): **any objection → `objection`; else any
  not-reviewed → `not_reviewed`; only a unanimous approval → `approve`.** An empty panel is
  `not_reviewed`.
- GIVEN `shadow` THEN the panel starts in the background and the dispatch does not wait for it;
  its verdict is stored on the task (`properties.review_panel`: mode, verdict, reason, risky
  reasons, members with model/verdict/reason/duration, `gated: false`) and emitted as a
  `review_panel` task event. It changes nothing on the run or the approval. At most
  `MAX_SHADOW_IN_FLIGHT` (2) at once; more are stored `skipped` / `panel busy`.
- GIVEN `enforce` THEN the dispatch waits (bounded by the member timeout) and anything but a
  unanimous approval sets `hold_auto`: the PR approval is filed for a person with no auto-open and
  no auto-merge, and `payload.autonomy.review_panel = {verdict, members}`. A panel approval never
  approves anything nor lifts an existing hold (invariant 1). A panel crash in enforce holds.
- Kill switch paused: `shadow` stores `skipped` / `kill switch` (no model call); `enforce` stores
  `not_reviewed` and holds.
- The outcome log reads the verdict with `review_panel.panel_for_outcome(task.properties)`.
- Not covered: the resumed "land only" path whose branch already landed (it files the approval
  without Step 6b, so neither the risk report nor the panel run there).

### Data model

```sql
-- Migration 064_autonomy_policies.py
CREATE TABLE autonomy_policies (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   VARCHAR(64) NOT NULL,
    scope       VARCHAR(64) NOT NULL,          -- 'global' or the project's UUID as text
    policy      JSONB NOT NULL DEFAULT '{}',   -- validated by services/dev/autonomy_policy.py
    updated_by  VARCHAR(128),                  -- who the server saw (approval_identity.resolver)
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_autonomy_policies_tenant_scope UNIQUE (tenant_id, scope)
);
```

Per-task results need no schema change: `agent_tasks.properties.review_stages` /
`.risk_report` (cleared when a new dispatch of the task starts), and rounds are
`verification_runs` rows with `attempt` ≥ 3.

### API contracts

All under `/api/v1`, tenant-scoped by `X-Tenant-ID`. Reads: any tenant key. Writes (`PUT`,
`DELETE`): **owner only** (`approval_identity.owner_only`, as trust overrides and autonomy levels)
→ 403 `{"detail": "Changing the autonomy policy needs the owner: an owner API key or a paired phone."}`.
Invalid bodies → 422 (unknown fields are refused). Responses use the usual `{"data": …}` envelope.
Errors use the app-wide error envelope (main.py handlers), with FastAPI's `detail` kept at the
top level as a string:

```
422 {"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed.",
               "details": [{"field": "body → verify_fix_rounds", "message": "…"}], "request_id": "…"},
     "detail": "Request validation failed."}
404 {"error": {"code": "PROJECT_NOT_FOUND", "message": "Project not found", "request_id": "…"},
     "detail": "Project not found"}
```

**Policy body** — global (`PUT /autonomy/policy`); every field optional, omitted = neutral default
(`//` comments are annotations, not part of the body):

```jsonc
{
  "conditions": {
    "max_changed_lines": 80,              // int 0..100000 | null (off)
    "max_files": 4,                       // int 0..10000 | null
    "paths_allowed": ["docs/*", "tests/*"],   // ≤ 50 globs; [] = off
    "paths_forbidden": ["*.env"],             // ≤ 50 globs; [] = off
    "require_verification_passed": true,  // default false
    "require_no_reviewer_objection": true,// default false
    "risk_tolerance": "warnings"          // "any" (default) | "warnings" | "none"
  },
  "daily_auto_approval_cap": 5,           // int 0..1000 | null (no cap); global only
  "review_stages": [                      // ≤ 4, unique names; [] = default single review
    {"name": "security", "reviewer": "model:gemini/gemini-2.5-flash", "focus": "secrets, auth"},
    {"name": "owner", "reviewer": "human", "focus": ""}   // reviewer: "human" | "pr_agent" | "model:<id>"
  ],
  "verify_fix_rounds": 2,                 // int 0..3, default 0
  "review_fix_rounds": 1                  // int 0..3, default 0
}
```

Project body (`PUT /autonomy/policy/projects/{project_id}`): the same without
`daily_auto_approval_cap` (422 if sent); `review_stages`, `verify_fix_rounds` and
`review_fix_rounds` may be `null` (= use the global value). Project conditions are checked in
addition to the global ones; non-null stages/rounds replace the global ones (a `human` stage in
either list still forbids auto-approval).

```
GET /autonomy/policy
→ 200 {"data": {
    "global": {"policy": {…global body…}, "updated_by": "owner", "updated_at": "2026-11-27T10:00:00+00:00"} | null,
    "projects": [{"project_id": "<uuid>", "name": "race-app" | null, "active": true, "override": true,
                  "policy": {…project body…}, "updated_by": "owner", "updated_at": "…"}],
    "auto_approvals_today": 2,
    "limits": {
      "max_fix_rounds": 3, "max_review_stages": 4, "max_globs": 50,          // original keys, kept
      "reviewers": ["human", "pr_agent", "model:<model id>"],                 // original, kept
      "reviewer_format": {"kinds": ["human", "pr_agent", "model"], "model_prefix": "model:",
                          "max_length": 120},
      "risk_tolerances": ["any", "warnings", "none"],
      "bounds": {                       // every bound the pydantic models enforce; [] = each item
        "conditions.max_changed_lines": {"min": 0, "max": 100000},
        "conditions.max_files": {"min": 0, "max": 10000},
        "conditions.paths_allowed": {"max_items": 50, "item_max_length": 200},
        "conditions.paths_forbidden": {"max_items": 50, "item_max_length": 200},
        "daily_auto_approval_cap": {"min": 0, "max": 1000},
        "review_stages": {"max_items": 4},
        "review_stages[].name": {"min_length": 1, "max_length": 60},
        "review_stages[].reviewer": {"min_length": 1, "max_length": 120},
        "review_stages[].focus": {"max_length": 2000},
        "verify_fix_rounds": {"min": 0, "max": 3},
        "review_fix_rounds": {"min": 0, "max": 3}}}}}

`projects[]` lists exactly the stored project overrides (one row each, sorted by id): `name` and
`active` come from `projects`; `active: false`, `name: null` = the row outlived its project
(gone, archived or another tenant's id) and applies to no task.

PUT /autonomy/policy            body: global body   → 200, same shape as GET
DELETE /autonomy/policy                              → 200 {"data": {"removed": true}}

GET /autonomy/policy/projects/{project_id}
    404 PROJECT_NOT_FOUND: unknown, inactive or other-tenant project, or not a UUID.
    A known project with no override is 200 with "override": null (effective = global).
→ 200 {"data": {
    "project_id": "<uuid>", "name": "race-app", "has_override": true,
    "override": {"policy": {…}, "updated_by": "owner", "updated_at": "…"} | null,
    "policy": …same as override (original name, kept)…,
    "effective": {
      "configured": true, "sources": ["global", "project"],
      "conditions": [{"source": "global", …conditions…}, {"source": "project", …conditions…}],
      "daily_auto_approval_cap": 5,
      "review_stages": [{"name": "security", "reviewer": "model:…", "focus": "…"}],
      "human_stage": true, "verify_fix_rounds": 0, "review_fix_rounds": 1}}}

PUT /autonomy/policy/projects/{project_id}   body: project body → 200, same shape as GET
DELETE /autonomy/policy/projects/{project_id}       → 200 {"data": {"project_id": "<uuid>", "removed": true}}

GET /kernel/drivers/tasks/{task_id}/review-stages    (404: no task / no stage ran)
→ 200 {"data": {"task_id": "<uuid>",
    "results": [{"index": 0, "name": "security", "reviewer": "model:…", "focus": "…",
                 "verdict": "objection",            // no_objection|objection|unavailable|human|skipped
                 "concern": "…", "fix_round": 0, "note": null, "at": "2026-11-27T10:00:00+00:00"},
                {"index": 0, "name": "security", …, "verdict": "no_objection", "fix_round": 1, …}],
    "latest": [{"index": 0, "name": "security", "reviewer": "model:…", "verdict": "no_objection", "fix_round": 1}]}}

GET /kernel/drivers/tasks/{task_id}/risk             (404: no task / nothing landed)
→ 200 {"data": {"task_id": "<uuid>", "version": 1, "generated_at": "…", "complete": true,
    "files": 3, "block": 1, "warn": 2, "truncated": false,
    "findings": [{"severity": "block", "rule": "high_entropy_string", "file": "app/config.py",
                  "line": 11, "detail": "32-char string, 4.6 bits/char"}, …]}}

GET /kernel/drivers/tasks/{task_id}   (existing) now also returns "review_stages" and "risk_report"
(null when absent).
```

The PR/merge approval payload gains `autonomy` (when anything was recorded):
`{"review_stages": [latest per stage], "human_stage": true?, "risk": {"block", "warn", "complete"},
"verify_fix": {"rounds", "allowed", "stopped"}?, "review_fix": {"rounds", "allowed"}?,
"policy_note": "…"?}`.

`autonomy.policy_note` (string, plain one line, ≤ 300 chars, secrets redacted by
`core/redaction.redact_secrets`) is the reason `auto_gate` refused an unattended step, in the
gate's own words — e.g. `"owner policy: owner rule (global): 412 changed lines (at most 300)"`,
`"not yet trusted for code changes: codex has 2/5 code PRs merged"`. On the `driver_pr` approval
it is set when auto-open was asked and refused (after the approval is filed); on the
`driver_merge` approval when auto-merge was asked and refused (at filing, and again by each
`retry_auto_merges` sweep). A later check that passes removes it; a merge approval never
inherits the PR approval's note. Absent = no unattended step was refused (none was asked, or it
passed). Local mode and unverified branches never consult the gate, so they set no note.
Task events gain kind `round` (`data.kind` = `verify_fix` | `review_fix`).

### What the defaults guarantee

No `autonomy_policies` row ⇒ `owner_policy_reasons` returns `[]` without consulting the kill
switch or the cap; the dispatcher's policy is `NEUTRAL` (0 rounds, no stages) ⇒ the one bounce,
the single default review, and auto_gate's answers are exactly as before. Additions that do run
by default are informational only: the risk report (stored, never acted on without
`risk_tolerance`) and the `autonomy` block on new approval payloads.

### Not in this amendment

Nudges, stall retries, park-on-limit and PR-feedback rounds (race-app TEAMWORK §3, migration
Phase 3/4) — they will reuse `_round_allowed` and the attempt counter. Driver-backed reviewers.
The cap counts at decision time, so two auto-approvals deciding in the same instant can exceed it
by one.

### Tasks

- [x] `autonomy_policies` table + migration 064; model `AutonomyPolicy`
- [x] `services/dev/autonomy_policy.py`: schemas, merge, conditions, cap, kill switch; wired last into `auto_gate`
- [x] `services/dev/review_stages.py` + `drivers/review_stages.py`: stages, review-fix rounds, stored results
- [x] Verify-fix rounds in `_bounce_or_escalate`; `_bounce_task(attempt=…)`; Governor booking for extra rounds
- [x] `services/dev/risk_report.py` (entropy + line/change rules), stored report; opt-in `no_high_entropy_in_diff`
- [x] API `/autonomy/policy*` (owner-only writes), `/kernel/drivers/tasks/{id}/review-stages|risk`
- [x] Unit tests: narrowing only, cap, stages incl. human, bounded rounds and default 0, entropy, API
- [x] Cockpit gaps (race-app): `autonomy.policy_note` on refused auto-open/merge; complete
      `limits` (`bounds`, `reviewer_format`, `risk_tolerances`); `projects[].name|active|override`;
      `override`/`has_override`/`name` and 404 `PROJECT_NOT_FOUND` on the project route
- [ ] Integration test against Postgres (migration up/down, cap count on real approvals)
- [ ] race-app Settings → Autonomy reads/writes these endpoints; race-app's local pipeline reads this policy
---

## Phase 3a (2026-11-27): Codex and Gemini CLI drivers

> **Status: Built, fixture-tested.** `drivers/codex.py`, `drivers/gemini.py`, shared
> `drivers/cli_driver.py` (the common dispatch flow), `drivers/cli_run.py` (host run + detection) and `drivers/cli_failure.py` (failure
> classification). Both drivers are **off by default** and have not yet run against a
> signed-in CLI: on the workstation both CLIs were signed out on 2026-11-27, so the event
> parsers are tested against fixtures built from the CLIs' own event definitions, not
> recorded runs. Part of the race-app migration (race-app's `agents/runtimes/codex*.ts`
> rebuilt in Python; Gemini had no race-app parser yet).

### Requirements

- GIVEN `driver_codex_enabled` (or `driver_gemini_enabled`) is false WHEN the dispatcher
  selects a driver THEN that driver reports unavailable and is skipped, installed or not.
- GIVEN it is enabled but the binary is missing, or the CLI reports it is signed out, THEN
  it is unavailable, and `GET /kernel/drivers` shows why (`detail.installed`,
  `detail.version`, `detail.logged_in`, `detail.hint` such as "run `codex login`"). No token
  is ever read or printed: Codex is asked `codex login status` (exit code only); Gemini is
  judged by whether `~/.gemini/oauth_creds.json` exists or a key variable is passed through.
- GIVEN a dispatch WHEN the driver runs THEN it uses the CLI's headless, structured mode in
  the task workdir, on the host, with the `host_exec` environment allowlist, its own
  process group (a timeout kills the group) and the prompt on stdin:
  - Codex: `codex exec --json` with `-s read-only` for a plan (or a persona without write
    tools) and `-s workspace-write` otherwise, `approval_policy="never"`, network off in
    the sandbox, web search, browser, computer use, apps, plugins, hooks and memories off,
    and the user's `config.toml` ignored (so its MCP servers do not load).
  - Gemini: `gemini -p … -o stream-json` with `--approval-mode plan` for a plan and
    `auto_edit` otherwise; never `yolo`, never `-w`. A run-scoped system settings file
    (`GEMINI_CLI_SYSTEM_SETTINGS_PATH`, highest precedence) excludes the shell and web
    tools and turns hooks, tool-discovery commands and usage statistics off;
    `--allowed-mcp-server-names` names a server that does not exist, so none load.
- GIVEN the run ends THEN the result has the same shape as `claude_code`'s: `output` is the
  final agent message, `metadata.steps` the driver-neutral steps (`text`, `thinking`,
  `tool_call`, `tool_result`, `error`), `metadata.session_id` the Codex thread id or the
  Gemini session id, `metadata.usage` the token counts when the CLI reports them, and live
  session events are emitted line by line. `cost_usd` is 0: both run on a subscription
  login, which reports no price.
- GIVEN the run fails THEN `metadata.failure` classifies it: `rate_limited` (with
  `resets_at` when the CLI gives a reset: a Codex rate-limit snapshot, an ISO time, or
  "try again in 2 hours 5 minutes"), `auth` (with the sign-in command), or `other`.
  Messages are scrubbed of token-shaped strings and clipped to 200 characters.
- GIVEN the packet WHEN the prompt is built THEN memories, preferences and procedures are
  dropped (CHARTER invariant 7: both CLIs send everything to a cloud provider), whatever
  `packet.private` says.
- GIVEN Codex on the host WHEN `driver_allow_host_shell` is false THEN the dispatch is
  refused (`exit_status=refused_host_shell`). Codex has no way to run without its shell,
  and its sandbox confines writes and network but not reads, so it can read anything this
  user can and send it to the model. Gemini runs with its shell excluded and its file
  tools limited to the workspace directories by the CLI itself.
- GIVEN cheapest-capable selection THEN drivers sort by `(cost_per_task, billing)`, where
  `billing` is `local` < `subscription` < `api` (a driver without the attribute counts as
  `api`). Codex and Gemini are `subscription` with a marginal cost of $0, so at equal cost
  a local driver still wins. A persona pinned to `codex` or `gemini` gets that driver
  when it is available.

### Config

`driver_codex_enabled`, `driver_codex_bin`, `driver_codex_model` (empty = the CLI's
default), `driver_codex_timeout_seconds`; the same four for `gemini`. A CLI's own login
location passes through (`CODEX_HOME`; Gemini reads `~/.gemini`); an API key only when the
operator lists it in `driver_host_env_passthrough`.

### Not in 3a (Phase 3b)

- Accounts, a login pool and plan-limit polling (race-app `limits/**`); the rate-limit
  windows are captured in `metadata.rate_limits` but nothing schedules around them yet.
- Resume/continue (`codex exec resume <thread>`, `gemini -r`), so no self-check loop.
- Parking a task until `resets_at` instead of failing it.
- Subscription budget (risk D4): the Governor sees $0 for these runs, so its monthly cap
  does not limit them; only the drivers' own `max_concurrency = 1` does.
- Running either CLI in the per-task container runtime (needed before Codex can run
  without `driver_allow_host_shell`).
- Recorded fixtures from a signed-in run of each CLI.

### Tasks

- [x] `drivers/cli_driver.py`, `drivers/cli_failure.py`, `drivers/cli_run.py`
- [x] `drivers/codex.py`: argv, event parser, rate-limit snapshot, failure classification
- [x] `drivers/gemini.py`: argv, system settings, event parser, failure classification
- [x] Registration (`drivers/setup.py`), `billing` attribute, selection tiebreak, config flags
- [x] Unit tests with fixture event streams and a fake CLI binary
- [ ] Record real fixtures once the owner signs in (`codex login`, `gemini`)

## Phase 3b (2026-11-27): accounts, pool, limits, resume

> **Status: Part 1 and part 2 built, fixture-tested** (part 2: see
> [Phase 3b part 2](#phase-3b-part-2-2026-11-27)). Migration `065_agent_accounts.py`;
> `services/agent_accounts/` (`catalog`, `env`, `homes`, `identity`, `pool`, `limits`,
> `service`), `drivers/accounts_hook.py`, `api/agent_accounts.py`; resume paths in
> `drivers/cli_driver.py`, `codex.py`, `gemini.py`, `claude_code.py`. Everything is **off
> by default** (`driver_accounts_enabled=false`): with it off, or with no enabled account
> for a driver, every driver runs on the host's single login exactly as in 3a. No CLI was
> signed in on 2026-11-27, so no account run, resume or Codex probe has run against a
> real login; flags were verified with each CLI's `--help` and bundle only. Part 2
> (re-dispatch on a rate limit, parking, `continue_task`, budget D4, run health) is built:
> see its own section below. Rebuilt from race-app's `AGENT_CONNECTIONS.md`, `AGENT_ACCOUNTS_USAGE.md`,
> `agents/connections/**` and `agents/limits/**` (the owner's code).

### Requirements

- GIVEN `driver_accounts_enabled` is false WHEN any driver runs THEN the accounts table is
  never read and the run is unchanged (the hook returns an empty lease).
- GIVEN it is on and the driver has no **enabled** account THEN the run is unchanged (the
  owner disabling every account turns that driver's pool off).
- GIVEN enabled accounts WHEN a run starts THEN the first one in pool order (`priority`,
  then age, then name) that is not cooling down is used: the CLI runs with its home
  variable pointing at that account's own directory, and an API-key account's key is
  resolved from the vault for that one process.
- GIVEN every enabled account is cooling down THEN the run is refused with
  `exit_status=rate_limited` and `metadata.failure = {kind: rate_limited, resets_at:
  <earliest cooldown end>}` (what part 2 parks on). Never a silent fallback to the default
  login (CHARTER invariant 5): a database error, a home outside the root, a group-readable
  home, a symlinked home, a missing or revoked key all refuse as `account_unavailable`.
- GIVEN a run on an account fails `rate_limited` THEN the account's `cooldown_until` is the
  CLI's `resets_at` when it is in the future and within 8 days, else now +
  `driver_accounts_default_cooldown_minutes`; `metadata.account.next` names the account a
  retry would use (or `{state: cooling, retry_at}`, or null). An `auth` failure sets
  `last_error` (with the sign-in hint) and no cooldown; only `rate_limited` moves on.
- GIVEN a run reports plan windows THEN the latest reading of each window is stored per
  account (`agent_account_limits`, source `run`): Codex from 3a's `metadata.rate_limits`
  (5-hour / weekly picked by window duration), Claude from `rate_limit_event` lines in its
  own `stream-json` output. **Claude's OAuth usage is never polled (owner decision U4).**
  Gemini reports no windows.
- GIVEN `driver_accounts_codex_probe_enabled` and an owner's `?refresh=true` THEN a Codex
  subscription account's windows are read with `codex app-server` (`initialize` →
  `account/read` → `account/rateLimits/read`; no prompt, nothing spent), at most once per
  5 minutes per account (429 + `Retry-After`).
- GIVEN the API THEN no route returns a key, its length, its vault handle or reference, the
  raw identity, its hash, or the home path — except `GET .../home`, which is owner only.
- GIVEN a resume (`driver.resume(packet, workdir, session_id, prompt)`) THEN the CLI
  continues that session with the prompt on stdin / `-p`, memories and preferences are not
  added, a value that is not a session id is refused (`bad_session`), and a sandboxed
  claude_code run refuses (`resume_unsupported`: the container's config dir is thrown away).

### Verified CLI facts (installed, 2026-11-27, not signed in)

| CLI | Home variable | API key variable | Vertex | Resume |
|---|---|---|---|---|
| Claude Code 2.1.328 | `CLAUDE_CONFIG_DIR` | `ANTHROPIC_API_KEY` | `CLAUDE_CODE_USE_VERTEX=1`, `ANTHROPIC_VERTEX_PROJECT_ID`, `CLOUD_ML_REGION` | `claude -p <prompt> --resume <session-id>` (`-r, --resume [value]`) |
| codex-cli 0.172.0 | `CODEX_HOME` | `CODEX_API_KEY` (binary: "run `codex login` or set CODEX_API_KEY") | — | `codex exec [--json --color never -s MODE] resume [--ignore-user-config -c ...] <SESSION_ID> -` — `resume` takes no `-s`/`--color` (they parse before it), so the sandbox is also `-c sandbox_mode="MODE"` |
| gemini-cli 0.71.1 | `GEMINI_CLI_HOME` (replaces the dir `.gemini/` lives under) | `GEMINI_API_KEY` | `GOOGLE_GENAI_USE_VERTEXAI=true`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` | `--resume <uuid>` (also `latest` / index; only a UUID is passed). Sessions are per project dir: same workdir and home |

`CODEX_HOME` and `GEMINI_CLI_HOME` joined `CLAUDE_CONFIG_DIR` in the host env allowlist
(`drivers/host_exec.py`): locations, not credentials. Gemini's sign-in check now honours
`GEMINI_CLI_HOME`.

### Data

`agent_accounts` (064): `id, tenant_id, driver (claude_code|codex|gemini|opencode), name
(unique per tenant+driver), kind (subscription|api_key|vertex), home_dir, secret_ref (a
vault_secrets id), secret_set_at, identity_masked, identity_hash (HMAC-SHA256 under a key
derived from the vault key; unique per tenant+driver when set), enabled, priority,
cooldown_until, last_error (scrubbed, 200 chars), last_used_at, properties (JSONB:
vertex project/region, model), created_at, updated_at`.
`agent_account_limits` (064): `account_id (cascade), window, used_percent, window_minutes,
resets_at, status (allowed|warning|rejected), source (run|probe), observed_at`, unique
`(account_id, window)`.

Supported kinds: claude_code subscription/api_key/vertex; codex subscription/api_key;
gemini subscription/api_key/vertex; opencode none yet (parked, its login location is
unverified). Homes: `<driver_accounts_home_root>/<tenant>/<driver>/<id>`, every level
0700, created by the server; an API key is stored in the vault with `secret_type=token`
and `allowed_origins` = the provider's API origin, so its handle resolves nowhere else.
A run's environment = the host allowlist, minus every credential variable of that driver
(so `driver_host_env_passthrough` cannot leak a default key into an account run), plus the
account overlay; an overlay name not on the driver×kind allowlist is refused.

### API (`/api/v1/kernel/agent-accounts`)

| Route | Who | Body → response `data` |
|---|---|---|
| `GET ?driver=` | tenant | → `{accounts: Account[]}` in pool order |
| `GET /limits?driver=` | tenant | → `{accounts: Limits[]}` |
| `GET /{id}` | tenant | → `Account` (404 for another tenant's id or a malformed one) |
| `GET /{id}/limits?refresh=` | tenant; `refresh=true` owner | → `Limits` (+ `refresh: {kind, reason?, observed_at?}`) |
| `GET /{id}/home` | owner | → `{id, driver, home_dir, home_root, env: {CODEX_HOME: …}, login_command: ["codex","login"]}` — `home_root` is `driver_accounts_home_root`, absolute and normalised (`~` expanded, symlinks resolved), so a client can check `home_dir` lies under it |
| `POST` | owner | `{driver, name, kind, enabled?, priority?, identity?, properties?}` (unknown fields → 422, so a key cannot ride along) → 201 `Account`; 400 driver/kind/name/properties, 409 name or identity taken |
| `PATCH /{id}` | owner | `{name?, enabled?, priority?, identity? ("" clears), properties?}` → `Account` |
| `POST /{id}/enable`, `/{id}/disable` | owner | → `Account` |
| `POST /{id}/cooldown/reset` | owner | → `Account` (cooldown and last_error cleared) |
| `PUT /{id}/secret` | owner | `{value}` → `Account` with `has_secret: true`; write-only into the vault, the previous key revoked; 400 for a non-api_key account |
| `DELETE /{id}/secret` | owner | → `Account` (key revoked, ciphertext destroyed) |
| `PUT /pool/{driver}` | owner | `{order: [id, …]}` → `{driver, accounts}`; named ids first (priorities 10, 20, …), the rest keep their order; 400 unknown or repeated ids |
| `DELETE /{id}?wipe_home=` | owner | → `{id, deleted, home_removed}`; its key is revoked |

`Account`: `{id, driver, name, kind, enabled, priority, identity (masked), has_secret,
secret_set_at, has_home, properties, status (ready|cooling_down|error|disabled),
cooldown_until, last_error, last_used_at, created_at, updated_at}`.
`Limits`: `{account_id, driver, name, windows: [{window, used_percent, window_minutes,
resets_at, status, source, observed_at}], observed_at, unavailable_reason?}`.
Owner = `api/approval_identity.owner_only` (an owner key, a paired phone, or auth off).
Run metadata gains `account: {id, name, kind, env: [names], cooldown_until?, next?}`.

### Sign-in stays on the host (race-app)

life-graph never logs a CLI in. race-app's PTY runs `login_command` from `GET .../home`
with `env` set (`CLAUDE_CONFIG_DIR=<home> claude auth login`, `CODEX_HOME=<home> codex
login`, `GEMINI_CLI_HOME=<home> gemini`); the CLI writes its login into the home and
life-graph only ever points the next run at it.

### Part 2 hooks (the design; built as specified in "Phase 3b part 2" below)

1. **Re-dispatch on a rate limit.** In the dispatcher, after `_run_driver` (and the
   bounce), when `result.metadata.failure.kind == "rate_limited"` and
   `result.metadata.account.next.id` is set: dispatch once more on the same packet and
   worktree (the driver's hook will pick `next` itself, the cooled account now being
   skipped), at most once per pool account per task, prompt = original instruction +
   "a previous attempt was interrupted by a rate limit; inspect the current changes in
   this worktree and continue" (race-app §9.3). Sessions are per home, so this is a new
   session, not a resume. Never on `auth`/`other`.
2. **Park until reset.** When the failure is `rate_limited` and there is no next account
   (`next` null or `{state: cooling}`; or the refusal with `account_pool.state=cooling`),
   set the task to a `parked` state with `properties.resume_at = failure.resets_at` instead
   of failed; the runner re-queues it at that time (a scheduler check, in
   `services/dev/tasks.py`, which this part did not touch).
3. **`continue_task(task_id, feedback)`** (service function in `services/dev/`): load the
   task's last run metadata (`driver`, `session_id`, `account.id`, `workdir`), require that
   the worktree was kept (today `remove_worktree` runs after every dispatch: part 2 must
   keep it for tasks that may be continued, or land the branch and re-create a worktree on
   it — a Gemini session is bound to the directory path, Codex and Claude sessions to the
   home), build a packet whose `project_context.path` is that worktree with
   `isolation=False`, and call `driver.resume(packet, workdir, session_id, feedback,
   account_id=account.id)`; then run the same verify/land chain as a dispatch. Refuse when
   the session or worktree is gone (fall back to a fresh dispatch with the feedback).
4. **Subscription budget (risk D4).** Subscription runs report $0, so the Governor's monthly
   cap does not see them. Part 2: count runs and tokens per account per window from
   `agent_account_limits` + run metadata, and refuse (or park) an unattended dispatch when
   an account is above a configured share of its window (e.g. ≥ 90 % of `five_hour`), so
   nightly work cannot exhaust the owner's interactive quota. An API-key account's real
   spend is in `metadata.cost_usd` (claude) and should be booked to the Governor as `api`
   billing: `ClaudeCodeDriver.billing` still reads `driver_claude_code_auth`, not the
   account's kind.

### Tasks

- [x] Migration 065, models `AgentAccount` / `AgentAccountLimit`
- [x] `services/agent_accounts/*`: catalog, env overlay + allowlist, homes, identity, pool,
      limits (Codex windows + app-server probe ported from stablyai/orca, Claude passive),
      service
- [x] `drivers/accounts_hook.py`; codex/gemini (via `cli_driver`) and claude_code use it
- [x] Resume: `codex exec resume`, `gemini --resume`, `claude --resume`; `driver.resume()`
- [x] API + owner gates; unit tests (fakes, fake CLIs, fake app-server)
- [x] Part 2: re-dispatch, park, `continue_task`, budget D4 (see "Phase 3b part 2")
- [ ] Record a real account run, resume and probe once the owner signs a CLI in

## Phase 3b part 2 (2026-11-27)

> **Status: Built, fixture-tested.** Branch `race/migration`. Code: `drivers/run_health.py`
> (dispatcher mixin: rotation, stall retries, nudges, park decision, spend booking, worktree
> retention), `drivers/continue_run.py` (`continue_dispatch`), `services/dev/continuation.py`
> (`continue_task`), `services/agent_accounts/budget.py` (D4), `drivers/accounts_hook.py`
> (`unattended`, `preview`, `billing_of`), parking in `services/dev/tasks.py` and the runner's
> `housekeep()` (`services/dev/runner.py`). **No migration**: `agent_tasks.status` has no
> check constraint (`parked` is a new value), and every new record lives in
> `agent_tasks.properties` or on approvals. Everything is **off by default**; with the
> defaults a dispatch makes exactly one driver call and books, fails and cleans up exactly as
> before. Not yet run against a signed-in CLI (as part 1). Rebuilt from race-app's
> `TEAMWORK.md` §3, `providers/local/{run-health,park-manager,engine-control}.ts`.

### Requirements

**Re-dispatch on a rate limit** (needs `driver_accounts_enabled`)
- GIVEN a driver run fails with `metadata.failure.kind == "rate_limited"` AND
  `metadata.account.next.id` is set AND that account has not run this task yet THEN the
  dispatcher runs once more in the **same worktree**, pinned to that account
  (`ContextPacket.account_id`), with the prompt *"A previous attempt at this task was
  interrupted by a rate limit. Inspect the current changes in this working tree and continue
  …"*, a hand-off note (the previous attempt's last agent messages, newest kept, ≤ 1500
  characters) and the original task. A new session (sessions live in an account's home).
- At most **one attempt per account per task** (`run.accounts_tried`). Never on `auth` or
  `other` failures. The kill switch and the per-task cost cap are checked first (and the
  Governor, unless the next account is a subscription one).
- Applies to every driver call of a dispatch (first run, bounce, fix rounds, nudges,
  continuations). Each switch is its own attempt: the interrupted run's steps are recorded
  under its attempt, the new run under the next (`run.next_attempt`).
- Recorded: task event `round` (`data.kind = rate_limit_switch`, `from`, `to`, `attempt`,
  `handoff_chars`), EventBus `driver:account:switched` and `driver:run_health:round`, and
  `payload.autonomy.run_health[]` on the PR approval.

**Park until reset** (owner policy `wait_for_reset`, default false)
- GIVEN the final result is still `rate_limited` (no next account, the pool all cooling,
  every account over its D4 share, or a CLI limit without accounts) AND `wait_for_reset`
  THEN `metadata.park = {resets_at, resume_at, reason, budget?}`: `resets_at` = the earliest
  of the account's `cooldown_until` / `failure.resets_at`, `next.retry_at`,
  `account_pool.retry_at` still in the future (else now + `driver_accounts_default_cooldown_minutes`);
  `resume_at = resets_at + 60 s`. The task becomes **`parked`** (status; `properties.park`
  adds `parked_at`, `count`; `properties.parks` counts parks), not failed;
  `completed_at` stays null. At most `MAX_PARKS_PER_TASK = 5` parks, then it fails as before.
- The runner's loop (`DevTaskRunner.housekeep`, before every fill, i.e. each wake-up or
  ≤ 60 s) calls `release_parked`: a parked task whose `resume_at` passed goes back to
  `queued` (`properties.unparked = {at, resume_at, note}`) and runs as a fresh dispatch
  (new worktree; its WIP, kill-switch and budget checks apply). Rows are the only state, so
  a restart resumes parks on time. A paused tenant's tasks stay parked.
- Default off: a rate-limited task fails as before (and the free-cloud re-queue in
  `_after_queued_run` is unchanged).
- `parked` counts as open (duplicate check), is cancellable (cancelled at once), has stage
  `parked`, and is not a terminal status for the event stream.

**Run health** (owner policy, default 0)
- `max_nudges` (0–3): an edit task (`code`, `code_change`) whose run succeeded, changed no
  file, and whose output is plan-only or a question (≥ 2 list items, or a `?`) gets *"You
  described the plan but changed no files. Carry it out now; don't ask for confirmation."* —
  a resume of its session (a re-dispatch with the text prepended when there is none) — then
  the tamper and file checks run again; out of nudges → today's "changed no files" failure.
  An `empty` answer is not nudged. *(2026-11-28: a run that explicitly says nothing needed
  changing is not nudged and ends as "no changes needed" — see
  [the amendment](#amendment-2026-11-28--no-changes-needed-outcome-step-4c).)*
- `max_stall_retries` (0–3): a driver call that timed out (`exit_status == "timeout"`) is
  retried after 10 s × 2ⁿ (cap 5 min) as *"Your previous run stopped responding. Continue
  from the current state of the worktree."* (resume, else re-dispatch). Gated before the wait
  and again after it.
- Each round is gated by `_round_allowed` (kill switch, per-task cost cap, Governor — the
  Governor skipped for a subscription-account run), recorded as the next attempt with a task
  event `round` (`nudge` / `stall_retry`; `stall_wait` before the backoff), EventBus
  `driver:run_health:round`, and `payload.autonomy.run_health[]`. A refused round emits a
  `round` event with `skipped: true` and the reason. Rounds never approve.

**`continue_task(task_id, feedback, reason)`** (`driver_continue_enabled`, default false)
- Retention: with the flag on, a dispatch's worktree is **kept** (not removed) when the run
  left a CLI session, the worktree is intact, the run did not park, and the task row exists;
  `properties.continuation = {worktree, origin, driver, session_id, account_id, branch,
  base_commit, verify_chain, rounds, kept_at, keep_until}`. The runner sweeps kept worktrees
  every 15 min (`sweep_kept_worktrees`): removed once the task is not queued/running/parked,
  its PR is not open or awaiting approval (stage not `awaiting_pr` / `pr_open` /
  `awaiting_merge`) and `keep_until` (`kept_at + driver_continue_keep_hours`) passed; all of
  them when the flag is off.
- `continue_task` refuses (409 unless noted, nothing changes): `continue_disabled`,
  `not_found` (404), `no_feedback` (422), `busy` (queued/running/parked), `not_continuable`
  (cancelled, or PR merged/closed), `no_session`, `no_workdir` (gone or not intact),
  `resume_unsupported`, `paused` (kill switch). Otherwise it queues the task (`start_now`,
  `interactive`, `properties.continue_request = {feedback ≤ 8000, reason ≤ 200, requested_at}`).
- The runner then calls `TaskDispatcher.continue_dispatch`: WIP check, the packet with the
  worktree as its path (`isolation=False`), the budget gate (interactive), `driver.resume`
  on the **same session and account** with the feedback, then the normal chain: tamper and
  file checks (with nudges), the verifier chain (bounce, fix rounds, review stages), landing,
  the PR approval, stats. Landing commits on top of `lg/task-<id>` (same branch).
- **Single approval path**: the approval describes the change from the task's first
  `base_commit` (the whole branch, as its PR shows it). A **pending** `driver_pr` approval of
  the task is updated in place; once its PR is open a new `driver_pr` approval is filed
  ("Update PR: …", `payload.continuation = {round, previous_approval, pr_url}`): approving
  it pushes the branch into the **same** PR (`open_pull_request` finds it by branch), never a
  second PR. A pending `driver_merge` of the task is rejected (`resolved_by = "system:
  continued"`): it names the old head, which `merge_pull_request` would refuse anyway. The
  worktree is kept again for the next round (`rounds` + 1).

**Subscription budget (risk D4)** (needs `driver_accounts_enabled`)
- An **unattended** run (`packet.unattended = not interactive`) skips a subscription account
  whose fullest live window reading (`agent_account_limits`; a reading counts until its
  `resets_at`, or 5 h after `observed_at` when it has none) is ≥
  `driver_accounts_subscription_max_share` × 100 %, falling to the next account in pool
  order. None left → refused `exit_status=subscription_budget`, `failure = {kind:
  rate_limited, reason: subscription_budget, resets_at: earliest window reset}`,
  `account_pool = {state: over_budget, retry_at}` → parks when `wait_for_reset`, else fails.
  A pinned (resumed/rotated) account over its share refuses the same way. Attended runs and
  a share of 1.0 are never budgeted.
- The $ Governor applies to api-billed runs only: the budget gate previews the account
  (`accounts_hook.preview`) and does not consult the Governor for a subscription account (or
  when every account is over budget — the driver refuses); spend of a run on a subscription
  account is not booked (`metadata.account` present and `metadata.billing ==
  "subscription"`). API-key and Vertex accounts stay under the dollar cap. Without accounts
  every run books exactly as before.
- `metadata.billing` follows the chosen account's kind (`subscription` → `subscription`,
  `api_key`/`vertex` → `api`) for codex/gemini and **claude_code** (whose static `billing`
  attribute, used for driver selection, still reads `driver_claude_code_auth`).
- The decision is a task event `budget` (account, kind, window share, skipped accounts and
  why), and `metadata.account.budget` on the result.

### Settings

| Where | Name | Default | Meaning |
|---|---|---|---|
| autonomy policy (global; project `null` = global) | `max_nudges` | 0 | 0–3 nudges per dispatch |
| autonomy policy | `max_stall_retries` | 0 | 0–3 stall retries per driver call chain |
| autonomy policy | `wait_for_reset` | false | park instead of fail on a plan limit |
| env `LIFE_GRAPH_DRIVER_ACCOUNTS_SUBSCRIPTION_MAX_SHARE` | `driver_accounts_subscription_max_share` | 0.9 | D4 share (only with accounts on) |
| env `LIFE_GRAPH_DRIVER_CONTINUE_ENABLED` | `driver_continue_enabled` | false | keep worktrees; allow continue_task |
| env `LIFE_GRAPH_DRIVER_CONTINUE_KEEP_HOURS` | `driver_continue_keep_hours` | 24 | retention after the last run (PR open keeps longer) |

Re-dispatch on a rate limit has no switch of its own: it is part of `driver_accounts_enabled`
(off by default). The policy fields appear in `GET /autonomy/policy` bodies,
`effective` and `limits.bounds` (`max_nudges`, `max_stall_retries`: `{min: 0, max: 3}`).

### API

| Route | Who | Body → `data` |
|---|---|---|
| `POST /kernel/drivers/tasks/{id}/continue` | owner | `{feedback (1..8000), reason? (≤200)}` (unknown fields 422) → the task (`status: queued`); 409 `"<code>: <message>"`, 404 |
| `POST /kernel/drivers/tasks/{id}/resume` | owner | → the task + `resumed: true` (front of the queue); 409 when not parked, 404 |
| `GET /kernel/drivers/tasks/parked` | tenant (also a paired phone) | → `{tasks: [task…], count}`, soonest `resume_at` first |
| `GET /kernel/drivers/tasks[/{id}]` (existing) | tenant | each task gains `park` (when parked) and `continuation: {driver, branch, rounds, kept_at, keep_until} \| null` (no paths) |

### Events

EventBus: `driver:account:switched` (`tenant_id, task_id, driver, from_account,
to_account`), `driver:run_health:round` (`tenant_id, task_id, kind, attempt, …`),
`driver:task:parked` (`tenant_id, task_id, resume_at, reason`), `driver:task:unparked`
(`tenant_id, task_id, by: schedule|owner`), `driver:task:continued` (`tenant_id, task_id,
reason, driver`). Task events: `round` (`rate_limit_switch`, `stall_wait`, `stall_retry`,
`nudge`, `park`, `continue`; `skipped` with a reason), `budget`, and `status` `parked` /
`queued` with `unparked` or `continue` data.

### What race-app's UI needs

Settings → Autonomy: the three run-health fields (global and per project, `null` = inherit).
Task view: status/stage `parked` with `park.resume_at` ("waiting for the plan limit to reset
at HH:MM"), a **Resume now** button (`POST …/resume`), and a parked list
(`GET …/tasks/parked`); the `round` and `budget` timeline events; **Request changes** / the
PR-feedback loop call `POST …/continue` (show `continuation.rounds`, `keep_until`, and the
409 reason, falling back to a new task on `no_session` / `no_workdir`).

### Not in part 2

A parked task re-runs from a fresh worktree (the interrupted attempt's uncommitted work is
not carried over). Driver-backed reviewers; PR-feedback polling itself (race-app calls
continue). Integration tests against Postgres and recorded runs of signed-in CLIs.

### Tasks

- [x] `drivers/run_health.py`: `_drive` (rotation, stall retries), nudges, park decision, `_book_spend`, retention
- [x] Autonomy policy fields `max_nudges`, `max_stall_retries`, `wait_for_reset`
- [x] `parked` status, `release_parked` / `resume_parked` / `list_parked`, runner `housekeep`
- [x] `continue_task` + `continue_dispatch`, kept worktrees + sweep, continuation approvals
- [x] D4: `services/agent_accounts/budget.py`, `acquire(unattended)`, `preview`, billing per account
- [x] API, events, unit tests (`test_run_health.py`, `test_phase3b_part2.py`, `test_phase3b_part2_api.py`)
- [ ] Integration test against Postgres; a real rotation, park and continue on signed-in CLIs

## Phase 4b (2026-11-27): dependencies, parallel plans, PR feedback loop, arena

> **Status: Built, fixture-tested.** Branch `race/automation-teams` (off `race/migration`).
> Migration `067_dev_task_groups_pr_watches.py` (revises 066, dev automation). Code: `services/dev/dependencies.py`,
> `services/dev/team_scope.py`, `services/dev/teams.py`, `drivers/seed_branches.py`,
> `services/dev/pr_feedback_signals.py`, `services/dev/pr_watch.py`, `services/dev/arena.py`,
> `services/dev/automation_gate.py`, `models/dev_groups.py`, `api/drivers_automation.py`;
> hooks in `services/dev/tasks.py` (create, claim, run options, serialize), `drivers/dispatcher.py`
> (seed, hand-off, pinned driver, `hold_auto`), `drivers/plan_spec.py` (`Files:`),
> `services/approvals.py` (team fan-out), `services/dev/runner.py` (`housekeep`). Everything is
> **off by default**, and nothing in this phase approves, merges or pushes on its own: the
> one approval a team or a race produces is an ordinary pending `driver_pr`. Rebuilt from
> race-app's `docs/specs/TEAMWORK.md` §4, §7, §8, `automation/{pr-watch,team}/**`,
> `providers/local/{dependencies,handoff-branch}.ts`, `agents/worktree-seed.ts` and
> `arena/arena-manager.ts` (the owner's code; nothing third-party was ported). Not yet run
> against a real GitHub PR or signed-in CLIs.

### The gate before every automatic action

Two things in this phase start work without anyone pressing a button: releasing a held task
once its dependencies finished, and a PR-feedback round. Before each,
`automation_gate.blockers(tenant, driver, account_id)` asks, in order: the **kill switch**
(paused tenant → wait), the **subscription share** (D4; with agent accounts on, the driver's
pool — or the pinned account — previewed as an unattended run: `over_budget`, `cooling` or an
unreadable pool → wait), and the **Governor** as an unattended spend (skipped when the run is
billed to a subscription account). A refusal is recorded (`dependency_wait.blocked`,
`pr_watches.last_error = "Waiting: …"`) and retried on the next pass; nothing is dropped.
Team workers and racers are ordinary queued tasks: the claim checks the kill switch and the
dispatch applies the Governor (unattended workers) and D4 as for any task.

### Requirements

**Task dependencies** (no switch: nothing changes unless a task is created with `depends_on`)
- GIVEN `POST /kernel/drivers/tasks` with `depends_on: [task ids]` (≤ 20) WHEN an id is not a
  dev task of this tenant (another tenant's id reads as unknown), not a UUID, or the
  dependencies' own `depends_on` graph has a cycle THEN 422 `"<invalid|unknown|cyclic>: …"` and
  nothing is created.
- GIVEN it is valid THEN the task is `queued` with `properties.depends_on`,
  `deps_pending: true` and `dependency_wait = {waiting_on, since}`; the claim skips it.
- WHEN every dependency reached a **work-finished** stage — `awaiting_pr`, `pr_open`,
  `awaiting_merge`, `merged`, or `landed` (a branch hand-off), or `completed` with nothing to
  approve — AND the gate allows THEN the hold is lifted (`dependencies_met_at`) and it runs like
  any queued task (its own `start_now`/`interactive` kept).
- WHEN a dependency is `failed` / `cancelled` / `timeout`, its PR was rejected or closed, or its
  row is gone THEN the task is `cancelled` with `error = "Dependency <id> failed (<stage>)"` and
  `properties.dependency_failed = {task_id, stage}`; its own dependents follow on the next pass.
- The runner's loop (`DevTaskRunner.housekeep`, before every fill: each wake-up, a task ending,
  or ≤ 60 s) calls `release_dependencies`. Rows are the only state: a restart resumes exactly.

**Parallel plans — teams** (`driver_team_max_parallel`, default 1)
- GIVEN the default 1 THEN plan fan-out is exactly as before: tasks run one at a time, each
  waiting for the previous one to merge, each with its own PR approval.
- GIVEN `driver_team_max_parallel > 1` WHEN a plan is generated THEN the plan prompt also asks
  each task to end with `Files: <paths or globs>` (spec format extension, parsed by
  `plan_spec.parse_task_files`: comma/space separated, backticks and `(AC-n)` ignored; `*` =
  one segment part, `**` = any depth, `?` = one character).
- GIVEN an approved plan with ≥ 2 tasks of which at least one declares files THEN it becomes a
  **team** (`dev_task_groups` row, kind `team`, id = `plan_group_id`):
  - one **worker** dev task per plan task (`origin: team_worker`, `team_role: worker`,
    `team_files`, `team_max_parallel`), queued unattended; a task whose scope overlaps an
    earlier task's (`team_scope.overlap_dependencies`: same path, nested directory, glob match;
    two globs by literal prefix; **an undeclared scope overlaps everything**) gets `depends_on`
    on it and `seed_from` it;
  - one **integration** task (`origin: team_integration`, `team_role: integration`)
    `depends_on` and `seed_from` every worker, checked against every acceptance criterion the
    spec binds.
- The claim runs at most `team_max_parallel` workers of one team at once (also bounded by the
  project WIP limit of 2, the tenant's 5 and `dev_runner_max_concurrency`); team tasks do not
  take the runner's single unattended slot and skip the sequential plan gate.
- A worker dispatch: its worktree first gets the hand-offs of its `seed_from` workers applied
  (`git apply --3way`) and **committed** as a seed commit (any that does not apply cleanly →
  the worker fails `exit_status = seed_failed`, nothing runs); then the normal chain; landing
  commits on `lg/task-<id>` and stops there: **no `driver_pr` approval, no PR** (branch
  hand-off). `result.metadata.handoff = {task_id, branch, base_commit, head_commit}` is its own
  delta (base = the seed commit). Its worktree is never kept for `continue_task`.
- The integration dispatch: every worker's hand-off is applied in plan order with
  `git diff --binary base head | git apply --3way`, **left uncommitted** (index reset), conflicts
  as markers; the agent gets the report (applied / CONFLICTS in … / could not be applied); after
  the run a file that was conflicted and still holds `<<<<<<<` / `>>>>>>>` / `|||||||` lines fails
  it (`stop_reason = unresolved_conflicts`); then the normal verifier chain, landing and the
  plan's **single** `driver_pr` approval (auto-open/auto-merge rules as for any task).
- Any worker `failed` / `cancelled` / `timeout` THEN `teams.reconcile` (runner loop) cancels
  every other open team task (queued at once, running through its runner), the team is
  `failed` with the reason, the owner is told once (`approval:filed`, kind `plan_stopped`) and
  `driver:team:failed` fires. Re-approving the plan starts a new team.
- Team status: `running` → `integrating` (integration task running) → `awaiting_approval`
  (its PR approval filed) | `failed`.

**PR feedback loop** (`driver_pr_feedback_enabled`, default false)
- Watches dev tasks with status `completed`, stage `pr_open` / `awaiting_merge`, a `driver_pr`
  approval with a `pr_url`, and a kept worktree + session (`properties.continuation`, needs
  `driver_continue_enabled`). One `pr_watches` row per task; `since` = when the PR approval
  was resolved.
- Every `driver_pr_feedback_poll_minutes` (ARQ cron `poll_pr_feedback`, every 5 min; or the
  owner's `POST …/pr-watch/poll`, which ignores the interval) it reads, **read only**:
  `gh pr view <url> --json state,mergeable,headRefOid,statusCheckRollup,reviews,comments`,
  `gh api repos/<o>/<r>/pulls/<n>/comments?per_page=100` (when review comments are on) and
  `gh run view <run> --repo <o>/<r> --log-failed` (≤ 3 failing Actions checks; tail 60 lines /
  3000 chars).
- New = not in `seen` and not older than `since`: failing checks on the head SHA (key
  `check:<sha>:<name>`; the same check failing on a new head is new), reviews requesting
  changes or commented with a body (`review:<id>`), PR comments (`comment:<id>`), inline review
  comments (`inline:<id>`), `mergeable == CONFLICTING` (`conflict:<sha>`). Life Graph's own text
  (starts with "Life Graph" / `<!-- life-graph`) and approvals are skipped. Each of the three
  kinds has its toggle.
- New feedback → the gate → **one** message (failing checks with log tails, comments with
  author/path/line, the conflict with "merge `origin/<base>`", "don't push") →
  `continue_task(task, feedback, reason="pr_feedback: <summary>")`; the row goes
  `feeding_back`, `rounds + 1`, the keys join `seen`.
- One round in flight: while the task is queued/running/parked or its newest `driver_pr`
  approval ("Update PR") is pending, nothing is read; once that update was approved (pushed)
  the watch is `watching` again and is read at once. A round that ended failed → `needs_you`.
- `rounds ≥ driver_pr_feedback_max_rounds` and still new feedback → `needs_you`, notified once
  (`approval:filed`, kind `pr_feedback`). `MERGED` → `merged`, `CLOSED` → `closed`, worktree or
  session gone / not a GitHub URL / `continue_task` refused other than `busy` → `stopped` with
  the reason; `busy` waits; `paused` waits. The owner's stop → `stopped`, never re-watched.
- Concurrency: each check holds its `pr_watches` row `FOR UPDATE SKIP LOCKED` across the
  hand-over, so the cron and an API poll never send the same round.

**Arena** (`driver_arena_enabled`, default false)
- `POST /kernel/drivers/arena` (owner) with 2–5 racers (a driver name, or `{driver, account_id}`
  — the same driver on two accounts is two racers): one dev task per racer, the same
  instruction, `start_now` (the owner asked), `properties.arena_id`, `driver_pin`,
  `account_pin`; the duplicate check is per racer (`dedupe_scope`). Unknown driver or an account
  that is not this tenant's account of that driver → 422.
- A racer runs on exactly its driver (unavailable → the dispatch fails, never another driver)
  and account (`ContextPacket.account_id`; the D4 preview uses it), and its result never
  auto-opens or auto-merges (`hold_auto`): at most a pending `driver_pr`.
- `GET …/arena/{id}`: status `racing` (a racer still queued/running/parked) → `ready_to_pick` →
  `decided`; per racer: status, stage, error, driver it ran on, model, cost, duration, rounds
  (verification attempts), `verified`, checks, diff size (`files`, `lines` from the approval's
  change summary), branch, approval, and the driver's 30-day scorecard.
- `POST …/arena/{id}/pick {task_id}` (owner): the winner must have landed (stage
  `awaiting_pr` / `pr_open` / `awaiting_merge` / `merged`; else 409 `not_ready`); every other
  racer still open is cancelled, their pending `driver_pr` / `driver_merge` approvals are
  rejected (`resolved_by = "system: arena"`); the winner's approval is untouched and proceeds
  normally. Decided → 409 `decided`; not a racer → 422.

### Data (migration 067)

```sql
CREATE TABLE dev_task_groups (
    id          UUID PRIMARY KEY,            -- a team's id = its plan_group_id
    tenant_id   VARCHAR(64) NOT NULL,
    kind        VARCHAR(16) NOT NULL,        -- team | arena
    project_id  UUID,
    status      VARCHAR(24) NOT NULL,        -- team: running|integrating|awaiting_approval|failed
                                             -- arena: racing|decided|cancelled
    title       VARCHAR(200) NOT NULL DEFAULT '',
    source_ref  VARCHAR(64),                 -- team: the plan task id
    properties  JSONB NOT NULL DEFAULT '{}', -- team: max_parallel, scopes, waves, worker_ids,
                                             --   integration_task_id, reason, history
                                             -- arena: instruction, racers[{task_id,driver,account_id}],
                                             --   winner_task_id, decided_at, cancelled_task_ids,
                                             --   rejected_approval_ids
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_dev_task_groups_state ON dev_task_groups (tenant_id, kind, status);

CREATE TABLE pr_watches (
    id              UUID PRIMARY KEY,
    tenant_id       VARCHAR(64) NOT NULL,
    task_id         UUID NOT NULL REFERENCES agent_tasks(id) ON DELETE CASCADE,
    pr_url          VARCHAR(300) NOT NULL,
    state           VARCHAR(20) NOT NULL DEFAULT 'watching',
                    -- watching|feeding_back|needs_you|merged|closed|stopped
    rounds          INTEGER NOT NULL DEFAULT 0,
    seen            JSONB NOT NULL DEFAULT '[]',   -- dedupe keys already handed back
    since           TIMESTAMPTZ,
    last_checked_at TIMESTAMPTZ,
    last_feedback   VARCHAR(300),
    last_error      VARCHAR(300),
    notified_at     TIMESTAMPTZ,
    properties      JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_pr_watches_task UNIQUE (tenant_id, task_id)
);
CREATE INDEX ix_pr_watches_state ON pr_watches (state);
```

Dev-task `properties` (no migration): `depends_on`, `deps_pending`, `dependency_wait
{waiting_on, since, blocked?}`, `dependencies_met_at`, `dependency_failed {task_id, stage}`;
team: `team_role` (worker|integration), `team_files`, `team_max_parallel`, `seed_from`, plus
the existing `plan_task_id` / `plan_group_id` / `plan_task_index` / `plan_task_count`;
arena: `arena_id`, `arena_index`, `driver_pin`, `account_pin`. Run metadata: `handoff`,
`seed` (on `seed_failed`); task events `seed`, `handoff`, `dependencies`, `pr_watch`.

### Settings

| Env (`LIFE_GRAPH_…`) | Setting | Default | Meaning |
|---|---|---|---|
| `DRIVER_TEAM_MAX_PARALLEL` | `driver_team_max_parallel` | 1 | workers of one plan at once; 1 = sequential fan-out as before |
| `DRIVER_PR_FEEDBACK_ENABLED` | `driver_pr_feedback_enabled` | false | the PR feedback loop |
| `DRIVER_PR_FEEDBACK_POLL_MINUTES` | `driver_pr_feedback_poll_minutes` | 10 | per-PR read interval |
| `DRIVER_PR_FEEDBACK_MAX_ROUNDS` | `driver_pr_feedback_max_rounds` | 3 | rounds per PR, then `needs_you` |
| `DRIVER_PR_FEEDBACK_ON_FAILING_CHECKS` | `driver_pr_feedback_on_failing_checks` | true | hand back failing checks |
| `DRIVER_PR_FEEDBACK_ON_REVIEW_COMMENTS` | `driver_pr_feedback_on_review_comments` | true | hand back reviews / comments |
| `DRIVER_PR_FEEDBACK_ON_CONFLICTS` | `driver_pr_feedback_on_conflicts` | true | hand back merge conflicts |
| `DRIVER_ARENA_ENABLED` | `driver_arena_enabled` | false | `POST …/arena` (409 when off) |

The PR loop also needs `driver_continue_enabled` (worktrees kept) and a logged-in `gh`.

### API (`/api/v1/kernel/drivers`)

| Route | Who | Body → `data` |
|---|---|---|
| `POST /tasks` (existing) | tenant | + `depends_on?: [uuid] (≤20)` → the task; 422 `"unknown: …"` / `"cyclic: …"` / `"invalid: …"` |
| `GET /tasks[/{id}]` (existing) | tenant | each task + `depends_on: []`, `dependency_wait: {waiting_on, since, blocked?} \| null`, `dependency_failed`, `team: {group_id, role, files, seed_from} \| null`, `arena: {id, index, driver, account_id} \| null`, `handoff` |
| `GET /plans/{id}` (existing) | tenant | + `team: {group_id, status, reason, max_parallel, waves, workers: [Row], integration: Row} \| null`; a held child's `gate = {state: wait, waiting_on}` |
| `GET /pr-watch` | tenant | → `{settings: {enabled, poll_minutes, max_rounds, on_failing_checks, on_review_comments, on_conflicts}, watches: [Watch]}` |
| `POST /pr-watch/poll` | owner | → `{enabled, discovered, checked, outcomes: {sent, quiet, in_flight, blocked, needs_you, merged, closed, stopped, not_due, error}}` (`{enabled: false, checked: 0}` when off) |
| `POST /pr-watch/{task_id}/stop` | owner | → `Watch` (`state: stopped`); 404 not watched, 400 not a UUID |
| `POST /arena` | owner | `{project_id, instruction (5..8000), drivers: [name \| {driver, account_id?}] (2..5), persona_name? = "code-fixer"}` (unknown fields 422) → 202 `Arena`; 409 `arena_disabled`, 422 unknown driver/account, 404 project/persona |
| `GET /arena/{id}` | tenant | → `Arena`; 404 |
| `POST /arena/{id}/pick` | owner | `{task_id}` → `Arena` + `cancelled_task_ids`, `rejected_approval_ids`; 409 `decided` / `not_ready`, 422 `not_a_racer`, 404 |

`Row` (team): `{task_id, index, title, files, depends_on, status, stage, waiting, branch,
handoff, error}`. `Watch`: `{task_id, pr_url, state, rounds, max_rounds, seen (count), since,
last_checked_at, last_feedback, last_error, notified_at}`. `Arena`: `{id, project_id,
instruction, status (racing|ready_to_pick|decided), winner_task_id, decided_at, created_at,
racers: [{task_id, driver, account_id, ran_on, model, status, stage, error, cost_usd,
duration_ms, rounds, verified, checks, diff: {files, lines, kind} | null, branch,
approval: {id, status, title} | null, scorecard: {runs, success_rate, bounce_rate, merged,
cost_per_merged} | null}]}`.

Example — `POST /kernel/drivers/arena`:

```json
{"project_id": "5b0c…", "instruction": "Make the importer stream instead of loading the whole file",
 "drivers": ["claude_code", {"driver": "codex", "account_id": "a6f1…"}]}
```

### Events

EventBus: `driver:task:dependencies_met` (`tenant_id, task_id`), `driver:task:dependency_failed`
(`tenant_id, task_id, dependency, stage`), `driver:team:started` (`tenant_id, group_id,
plan_task_id, workers, max_parallel`), `driver:team:integrating`, `driver:team:awaiting_approval`,
`driver:team:failed` (`tenant_id, group_id, plan_task_id, status, reason,
integration_task_id`), `driver:pr_watch:feedback` (`tenant_id, task_id, round, summary,
pr_url`), `driver:pr_watch:needs_you` (`tenant_id, task_id, reason`), `driver:pr_watch:stopped`
(`tenant_id, task_id, state, reason`), `driver:arena:created` (`tenant_id, arena_id, racers,
drivers`), `driver:arena:decided` (`tenant_id, arena_id, winner_task_id, winner_driver,
cancelled, rejected`). Notifications reuse `driver:approval:filed` with kind `plan_stopped`
(team failed) and `pr_feedback` (needs you). Task events: `dependencies`, `seed`, `handoff`,
`pr_watch`, and `status cancelled` with `dependency_failed`.

### What race-app's UI needs

- **New task**: a "Depends on" picker (task ids → `depends_on`); show the 422 reason. Task view:
  "waiting for N tasks" from `dependency_wait.waiting_on` (and `blocked` — "kill switch on" /
  "over the plan share" / "budget"), "cancelled: dependency X failed" from `dependency_failed`.
- **Settings → Automation**: `driver_team_max_parallel`, the PR-feedback switches and the arena
  switch are env settings for now (read-only display from `GET …/pr-watch` `settings`).
- **Plan view** (`GET …/plans/{id}`): when `team` is set, a team board — workers with files,
  status/stage, branch, "waiting on", grouped by `waves`; the integration task; team status and
  `reason`; the one approval is the integration task's.
- **PR feedback**: a watched-PRs list (`GET …/pr-watch`): state, rounds / max_rounds, last
  feedback, last error ("Waiting: …"), "Poll now" (`POST …/poll`), "Stop" per PR; `needs_you`
  appears in the inbox via the `pr_feedback` notification.
- **Arena**: "Race this" on a new task (drivers/accounts multi-select → `POST …/arena`), a side
  by side page polling `GET …/arena/{id}` (diff size, verified, cost, rounds, time, scorecard)
  with "Pick winner" (`POST …/pick`), then the winner's normal approval.

### Not in 4b

A lead agent planning a team (the plan task's spec is the plan); retrying one failed worker in
place (re-approve the plan); per-project overrides of the new settings; settings editable at
runtime (they are env); cancelling a whole team or race in one call (cancel each task); racing
plan tasks. Integration tests against Postgres, a real GitHub PR and signed-in CLIs.

### Tasks

- [x] Migration 067, models `DevTaskGroup`, `PrWatch`
- [x] Dependencies: create-time validation (unknown/cyclic 422), hold, release/cancel in the runner loop, API field
- [x] `Files:` scopes, overlap rules, team fan-out, `max_parallel` claim bound, worker hand-off, seeding (`git apply --3way`), conflict-marker guard, integration task, reconcile + failure cancel, team view
- [x] PR feedback loop: gh reader (read only), signals + dedupe, one round in flight, max rounds, merged/closed, gate, cron + API
- [x] Arena: create (pinned drivers/accounts, `hold_auto`), side-by-side view with scorecards, pick
- [x] Automation gate (kill switch, D4 share, Governor); unit tests (`tests/unit/test_phase4b_*.py`, real temp git repo for seeding)
- [ ] Integration tests against Postgres; a real PR round on GitHub; a real team run

## Amendment 2026-11-28 — "No changes needed" outcome (Step 4c)

> **Status: Built.** `life_graph/drivers/dispatcher.py` (`states_no_change_needed`,
> `is_no_changes`, `_check_files_changed`), `services/dev/tasks.py` (`final_status`, `_stage`),
> tests `tests/unit/test_no_changes_outcome.py`.

**Why.** A nightly "health check" schedule ran lint, typecheck and tests on prod, correctly
found nothing to fix and changed nothing; Step 4c failed it ("The run changed no files, so
there is nothing to verify or land"). For recurring maintenance that is a normal outcome, and
recording it as a failure fed the circuit breaker (3 identical failures → automation paused)
and the morning digest's "failed" line.

**Requirement.** GIVEN an edit task (`code`, `code_change`) in a worktree WHEN its run
**finished normally** (`DriverResult.success`: the CLI exited 0 and reported no error — not a
crash, timeout, auth/rate-limit failure or refusal, which are all `success = false`), its diff
is empty, and its final message **explicitly states that nothing needed changing** THEN the
dispatch ends as **"no changes needed"** instead of failing:

- `DriverResult(success=False, error=None, output=<the agent's message>,
  metadata={…, "outcome": "no_changes", "stop_reason": "no_change_needed"})`. `success` stays
  false so nothing downstream treats it as verified work: the verifier chain, Step 6c and
  Step 6b (landing) are skipped, no approval is filed, the `finished` checkpoint is `ok=False`
  (a crash before the row write recovers as failed — fail-closed).
- The dev task row: **`status: "completed"`, `stage: "no_changes"`, `error: null`**, `output`
  = the agent's message (the summary). `result.metadata.outcome = "no_changes"`.
- `driver_stats` is not touched (it counts landed vs failed; this is neither, so it does not
  lower the driver's trust). `driver:result` carries `"outcome": "no_changes"`.
- A fanned-out plan's next task treats a `no_changes` predecessor as done; `depends_on` already
  treated any `completed` task as done.

**The statement** (plain rules, no model call): one of "no (code/source/file/further)
change(s)/fix(es)/edit(s) (are/were) needed/required/necessary/warranted", "nothing (in …) to
fix/change/do/update", "nothing needs fixing/changing", "already (been) fixed/resolved/
implemented/in place/up to date". Disqualified by a question (`?`), a claim of having edited
something ("I fixed …", a line starting "Added/Updated/…"), or refusal words (can't, cannot,
unable to, won't, permission, denied, blocked). "all done", "tests pass" and silence are **not**
statements: such a run still fails as "changed no files" (task ade60cc6's case).

**Run health.** The nudge (`max_nudges`) is unchanged for plan-only/question output: it is
nudged first and becomes "no changes needed" only if a later turn says so; out of nudges it
fails as before. A run whose output already states that nothing needed changing is not nudged.

**Origins.** The same for every origin (schedule, intake, nightly, dashboard/manual,
continuations). The gate is what the run did and said, not who started it: an owner-started
"fix X" whose agent answers "already fixed on master" did not fail either, it is shown to the
owner with the agent's reason, and nothing lands or is approved on the strength of it. Manual
tasks are never counted by the automation breaker in any case.
