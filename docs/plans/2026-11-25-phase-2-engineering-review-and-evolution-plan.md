# Life Graph — Phase 2 Engineering Review and Evolution Plan

**Status:** Proposed plan; documentation-only commit  
**Prepared:** 2026-11-25  
**Repository baseline:** `master` at `07867911e0a66ec3d5797998b5b07d67c4d29287`  
**Purpose:** Establish a verified engineering baseline, close the highest-risk operational gaps, improve the memory/context pipeline, and define measurable product outcomes before expanding Life Graph's capabilities.

> This document is a plan, not evidence that every listed capability is deployed or operational. Treat prior work-order status, audit notes, generated inventories, and release records as leads to verify against current source, tests, effective configuration, and the running deployment.

---

## 1. Executive direction

Life Graph has grown beyond a conventional memory service. Its documented architecture combines:

- Memory ingestion, extraction, scoring, consolidation, retrieval, and graph relationships.
- A kernel for personas, task routing, scheduling, projects, and process coordination.
- Autonomy controls for risk, trust, approvals, audit history, and emergency stop.
- Drivers for code and browser work, with verification and review workflows.
- Judgment capabilities for decisions, predictions, and outcome evaluation.
- Ambient watchers and proactive workflows.
- Jarvis as the chat, voice, delegation, and notification surface.

The next phase should not be a broad feature expansion. It should make these layers behave as one dependable system.

**Strategic thesis:** evolve Life Graph from a memory operating system into a context operating system. It should maintain a grounded model of current state, retrieve the right context for a task, identify relevant intentions and constraints, propose or execute permitted actions, and learn from verified outcomes.

Memory remains the substrate. It is context, not authority: a remembered fact must never grant permission to execute an action.

### Outcomes sought

1. Production execution is secure, observable, recoverable, and demonstrably configured as intended.
2. Memory retrieval is accurate, explainable, temporally aware, and resistant to stale or contradictory facts.
3. Jarvis provides a consistent, reconnectable experience across clients and delegated agents.
4. Agent execution quality is measured with reproducible evaluations, not anecdotes.
5. The architecture remains understandable and changeable as capabilities grow.
6. Users can install, integrate, operate, back up, restore, and upgrade Life Graph with confidence.

---

## 2. Baseline and known evidence

The following are observations from repository documentation and recent Git history at the baseline above. They are not a substitute for re-running tests or inspecting the live host.

### Recent work visible in Git history

- The November 25 release record describes release `prod-20261125-0126`, a rollback reference, production health checks, backup locations, and deletion of 57 old-name alias modules.
- Recent changes include shared ARQ pool usage and a NumPy-based memory clustering optimization. The commit reports 1,000-memory clustering improving from 13.6 seconds to 0.43 seconds in its benchmark.
- Chat stream parity tests were added for the dashboard and phone endpoints before extracting shared chat-turn logic. The test documents a current delegated-child streaming behavior: the child's first token opens its dashboard panel, but the child's text is not delivered.
- An open architecture issue (#302) records remaining core-to-services and storage-to-services import boundary violations.

### Secure execution runtime work order

`docs/work-orders/secure-execution-runtime.md` reports that a per-task Docker runtime, durable worker boundary, interactive session API/UI, benchmark work, and security probes were implemented and tested in a development environment. Its status table says these stages were not deployed at the time of that update.

The associated security probe report records meaningful controls and a successful end-to-end coding task, but also explicitly lists untested or environment-dependent areas, including OpenCode inside the new runtime, concurrent long-running tasks under pressure, and production activation. The older legacy Claude sandbox and verifier dependency-setup network path also need careful review.

> **Verified 2026-11-25 (Stage 0):** prod switched to the task runtime on 2026-11-19, and the work order's "not deployed" table was stale (now updated). Prod `.env` shows `DRIVER_CLAUDE_SANDBOX=task` and `VERIFIER_SANDBOX=docker`. See `docs/audits/2026-11-25-stage0-current-truth.html`.

**Therefore, production activation and effective runtime configuration are P0 verification tasks. Do not infer that a source default or a successful workstation probe proves the production host is using the intended boundary.**

### Other documented frontier items

The Charter identifies WhatsApp as not started, typed Jarvis turns remaining silent despite local TTS support, SDK documentation as open, and autonomy trust graduation as a policy decision dependent on real shadow-mode evidence. These are not all equally urgent; see prioritization below.

---

## 3. Mandatory operating method

Every implementation work session must follow this sequence:

1. Fetch the latest remote default branch and record its SHA.
2. Synchronize the working tree without discarding local changes.
3. Read this plan and the current relevant source-of-truth documents.
4. Inspect current code, tests, configuration, deployment manifests, and recent history. Treat this plan's observations as hypotheses to re-check.
5. Update the relevant work-order/progress record with findings and intended scope before editing.
6. Select the highest-priority incomplete task that can be completed safely.
7. Make a small, reviewable change. Preserve existing contracts and safety controls.
8. Run focused tests, then the appropriate broader suite; record exact commands and results.
9. Update documentation with implemented, tested, deployed, and operationally verified states separately.
10. Commit code, tests, and documentation together where practical. Reconcile any remote movement before pushing.

Never weaken, delete, skip, or loosen tests to obtain a green result. Do not report a task complete merely because code exists or a unit test passes.

### Evidence labels

Every significant status statement in reports should use one of these labels:

- **Implemented:** code exists.
- **Tested:** an identified automated or manual test passed; cite the exact test/probe and environment.
- **Deployed:** the relevant version/configuration is installed in the target environment.
- **Operationally verified:** behavior was observed in the running target environment.
- **Unverified / blocked:** evidence is missing, stale, environment-dependent, or contradictory.

---

## 4. Priority roadmap

### P0 — Production safety and recoverability

**Objective:** prove that privileged or long-running work cannot silently escape its intended boundary, and that the system can recover safely.

#### 4.1 Secure execution runtime activation

Inspect and verify:

- Current driver selection and effective environment/configuration in production.
- Per-task runtime image, version, policy version, workspace mounts, user identity, capabilities, seccomp, read-only filesystem, resource limits, and deadline enforcement.
- Network isolation and allowlisted egress, including host bridge/gateway reachability and metadata-service denial.
- Secret staging and cleanup; no broad inheritance of API-host credentials.
- Symlink and path traversal defenses before any host-side verifier, review model, PR builder, or landing process reads the worktree.
- Runtime cleanup after normal completion, timeout, cancellation, API crash, worker crash, and machine restart.
- Explicit behavior for missing images, unavailable Docker, proxy failure, and policy mismatch. Every unsafe failure must fail closed; never fall back to host execution.
- Every supported driver separately. Do not assume Claude Code, OpenCode, local drivers, cloud drivers, browser sandbox, and verifier phases share one boundary.

Inspect at minimum the secure runtime ADR, task runtime implementation, driver adapters, verifier setup and execution paths, worker runner, deployment manifests, configuration, operational docs, and runtime security probes.

**Deliverables:**
- A current production configuration report with redacted values and exact image/policy versions.
- A driver-by-driver execution-boundary matrix.
- A gap list for any legacy or unsupported path.
- A controlled production smoke test and rollback procedure.
- Updated operations and security documentation.

**Acceptance criteria:**
- Shell-capable execution is sandboxed or explicitly unavailable for every enabled driver.
- Runtime startup failure cannot silently invoke host execution.
- An agent cannot access unrelated host paths, host runtime sockets, other task workspaces, or unauthorized network destinations in the tested threat model.
- Resource and time limits are enforced.
- Runtime metadata, logs, and cleanup outcomes are auditable.
- A real task produces a reviewable diff and passes independent verification.
- Production activation is recorded separately from workstation testing.

#### 4.2 Durable execution and backup/restore drills

Verify queue/worker semantics under duplicate delivery, lease expiry, worker termination, API restart, cancellation, and concurrent tasks. Preserve the existing PostgreSQL locking/checkpoint/recovery design unless evidence demonstrates a defect.

Run and record:
- A real backup and restore drill.
- Database and graph integrity checks after restore.
- Off-site backup status and encryption/retention configuration.
- Recovery from a failed or partial backup.
- Disk growth and cleanup behavior for workspaces, logs, artifacts, and backups.

**Acceptance criteria:** recovery is deterministic and bounded; duplicate delivery does not duplicate side effects; concurrent tasks never share writable workspaces; a tested backup can restore the required application state.

#### 4.3 Chat stream and delegation correctness

Fix the known delegated-child streaming gap recorded in the parity test. Keep the parity test as a regression contract unless the client protocol is intentionally versioned.

Test:
- Parent and child tokens, tool calls/results, child completion and child failure.
- Multiple delegated children and ordering.
- Cancellation, timeout, client disconnect, reconnect, and worker/API restart.
- Conversation history and identity across dashboard and phone routes.
- Temporary conversation restrictions and refusal/error contracts.
- No duplicate or lost final messages.

**Acceptance criteria:** both clients receive the documented event contract; child text is visible; reconnect behavior is deterministic; failure and cancellation are represented clearly.

---

### P0 — Memory and context quality

**Objective:** make the system reliably retrieve and apply the right information, rather than simply storing more information.

#### 4.4 Establish a memory quality evaluation suite

Create a versioned, privacy-safe evaluation dataset using synthetic or explicitly approved fixtures. Include:

- Direct factual recall.
- Multi-hop relationship recall.
- Temporal facts and changed preferences.
- Contradictory statements and corrections.
- Entity identity and alias resolution.
- Similar but distinct memories.
- Low-confidence or inferred facts.
- Sensitive data handling and tenant isolation.
- Stale, decayed, dismissed, and superseded memories.
- Queries where the correct answer is “unknown” or “insufficient evidence.”

Measure at minimum:
- Recall@k and precision@k for retrieval.
- MRR or nDCG for ranking.
- Correctness of temporal/current-state selection.
- Contradiction detection precision and recall.
- Unsupported-claim rate / abstention quality.
- Duplicate memory rate.
- Retrieval latency and consolidation throughput.
- Token/context cost where LLMs are involved.

Do not optimize only for retrieval similarity. Evaluate whether the retrieved evidence supports the generated answer.

#### 4.5 Improve temporal and epistemic context

Inspect current memory schemas and services before proposing migrations. Evaluate whether memories consistently capture:

- Subject/entity and relationship.
- Claim or event.
- Source and provenance.
- Observed time versus valid time.
- Confidence and evidence strength.
- Status: current, superseded, disputed, rejected, or expired.
- Sensitivity and permitted visibility.
- Links to decisions, tasks, projects, and outcomes.

Prefer incremental compatibility-preserving changes. Do not introduce a large schema redesign without a migration, backfill, rollback, and export plan.

**Acceptance criteria:** a changed fact does not erase its history; current-state questions prefer current supported evidence; uncertainty is preserved; the system can explain why a memory was retrieved and which evidence supports a claim.

#### 4.6 Retrieval pipeline and context assembly

Trace the full path: query understanding → candidate retrieval (vector/BM25/graph as implemented) → filtering → ranking → deduplication → context packing → answer grounding → feedback.

Evaluate:
- Hybrid retrieval and score calibration.
- Query expansion only where measurable.
- Graph traversal depth and relevance.
- Recency/valid-time handling.
- Tenant, privacy, and source-visibility filters before context reaches a model.
- Token-budget allocation and evidence diversity.
- Proactive recall usefulness and anti-annoyance controls.
- Feedback from accept, dismiss, correction, and “not relevant” actions.

Do not add another retrieval subsystem simply because it is fashionable. Compare changes on the same frozen benchmark and retain the simplest approach that improves quality.

#### 4.7 Consolidation and forgetting safety

Validate clustering, deduplication, distillation, importance/access scoring, decay, and deletion/retention semantics. Include adversarial cases where similar memories must remain separate.

**Acceptance criteria:** consolidation is repeatable and observable; it does not merge distinct people/events or erase critical qualifiers; deletion and export semantics are documented; performance improvements preserve ranking/selection behavior within explicitly tested tolerances.

---

### P1 — Jarvis as the dependable personal interface

**Objective:** make the existing capabilities coherent and useful from the user's everyday devices.

#### 4.8 Cross-client assistant contract

Define a shared, versioned conversation/event contract for dashboard, phone, Telegram, and future clients. Document:
- Message and conversation identity.
- Streaming event types and ordering.
- Tool/delegation visibility.
- Errors, retries, cancellation, and reconnect.
- Attachments and voice lifecycle.
- Context provenance and memory feedback.
- Temporary/private session semantics.

Avoid separate chat implementations drifting independently.

#### 4.9 Voice and remote interaction

Verify current speech-to-text and text-to-speech integration and operational requirements. Then prioritize:
- Spoken response for typed turns when enabled by user preference.
- Interruptible speech and cancellation.
- Clear recording/transcription privacy controls.
- Reliable remote notifications and deep links to relevant task/context.
- Low-bandwidth mobile behavior.

Do not start a WhatsApp integration until the Telegram/client contract, security model, and actual user need are clear. Treat WhatsApp as a separate integration proposal with provider, cost, consent, and policy analysis.

#### 4.10 Proactive context, intentions, and anti-annoyance

Improve the quality of proactive notifications before increasing their frequency. Every proactive item should explain:
- What changed or triggered it.
- Why it matters now.
- Which evidence/context supports it.
- What action is suggested.
- Whether the action is informational, approval-required, or safely autonomous.

Measure useful-notification rate, dismissal rate, repeated-alert rate, and actions taken. Provide quiet hours, deduplication, snoozing, and per-watcher controls.

#### 4.11 Autonomy graduation

Keep conservative defaults. Use shadow-mode evidence to calibrate trust by persona, action type, and risk category. Do not raise autonomy globally because a few tasks succeeded.

Acceptance requires:
- A sufficiently large and representative outcome sample.
- Calibration and failure analysis.
- Explicit owner approval for policy changes.
- Kill-switch and capability-revocation tests.
- Auditable per-action authorization.
- No approval bypass through memory, prompts, or delegated agents.

---

### P1 — Agent execution quality and measurable capability

#### 4.12 Reproducible coding-agent benchmark

Expand beyond a small fixture set. Create a versioned benchmark spanning representative repositories and task categories:
- Bug fixes.
- Small features.
- Refactoring with behavior preservation.
- Tests and test repair.
- Type/lint/build failures.
- Documentation changes.
- Dependency/security fixes.
- Multi-file changes and repository exploration.

Measure:
- Task success against hidden or independent acceptance tests.
- Verification precision and false-pass rate.
- Regression rate and scope discipline.
- Runtime, retries, and recovery.
- Provider/model and infrastructure cost.
- Human intervention and approval rate.
- Security policy violations.

Keep benchmark tasks stable and report per-category results. Avoid comparing runs with different task difficulty or environment.

#### 4.13 Verification quality

Review each verifier for false positives, false negatives, and failure behavior. A missing diff, unavailable Git, or verifier crash must not accidentally count as success. Preserve independent verification and approval boundaries.

#### 4.14 Context packets for coding tasks

Evaluate whether repository/project context packets include the right architecture, conventions, recent decisions, relevant memories, and prior failures without overwhelming the coding model. Benchmark context quality and token cost. Keep memory as advisory context, never as authorization.

---

### P1 — Architecture maintainability

#### 4.15 Close import/layering violations

Revisit issue #302 and the recorded exceptions in import-linter. For each exception:
- Confirm it still exists on current master.
- Identify the true responsibility of the importing module.
- Choose the smallest dependency inversion or package-boundary correction.
- Add or tighten an enforceable import contract.
- Remove the exception only after the code has moved and tests pass.

Do not perform a broad package rename or refactor solely to improve aesthetics.

#### 4.16 Complexity and operational observability

Use generated inventory as a navigation aid, not a quality score. Track:
- Critical-path module ownership and dependencies.
- Broad exception handling and silent failure ratchets.
- API endpoint usage and deprecation.
- Migration count and schema ownership.
- Background job ownership and queue health.
- Slow queries and high-cardinality metrics.
- Test duration, flaky tests, and skipped integration coverage.

Keep generated documentation current and make drift detectable in CI.

---

### P2 — Developer ecosystem and adoption

#### 4.17 SDKs and integration experience

Complete Python and TypeScript SDK documentation with runnable examples for:
- Authentication and tenant context.
- Memory capture and retrieval.
- Projects and tasks.
- Chat streaming and reconnect.
- Approval and status inspection.
- Error handling, retries, and pagination.
- Local development and test fixtures.

#### 4.18 Self-hosting and upgrade experience

Create a clean installation and upgrade path:
- Supported deployment profiles and minimum resources.
- Environment/configuration reference.
- Secret management guidance.
- Database migration and rollback procedure.
- Backup/restore verification.
- Health checks and troubleshooting.
- Optional connectors and model providers.
- Privacy, telemetry, and data export.

Do not promise one-command installation until it is tested from a clean machine.

---

## 5. Context Operating System: product architecture proposal

This is a product direction to validate, not a request for an immediate rewrite.

A context cycle should look like:

```text
Observe
  → Normalize events and provenance
  → Update entities, facts, intentions, and project state
  → Retrieve relevant temporal context
  → Identify gaps, conflicts, risks, and opportunities
  → Recommend or propose an action
  → Autonomy / authorization gate
  → Execute through an isolated driver when permitted
  → Independently verify the outcome
  → Record evidence, outcome, and feedback
  → Consolidate and improve future context
```

Key design rules:

1. Separate observation, belief, decision, authorization, execution, and outcome.
2. Keep source provenance and time semantics attached to facts.
3. Treat model output and external content as untrusted.
4. Memory informs a decision but never grants permission.
5. Deterministic policy code should enforce permissions and invariants.
6. Side effects pass through the existing autonomy/approval boundary.
7. Every action should have an auditable reason, evidence, and result.
8. Prefer event-driven updates where they simplify consistency; avoid introducing a second source of truth.
9. Make context exportable and inspectable.
10. Optimize for useful, correct context—not maximum memory volume.

---

## 6. Measurement dashboard

Create a small baseline report before optimizing. Suggested measures:

| Domain | Core measures |
|---|---|
| Memory retrieval | Recall@5, precision@5, MRR/nDCG |
| Grounding | Supported-claim rate, unsupported-claim rate, abstention quality |
| Temporal context | Correct current fact selection, supersession accuracy |
| Consolidation | Duplicate rate, false-merge rate, throughput |
| Jarvis | Completion rate, reconnect success, lost/duplicate events |
| Delegation | Child-output delivery, completion/failure visibility |
| Coding agents | Acceptance-test success, regression rate, verifier false-pass rate |
| Runtime | Startup latency, task duration, CPU/RAM, cleanup success |
| Reliability | Recovery success, duplicate execution, backup restore success |
| Security | Unauthorized access attempts blocked, fail-closed behavior |
| Proactive UX | Useful-notification rate, dismissal/repeat rate |
| Operations | Queue lag, error rate, backup age, disk growth, restore drill |

For each metric record definition, data source, baseline, target, sample size, and known limitations. Do not invent target numbers before establishing a reliable baseline.

---

## 7. Sequencing and decision gates

Work in short, reviewable milestones. Suggested order:

| Milestone | Scope | Exit gate |
|---|---|---|
| M0 — Truth baseline | Re-fetch master; inspect current source, tests, effective config, deployment, open issues | Evidence-backed status report |
| M1 — Production safety | Runtime activation, driver matrix, recovery and backup drills | P0 security/reliability acceptance |
| M2 — Chat correctness | Delegated stream fix, shared contract, reconnect/cancel tests | Cross-client regression suite passes |
| M3 — Memory evaluation | Frozen benchmark, baseline metrics, temporal/contradiction fixtures | Reproducible quality report |
| M4 — Context quality | Targeted retrieval/temporal/consolidation improvements | Measured improvement without safety regression |
| M5 — Agent quality | Broader coding benchmark and verifier analysis | Reproducible per-category report |
| M6 — Architecture | Import boundaries, complexity ratchets, docs drift | Enforced contracts and updated docs |
| M7 — Product experience | Jarvis proactive/voice UX, SDKs, self-hosting | Usability and operational acceptance |

**Do not begin M2–M7 by assuming M1 is complete.** If a P0 blocker is found, stop feature expansion and resolve or explicitly escalate it.

At the end of each milestone, produce:
- What was inspected.
- What changed.
- Exact files and migrations.
- Tests/probes run and results.
- Deployment status and environment.
- Residual risks and unverified claims.
- Rollback instructions.
- Next smallest safe milestone.

---

## 8. Non-goals and guardrails

This plan does not authorize:
- A full rewrite of the memory system, kernel, dispatcher, or dashboard.
- Replacing PostgreSQL, Redis, the current queue, or the current autonomy architecture without evidence and a migration plan.
- Introducing Kubernetes or another large orchestration platform by default.
- Enabling unrestricted host shell execution.
- Weakening approvals, merge safeguards, tenant isolation, or the kill switch.
- Increasing autonomy levels without owner approval and evidence.
- Adding WhatsApp, more personas, or more watchers ahead of core reliability.
- Storing more personal data simply because storage is available.
- Sending private memory or connector data to cloud models without explicit policy and visibility controls.
- Treating benchmark scores or generated inventory counts as proof of real-world intelligence.

---

## 9. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Source says implemented but production differs | Inspect effective config and observe the live target |
| Runtime path silently falls back to host | Fail-closed tests for missing image, Docker, proxy, and policy |
| Verifier trusts hostile worktree content | Symlink/path validation and isolated verifier inputs |
| Memory merges distinct facts | Adversarial fixtures and reversible consolidation |
| Stale facts override current facts | Explicit temporal semantics and correction tests |
| Retrieval improves scores but worsens answers | Evaluate evidence support and abstention |
| Proactive system becomes noisy | Anti-annoyance metrics, dedup, quiet hours, feedback |
| More abstraction increases complexity | Small changes, dependency contracts, operational ownership |
| Worker migration loses recovery behavior | Preserve checkpoints/locks and fault-injection tests |
| Sensitive data leaks through logs or prompts | Redaction, tenant/visibility checks, data-flow tests |

---

## 10. Required first task: Stage 0 current-truth report

Before implementation, the coding agent must:

1. Fetch the latest remote default branch and record its SHA.
2. Read `CHARTER.md`, `docs/STATE.md`, `docs/OPERATIONS.md`, `docs/AI_WORK_ORDER.md`, `docs/work-orders/secure-execution-runtime.md`, the secure-runtime ADR, current memory/retrieval specifications, `docs/AGENT_COMMUNICATION.md`, and relevant audit reports.
3. Inspect the current runtime, worker, drivers, verifiers, memory retrieval/consolidation, chat streams, autonomy/approval, deployment configuration, and tests.
4. Check open issues and recent merged work for conflicts or completed tasks.
5. Trace one coding task end-to-end and one memory query end-to-end.
6. Distinguish code facts, test evidence, effective configuration, production observations, and unknowns.
7. Produce a concise report with file paths and line references, a driver-by-driver runtime matrix, a memory/context data-flow diagram, prioritized gaps, and a smallest-safe implementation proposal.

**Stop after the report and wait for owner approval before changing runtime policy, deployment configuration, authorization, autonomy, database schema, or broad architecture.** Routine isolated fixes may proceed only if they are clearly within an already approved work item and do not change those boundaries.

---

## 11. Definition of success

Life Graph is succeeding when it can:

- Maintain a useful, temporally correct, provenance-aware model of a user's projects, preferences, decisions, and intentions.
- Retrieve context that measurably improves answers and task outcomes.
- Explain which evidence supports a response or action.
- Execute permitted work in an isolated, recoverable environment.
- Independently verify results and return an auditable diff or outcome.
- Keep dashboard and mobile/voice interactions consistent.
- Proactively surface useful information without becoming noisy.
- Preserve user control, privacy, exportability, and safe defaults.
- Demonstrate these claims with reproducible evaluations and operational evidence.

**North star:** make Life Graph more dependable and contextually intelligent before making it more autonomous or more complicated.
