# Agent Drivers — Rent the Muscle, Own the Nervous System — Feature Spec

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
- Cost runaway guard: per-task cost cap (default $2) — driver processes killed past cap, task marked failed

### Security Considerations

- External drivers execute with project-scoped workdirs only — never `$HOME`, never the Life Graph repo itself without an explicit persona permission
- Private-flagged tasks strip memory/preference packet sections for external drivers (Story 2); enforced in the packet builder, not by driver goodwill
- Era-8 safety classifier runs on task **intent** before dispatch (existing) and on **artifacts** before landing — destructive-action patterns route to the approval queue regardless of trust level
- Driver subprocess env is allow-listed (no ambient API keys beyond what the driver itself needs)

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
- [ ] `drivers/base.py` protocol + `drivers/registry.py` (availability probing, stats surface)
- [ ] `drivers/claude_code.py` (headless subprocess, JSON parse, worktree isolation option)
- [ ] `drivers/local.py` wrapping `AgentOrchestrator`
- [ ] Migration `021_agent_drivers.py`; `GET /kernel/drivers` endpoint; new EventTypes

### Phase 2: Context Packets (~1.5 days)
- [ ] Extend `services/context.py`: packet sections, token budget with priority truncation, privacy stripping
- [ ] Packet snapshot into `agent_tasks.input`; extend `/api/v1/agent/context` params
- [ ] Judgment-profile section stub (activates when judgment engine ships)

### Phase 3: Verifier Chain (~2 days)
- [ ] `services/verifiers.py`: registry decorator + built-ins (tests_pass, lint_clean, build_ok, diff_within_scope, citations_present, style_conforms, claims_evidenced)
- [ ] One-bounce rule; wire into `autonomy/pipeline/executor.py`; `verification_runs` storage
- [ ] Second-opinion reviewer pass (dissenting cheap model)

### Phase 4: Dispatch + Results Loop (~1.5 days)
- [ ] `drivers/dispatcher.py`: selection (pin → cheapest capable trusted → fallback), WIP/concurrency limits, cost cap
- [ ] `services/results_loop.py`: capture-spine observation, implicit judgment prediction, trust update, `driver_stats` upsert
- [ ] Persona columns live: create `uzhavu-ops` and `dependency-updater` personas as rows (proof of Story 5)

### Phase 5: Standing Pipelines (~1.5 days)
- [ ] Watcher-finding → task origination rules; scheduler-originated tasks
- [ ] Launch the three pipelines: dependency updates, code review on push, content pipeline
- [ ] `GET /kernel/drivers/stats` with verified-per-₹ weekly series

### Phase 6: Tests & Docs (~1 day)
- [ ] Integration tests: driver fallback, packet privacy stripping, bounce-once, autonomy-gate routing, WIP limits (mock drivers — no real subprocess in CI)
- [ ] Update KNOWLEDGE.md (drivers section, new tables/events), .env.example, OpenAPI examples

**Total: ~9.5 days**
