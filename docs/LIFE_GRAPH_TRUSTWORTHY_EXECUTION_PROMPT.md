> **Historical (2026-11-18).** Not an active instruction. Its work is recorded as
> complete in `docs/AI_WORK_ORDER.md`; the active work order is
> `docs/work-orders/secure-execution-runtime.md`.

# Life Graph — Trustworthy Autonomous Execution & Memory Integrity

## Mission

Work in the existing Life Graph repository to close the highest-risk correctness and security gaps identified in the latest review, while completing the memory-integrity work already planned.

Do not start unrelated features or redesign working subsystems without evidence. First inspect the current repository state and recent commits; some findings may already have been fixed. Verify each finding against current code and tests before changing anything.

The goal is not merely to add code. The goal is to make the system's trust boundaries, memory history, evidence, autonomy permissions, cloud spending, and browser execution demonstrably correct.

## Operating rules

1. Read and follow `CHARTER.md`, `docs/STATE.md`, `docs/LIFE_GRAPH_EVOLUTION_ROADMAP.md`, `docs/AI_REVIEW_AND_EXECUTION_INSTRUCTIONS.md`, `docs/OPERATIONS.md`, and the relevant design/spec documents before implementation.
2. Inspect the current implementation and git history. Mark every prior finding as **fixed**, **partially fixed**, **not fixed**, or **not applicable**, with file/line references and tests.
3. Preserve existing architecture and public interfaces unless a change is necessary. Prefer small, reviewable changes.
4. Do not trust client-supplied claims about identity, provenance, authorization, tenant, policy, or approval.
5. Fail closed for privileged actions. If authority or evidence cannot be verified, deny or abstain.
6. Do not let LLM output, web-page content, imported documents, MCP payloads, or other untrusted inputs grant themselves authority.
7. Keep private personal data local. Cloud models may receive only appropriately scrubbed general-purpose task content. Never expose personal tools or secrets to cloud models.
8. Add regression and adversarial tests for every security or correctness fix.
9. Run the relevant tests, then the full appropriate test suite. Report exact commands, results, skips, and failures. Do not claim CI passed unless an actual CI run confirms it.
10. Work in focused commits. Do not combine unrelated changes. Update documentation and `docs/STATE.md` only after verifying the resulting implementation.

For every capability, distinguish clearly between: **designed**, **implemented**, **integrated**, **unit-tested**, **integration-tested**, **operationally verified**, and **complete**.

---

## Phase 0 — Establish the real implementation state

- Inspect the current branch, working tree, latest commits, and CI/workflow status.
- Read the relevant code paths rather than relying on commit messages or documentation claims.
- Re-check all findings below; do not assume they remain true or have been fixed.
- Produce a concise implementation plan ordered by security severity and dependency.
- Identify migrations, compatibility risks, and existing callers before changing interfaces.

## Phase 1 — Close critical trust and authorization gaps

### 1.1 Server-authenticated memory provenance

Review memory creation paths, including structured API requests, freeform capture, extraction fallback, imports, bulk operations, CLI, dashboard, and MCP.

The source type or provenance tier must not be trusted merely because it appears in a client-controlled request body. In particular, verify whether a caller can set a value such as `chat`, `manual`, `dashboard`, or `cli` to make externally supplied content appear first-party or owner-authored.

Implement provenance based on authenticated server-side ingress context:

- Derive the ingress identity and trust tier from authenticated server context, not caller-supplied strings.
- Treat external, imported, unknown, and unrecognized sources as untrusted by default.
- Preserve legitimate owner-entered notes through an authenticated owner-controlled path.
- Make explicit owner confirmation a separate, auditable operation with actor, timestamp, target, and evidence.
- Prevent models and external content from asserting `owner_confirmed`, trusted evidence, or privileged lineage fields.
- Keep provenance decisions consistent across every memory creation path.

Add adversarial tests proving that changing request fields cannot upgrade trust, including structured, freeform, fallback extraction, MCP, and bulk-import cases.

### 1.2 Authenticate authority for actions and standing rules

Audit `ActionRequest`, `request_from_payload()`, `owner_request`, `standing_rules`, the policy checker, and BrowserErrand creation/execution.

A structurally valid owner request is not proof that the owner actually authorized it.

- Only trusted owner-authenticated UI/server code may create an authorization mandate.
- Represent approval as an opaque, short-lived capability or server-side record that is bound to tenant, task, action, target, scope, and expiry.
- Verify the capability at the point of execution; do not accept a model-generated or client-supplied imitation.
- Load standing rules only from trusted, tenant-scoped configuration. Never accept them from agent output, page content, or arbitrary request payloads.
- Make approval revocable and auditable.
- Ensure authorization cannot be broadened by a later model response or hostile web content.
- Keep read-only, reversible, sensitive, and irreversible actions distinct, with policy appropriate to each category.

Add prompt-injection and payload-forgery tests. For example, a hostile page instructs the agent to invent an owner mandate or add an ALLOW standing rule. The action must remain denied unless a valid owner-issued capability exists.

## Phase 2 — Harden browser navigation and execution

### 2.1 Validate destinations at the application boundary

Review every interactive browser navigation and fetch path. Do not rely on the browser driver alone to reject dangerous URLs.

- Allow only explicitly supported schemes, normally HTTP and HTTPS.
- Reject `file:`, `data:`, `javascript:`, `ftp:`, and other unsupported schemes.
- Reject localhost, loopback, private, link-local, reserved, multicast, and cloud metadata destinations, including IPv4 and IPv6 representations.
- Resolve DNS and validate the actual destination addresses.
- Revalidate every redirect and every new navigation.
- Address DNS rebinding and time-of-check/time-of-use risks; enforce restrictions at the network/proxy layer as well as in application code.
- Normalize and parse URLs with a robust URL parser. Reject malformed authorities, userinfo tricks, ambiguous host forms, and invalid ports.
- Ensure origin authorization and destination authorization are separate checks.
- Apply equivalent protections to interactive browsing and safe-fetch paths.

Add tests for encoded IP forms, IPv6, redirects to private destinations, DNS changes, userinfo confusion, non-HTTP schemes, and metadata endpoints.

### 2.2 Complete the browser execution integration

Determine whether the BrowserErrand executor is actually wired into the production workflow and the existing Playwright/MCP browser bridge.

- Identify the concrete browser driver implementation and its lifecycle.
- If a driver is missing, implement the smallest compatible adapter or clearly document the integration boundary.
- Connect task creation, policy authorization, sandbox lifecycle, browser actions, evidence capture, and final result reporting end to end.
- Keep page text and page instructions explicitly untrusted.
- Ensure secrets are filled only through the vault's controlled path; never expose plaintext secrets to the model, logs, screenshots, traces, or task results.
- Do not describe browser errands as operational until the complete path has been integration-tested.

### 2.3 Sandbox network and control-plane boundaries

Preserve default-deny network egress.

- Do not enable unrestricted internet access as a shortcut.
- If public browsing is required, use a dedicated egress proxy with domain allowlisting, DNS/IP validation, redirect checks, and auditable policy.
- Review whether untrusted workspace code can access the browser's control WebSocket and take over a session or inspect sensitive state.
- Separate privileged browser control from arbitrary workspace execution; authenticate and scope control channels.
- Keep secrets, host mounts, Docker socket, and privileged host capabilities out of untrusted containers.
- Document the actual network topology and what each container can reach.

Add integration tests proving that untrusted workspace code cannot bypass the proxy or gain unauthorized browser control.

## Phase 3 — Make cloud spending limits enforceable

Review `spend_guardrails.py` and all cloud-model call paths.

A check-then-record flow is not a hard budget: concurrent requests can all pass the same balance check and overspend.

Implement atomic reservations:

1. Estimate a conservative maximum cost before the provider call.
2. Atomically reserve that amount against the applicable monthly, per-task, and tenant limits.
3. Deny the call if reservation would exceed a limit.
4. Reconcile the reservation with actual provider usage/cost when available.
5. Release unused reservation.
6. Handle provider errors, timeouts, cancellations, retries, and process crashes without leaking or duplicating reservations.
7. Attribute usage to the correct tenant and task; define explicit behavior when there is no TaskContext.
8. Treat unknown model pricing as unknown, not free. Handle provider fallback models and pricing explicitly.
9. Clearly distinguish estimated usage from provider-reported actual usage.

If limits are intended to hold across workers or restarts, use durable shared accounting with transactional concurrency control. An in-process singleton is not a global monthly cap.

Add concurrency tests in which many requests compete for a small remaining budget. Prove the total reservations cannot exceed the configured cap. Add restart/recovery and failure-path tests.

## Phase 4 — Harden the secret vault

Review vault encryption, origin normalization, one-use behavior, key handling, and API/logging surfaces.

- Retain authenticated encryption and tenant binding.
- Parse origins with a robust URL parser and canonicalize scheme, hostname, and port.
- Reject malformed URLs, userinfo, unsupported schemes, invalid ports, deceptive host forms, and unexpected paths where origin-only input is required.
- Test wildcard subdomain matching, including dot-boundary behavior and scheme/port restrictions.
- Verify origin authorization before consuming a one-use secret.
- Make one-use consumption atomic under concurrent requests; a secret must not be returned twice.
- Ensure API responses, logs, exceptions, traces, and errors never reveal plaintext secrets.
- Review key provisioning, rotation, backup, recovery, and failure behavior. Document what is implemented and what remains an operational responsibility.
- Keep revocation behavior explicit and testable.

Add malformed-origin, wildcard, cross-tenant, concurrent one-use, revoked-secret, and no-plaintext-leak tests.

## Phase 5 — Memory integrity and temporal correctness

### 5.1 True bitemporal history

Separate:

- **Valid time** — when a fact is true in the real world.
- **Transaction/recorded time** — when the system learned or recorded that fact.

Do not use `created_at` as a substitute for transaction-time history if records can be edited in place.

- Preserve immutable revisions or an equivalent append-only history for changes and corrections.
- Support queries such as “what did we believe on date X?” and “what do we now believe was true on date Y?”
- Ensure supersession and late-arriving captures preserve both timelines.
- Audit all `as_of` retrieval paths, including episodes and summaries. Historical queries must not silently use the current date for their time window.
- Define timezone semantics and test boundary cases.

Add tests for corrections, backdated facts, late-arriving evidence, supersession, and historical reconstruction.

### 5.2 End-to-end evidence lineage and claim verification

Build and verify the complete chain:

**original capture → exact source span → extraction trace → candidate claim → approved memory → consolidation/supersession → retrieved evidence → answer claim/citation**

- Preserve exact source references and spans where available, with a retention policy for raw content.
- Make lineage consistent across every ingestion path.
- Verify that referenced evidence actually supports the claim; the presence of a citation marker alone is not proof of entailment.
- Distinguish support, contradiction, context, and insufficient evidence.
- Provide claim-level citations or an explicit abstention when evidence is missing or ambiguous.
- Make source availability mean that the source can actually be resolved and verified, not merely that a reference string exists.
- Preserve provenance through memory consolidation and answer generation.

Add tests for missing sources, invalid spans, contradictory evidence, irrelevant citations, unsupported claims, and lineage through consolidation.

### 5.3 Confidence calibration and retrieval

Audit confidence decomposition, confidence ordering, evidence aggregation, and abstention.

- Do not treat fixed heuristic weights as calibrated probabilities.
- Keep extraction confidence, source trust, evidence support, freshness, and retrieval relevance distinguishable.
- Prevent one high-confidence memory from masking contradictory or weaker evidence.
- Use provenance and contradiction-aware aggregation.
- Measure calibration on held-out labeled data (for example, Brier score and reliability/calibration error).
- Fit or adjust calibration only with appropriate evaluation data; do not claim calibration merely because a metric is calculated.
- Define thresholds for answer, qualify, ask, and abstain, with tests for each outcome.

### 5.4 Causal and procedural memory

Verify whether the system can preserve the full chain:

**context/problem → options → decision → rationale → action → observed outcome → supporting evidence**

- Distinguish explicitly stated rationale from inferred rationale.
- Preserve alternatives considered and why they were rejected when known.
- Learn procedures from successful and failed tasks only when supported by verified outcomes.
- Track prerequisites, tool/environment versions, verification steps, failure modes, and confidence.
- Do not promote a one-off success into a reliable procedure without adequate evidence.

## Phase 6 — Evaluation and regression suite

Create or extend a repeatable evaluation suite covering:

- Provenance spoofing and owner-confirmation forgery.
- Prompt injection attempting to create authority or bypass policy.
- Cross-tenant memory, procedure, graph, vault, and task access.
- Browser SSRF, redirects, DNS rebinding, and private-network access.
- Secret leakage through model context, logs, screenshots, errors, and traces.
- Concurrent spend reservations, process failure, and recovery.
- Bitemporal reconstruction and historical `as_of` queries.
- Evidence lineage, source-span validity, contradiction handling, and claim-level support.
- Confidence calibration, abstention, and retrieval ranking.
- Procedure learning and verification.

For each evaluation, record the scenario, expected result, actual result, and regression test. Prefer deterministic fixtures and adversarial tests that fail before the fix and pass after it.

## Phase 7 — Documentation and completion report

Update the relevant design/spec documents, operational guidance, and `docs/STATE.md` to reflect verified behavior only.

At completion, provide:

1. Findings re-check table: fixed / partially fixed / not fixed / not applicable.
2. Changes made, with file paths and commit SHAs.
3. Security decisions and any remaining trust assumptions.
4. Tests executed, exact commands, pass/fail/skip counts, and any limitations.
5. CI status based on actual workflow results.
6. Operational prerequisites, configuration, migrations, and deployment steps.
7. Remaining risks and deferred work, ranked by severity.
8. A capability status matrix using the lifecycle labels defined above.

Do not mark a phase complete because code exists. Mark it complete only when the relevant integration and tests demonstrate the intended behavior.

## Priority order

1. Authenticated provenance and authenticated action authority.
2. Browser destination validation and sandbox/control-channel boundaries.
3. Atomic cloud spend reservations.
4. Vault origin and one-use hardening.
5. Bitemporal history and evidence lineage.
6. Confidence calibration, causal/procedural memory, and broader evaluations.

Start with Phase 0. Then implement the highest-priority verified gaps in small commits. Do not add unrelated features until these foundations are demonstrably safe and correct.
