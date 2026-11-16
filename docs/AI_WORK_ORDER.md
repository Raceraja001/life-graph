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
- P0 isolated browser integration: **Designed, Implemented, Integrated, Unit-tested, Adversarially tested** through slice 2 — the real `run_browser_errand` path selects only `IsolatedBrowserDriver` against the sandbox browser-server endpoint, fails closed when it is absent, never falls back to `MCPBrowserDriver`, enforces per-errand context lifecycle and cleanup, and now puts a destination-validating, IP-pinning egress proxy in front of every browser context (`services/browser_egress_proxy.py`), refusing the errand when that proxy is unavailable. Of the three §3 controls slice 1 left open, two are now closed in code — the egress proxy and network-layer destination/DNS pinning — and one is **still Not implemented**: the authenticated tenant/errand-scoped control channel in front of the browser-server websocket (slice 2 stopped *telling* the workspace container that endpoint, but it is still reachable on the shared bridge). **Not Operationally verified end to end**: the shipped `compose.sandbox.yaml` has no proxy service, and an ephemeral proxy on the application's loopback is unreachable from a container on an `internal: true` bridge, so no browser errand has yet reached a real site. The container chassis itself was operationally checked on 2026-11-16 (non-root, read-only root, caps dropped, no published port, no host route in, no egress out) — see the entries below. Do not call the browser path production-safe.
- P1 durable authorization: **Implemented, Integrated, Unit-tested** — multi-worker consistency proven with 16 concurrent threads against real Postgres; not yet exercised across separate OS processes or a real restart in a deployed environment
- P1 historical episode retrieval: **Implemented, Integrated, Unit-tested**
- P1 evidence/confidence evaluation: **Needs verification** (not started this session)
- P1 adversarial end-to-end testing: **Partially addressed** — replay, cross-errand, cross-step, cross-tenant, re-pointed selector, edited value, forged handle, tampered approval payload and store-outage scenarios are covered for the authorization path. Slice 2 adds the network scenarios §7 asks for at the egress-enforcement layer: DNS rebinding, SSRF to loopback/private/link-local/carrier-NAT/reserved/multicast/broadcast ranges, alternate IP encodings (bare decimal, octal, hex, IPv4-mapped IPv6, NAT64, 6to4), cloud metadata endpoints, non-web ports, forbidden schemes, redirects off the approved origins, and request smuggling onto an already-authorised connection. Still open end to end: those same scenarios driven through a real Chromium against a deployed proxy, and proxy-bypass attempts from inside the container
- P2 operations documentation: **Needs verification** (not started this session)

### 2026-11-16 — P0 isolated browser runtime, slice 2: network-layer egress proxy and DNS pinning

```text
Date: 2026-11-16
Remote base commit: 2853f06 (feat(browser): isolated browser driver adapter
  and fail-closed seam (#244)) on branch
  feat/work-order-browser-egress-proxy-p0 from master.
Working commit: 994517f on that branch. Not pushed — the push is the
  developer's call.
Tasks inspected: section 3 (P0 isolated browser integration), the three
  controls slice 1 left open; life_graph/services/browser_sandbox_driver.py,
  life_graph/services/destination_validator.py,
  life_graph/services/sandbox.py, life_graph/tools/errand.py,
  life_graph/config.py, compose.sandbox.yaml,
  tests/unit/test_sandbox_isolation.py,
  tests/unit/test_isolated_browser_driver.py,
  docs/LIFE_GRAPH_IMPROVEMENT_PLAN.md.

Findings (before changing code):
  - The destination rules §3 asks for already existed, and existed *once*:
    services/destination_validator.py's address_refusal() covers loopback,
    the unspecified address, link-local, multicast, private (which in
    CPython includes the broadcast address, the documentation ranges and
    198.18.0.0/15 benchmarking), reserved and carrier-NAT, plus the cloud
    metadata addresses by name, and _unwrap() judges IPv4-mapped IPv6, NAT64
    and 6to4 as the IPv4 address they carry. parse_host_address() handles the
    bare-decimal/octal/hex spellings. The gap was never the rules — it was
    *where* they ran. So the proxy reuses that module rather than carrying a
    second copy of the ranges, which is also the only way the two cannot
    drift apart.
  - The gap the module's own docstring names: it resolves the name and the
    browser resolves the name again. One application-level check also sees
    exactly one URL, so every redirect hop, sub-resource and page-initiated
    fetch() was unjudged. Both are closed only by deciding at the connection.
  - compose.sandbox.yaml handed the `workspace` service
    SANDBOX_BROWSER_WS_URL: ws://browser:9222/, and
    tests/unit/test_sandbox_isolation.py asserted that it did. Playwright's
    browser-server websocket is unauthenticated, so that variable was a
    remote-code-execution handle on a browser that may be holding the owner's
    logged-in banking session, handed to the one container that runs
    untrusted errand work.
  - services/sandbox.py's workspace_spec(browser=...) sets the same variable,
    but it is opt-in and has no caller anywhere in the application.

Threat model for this slice (what it does and does not close):
  - Closes: DNS rebinding against a browser errand (resolved once, the socket
    goes to that address, the browser's own lookup never happens); a redirect
    or a page-initiated request to loopback/RFC1918/link-local/carrier-NAT/
    reserved/documentation/benchmarking/multicast/broadcast/unspecified or a
    cloud metadata endpoint, in every spelling including the IPv6 wrappers;
    CONNECT used as a general-purpose TCP relay to 22/25/3306/5432/6379 — and
    to 9222, the sandbox browser's own control port; a redirect off the
    errand's approved origins; a hop credential (Proxy-Authorization) being
    forwarded to a destination; a second request smuggled onto a connection
    whose single request had already been authorised; the workspace container
    being *told* where the browser control endpoint is.
  - Does not close: the browser-server websocket is still unauthenticated and
    the two sandbox services still share a bridge, so the endpoint is
    guessable even though nothing is told it — the authenticated control
    channel is still the open §3 requirement; the proxy does not terminate
    TLS by design, so it authorises where a connection goes and not what
    travels through it (response-size and download limits stay with the
    browser and the errand engine); and "default-deny" is a property of the
    network, not of the proxy — it holds because the sandbox bridge is
    `internal: true` and gives the browser container no gateway, so the proxy
    is its only path out. Proxy *and* no route; neither alone.

Changes made:
  - NEW life_graph/services/browser_egress_proxy.py — BrowserEgressProxy, an
    async forward proxy. Handles CONNECT (tunnel) and absolute-form HTTP.
    Authorisation order is cheapest-and-most-decisive first, so a destination
    that was never going to be allowed causes no DNS query (a query is an
    outbound signal to whoever runs that zone): port against
    DEFAULT_ALLOWED_PORTS = (80, 443, 8080, 8443); then
    destination_validator.split_destination() for scheme, userinfo, control
    characters, the local/metadata names, the .localhost/.internal suffixes
    and an address literal in any spelling; then the origin fence; then one
    resolution, with address_refusal() applied to EVERY address returned, not
    the first. The permitted address is the pin: the socket is opened with
    host=<address>, so asyncio consults no resolver. start() -> (host, port)
    on 127.0.0.1:0 by default, stop(), async context manager, and `url` raises
    rather than answering "" for a proxy that is not listening — a blank url
    handed to new_context() would quietly mean "no proxy", which is the one
    failure the module exists to prevent. Refusal is exactly
    b"HTTP/1.1 403 Forbidden\r\n\r\n" with no body and no reason (the client
    is a page the owner did not write); 502 is kept separate from 403 so a
    denied-egress alert does not fire on a flaky site. Forwarded requests get
    Host rewritten to the authorised authority, Proxy-Authorization and
    Proxy-Connection dropped, and Connection: close forced — without that a
    client could send a second request, to a different host, on a connection
    this proxy had finished authorising. Decisions are recorded (bounded) for
    the audit trail; resolver and connector are seams so the suite needs no
    network. Nothing terminates TLS, deliberately, and the docstring says so.
  - life_graph/services/browser_sandbox_driver.py — IsolatedBrowserTransport
    .open_session() now takes proxy_url; PlaywrightServerTransport passes it
    as new_context(proxy={"server": ...}) (per context, not per browser — a
    browser-level proxy is a setting one errand could leave for the next).
    IsolatedBrowserDriver takes proxy_url / allowed_origins /
    enforce_egress_proxy / proxy_factory, and on first use either points at a
    configured proxy, mints an ephemeral one scoped to the errand and fenced
    to its approved origins, or — enforcement on and no proxy — raises
    SandboxUnavailableError. _stop_proxy() runs in close()'s `finally`, after
    the session, so a session that would not close cannot leave a listener
    behind. New helpers egress_proxy_enforced() (defaults on when the setting
    is absent) and configured_egress_proxy_url() (a set-but-unusable value
    reads as "none configured", so a typo falls back to the enforced path and
    never to going direct).
  - life_graph/tools/errand.py — get_driver() takes allowed_origins and hands
    the plan's fence to the driver, so the origin check applies to every
    request the *browser* makes rather than only the urls the plan named.
    Safe to take from model output for the same reason _fenced() does: a
    fence can only narrow.
  - life_graph/config.py + .env.example — browser_sandbox_egress_proxy_url
    ("" = mint an ephemeral per-errand proxy) and
    browser_sandbox_enforce_egress_proxy (True).
  - compose.sandbox.yaml — SANDBOX_BROWSER_WS_URL removed from `workspace`,
    with the reasoning in place of it. §3 requirement "do not expose an
    unauthenticated browser debugging/WebSocket endpoint to workspace code":
    partially closed (told: no; reachable: still yes).
  - tests/unit/test_sandbox_isolation.py —
    test_the_browser_endpoint_the_workspace_is_given_is_internal became
    test_the_workspace_is_not_given_the_browser_control_endpoint (an absence
    test that also refuses any workspace value naming the browser or its
    port, so a renamed variable cannot pass) plus
    test_the_browser_endpoint_a_spec_may_be_given_is_internal_and_opt_in,
    which keeps the workspace_spec(browser=...) assertion. An inversion, not
    a loosening: the file has one more assertion than before, and the
    mutation check below shows both tests bite.
  - tests/unit/test_isolated_browser_driver.py — FakeTransport.open_session
    accepts and records proxy_url. Signature addition only; no assertion
    changed or removed.
  - NEW tests/unit/test_browser_egress_proxy.py — 41 tests.
  - docs/STATE.md and docs/feature-inventory.html regenerated
    (292 -> 294 settings).

Tests run (exact commands):
  1. /home/raja/.venvs/life-graph/bin/pytest \
       tests/unit/test_browser_egress_proxy.py \
       tests/unit/test_isolated_browser_driver.py \
       tests/unit/test_exact_bound_capabilities.py \
       tests/unit/test_historical_episodes.py \
       tests/unit/test_jarvis_errands.py \
       tests/unit/test_trustworthy_execution_eval.py -v
     (plus tests/unit/test_sandbox_isolation.py, which this slice changes)
  2. /home/raja/.venvs/life-graph/bin/pytest tests/unit/ -q, before and after,
     in the same working tree (the slice stashed for the baseline run so the
     environment was identical), FAILED lists diffed
  3. /home/raja/.venvs/life-graph/bin/ruff check + ruff format --check on
     every changed file
  4. /home/raja/.venvs/life-graph/bin/python scripts/gen_state.py --check

Results:
  1. 310 passed, 0 failed (269 pre-existing + 41 new).
  2. Baseline (this slice stashed): 26 failed, 5212 passed, 5 skipped.
     After: 26 failed, 5254 passed, 5 skipped.
     The FAILED lists are identical (diffed), so 0 regressions and +42
     passing (41 new tests, plus the one test that became two). Those 26 are
     pre-existing on this machine and unrelated — model-default,
     cron-registration, graph-tenant-scoping, multimodal-router/service,
     diff-scoped-verifier, mcp-servers-config and jarvis-prompt tests.
     A first attempt to baseline in a clean `git worktree` was discarded as
     invalid rather than reported: without this tree's .env and untracked
     files it skipped 24 tests instead of 5 and is not comparable.
  3. All checks passed. (`ruff check life_graph/` still reports the same 31
     pre-existing errors in untracked work-in-progress files — api/lore.py,
     prosody/, tools/media_generation.py — none touched here.)
  4. OK: docs/STATE.md is up to date.

Mutation checks (that the new tests actually bite) — seven applied one at a
time and each reverted:
  - connect to pinned.host instead of pinned.ip (undo the pin) -> 7 failures,
    including test_proxy_pins_ip_against_dns_rebinding.
  - judge only the first resolved address instead of all of them -> 1 failure
    (test_every_resolved_address_must_be_permitted).
  - drop the port allowlist -> 2 failures (test_proxy_blocks_dangerous_ports,
    test_authorize_is_usable_on_its_own).
  - return "" instead of raising when no proxy can be started (fail open) ->
    2 failures (test_the_errand_refuses_to_run_when_no_proxy_can_be_started,
    test_a_proxy_that_hangs_on_start_is_also_a_refusal).
  - pass proxy_url="" to the transport (browser goes direct) -> 4 failures.
  - remove `await self._stop_proxy()` from close()'s finally -> 2 failures,
    including the stubborn-session case.
  - put SANDBOX_BROWSER_WS_URL back in compose.sandbox.yaml -> 2 failures,
    one in each of the two test files that assert the absence.

Acceptance criteria met (§3), with the labels from section 9:
  - Egress proxy validating destination host and resolved IP, blocking
    loopback/private/link-local/reserved/multicast and cloud metadata:
    Implemented, Integrated, Unit-tested, Adversarially tested.
  - DNS rebinding mitigated by resolving and pinning at the network
    enforcement layer rather than relying on a prior application-level
    lookup: Implemented, Integrated, Unit-tested, Adversarially tested.
  - Every redirect and navigation destination revalidated: Implemented by
    construction (the proxy sees each hop as its own request) and unit-tested
    at the proxy; not yet observed end to end through a real Chromium.
  - Unauthenticated browser control endpoint not exposed to workspace code:
    Partially implemented — not told, still reachable on the shared bridge.
  - Fail closed if the egress proxy is unavailable: Implemented, Integrated,
    Unit-tested, Adversarially tested.
  - Default-deny outbound network policy: Designed and Implemented at two
    layers (the `internal: true` bridge, which is operationally verified from
    slice 1, plus this proxy), but NOT Operationally verified together.

Remaining risks and blockers (the smallest safe next steps, in order):
  1. The ephemeral proxy binds the application's loopback, and a container on
     an `internal: true` bridge cannot reach the application's loopback. So
     the shipped compose stack still cannot send a browser errand to a real
     site: it fails at the network, which is the right direction and is not
     the finished control. Next step: an `egress` service in
     compose.sandbox.yaml attached to both sandbox_internal and a second
     egress-only network, running this proxy, with
     LIFE_GRAPH_BROWSER_SANDBOX_EGRESS_PROXY_URL pointing at it — then the
     §3 verification list (proxy bypass attempt, redirect to a blocked
     destination, real rebinding zone) run against the deployed stack.
  2. The authenticated control channel in front of ws://browser:9222 is still
     absent. Until it exists, nothing other than this application may be
     attached to life_graph_sandbox_internal.
  3. Nothing terminates TLS, so the proxy cannot enforce response-size,
     download or content limits; those stay with the browser and the errand
     engine and are not yet implemented there either.
  4. Chromium's proxy setting does not cover every path out of a process
     (WebRTC, QUIC, a bypass list). The control that makes the proxy
     unavoidable is the absent route, not the setting.

Do not call the browser errand path production-safe. Nothing in this slice
has been exercised against a real site through a real Chromium.
```

### 2026-11-16 — P0 isolated browser runtime, slice 1: driver adapter and fail-closed seam

```text
Date: 2026-11-16
Remote base commit: 596a1a016af773d1ad3c9a9bed509977db94fba2
Working commit: 756e697on branch feat/work-order-browser-isolation-p0 from 596a1a0
Tasks inspected: section 3 (P0 isolated browser integration) and the
  2026-11-15 assignment; life_graph/tools/errand.py,
  life_graph/services/browser_errand.py, life_graph/services/sandbox.py,
  compose.sandbox.yaml, Dockerfile.browser, Dockerfile.workspace,
  tests/unit/test_jarvis_errands.py, docs/LIFE_GRAPH_IMPROVEMENT_PLAN.md.

Findings (architecture trace, before changing code):
  - Path was: run_browser_errand -> get_driver() -> MCPBrowserDriver() when
    `mcp_playwright_browser_navigate` was in the tool registry -> registry
    .execute() -> services/mcp_bridge.py -> whatever browser the bridged
    Playwright MCP server owns. That server runs as a child of the
    application process on the host, so the "browser errand" browser was a
    host browser sitting beside the app's own credentials. No container
    boundary was crossed anywhere on the live path.
  - get_driver() took no arguments and therefore could not scope a session to
    a tenant or an errand; the driver had no close()/lifecycle at all, so
    cookies, localStorage and history were whatever the shared MCP browser
    had accumulated, across errands and across tenants.
  - The isolation chassis existed and was unreferenced by that path:
    compose.sandbox.yaml `browser` service (Playwright `run-server` on
    9222, `expose` not `ports`, internal-only bridge) plus
    services/sandbox.py browser_spec()/SandboxManager/validate_spec.
    Container boundary: app process (host) -> ws://browser:9222 on
    life_graph_sandbox_internal -> `python3 -m playwright run-server`
    (uid 1000) -> Chromium from /ms-playwright with /tmp and /dev/shm tmpfs.
  - No egress proxy, no authenticated control channel, and no network-layer
    destination pinning exist anywhere in the repo. The application-level
    destination validator (services/destination_validator.py) and the
    approval/vault/capability checks are the only destination controls, and
    they are preflight checks in the app, not enforcement at the boundary.

Threat model for this slice (what it does and does not close):
  - Closes: an errand running in an uncontained host browser; an errand
    running at all when the contained runtime is missing; a silent downgrade
    to the MCP/host driver; cookies or storage shared between two errands or
    two tenants; a browser context outliving the errand that opened it; a
    driver reporting an origin it expected rather than the one the page is
    on (which would defeat the vault's origin check).
  - Does not close: SSRF/DNS-rebinding at the network layer (still
    application preflight only); an unauthenticated browser-server websocket
    reachable by anything else on the internal network; browser egress
    (currently *all* egress is denied by `internal: true`, which is safe but
    also means no real site is reachable yet — the allowlisting proxy is the
    next slice); downloads (refused outright for now).

Changes made:
  - NEW life_graph/services/browser_sandbox_driver.py — IsolatedBrowserDriver
    (the five BrowserDriver methods + close() + async context manager) over
    an injectable IsolatedBrowserTransport; PlaywrightServerTransport as the
    real transport and the only Playwright importer in the codebase;
    configured_endpoint()/browser_sandbox_available()/sandbox_mode()/
    sandbox_timeout()/redacted(); BrowserRuntimeUnusableError.
    Fail-closed rules: unconfigured or non-ws/http endpoint raises
    SandboxUnavailableError from __init__; unreachable/refused/timeout/5xx/
    no-session raises it from the first step; a session lost mid-errand or an
    operation timeout marks the session lost so every later step refuses; a
    closed driver never silently opens a second context; cleanup failure
    raises rather than being swallowed. current_origin() is read live and
    `fullmatch`-validated against https?://[A-Za-z0-9._~%:\[\]-]+ — blank,
    "about:blank", "null" and a prefix match are all RuntimeError, and the
    page's own text is never put into the message. Endpoint is redacted to
    scheme://host:port in every log line, error and repr.
  - life_graph/tools/errand.py — get_driver(errand_id, tenant_id) now returns
    IsolatedBrowserDriver or None, and nothing else; the `_driver_override`
    seam is the only other way in and is explicit. MCPBrowserDriver is kept
    but is unreachable from the seam. The driver is built *after*
    build_errand so the session is scoped to the minted run id. A None
    driver now reports {"status": "failed", "reason": "sandbox_unavailable",
    "message"/"error": NO_BROWSER}; NO_BROWSER is now the isolation sentence.
    executor.run() is wrapped so `_release(driver)` runs in a `finally` on
    every exit — done, failed, denied, paused — and a cleanup failure adds
    "cleanup_failed": true to the reply instead of only a log line.
  - life_graph/services/browser_errand.py — BrowserDriver is @runtime_checkable
    (method-presence only) so a test can assert a concrete driver presents all
    five; docstring records that lifecycle is the caller's job. No behaviour
    change.
  - life_graph/config.py — browser_sandbox_url, browser_sandbox_ws_url,
    browser_sandbox_mode ("isolated" default; "disabled"/"mock"; unknown
    reads as disabled), browser_sandbox_timeout_seconds (30). Empty url means
    no browser errands.
  - pyproject.toml — new optional extra `browser-sandbox` = playwright==1.52.0
    (client only, version pinned to Dockerfile.browser's base image), folded
    into `all`. .env.example documents the three settings.
  - tests/unit/test_jarvis_errands.py — the three `get_driver` monkeypatches
    moved to the `_driver_override` seam (signature change, not a loosening);
    test_no_browser_connected_is_a_sentence_not_a_crash now goes through the
    real get_driver with no sandbox configured and additionally asserts
    status/reason. No assertion was removed or weakened.
  - NEW tests/unit/test_isolated_browser_driver.py — 45 tests.
  - docs/STATE.md regenerated (288 -> 292 settings).

Tests run (exact commands):
  1. /home/raja/.venvs/life-graph/bin/pytest \
       tests/unit/test_isolated_browser_driver.py \
       tests/unit/test_exact_bound_capabilities.py \
       tests/unit/test_historical_episodes.py \
       tests/unit/test_jarvis_errands.py \
       tests/unit/test_trustworthy_execution_eval.py -v
  2. /home/raja/.venvs/life-graph/bin/pytest tests/unit/ -q   (before and
     after the change, failure lists diffed)
  3. /home/raja/.venvs/life-graph/bin/ruff check life_graph/ ;
     ruff format --check on the changed files
  4. /home/raja/.venvs/life-graph/bin/python scripts/gen_state.py --check
  5. docker compose -f compose.sandbox.yaml up -d browser workspace ;
     docker inspect / docker port / docker network inspect ;
     in-container and host-side connection attempts ; down -v
  6. LIFE_GRAPH_BROWSER_SANDBOX_URL=ws://browser:9222/ python -c "<the real
     get_driver + IsolatedBrowserDriver.navigate path>"

Results:
  1. 175 passed (130 before this slice + 45 new). 0 failures.
  2. Baseline 26 failed / 5167 passed; after 26 failed / 5212 passed. The
     FAILED lists are byte-identical (diffed), so 0 regressions and +45
     passing. Those 26 are pre-existing on this machine and unrelated
     (model-default, cron-registration, graph-tenant, multimodal-router and
     verifier-sandbox tests).
  3. All checks passed on the changed files. (`ruff check life_graph/`
     reports 31 pre-existing errors in untracked work-in-progress files —
     api/lore.py, prosody/, tools/media_generation.py — none touched here.)
  4. OK: docs/STATE.md is up to date.
  5. Container evidence, real docker run:
       - health: healthy (browser-server accepting on 9222 inside).
       - User=1000:1000, ReadonlyRootfs=true, CapDrop=[ALL], CapAdd=[],
         SecurityOpt=[no-new-privileges:true], Privileged=false,
         PidsLimit=512, Memory=1g, Binds=[], PortBindings=map[].
       - `docker port` prints nothing: no port on host/LAN/public.
       - network life_graph_sandbox_internal: Internal=true.
       - container env is HOME/PLAYWRIGHT_BROWSERS_PATH/SANDBOX_*/TZ/PYTHON*
         only: no LIFE_GRAPH_*, no provider key, no DB credential.
       - from the host: 127.0.0.1:9222 ConnectionRefused, [::1]:9222 OSError.
       - from inside the internal network (alpine on the same bridge):
         browser:9222 reachable, 93.184.216.34:443 blocked.
       - from inside the browser container: 93.184.216.34:443,
         169.254.169.254:80 and 8.8.8.8:53 all blocked (OSError).
       - stack torn down with `down -v`; no leftover container or network.
  6. mode=isolated, configured_endpoint=ws://browser:9222/, available=True,
     get_driver -> IsolatedBrowserDriver(scope='default/errand_live',
     endpoint='ws://browser:9222'); navigate raised
     SandboxUnavailableError("the playwright client is not installed, so the
     isolated browser runtime cannot be driven"); with the setting cleared,
     get_driver returned None. Fail-closed on the real path, on real settings.

Mutation checks (that the new tests actually bite):
  - Reintroducing the MCP fallback inside get_driver -> 3 failures
    (test_no_silent_fallback_to_mcp_when_isolated_mode,
    test_the_mcp_driver_is_never_what_the_seam_returns,
    test_the_tool_refuses_the_errand_when_the_sandbox_is_offline).
  - Removing `_release(driver)` from the finally block and loosening the
    origin `fullmatch` to a `search` -> 4 failures. Both mutations reverted.

Acceptance criteria met (from the 2026-11-15 assignment):
  - (1) architecture trace recorded above: yes.
  - (2) concrete isolated BrowserDriver adapter, no silent fallback: yes,
        Implemented + Integrated + Unit-tested + Adversarially tested.
  - (4) per-errand context, time ceiling, close on success/failure/pause,
        explicit cleanup policy: yes at the application layer. Not yet
        exercised against a real container (see blockers).
  - (8) vault flow unchanged and still origin-checked against the live
        driver origin: unchanged; existing assertions still pass, and a
        vault fill with no mandate is still denied and still asked about.
  - (9) runtime unavailability / auth failure / cleanup failure as explicit
        closed failures: yes for runtime and cleanup. Auth failure is N/A
        until (3) exists.
  - (10) settings, extras, .env.example and docs/STATE.md updated: yes. No
        unused compose service was added and nothing new is claimed from
        configuration presence.
  NOT met, deliberately out of this slice: (3) authenticated tenant/errand
  -scoped control channel; (5) default-deny egress with proxy-bypass
  prevention; (6) network-boundary destination policy with per-connection
  address pinning and redirect re-checks; (7) review of whether
  workspace->browser reachability should be removed entirely.

Remaining risks/blockers:
  - The browser-server websocket on the internal network is still
    unauthenticated. Anything else on life_graph_sandbox_internal — today,
    the `workspace` service — can drive that browser. Verified reachable
    from a throwaway container on that bridge. This is §3 control (3) and is
    the next slice; until it lands, nothing other than the application
    should be attached to that network.
  - No live drive of the sandboxed browser has been performed. Two reasons,
    both real: the Playwright client is not installed in this venv (now
    declared as the `browser-sandbox` extra), and `internal: true` gives the
    host no route to the container, so the app has to be *on* that network —
    which is a deployment change that belongs with the egress proxy slice.
    PlaywrightServerTransport is therefore Implemented but NOT
    Integration-tested or Operationally verified. Its failure path is
    verified; its success path is not.
  - With `internal: true` and no proxy, a browser errand that reached a real
    site would fail at the network. The fail-closed direction is correct but
    the feature is not usable end to end until the allowlisting proxy exists.
  - Downloads are refused (accept_downloads=False) rather than captured to a
    policed location; the "download a statement" errand in the tool
    description is not supported yet. Documented here rather than silently
    broken.
  - `MCPBrowserDriver` remains in the tree, unreachable from the seam but
    reachable by passing it to set_driver_override. That is deliberate and
    explicit, not a fallback; it is still a thing a future change could
    misuse, so it is called out in its own docstring.

Commit(s) pushed: none yet — review first (the developer approves plans and
  diffs before anything is pushed).
```

### 2026-11-14 — P0 exact-bound approvals, P1 durable authorization, P1 historical episodes

```text
Date: 2026-11-14
Remote base commit: a9f35c97ad4c39bd8a6bc9d174b398306c9d6213 (origin/master == local HEAD at session start)
Working commit: 756e697b597fa2b73db6e550b93ae50c7d974960a679720
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

Commit(s) pushed: 3ab59b9 (PR #243 merged to origin/master; working commits b597fa2, 5e2c803)
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

### 2026-11-15 — P0 isolated browser runtime: implementation assignment

```text
Date: 2026-11-15
Remote base commit: fe514e1a31467fd77ba15d5fd20a05745718c7f9
Tasks inspected: section 3 (P0 isolated browser integration), current
  `life_graph/tools/errand.py`, `life_graph/services/browser_errand.py`,
  `life_graph/services/sandbox.py`, `life_graph/services/mcp_bridge.py`,
  `compose.sandbox.yaml`, and `Dockerfile.browser`.

Verified starting state:
  - `life_graph/tools/errand.py` currently selects `MCPBrowserDriver`
    when `mcp_playwright_browser_navigate` is registered.
  - That driver sends browser operations through the generic bridged MCP
    registry. It does not, by itself, prove that the request reaches the
    isolated browser container.
  - `compose.sandbox.yaml` describes a non-root browser container and a
    workspace container on an internal-only network. This is a chassis,
    not proof that the real errand path uses it.
  - The sandbox browser service exposes a Playwright browser-server
    WebSocket on the internal network. Treat that endpoint as a privileged
    remote-control interface, not as a generally reachable service.
  - The reviewed files do not establish a deployed egress proxy with
    redirect-aware destination checks and network-layer DNS pinning.
  - Do not remove or bypass the existing destination validator, owner
    approval policy, vault origin checks, or exact-action capability checks.

Priority: P0. This assignment supersedes feature work until the real errand
  execution path is demonstrably isolated.

Required implementation:
  1. Trace the complete production path from `run_browser_errand` through
     `get_driver()`, MCP registration, container startup, browser context
     creation, navigation, redirects, downloads, and cleanup. Record the
     actual process/container boundaries before changing code.
  2. Implement a concrete isolated BrowserDriver adapter using the existing
     BrowserDriver protocol. The adapter must connect only to the dedicated
     browser runtime, never silently fall back to the generic host/MCP browser.
  3. Give the browser-control endpoint an authenticated, tenant/errand-scoped
     control channel. Do not expose an unauthenticated Playwright WebSocket
     to the workspace, arbitrary MCP clients, other tenants, or public
     interfaces. Prefer a narrow broker that owns the browser session over
     distributing a reusable browser-server credential.
  4. Integrate lifecycle management: provision a fresh isolated browser
     context per errand (or a rigorously isolated reusable context), enforce
     time/resource limits, close it on success/failure/cancellation/timeout,
     and remove cookies, storage, downloads, and temporary data according
     to an explicit cleanup policy.
  5. Implement default-deny browser egress. All browser-originated traffic
     must traverse an explicit proxy/firewall policy; direct TCP, UDP, DNS,
     WebRTC, QUIC, alternate protocols, and proxy bypass attempts must not
     provide an escape route. Permit only the public destinations required
     by the errand policy.
  6. Enforce destination policy at the network boundary. Resolve and pin
     permitted addresses for each connection; reject loopback, private,
     link-local, reserved, multicast, IPv4-mapped IPv6, IPv6 local ranges,
     cloud metadata, internal service names, and unsafe ports. Re-check every
     redirect and new connection. Application-level preflight validation
     remains defense in depth, not the only SSRF control.
  7. Ensure the browser container has no host mounts, Docker socket,
     application/database credentials, vault key, or unnecessary network
     route. Keep the control plane separate from browser egress. Review
     whether workspace-to-browser network reachability should be removed
     entirely or mediated by an authenticated broker.
  8. Keep the vault secret flow safe: resolve a secret only for the live,
     validated destination origin; do not expose plaintext to the model,
     logs, browser snapshots, or approval metadata. Do not allow navigation
     between validation and action to change the destination unnoticed.
  9. Make runtime unavailability, proxy failure, authentication failure,
     policy uncertainty, and cleanup failure explicit closed failures.
     No fallback to the existing generic MCP browser for an errand requiring
     isolation or owner-approved side effects.
  10. Update deployment configuration, health checks, settings, migrations
      if truly needed, security docs, and generated state/inventory only
      where the implementation changes them. Do not add unused compose
      services or claim integration based on configuration presence alone.

Acceptance tests (must exercise the real errand entry point):
  - The actual `run_browser_errand` path reports/records that it used the
    isolated runtime; tests must fail if the generic MCP driver is selected.
  - No browser service port is published to host/LAN/public interfaces.
  - Unauthenticated, wrong-tenant, wrong-errand, expired, and replayed
    control requests are denied.
  - Browser and workspace cannot reach application DB, host services,
    Docker socket, internal control-plane endpoints, or cloud metadata.
  - Direct egress and proxy-bypass attempts fail for TCP, UDP, DNS, QUIC,
    WebRTC/STUN, and alternate URL schemes as applicable to the chosen
    runtime/network architecture.
  - Public HTTP/HTTPS navigation works only through the approved proxy.
  - Redirects to blocked/private destinations are blocked before the
    redirected request reaches the destination.
  - DNS rebinding / answer changes cannot cause a connection to a prohibited
    address after a hostname was initially approved.
  - Test IPv4, IPv6, IPv4-mapped IPv6, integer/hex/octal/short IP forms,
    localhost aliases, private/link-local/reserved ranges, metadata IPs,
    and internal DNS names.
  - Two tenants/errands cannot read each other's cookies, storage, downloads,
    browser snapshots, or control messages.
  - Context/container cleanup occurs after success, denial, exception,
    cancellation, timeout, and process shutdown.
  - Proxy, broker, browser, or durable policy store outage fails closed;
    no unsafe driver fallback is attempted.
  - Owner approval remains exact-action-bound and one-use after integration.
  - Existing browser policy, vault, destination-validator, and approval tests
    remain passing; do not weaken existing assertions.

Required evidence:
  - Exact files changed and architecture/data-flow diagram.
  - Exact commands and results for focused, full relevant, and container/
    network integration tests.
  - Evidence from a real Docker/Compose run, including network inspection
    and attempted prohibited connections. Unit tests and static YAML checks
    alone are insufficient.
  - State clearly which controls are implemented, integrated, unit-tested,
    integration-tested, adversarially tested, and operationally verified.
  - Record any environment-dependent tests not run and why. Do not label the
    browser path production-safe or complete until the network and runtime
    isolation tests pass in the deployed configuration.

Scope discipline:
  - First deliver a short architecture trace and threat model, then implement
    the smallest coherent vertical slice from errand entry point to isolated
    browser to egress enforcement.
  - Do not spend this session on confidence calibration, unrelated memory
    features, UI redesign, or broad refactoring.
  - If a genuine architectural blocker prevents safe integration, stop before
    weakening isolation; report the blocker and the smallest viable design.
```

