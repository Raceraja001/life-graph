# Work Order: Secure, Persistent Development Execution Runtime

**Repository:** Raceraja001/life-graph  
**Priority:** P0  
**Purpose:** Evolve Life Graph's existing development-agent system into a secure, persistent, recoverable software-development execution platform inspired by OpenHands.

## Agent prompt

You are the senior software infrastructure engineer working in this repository.

Inspect the current implementation before changing anything. Life Graph already has substantial development-agent capabilities. Do not rewrite or replace the dispatcher, memory system, task records, verifier chains, approval workflow, or Git worktree system without concrete evidence that replacement is necessary. Prefer the smallest safe incremental changes.

### Product outcome

A user should be able to submit a software task against a repository and Life Graph should:

1. Understand repository and task context.
2. Plan the work and define acceptance criteria.
3. Create an isolated task workspace.
4. Let a supported coding engine inspect files, edit code, and run permitted commands.
5. Stream execution events and logs.
6. Run independent verification.
7. Preserve task state across API/worker restarts.
8. Return an auditable diff and verification evidence.
9. Respect existing approval, PR, and merge policies.

A Git worktree is not an OS security boundary.

### Existing capabilities to preserve and re-verify

A previous repository review found support for Claude Code, OpenCode, local/cloud/auto drivers; project registry and context packets; code graph/repository understanding; planning and acceptance criteria; Git worktrees; verifier chains and E2E support; durable tasks, steps, checkpoints and restart recovery; PostgreSQL advisory locking; approval/PR/merge/deployment workflows; bounded multi-agent delegation; and dashboard/API views for task status, steps, diffs, conformance and approvals.

These are prior-review findings, not proof of current behavior. Verify them against current master, tests, configuration and deployment manifests.

## Known gaps to investigate

Treat these as hypotheses to re-check, not assumed facts.

### 1. Execution isolation

The previous review observed source defaults similar to:

    driver_claude_sandbox = "none"
    verifier_sandbox = "none"
    driver_opencode_allow_bash = False

It found that Claude Code could run on the host when sandboxing was disabled; OpenCode Bash was disabled by default because its process was not sandboxed; Git worktrees do not isolate OS access; and the browser sandbox is separate from a coding execution sandbox. Deployed environment overrides were not inspected.

**Required:** establish a fail-closed, per-task execution boundary before enabling broad shell access. Distinguish source defaults from actual runtime configuration.

### 2. API-coupled long-running work

The previous review found immediate tasks launched using asyncio.create_task(...), plus a queue runner using PostgreSQL advisory locking and checkpoint/recovery logic. Recovery reportedly handles already-landed work, land-only recovery after verification, and redispatch from earlier stages with bounded retry.

**Required:** determine whether execution should move to a dedicated worker/service while preserving durable task state, locking, checkpoints and recovery. Do not discard existing recovery behavior.

### 3. Interactive developer experience

The dashboard reportedly supports task creation/listing, status, verification, step timelines, diffs and approvals. A complete reconnectable terminal/workspace experience was not found.

**Required:** assess the smallest coherent path to live events and reconnectable terminal sessions. Do not build a full IDE unless justified.

### 4. Benchmark coverage

The prior review found a small fixture set (six tasks per run, sometimes repeated). This is useful initial evidence, not broad proof of software-engineering capability.

**Required:** propose a reproducible benchmark for task success, verification quality, runtime, cost, recovery and security across representative repositories and task types.

### 5. Documentation drift

Reconcile current code and merged work with:
- docs/AI_WORK_ORDER.md
- docs/LIFE_GRAPH_IMPROVEMENT_PLAN.md
- docs/AGENT_COMMUNICATION.md

Avoid conflicting or stale active instructions.

## Required stages

### Stage 0 — Establish current truth (mandatory)

1. Fetch latest master and record its SHA and working-tree state.
2. Read CHARTER.md, docs/STATE.md, docs/specs/autonomous-app-development.md, docs/AI_WORK_ORDER.md, docs/LIFE_GRAPH_IMPROVEMENT_PLAN.md and docs/AGENT_COMMUNICATION.md.
3. Inspect driver, task orchestration, sandbox, verifier, API, dashboard, configuration, deployment and test implementations.
4. Trace one task end-to-end: API request → driver → execution → verification → diff → approval → landing.
5. Separate confirmed code facts, configuration-dependent behavior, deployment/runtime facts unavailable from source, assumptions and recommendations.

**Deliverable:** concise architecture/gap report with file paths, line references, existing behavior, risks and recommended changes.

### Stage 1 — Design the secure execution boundary

Design a per-task runtime with:
- Fresh isolated workspace for every task; only the designated repository/worktree is mounted.
- No unrestricted host filesystem access or host Docker/runtime socket exposed to the agent.
- Non-root execution where feasible.
- CPU, memory, process, disk and execution-time limits.
- Explicit network policy; default-deny or tightly allowlisted egress where practical.
- No inherited API-host secrets or credentials by default; scoped short-lived credentials only when needed.
- Versioned, reproducible images and runtime configuration.
- Reliable cleanup, including after crashes.
- Fail-closed startup/health checks: never silently fall back to host execution.
- Audit metadata for task, runtime, image and policy.

Evaluate existing container/runtime choices first. Do not introduce Kubernetes or another large platform without evidence.

**Deliverable:** architecture decision record, threat model and implementation plan.

### Stage 2 — Implement the smallest safe vertical slice

For one supported coding driver:

1. Create a task and isolated runtime.
2. Mount only its assigned workspace.
3. Execute inspect/edit/test operations inside the runtime.
4. Capture structured logs and lifecycle events.
5. Run verification within the intended trust boundary.
6. Persist task state and runtime metadata.
7. Stop and clean up safely.
8. Return a reviewable diff and verification result through existing APIs.

Preserve existing task contracts where possible. Use an explicit runtime interface; make lifecycle operations idempotent; handle timeout, cancellation, worker/container crashes and cleanup failure. Add focused unit, integration and security tests. Keep approval/merge policies intact. Never silently fall back to host execution.

Do not enable broad shell access for a driver until its execution path is demonstrably sandboxed.

### Stage 3 — Durable worker boundary

After the vertical slice works, decide whether to extract a dedicated execution worker. If extracted:
- API processes enqueue and inspect tasks; they do not own long-running execution.
- Workers claim tasks through durable coordination.
- Leases/heartbeats prevent duplicate execution.
- Worker crashes do not lose task state or corrupt workspaces.
- Recovery is deterministic and bounded.
- Concurrent tasks never share writable workspaces.
- Preserve existing PostgreSQL locking/checkpoint behavior where appropriate.

Do not introduce a second queue or competing source of truth without a migration plan.

### Stage 4 — Interactive session and UI

Only after secure execution works:
- Add reconnectable terminal sessions or a clearly scoped command/session interface.
- Stream stdout/stderr and lifecycle events; persist enough history for reconnect/audit.
- Add cancellation and timeout controls.
- Show runtime status, logs, changed files, diff and verification in the existing dashboard.
- Authorize session access per user and task.
- Never expose raw host terminals.

### Stage 5 — Benchmark and harden

Automate tests for:

**Functional:** repository inspection, edits, build/test/lint/type-check, multi-step tasks, correct diff and PR generation.

**Reliability:** API/worker restart, container termination, network interruption, cancellation, timeout, duplicate delivery, concurrent tasks and cleanup after failure.

**Security:** attempts to read host files, access unrelated repositories, obtain host credentials/secrets, access runtime sockets, escalate privileges, access unauthorized networks or escape the workspace/container. Verify sandbox startup failure never causes host execution.

Run security tests in a controlled environment. Document what was tested and what remains unproven; do not claim containers are escape-proof.

**Performance/cost:** startup latency, task duration, CPU/memory, storage growth/cleanup, provider cost and success rate by task category/driver.

## Acceptance criteria

- [ ] Current architecture and runtime behavior documented from source.
- [ ] Every supported driver has an explicit documented execution boundary.
- [ ] Shell-capable execution is sandboxed by default or explicitly unavailable.
- [ ] Sandbox failure is fail-closed; no silent host fallback.
- [ ] Every task gets an isolated writable workspace.
- [ ] Host secrets/credentials are not inherited by default.
- [ ] Resource and timeout limits are enforced.
- [ ] Task state survives API/worker restarts.
- [ ] Duplicate execution and concurrent workspace corruption are prevented.
- [ ] Logs/events and runtime metadata are auditable.
- [ ] Existing verifier, approval, diff and PR workflows still work.
- [ ] Failure and cleanup paths have automated tests.
- [ ] Security boundary tests have recorded results.
- [ ] Documentation/work-order status is reconciled.
- [ ] No unsupported production-security claim is made.

## Engineering constraints

1. Inspect before changing; earlier findings may already be fixed.
2. Prefer incremental changes; no broad rewrite.
3. Preserve Life Graph's reusable memory, repository knowledge, decisions, evidence and governance capabilities.
4. Separate permission ("may this action run?") from verification ("did it succeed correctly?").
5. Memory is context, never execution authority.
6. Keep coding providers interchangeable behind a common execution contract.
7. Support major claims with code, tests, configuration or observed runs.
8. Avoid scope expansion: no unnecessary multi-agent complexity, frontend rewrite, Kubernetes or new orchestration platform.
9. Respect existing budget controls, including the current monthly budget cap, unless separately approved.
10. Do not weaken approvals or merge safeguards to make a demo appear more autonomous.

## Required initial response — wait for approval

Before implementation, report:

1. Current master SHA.
2. Concise diagram of the current task execution path.
3. Which previously identified gaps remain open, are partial, or are fixed.
4. Exact source files and tests involved.
5. Proposed runtime architecture and threat model.
6. Smallest vertical slice to implement.
7. Risks, migration impact and rollback plan.
8. Tests that prove the acceptance criteria.

**Then stop and wait for approval** before broad refactoring or changing execution/approval policy.

After approval, submit a focused PR containing the problem statement, ADR/threat model, code/tests, operational configuration and deployment notes, security limitations, benchmark results, and updated handoff/work-order docs.

**Definition of success:** Life Graph executes a real software task in a task-isolated environment, survives process interruption, verifies the result and returns an auditable diff—without granting the coding agent unrestricted host access.
