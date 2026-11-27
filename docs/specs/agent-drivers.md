# Agent Drivers — Rent the Muscle, Own the Nervous System — Feature Spec

> **Status: Built.** Implemented in `life_graph/drivers/dispatcher.py`. The [2026-11-27 autonomy-policy amendment](#amendment-2026-11-27--autonomy-policy-owner-decision-d2) is built too (migration `063_autonomy_policies`). This document records the design as it was specified; for what the code actually does now, see [docs/STATE.md](../STATE.md) — it is generated from the code.

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
5. **Privacy split is structural.** External drivers never receive memory/preference sections on private-flagged tasks; the local driver exists precisely for this.

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
> (dispatcher mixin), `autonomy/policy/router.py`; migration `063_autonomy_policies`.
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

### Data model

```sql
-- Migration 063_autonomy_policies.py
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

- [x] `autonomy_policies` table + migration 063; model `AutonomyPolicy`
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

> **Status: Part 1 built, fixture-tested.** Migration `064_agent_accounts.py`;
> `services/agent_accounts/` (`catalog`, `env`, `homes`, `identity`, `pool`, `limits`,
> `service`), `drivers/accounts_hook.py`, `api/agent_accounts.py`; resume paths in
> `drivers/cli_driver.py`, `codex.py`, `gemini.py`, `claude_code.py`. Everything is **off
> by default** (`driver_accounts_enabled=false`): with it off, or with no enabled account
> for a driver, every driver runs on the host's single login exactly as in 3a. No CLI was
> signed in on 2026-11-27, so no account run, resume or Codex probe has run against a
> real login; flags were verified with each CLI's `--help` and bundle only. Part 2
> (re-dispatch on a rate limit, parking, `continue_task`, budget D4) is designed below and
> not built. Rebuilt from race-app's `AGENT_CONNECTIONS.md`, `AGENT_ACCOUNTS_USAGE.md`,
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
| `GET /{id}/home` | owner | → `{id, driver, home_dir, env: {CODEX_HOME: …}, login_command: ["codex","login"]}` |
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

### Part 2 hooks (not built; after merge with race/autonomy-policy)

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

- [x] Migration 064, models `AgentAccount` / `AgentAccountLimit`
- [x] `services/agent_accounts/*`: catalog, env overlay + allowlist, homes, identity, pool,
      limits (Codex windows + app-server probe ported from stablyai/orca, Claude passive),
      service
- [x] `drivers/accounts_hook.py`; codex/gemini (via `cli_driver`) and claude_code use it
- [x] Resume: `codex exec resume`, `gemini --resume`, `claude --resume`; `driver.resume()`
- [x] API + owner gates; unit tests (fakes, fake CLIs, fake app-server)
- [ ] Part 2: re-dispatch, park, `continue_task`, budget D4 (above)
- [ ] Record a real account run, resume and probe once the owner signs a CLI in
