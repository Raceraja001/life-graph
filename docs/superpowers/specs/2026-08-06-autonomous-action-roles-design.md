# Autonomous Action Roles — Design (Sub-project B)

**Status:** Approved design, ready for implementation plan (Phase B1 first).
**Date:** 2026-08-06
**Builds on:** Sub-project A — [[ambient-advisory-roles]] (scheduler ticker, proposal→bridge→notification pattern, push), merged to local master @ 1eb87a0.

## Goal

Let scheduled **action** personas (ops, cody, swe-lead) run unprompted, **propose**
concrete actions, and have those actions flow through Life Graph's already-built
autonomy pipeline — classified by risk and trust, auto-executed when safe and trusted
(via a shadow-mode ramp), or queued for the user's approval otherwise — with the whole
thing surfaced in one mobile approvals inbox and pushed to the phone.

## The pivotal context (verified against master @ 1eb87a0)

There are **two parallel execution worlds that don't touch**:

1. **Live persona world** — `Scheduler.fire_job → ProcessManager.spawn → AgentOrchestrator.run`.
   Scheduled cody/ops/swe-lead run here. A write tool (`terminal`/`git`) **executes
   immediately**; the only gate is allowed-tools membership (`orchestrator.py` tool dispatch,
   `~:245`). No classification, trust, or approval.
2. **Autonomy "Era 8" island** — a fully-built, tested `classify → trust → shadow →
   execute` engine (`AutoFixService.process`, `autonomy/safety/classifier.py`
   `ActionClassifier`, `autonomy/trust/`, `autonomy/pipeline/executor.py` `CommandExecutor`)
   plus an approval queue (`ApprovalQueueEntry` in `autonomy/models.py`, `/autonomy/approvals`
   router, `check_approval_timeouts` + `send_approval_escalations` crons). It speaks
   **shell-command strings** and is reachable **only** via a manual `POST /autonomy/pipeline`
   endpoint. **No live producer feeds it.**

So B is **not** "build approvals." It is: **connect a persona's proposed action to the
existing island**, add the one execution route the island lacks (agent-work, not just
shell), wire approvals to notifications, and give the user one inbox.

## Decisions (locked with the developer)

1. **Both action flavors:** atomic **command** actions AND open-ended **agent_task** actions.
2. **Graduated auto-execute:** use the full L0–L3 trust×risk matrix — SAFE + high-trust
   actions auto-execute; MODERATE/DANGEROUS queue for approval. (Not approve-everything.)
3. **Shadow-first:** an auto-execute-eligible action-type runs in **shadow** (recorded, not
   performed) until it graduates over N observations; nothing new ever auto-runs for real on
   first encounter. Reuse `autonomy/shadow/`.
4. **Propose-mode via structured output** (NOT orchestrator tool-interception): action roles
   run read-only and emit a JSON list of proposed actions; a bridge feeds them to the engine.
   This mirrors Sub-project A and sidesteps deep orchestrator surgery.
5. **One approvals inbox:** extend the existing mobile `/m/approvals` to show autonomy
   entries alongside the generic feed; approve/reject routes to the autonomy resolve endpoint.
6. **Phased build:** one spec, two plan phases — **B1** (command actions, end-to-end) then
   **B2** (agent-work execution) layered on B1's plumbing.

## Architecture

```
ops / cody / swe-lead   (scheduled via the Sub-project A ticker; READ-ONLY tools; propose-mode prompt)
   emit as run output: JSON  [{type:"command"|"agent_task", name, command|task_spec, rationale, risk_hint}]
        │  ActionProposalBridge  (subscribes TASK_COMPLETED in worker + web, gate on action-role names)
        ▼
   for each proposal → AutoFixService.process(action_name, action_command|task, project_id, trigger=...)
        │      ActionClassifier: matching ActionSafetyRule → risk; effective trust; L0–L3 matrix
        ├── AUTO_EXECUTE (safe + trusted)
        │       └── shadow gate: first N runs recorded-not-performed → graduate → real execute
        ├── NOTIFY_BEFORE  → ApprovalQueueEntry(expires_at) → auto-approves if not vetoed in time
        └── QUEUE_FOR_APPROVAL → ApprovalQueueEntry (waits for you)
                                     │  approval→notification bridge → push to phone (/m/approvals)
                                     ▼  you approve/reject in the unified inbox
   EXECUTE (auto after shadow-graduation, or on approval):
        command    → CommandExecutor (exists)                         [Phase B1]
        agent_task → drivers.dispatch_task(persona, task_spec)        [Phase B2]
                       → verifier_chain + one-bounce + rollback-on-fail
        ▼
   AutoAction row updated + audit log + AUTONOMOUS_ACTION_COMPLETED event
```

## Components

### Reuse (already built — do not rebuild)
- `AutoFixService.process` (`autonomy/pipeline/service.py`) — the classify→trust→shadow→route→execute tie-together.
- `ActionClassifier` (`autonomy/safety/classifier.py`), `TrustScoreService` (`autonomy/trust/`), shadow (`autonomy/shadow/`).
- `CommandExecutor` (`autonomy/pipeline/executor.py`) — shell execution with timeout + restricted env.
- `ApprovalQueueEntry` + `ApprovalService` (`autonomy/approvals/`) + `/autonomy/approvals` router + `check_approval_timeouts`/`send_approval_escalations` crons.
- Driver path `dispatch_task` (`drivers/dispatcher.py`) — verifier chain, one-bounce, budget Governor, failure→approval.
- Sub-project A: the scheduler ticker (`workers/tasks.py tick_scheduled_jobs`), job seeding pattern, `PushService`, and the FindingsBridge pattern to mirror.

### Build (the connective tissue)
1. **`services/action_proposal_bridge.py` — `ActionProposalBridge`** *(B1)*. Subscribes
   `TASK_COMPLETED` (worker on_startup + web lifespan, like FindingsBridge), gated on the
   **action-role** persona names (a new constant `AMBIENT_ACTION = {"ops","cody","swe-lead"}`).
   Loads the task, parses the trailing JSON proposals (reuse/generalize A's `_extract_json_array`),
   and for each calls `AutoFixService.process(...)`. Malformed JSON → a single advisory
   notification ("proposed actions could not be parsed"), never a silent drop, never an execute.
2. **Propose-mode persona prompts + read-only tool sets** *(B1 for command roles; B2 extends)*.
   ops/cody/swe-lead get a proposal contract appended to their `system_prompt` (like A's
   findings contract) and, **when run on a schedule**, a read-only tool set (investigation only:
   `terminal` restricted to read-only? — safer: a dedicated read-only inspection toolset, or
   the persona is instructed to only *describe* commands, not run them; the scheduled run must
   not carry write tools). The interactive versions keep their normal tools.
3. **`agent_task` execution route** *(B2)*. The island only executes shell strings. Add a route
   so an approved (or auto-graduated) `agent_task` proposal dispatches the persona via
   `drivers.dispatch_task(persona, task_spec)` — running the write-enabled agent under the
   verifier chain + one-bounce + rollback. `ApprovalQueueEntry` gains a way to carry a task
   spec (reuse its `payload`/`action_command` as a JSON task descriptor + a `kind`
   discriminator) so resolve() can route command vs task.
4. **Approval→notification bridge** *(B1)*. Subscribe `AUTONOMOUS_ACTION_PENDING` (and hook the
   escalation cron) → `NotificationEngine.create(priority by risk, deliver_at_brief=False for
   dangerous)` + immediate `PushService.send_to_tenant`. Reuse A's push. Today these events
   notify no one.
5. **Unified mobile approvals** *(B1)*. Extend `/m/approvals` to also list `/autonomy/approvals`
   entries with a risk badge, the command/task preview, rationale, and proposing role; approve/
   reject routes to `POST /autonomy/approvals/{id}/resolve`. Generic `Approval` feed items keep
   their existing behavior. One combined, sorted inbox.
6. **Shadow log surface** *(B1)*. A read view of shadow-executed actions (what *would* have run)
   so the user can watch the ramp and veto a graduating action-type. Small screen or a section
   of the approvals/activity UI reading the shadow records.
7. **Seed `ActionSafetyRule`s** *(B1)*. Sensible per-deployment rules so classification is
   meaningful (e.g. `docker restart *` = MODERATE; `git *` read = SAFE, `git push`/`push --force`
   = DANGEROUS; `rm`/`DROP`/migrations = DANGEROUS+guardrail-force-queue; `docker logs`/`ps`/
   `df` = SAFE). Default (no rule) is DANGEROUS+QUEUE, so unseeded actions are safe-by-default.

### Ambient action roles + cadence
- Seed scheduled jobs (Sub-project A seeder pattern) for `ops` (daily infra sweep — propose
  restarts/cleanups/migrations it finds needed), `cody` (B2 — propose code fixes for failing
  tests/known issues), `swe-lead` (B2 — propose multi-step coordination). All seeded **inactive/
  opt-in** given they act on real infra; the user enables per role in the UI.
- V1 trigger = **scheduled** (reuse the ticker). **Reactive triggers** (a watcher/health signal
  → an action role proposes a fix) are a natural extension — the same bridge/queue — but out of
  scope for B1/B2.

## Data flow & models

- **No new core tables strictly required for B1:** proposals are transient (parsed from task
  result); `AutoAction` + `ApprovalQueueEntry` + shadow records already exist. B2 may add a
  `kind`/task-spec discriminator on `ApprovalQueueEntry` (or use its `payload` JSONB) — decide in
  the plan; prefer no migration if `payload` suffices.
- **Tenant scoping** on every new query; scheduled runs set `set_tenant_context(tenant, "system")`.
- **Events:** reuse `AUTONOMOUS_ACTION_PENDING`/`_COMPLETED`, `APPROVAL_*`. The bridges are
  wired in BOTH worker on_startup and web lifespan (worker-emitted events don't reach web
  subscribers — established in Sub-project A).

## Safety analysis (this system can act on production)

- **Default-deny:** no matching `ActionSafetyRule` ⇒ DANGEROUS ⇒ QUEUE. Unclassified actions
  never auto-run.
- **Shadow-first** for every auto-execute-eligible action-type; the user watches the shadow log
  and can veto before graduation.
- **Guardrail rules** force-queue destructive patterns regardless of trust.
- **Read-only propose-mode:** the scheduled run itself cannot perform writes — it only proposes.
  Execution happens only through the gated engine, never inline in the persona run.
- **CommandExecutor** keeps its timeout + restricted env; B2 agent-work runs under the driver
  verifier chain + one-bounce + rollback + Governor budget gate.
- **Escalation + expiry:** dangerous approvals never silently auto-approve (only NOTIFY_BEFORE
  entries have `expires_at`); escalation cron re-pings.
- The VM is the live box — seed rules conservatively; document that `LIFE_GRAPH_*` autonomy
  levels and safety rules are the real control surface at deploy.

## Error handling

- Bridge parse failure → advisory notification, no execution.
- `process(...)` failure on one proposal → logged, isolated, other proposals continue.
- Execution failure → `AutoAction` marked failed + audit + notification; B2 verifier failure →
  one-bounce then approval (existing driver behavior); rollback on destructive failure where the
  executor supports it.
- Push/notification failures swallowed (never break the flow), per Sub-project A.
- Bridge/handler exceptions never break task completion or worker startup (guarded, per A).

## Testing

- **Unit:** proposal JSON parse + fallback; bridge routes command vs agent_task; classifier
  wiring (a seeded rule → expected recommendation); approval→notification mapping (risk→priority,
  dangerous→immediate push); shadow-gate decision; agent_task route dispatches `dispatch_task`
  (B2).
- **Integration:** proposal → `process` → (auto safe / queued dangerous); a real
  `AUTONOMOUS_ACTION_PENDING` emit → notification created + push; approve a queued entry → command
  executes via CommandExecutor (mocked subprocess) / agent_task dispatches (B2, mocked driver);
  read-only propose-mode cannot carry write tools.
- Repo pattern: `httpx.AsyncClient` + `ASGITransport`, tenant headers, `conftest` pgvector mock.

## Scope

**Phase B1 (first plan):** action-role seeding (ops, opt-in) + propose-mode/read-only + proposal
contract; `ActionProposalBridge` → `AutoFixService.process` for **command** actions; approval→
notification bridge; unified `/m/approvals`; shadow log view; seed `ActionSafetyRule`s. Delivers a
complete, safe autonomous **command** loop with graduated auto-execute + shadow.

**Phase B2 (second plan):** open-ended **agent_task** actions — the execution route
(approve/auto → `dispatch_task` + verifier chain + one-bounce + rollback), cody/swe-lead ambient
roles, task-spec carriage on the queue. Layered on B1.

**Out (future):** reactive (watcher/health-triggered) proposals; auto-execute policy tuning UI;
per-project autonomy-level management UI.

## Open questions / risks

- **Read-only propose-mode enforcement.** The cleanest is a dedicated read-only inspection
  toolset for scheduled action roles (never `terminal`-write/`git`-write/`docker`-write). Confirm
  the exact tool split in the plan; the advisory-safety enforcement (allowed_tools filtering on
  the headless path) already exists and applies.
- **Free-model quality for proposals.** As in A, weak models may propose noisy/invalid actions;
  default-deny + classification + approval contain the blast radius. Better models sharpen it.
- **`ApprovalQueueEntry` for agent_task.** Its `action_command` is a shell string; carrying a
  task spec needs `payload` (JSONB) + a `kind` discriminator — settle in the B2 plan (prefer no
  migration).
- **CommandExecutor is POSIX** — fine on the Linux VM; not for local Windows dev runs of the
  executor (tests mock the subprocess).

---

## Phase B2 Design Addendum (2026-08-06 — after B1 merged @ 6cf115e)

Phase B1 (command actions) is built, reviewed (opus whole-branch: SHIP), and fast-forward-merged
into local master @ `6cf115e`. This addendum settles the B2 open questions the spec above deferred
"to the plan," grounded in a fresh code exploration of the merged tree. It **corrects three spec
assumptions** that the original architecture sketch got wrong, then locks three decisions.

### Corrections to the original B-spec (verified against master @ 6cf115e)

1. **`dispatch_task` is complete but has ZERO production callers.** `drivers/dispatcher.py`
   `TaskDispatcher.dispatch_task(tenant_id, task_id, instruction, task_type="general",
   project_id=None, session=None, persona_name=None, private=False, cost_cap_usd=2.0,
   verify_chain=None, interactive=False) -> DriverResult` runs a real agent loop
   (`LocalDriver → AgentOrchestrator`), with a **Governor budget gate** (`interactive=True`
   never throttles; autonomous dispatches do), a **verifier chain** (default
   `["build_ok","lint_clean"]`), a **one-bounce** retry, and **creates an `ApprovalQueueEntry`
   on terminal failure**. Its only caller today is the testing endpoint `POST /dispatch`
   (`api/drivers.py`). Wiring it into the autonomy pipeline is 100% net-new integration.
2. **"Task spec rides `ApprovalQueueEntry.payload`" is WRONG** — that table has no `payload`
   column. `action_command` is `NOT NULL` on both `AutoAction` and `ApprovalQueueEntry`.
   `AutoFixService._run_action` is a single hardcoded chokepoint
   (`self._executor.execute(command=auto_action.action_command, ...)`); `action_type` is a
   free-text label **never branched on**; there is **no `kind` discriminator anywhere**.
3. **Shadow is a log, not a simulator.** `ShadowRun.record_would_have_done` persists "would have
   run X" for a human to grade `good`/`bad`; it never dry-runs. Syntactically it can hold an
   agent_task instruction (untyped `Text`), but for open-ended agent work the agent never runs in
   shadow, so the human grades *intent with no outcome* — a materially weaker signal than for a
   deterministic shell command.

### Locked decisions (developer, 2026-08-06)

- **B2-D1 — Data model: one clean Alembic migration.** Add a `kind` discriminator
  (`'command'` | `'agent_task'`, default `'command'`) to `AutoAction` **and**
  `ApprovalQueueEntry`; make `action_command` **nullable**; add an `instruction` (`Text`,
  nullable) column to both for the agent_task natural-language spec. Rejected the zero-migration
  "stuff the instruction into `action_command`" approach — it conflates shell-command with
  instruction and breaks `rollback()`/`CommandExecutor`/audit-UI assumptions (safety-relevant).
  `_run_action`/`execute_pending` branch on `kind`.
- **B2-D2 — Execution posture: agent_task ALWAYS queues for approval.** No shadow ramp, no
  auto-execute for `agent_task` in B2. Every open-ended agent run is human-approved before it
  touches anything; write-enabled agent work never runs unattended on the live VM in this phase.
  Command actions keep B1's graduated auto-execute + shadow unchanged. Auto-executing agent work
  is a future phase, gated on a real outcome-based confidence signal (shadow-of-intent is
  insufficient). Concretely: the classifier/router path for `kind=='agent_task'` is forced to
  `QUEUE_FOR_APPROVAL` regardless of risk/trust.
- **B2-D3 — Roles: cody only.** Build the agent_task loop end-to-end with **cody** (propose code
  fixes for failing tests / known issues → approve → `dispatch_task(persona="cody")` implements →
  `build_ok`/`lint_clean` verifier chain → one-bounce → done/needs-human). **swe-lead deferred**
  to its own later phase — its "actions" are nested `delegate_to_persona` chains
  (delegation-under-autonomy), a materially harder execution model deserving separate design.

### B2 build surface (the seams to fill; details in the plan)

1. **`kind`-aware proposal contract + bridge branch.** A propose schema
   `{kind:"agent_task", name, instruction, rationale, risk_hint}` alongside the existing command
   shape; `ActionProposalBridge.process_result` currently hard-filters on `item.get("command")`
   and silently drops anything else — add a `kind`-dispatch that builds an agent_task
   `AutoFixRequest`. Factor the propose-contract prompt text (today duplicated verbatim inside the
   `ops` persona `system_prompt`) into a **shared constant** injected at ambient-run time, so
   `cody` and `ops` don't diverge.
2. **Execution branch + `DriverResult` adapter.** `_run_action`/`execute_pending` route
   `kind=='agent_task'` to `TaskDispatcher.dispatch_task(instruction=..., persona_name="cody",
   verify_chain=["build_ok","lint_clean"], interactive=False, cost_cap_usd=<conservative>)`.
   Adapt `DriverResult` (`success`/`output`/`error`/`cost_usd`/`duration_ms`, **no `exit_code`**)
   into the `AutoAction` persistence shape: `exit_code = 0 if success else 1`, `stdout=output`,
   `stderr=error`, carry `duration_ms`.
3. **Robustness — dispatch can raise.** `dispatch_task` may raise `DispatchError` (WIP-limit) or
   propagate driver errors, whereas `CommandExecutor.execute` **never raises** (always returns an
   `ExecutionResult`). The B1 approval bridge's idempotency swallow catches `ValueError` only, so
   the agent_task execution path must catch dispatch failures → mark the `AutoAction` failed +
   notify, and never wedge the unified-feed `Approval` row as unresolvable.
4. **`AutoFixRequest` extension.** Add `kind` + `instruction` to the pydantic
   `AutoFixRequest` (`autonomy/pipeline/schemas.py`) and thread them through `process()` into the
   new `AutoAction` columns (today `metadata`/`timeout_seconds` are explicitly "not persisted" —
   `instruction` must actually persist).
5. **cody ambient role.** Add `"cody"` to `AMBIENT_ACTION`; a `cody-ambient` job in
   `AMBIENT_JOBS` (opt-in, `active: False`, its own cron); cody's read-only propose-mode via the
   existing `AMBIENT_ACTION_READONLY_TOOLS` + `tool_override` (cody carries write tools
   unconditionally in `allowed_tools` — read-only-when-ambient is enforced ONLY by the scheduler
   `tool_override`; the load-bearing invariant, same as ops in B1); cody's propose-mode paragraph
   (agent_task-shaped) appended to its `system_prompt`.
6. **Seed cody `ActionSafetyRule`s.** cody's agent_task action-name space needs seeded rules or
   every proposal default-queues (`DANGEROUS+QUEUE`) — which is the safe default and also exactly
   B2-D2's forced posture, so seeding here is about *labelling risk for display*, not changing
   routing (agent_task queues regardless). Extend `autonomy/safety/ambient_rules.py`.
7. **Unified approvals UI.** agent_task rows in `/m/approvals` render the **instruction** (not a
   shell command), the verifier chain, the cost cap, and the proposing role; risk badge carries
   over from B1.

### B2 safety analysis

- Open-ended agent work **never runs unattended** in B2 (B2-D2: always human-approved).
- The scheduled proposer stays **read-only** (`tool_override` → `AMBIENT_ACTION_READONLY_TOOLS`),
  the same load-bearing invariant B1's whole-branch review confirmed holds through the retry path.
- The write-enabled cody run happens **only post-approval**, under `dispatch_task`'s verifier
  chain + one-bounce + **Governor budget gate** (a conservative `cost_cap_usd` bounds spend;
  autonomous dispatches are throttleable, unlike interactive).
- `kind` migration keeps shell-command semantics uncontaminated, so `rollback()` and the audit
  trail never mistake an instruction for a shell string.

### B2 testing

- **Unit:** proposal parse routes command vs agent_task by `kind`; agent_task `AutoFixRequest`
  built with `instruction` (not `command`); classifier/router forces agent_task →
  QUEUE_FOR_APPROVAL; `_run_action` `kind`-branch dispatches `dispatch_task` (mocked) and adapts
  `DriverResult` → AutoAction fields; dispatch raising `DispatchError` → AutoAction failed +
  no wedged feed row; shared propose-contract constant injected for both ops + cody.
- **Integration (E2E):** cody proposal → `process` → queued (never auto) → approve → `dispatch_task`
  invoked with the right instruction/persona/verify_chain (mocked driver) → AutoAction completed;
  read-only propose-mode cannot carry write tools (cody).
- Repo pattern: `httpx.AsyncClient` + `ASGITransport`, tenant headers, `conftest` pgvector mock;
  backend tests run with `/c/Python314/python.exe -m pytest`.

### Out of B2 (future)

swe-lead ambient role (nested delegation under autonomy); auto-execute for agent_task (needs an
outcome-based confidence signal, not shadow-of-intent); reactive (watcher/health-triggered)
proposals; per-project autonomy-level & auto-execute-policy management UI.
