# Life Graph — AI Implementation Work Order

**Status:** Active  
**Priority order:** P0 → P1 → P2  
**Purpose:** Close the remaining security, authorization, browser-isolation, and memory-integrity gaps before expanding product capabilities.

This file is the source of truth for the implementation work. Before changing code, the coding agent must fetch the latest remote default branch and read this file in full. Do not rely on an earlier chat prompt, local copy, cached repository state, or assumptions about what has already been implemented.

---

## 0. Mandatory remote-first workflow

At the start of every work session:

1. Fetch the latest remote default branch and inspect its current commit SHA.
2. Pull/rebase or otherwise synchronize the working tree to that remote state without discarding user changes.
3. Read this entire file and the relevant architecture, security, state, and deployment documentation.
4. Inspect the current implementation and tests for every task below. Some items may already be implemented or partially addressed; verify before editing.
5. Update the **Progress log** below with the current commit, findings, and intended scope before making changes.
6. Implement only the highest-priority incomplete work that can be completed safely in this session.
7. Run focused tests, then the relevant broader test suite. Report exact commands and results.
8. Update this file with implementation status, test evidence, remaining risks, and commit SHA. Commit and push code and this file together when the repository workflow permits.

Never overwrite or revert unrelated remote or local work. If the remote changed during implementation, reconcile it before pushing. Do not claim a task is complete merely because code exists or unit tests pass.

## 1. Engineering rules

- Preserve existing architecture and abstractions unless inspection proves a change is necessary.
- Prefer small, reviewable commits. Avoid unrelated features, broad refactors, and speculative rewrites.
- Do not weaken, delete, skip, or loosen tests to obtain a green result.
- Add regression tests for every confirmed vulnerability or bug.
- Fail closed for authorization, isolation, secret access, and egress-control failures.
- Treat model output, browser content, tool arguments, notifications, and external data as untrusted.
- Keep tenant boundaries explicit and test cross-tenant isolation.
- Do not log secrets, credentials, raw secret values, or sensitive browser form contents.
- Keep documentation synchronized with actual behavior. Clearly distinguish implemented, integrated, tested, and operationally verified controls.
- If a requirement conflicts with current architecture or cannot be completed safely, document the blocker and propose the smallest safe next step. Do not silently omit it.

## 2. P0 — Bind owner approval to one exact browser action

### Problem to verify

Earlier review found that errand approval capabilities were scoped to tenant, action type, origin, and TTL, but were not bound to the exact errand/task/notification/step/target/parameters and were not consumed after use. Verify the current remote implementation before assuming this remains true.

### Required outcome

An approval must authorize only the specific action the owner saw and approved. Bind authorization to, at minimum:

- tenant ID;
- task and errand IDs;
- approval/notification ID;
- exact step ID;
- action type;
- normalized destination origin;
- target element or stable selector/target identity;
- canonicalized action parameters (for example, field identity and approved value, or click target);
- expiry and issuance context.

Requirements:

1. Show the owner the exact action, destination, and meaningful target details before approval.
2. On approval, mint a narrowly scoped, opaque capability for that exact action.
3. Validate every bound field at execution time. Reject mismatches, stale steps, changed destinations, altered parameters, and cross-tenant use.
4. Atomically consume one-use authorization for irreversible or outward-facing actions. Prevent replay and concurrent double execution.
5. Support explicit revocation and expiry. Ensure retries cannot accidentally repeat a completed external action; use idempotency/reconciliation where possible.
6. Keep low-risk read-only operations such as navigation or page reading separate from owner-authorized side effects. Do not grant broad side-effect authority merely to permit read-only work.
7. Never accept owner intent, standing rules, or privileged authority directly from model-generated payloads.

### Tests

- Capability cannot be replayed after successful consumption.
- Two concurrent attempts cannot both consume the same capability.
- Capability from one errand, task, step, tenant, origin, action, selector, or parameter set cannot authorize another.
- Expired and revoked capabilities fail closed.
- A changed page target or changed form value invalidates approval.
- Read-only operations do not acquire side-effect authority.
- Approval UI/action payload tampering cannot broaden authority.

## 3. P0 — Integrate browser errands with an actually isolated browser runtime

### Problem to verify

Earlier review found that an isolated browser/workspace Compose environment existed, but the active browser errand path used a bridged Playwright MCP driver rather than demonstrably executing inside that isolated environment. A DNS check in application code alone does not close DNS-rebinding or redirect TOCTOU gaps. Verify current wiring and deployment.

### Required outcome

The browser driver used by real errands must execute in a dedicated, constrained browser environment. A Compose file or design document alone is not integration.

Minimum controls:

- Dedicated non-root browser container/process.
- Read-only root filesystem where practical; drop unnecessary Linux capabilities.
- No Docker socket, host filesystem mounts, application database credentials, vault master keys, or unrelated service secrets.
- Separate authenticated control channel; do not expose an unauthenticated browser debugging/WebSocket endpoint to workspace code or other tenants.
- Default-deny outbound network policy.
- Browser traffic must pass through an egress proxy that validates destination host and resolved IP, blocks loopback/private/link-local/reserved/multicast and cloud metadata destinations, and prevents proxy bypass.
- Revalidate every redirect and navigation destination.
- Mitigate DNS rebinding by resolving and pinning the permitted destination at the network enforcement layer for the connection; do not rely only on a prior application-level DNS lookup.
- Restrict access to internal services and control-plane endpoints.
- Enforce execution time, resource, download, upload, and response-size limits.
- Clean up browser contexts and temporary data after each errand; isolate cookies/storage by tenant and errand.
- Fail closed if the isolated runtime, authenticated control channel, or egress proxy is unavailable. Do not silently fall back to a less isolated local/MCP driver for privileged errands.

Integrate these controls through the existing BrowserDriver abstraction where possible. Document which operations are supported and which are deliberately unavailable.

### Tests and verification

- Integration test the actual errand execution path and prove it uses the isolated runtime.
- Attempt direct network access that bypasses the proxy; it must fail.
- Test localhost, private IPv4/IPv6, alternate IP encodings, metadata endpoints, redirects to blocked destinations, and DNS rebinding scenarios.
- Verify workspace code cannot connect to the browser control endpoint without authentication.
- Verify tenant/session separation and cleanup.
- Verify failure of proxy/runtime causes a closed failure, not fallback.
- Record container/network configuration and test evidence. Do not call this production-safe until these checks pass in the deployed environment.

## 4. P1 — Make capabilities and standing rules durable and consistent across workers

### Problem to verify

Earlier review found in-memory capability and standing-rule stores, which do not survive restarts and are not shared across workers.

### Required outcome

- Persist capabilities, revocation, expiry, consumption state, and standing rules in a tenant-scoped durable store.
- Use database transactions/atomic conditional updates for one-use consumption and concurrent authorization checks.
- Enforce unique identifiers and tenant-scoped queries.
- Define behavior for restart, multiple workers, database outage, migration, and clock skew.
- Fail closed if the durable authorization store is unavailable.
- Keep standing-rule creation/editing behind authenticated owner-controlled flows; never let model output create or broaden a standing rule.
- Add migrations, indexes, retention policy, and audit events without storing secrets unnecessarily.

### Tests

Restart persistence, multi-worker consistency, concurrent consumption, revocation, expiry, cross-tenant isolation, migration behavior, and database-unavailable fail-closed behavior.

## 5. P1 — Correct historical relative-date episode retrieval

### Problem to verify

Earlier review found that episode-window selection used the current date even when an historical `as_of` value was supplied. Verify the latest implementation and all callers.

### Required outcome

- Relative terms such as today, yesterday, this week, last month, and last year must be anchored to the correct reference date when historical `as_of` retrieval is requested.
- Preserve current-date behavior when `as_of` is absent.
- Keep valid time (when an event happened) distinct from transaction/recorded time (when the system learned it).
- Apply the relevant tenant/user timezone consistently.
- Handle late-arriving evidence without rewriting what the system knew at an earlier transaction-time cutoff.

### Tests

Historical and current retrieval, day/week/month/year boundaries, timezone/DST boundaries where applicable, late-arriving captures, and valid-time versus recorded-time queries.

## 6. P1 — Strengthen evidence lineage and confidence evaluation

### Required outcome

Inspect the full capture → normalization → memory/evidence → retrieval → answer path, including every supported ingestion surface.

- Preserve source identity and exact supporting spans/locations wherever available.
- Ensure claim-level citations point to evidence that actually supports the claim; a citation marker or lexical overlap alone is not proof of entailment.
- Distinguish supported, contradicted, unsupported, unresolved, and contextual evidence states accurately.
- Preserve contradictory evidence and temporal changes instead of silently overwriting them.
- Distinguish owner-confirmed facts from inferred or externally sourced information.
- Ensure confidence is not presented as calibrated unless it has been evaluated and calibrated on suitable data.
- Build representative evaluation data with separate calibration and held-out test sets.
- Report useful metrics such as Brier score, ECE/calibration gap, precision/recall, contradiction detection, and abstention quality, broken down by memory/evidence type where practical.
- Keep deterministic/lexical fallback behavior explicit and measurable; do not describe it as semantic entailment.

### Tests

End-to-end provenance across capture paths, unsupported claims, contradictory sources, stale facts, late evidence, missing source spans, tenant isolation, and confidence/abstention regressions.

## 7. P1 — Adversarial end-to-end security tests

Add or extend tests that exercise complete workflows, not just isolated helpers:

- Prompt injection in page content and external documents.
- Forged or replayed owner approvals.
- Cross-errand and cross-tenant capability reuse.
- Browser redirects, DNS rebinding, SSRF, internal service access, and proxy bypass.
- Secret exfiltration attempts and accidental secret logging.
- Browser session/cookie leakage between errands or tenants.
- Spend reservation concurrency, timeouts, retries, process restart, and multi-worker behavior.
- Memory provenance spoofing, contradictory evidence, late-arriving evidence, historical as-of retrieval, and unsupported answer claims.

Record the threat scenario, expected denial/safe behavior, actual result, and test identifier.

## 8. P2 — Operations and recovery documentation

Document and verify:

- Browser runtime and egress proxy deployment/configuration.
- Required secrets and least-privilege handling.
- Durable authorization schema and migrations.
- Restart/recovery and multi-worker behavior.
- Browser/session cleanup and retention.
- Audit logging and incident investigation.
- Emergency kill switch for autonomous browser actions.
- Monitoring/alerts for denied egress, authorization failures, replay attempts, and resource/spend limits.
- Known limitations and controls that remain unverified.

## 9. Definition of done

A task may be marked complete only with evidence. Use these labels precisely:

- **Designed:** documented approach exists.
- **Implemented:** code/configuration exists.
- **Integrated:** the real application execution path uses it.
- **Unit-tested:** focused unit tests pass.
- **Integration-tested:** interacting services/components were exercised.
- **Adversarially tested:** relevant attack scenarios were exercised.
- **Operationally verified:** deployed runtime/network behavior was checked.
- **Complete:** all acceptance criteria for that task have evidence and documentation.

A green unit-test suite does not prove network isolation, multi-worker durability, calibrated confidence, or production readiness.

## 10. Progress log

The coding agent must append concise entries here. Do not erase prior entries; add a new dated entry.

### Current status

- P0 exact-step-bound approval: **Needs verification**
- P0 isolated browser integration: **Needs verification**
- P1 durable authorization: **Needs verification**
- P1 historical episode retrieval: **Needs verification**
- P1 evidence/confidence evaluation: **Needs verification**
- P1 adversarial end-to-end testing: **Needs verification**
- P2 operations documentation: **Needs verification**

### Entry template

```text
Date:
Remote base commit:
Working commit:
Tasks inspected:
Findings:
Changes made:
Tests run (exact commands):
Results:
Acceptance criteria met:
Remaining risks/blockers:
Commit(s) pushed:
```

---

## 11. Required completion report

At the end of each work session, report:

1. Remote base commit SHA and working commit SHA.
2. Exact files changed and why.
3. Which acceptance criteria were met, with evidence.
4. Exact test commands and pass/fail counts.
5. Which checks were unit, integration, adversarial, or operational.
6. Any skipped tests and why.
7. Remaining vulnerabilities, assumptions, and blockers.
8. Whether changes were pushed to remote.
9. Updated status in this file.

**Do not claim the whole work order is complete until every P0 and P1 item has been verified to its stated standard.**