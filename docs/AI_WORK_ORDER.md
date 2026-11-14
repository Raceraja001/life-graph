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

Labels are the ones defined in section 9. "Complete" is deliberately absent
from any row whose remaining gap is operational.

- P0 exact-step-bound approval: **Implemented, Integrated, Unit-tested, Adversarially tested** — not operationally verified (no deployed run exercised yet)
- P0 isolated browser integration: **Needs verification** (not started this session; still the highest-priority incomplete item)
- P1 durable authorization: **Implemented, Integrated, Unit-tested** — multi-worker consistency proven with 16 concurrent threads against real Postgres; not yet exercised across separate OS processes or a real restart in a deployed environment
- P1 historical episode retrieval: **Implemented, Integrated, Unit-tested**
- P1 evidence/confidence evaluation: **Needs verification** (not started this session)
- P1 adversarial end-to-end testing: **Partially addressed** — replay, cross-errand, cross-step, cross-tenant, re-pointed selector, edited value, forged handle, tampered approval payload and store-outage scenarios are covered for the authorization path; browser/network scenarios depend on P0 §3 and remain open
- P2 operations documentation: **Needs verification** (not started this session)

### 2026-11-14 — P0 exact-bound approvals, P1 durable authorization, P1 historical episodes

```text
Date: 2026-11-14
Remote base commit: a9f35c97ad4c39bd8a6bc9d174b398306c9d6213 (origin/master == local HEAD at session start)
Working commit: b597fa2b73db6e550b93ae50c7d974960a679720
Tasks inspected: section 2 (P0 exact-bound approval), section 4 (P1 durable
  authorization), section 5 (P1 historical relative-date episodes). Sections 3,
  6, 7 and 8 were read but not implemented this session.

Findings (verified against the code, not assumed):
  - Section 2 was still open. AuthorizationCapability bound tenant, task,
    action_types, target_origins, expiry and an amount ceiling — and nothing
    else. There was no errand, step, selector or parameter binding, no
    consumption state and no consume() at all, so one tap on an approval card
    authorised any step of any later errand run that happened to be the same
    action type on the same origin, for the full 30-minute TTL, any number of
    times.
  - BrowserErrand carried no id, so there was nothing to bind an errand to.
    run_browser_errand minted a fresh errand_id on every call, including a
    resumed one.
  - Section 4 was open: CapabilityStore and StandingRuleStore were in-process
    dicts behind a threading.Lock.
  - Section 5 was open and the bug was exactly as described:
    memory_retrieval.retrieve passed datetime.now() to episodes.time_window
    regardless of as_of, so a historical query was answered with today's day
    summaries. episodes.time_window itself was correct relative to whatever
    anchor it was given (pinned by tests/unit/test_episodes_and_validity.py);
    the defect was only the anchor.
  - Two defects found while building, both in new code, both fixed before
    this entry: (a) StandingRule spells "any origin" as an *empty* frozenset,
    not None, so the durable rule store's first version silently persisted no
    rows for the owner's broadest rule; (b) StandingRule.max_amount has no
    column, and storing a rule without its ceiling is a widening — it is now
    refused with a ValueError rather than dropped.

Changes made:
  - life_graph/autonomy/approvals/capability.py — AuthorizationCapability
    gains errand_id, approval_id, step_index, target_selector,
    parameters_hash, one_use and consumed_at; new denial reasons
    ALREADY_CONSUMED, ERRAND_MISMATCH, STEP_MISMATCH, SELECTOR_MISMATCH,
    PARAMETERS_MISMATCH, STORE_UNAVAILABLE (all added to CHECK_REASONS);
    check_bindings() as the strict binding test; check() takes the bindings
    plus read_only; CapabilityStore.issue() records them; new
    CapabilityStore.consume() spends a one-use capability atomically; the
    store gained an optional durable backend that every method routes
    through (DurableBackend / DurableRuleBackend protocols).
  - life_graph/autonomy/approvals/policy_checker.py — _capability_for passes
    the exact bindings (read from structured_params, which the executor fills
    from the step it is holding) and spec.read_only through to verify().
  - life_graph/autonomy/approvals/durable_store.py (new) —
    DurableCapabilityStore and DurableStandingRuleStore over a synchronous
    psycopg2 engine; consumption is one UPDATE … WHERE consumed_at IS NULL …
    RETURNING. Insert raises on outage, reads return None, consume returns
    STORE_UNAVAILABLE: three fail-closed shapes, each chosen for its caller.
  - alembic/versions/059_durable_capabilities_and_standing_rules.py (new) —
    capabilities and standing_rules, with the indexes the work order lists
    plus (tenant_id, task_id) for revoke-all and expires_at for the purge.
  - life_graph/models/authorization.py (new) + models/db.py re-exports —
    Capability and StandingRuleRecord, so Base.metadata and docs/STATE.md
    tell the truth about the two tables. `alembic check` reports no drift for
    either (the rest of its output is pre-existing, unrelated drift).
  - life_graph/services/browser_errand.py — BrowserErrand.id; step_target()
    and canonical_parameters_hash(); CAPABILITY_GATED = (fill_field, click);
    StepResult carries target_selector/parameters_hash/errand_id; the
    executor consumes the capability atomically before touching the browser
    and aborts the step with the specific denial reason if it cannot.
  - life_graph/tools/errand.py — build_errand and run_browser_errand take
    errand_id so a resumed run is the same run; the approval card records
    target_selector and parameters_hash.
  - life_graph/services/notification_actions.py — _errand() binds the minted
    capability to errand_id, approval_id (the notification's own id),
    step_index, target_selector and parameters_hash, one-use; a card that
    cannot name its run and step is refused rather than widened.
  - life_graph/config.py + main.py — durable_authorization (default True) and
    the startup step that attaches the durable stores.
  - life_graph/services/memory_retrieval.py — the episode window is anchored
    to as_of's own calendar day in the tenant's timezone, and to today only
    when as_of is absent.
  - tests/conftest.py — an autouse fixture that returns the process-wide
    authorization stores to memory after each test. Several tests boot the
    app, which now attaches a Postgres backend to a module-global; without
    this the next test to call capability_store.issue() was quietly talking
    to a database. This was caught by the full-suite run, not in isolation.
  - tests/unit/test_exact_bound_capabilities.py (new, 59 tests),
    tests/unit/test_historical_episodes.py (new, 28 tests),
    tests/unit/test_jarvis_errands.py (the resume test now goes through a
    real pause to get a card that works, plus three new binding tests).

Tests run (exact commands):
  python -m alembic upgrade head                       # life_graph_dev, 057 -> 059
  LIFE_GRAPH_DATABASE_URL_SYNC=…/life_graph_dev_test python -m alembic upgrade head
  LIFE_GRAPH_DATABASE_URL_SYNC=…/life_graph_dev_test python -m alembic downgrade 058
  LIFE_GRAPH_DATABASE_URL_SYNC=…/life_graph_dev_test python -m alembic upgrade head
  python -m alembic check                              # drift review (see Findings)
  pytest tests/unit/test_exact_bound_capabilities.py tests/unit/test_historical_episodes.py \
         tests/unit/test_jarvis_errands.py tests/unit/test_trustworthy_execution_eval.py -v
  pytest tests/unit/ -q                                # before and after, compared
  ruff check life_graph/ ; ruff format --check <changed files>

Results:
  - Required four-file set: 130 passed, 0 failed.
  - Full unit suite: 5,167 passed, 26 failed, 5 skipped. The 26 failures are
    byte-identical to the list this working tree produces on the unmodified
    base commit (config model defaults, cron registration, graph tenant
    scoping, multimodal, MCP server config, ruff-on-PATH in the sandboxed
    verifier). They come from this machine's .env and from untracked
    work-in-progress files, not from these changes. The comparison was made
    by running the same suite on a clean worktree of a9f35c9 with the same
    .env and untracked files copied in, and diffing the FAILED lists.
  - The new suites are genuine regression tests, not tautologies: reverting
    the one-line anchor fix in memory_retrieval.py fails 6 of the 28
    historical-episode tests.
  - Postgres-backed tests ran (not skipped): 0 skips in
    test_exact_bound_capabilities.py.

Acceptance criteria met (section 2 "Tests"):
  - Capability cannot be replayed after consumption — ALREADY_CONSUMED, at
    both the policy check and the atomic consume, and end to end through
    run_browser_errand.
  - Two concurrent attempts cannot both consume — 16 threads on a barrier,
    in-process and against Postgres with 16 separate store objects; exactly
    one VALID, fifteen ALREADY_CONSUMED, both times.
  - Cross-errand, cross-step, cross-tenant, cross-origin, cross-action,
    cross-selector and cross-parameter reuse each denied with their own
    reason; a refusal does not burn the approval.
  - Expired and revoked fail closed; revocation is checked before
    consumption, so a kill switch reads as "the owner stopped this".
  - A changed page target or changed form value invalidates the approval.
  - Read-only operations acquire no side-effect authority: a navigate or a
    page read needs no capability, spends none, and still works after the
    errand's one approval has been spent.
  - Approval payload tampering cannot broaden authority: a card that cannot
    name its run and step mints nothing, and a card claiming a different step
    mints a mandate for *that* step, which the engine will not present.
  Section 4: restart/multi-worker (a second store object resolves and spends a
  capability the first issued), concurrent consumption, revocation, expiry,
  retention purge, cross-tenant isolation, migration up and down, and
  database-unavailable fail-closed behaviour are all covered.
  Section 5: historical and current retrieval, day/week/month/year and leap
  boundaries, the tenant timezone (including a UTC instant that is the next
  local day), a naive as_of, late-arriving captures, and valid-time versus
  recorded-time queries.

Which checks were which:
  - Unit: everything in the two new files and the errand/notification wiring.
  - Integration-tested: partially. The durable store was exercised against a
    real Postgres (migration 059, real transactions, real concurrency) from
    within the unit suite; the app's startup wiring is asserted, not booted.
  - Adversarially tested: replay, race, forged handle, lifted handle in
    another run, re-pointed selector, edited value, tampered approval
    metadata, cross-tenant spend, store outage.
  - Operationally verified: nothing. No deployed run.

Skipped tests: none. The Postgres-backed tests carry a skipif for an
  unreachable capabilities table so the suite still runs without a database;
  they were not skipped in this session's runs, and every property they check
  is also checked against the in-process store, which always runs.

Remaining risks / blockers:
  - P0 section 3 (isolated browser runtime) is untouched and is now the
    highest-priority incomplete item. Everything above binds *authority* to
    one action; none of it constrains what the browser can reach.
  - Durability is proven across threads and store objects, not across OS
    processes or a restart in a deployed environment. The statement that
    serialises consumption is a single conditional UPDATE, so the property
    does not depend on being in one process — but that is an argument, not
    evidence, until it runs under uvicorn plus an ARQ worker.
  - durable_authorization defaults to True, so a deployment whose database is
    unreachable will refuse to issue capabilities rather than falling back to
    in-memory ones. That is the intended fail-closed behaviour and it means
    an approval outage is now a database outage. Not yet observed in a
    deployed run; monitoring for STORE_UNAVAILABLE denials is section 8 work.
  - Standing rules with a max_amount cannot be persisted durably (the column
    does not exist and dropping the ceiling would widen the rule), so
    set_rules now raises for them. No caller passes one today; if the owner's
    rules screen ever needs ceilings, the table needs a column first.
  - episodes.time_window still returns no window for "last year" or "this
    month". Those terms fall through to semantic search, which does honour
    as_of and recorded_as_of, so nothing is mis-anchored — but they are not
    anchored either. Deliberately not added: episodes_between is LIMIT-ed and
    ordered by date ascending, so a year-wide window would return the oldest
    eight day summaries of that year, which is worse than the search it
    would replace. Widening the terms needs a sampling strategy first.
  - A fill_field step binds target_selector from step.field, because
    build_errand routes a fill's target there and a click's to step.selector.
    step_target() reads both. Noted because section 2 names
    "target_selector=step.selector", which would have left every fill
    unbound.
  - 26 pre-existing unit-test failures in this working tree remain
    unaddressed; they are environmental and predate this work.

Commit(s) pushed: none yet. Committed locally as b597fa2b73db on
  feat/work-order-p0-p1; pushing is held for the owner, who has not been
  asked for it in this session.
```

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