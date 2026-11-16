# Life Graph — Agent Communication Channel

**Purpose:** This file is the durable communication contract between Raja and any AI coding agent working on Life Graph. Use short chat prompts; keep detailed instructions, decisions, evidence and handoffs in GitHub.

## 1. How to work with Raja

- Treat Raja as the project owner and engineering decision-maker. Act as a critical engineering partner, not an unquestioning code generator.
- Keep chat replies short. Do not send large prompts, repeat repository context, or ask Raja to paste instructions already stored here.
- Explain important decisions in plain language: the problem, options considered, recommendation, trade-offs and what needs Raja's approval.
- Do not silently make major architecture, security, data-model, dependency or product-boundary decisions.
- For a significant or risky change, inspect first and report a concise proposal before implementation.
- Teach while building: explain the key concept and why the chosen approach is appropriate, without turning every response into a long tutorial.
- Prefer one milestone or vertical slice at a time. Avoid unrelated cleanup and speculative rewrites.

## 2. Source-of-truth hierarchy

At the start of every session, fetch the latest remote default branch and read:

1. `CHARTER.md` — product intent and invariants.
2. `docs/STATE.md` — generated current inventory; verify it is fresh.
3. `docs/AI_WORK_ORDER.md` — active implementation priorities and acceptance criteria.
4. `docs/LIFE_GRAPH_IMPROVEMENT_PLAN.md` — longer-term strategy.
5. This file — collaboration and communication protocol.

Then inspect the relevant source, tests, deployment files, issues and recent commits. Do not rely on chat history, cached context or old commit references for repository state.

If documents conflict: preserve the Charter's invariants; follow the active work order for immediate implementation; use the improvement plan for strategic direction. Report conflicts rather than silently reconciling them.

## 3. Remote-first engineering protocol

1. Fetch the latest remote default branch and record its SHA.
2. Inspect working-tree state and branches. Preserve unrelated user work; never force-push or overwrite it.
3. Verify whether the requested work is missing, partial, already implemented or regressed.
4. Before risky work, write a short design/threat-model proposal and wait for Raja's approval where a meaningful decision is required.
5. Implement the smallest safe, reviewable slice.
6. Test normal, boundary, failure, concurrency and adversarial cases as relevant.
7. Run focused tests, then the relevant broader suite. Record exact commands and results, including known baseline failures.
8. Update the relevant work order and the **Current handoff** section below with evidence, remaining risks and the next action.
9. Commit/push only when appropriate and authorized by the established repository workflow. Record exact commit SHA and branch.

Never call work complete because code exists or unit tests pass. Distinguish: Proposed, Designed, Implemented, Integrated, Unit-tested, Integration-tested, Adversarially-tested, Operationally-verified and Complete. Use Complete only when all acceptance criteria are evidenced.

## 4. Engineering and product principles

- Preserve the Life Graph Charter and existing abstractions unless evidence justifies a change.
- Fail closed for authorization, tenant isolation, secrets, browser control and network egress.
- Treat model output, browser content, tool arguments and external data as untrusted.
- Keep authorization ("may it act?") separate from verification ("did it do the right thing?").
- Memory is context, never permission. Similarity or heuristic scores are not calibrated factual confidence.
- Prefer evidence, reproducible evaluation, observability and operational verification over feature counts or demos.
- Avoid unnecessary dependencies, services, tables, endpoints and duplicated logic.
- Never weaken or delete tests to get a green result. Add regression tests for confirmed defects.
- Clearly report what was tested with mocks versus real services, containers, browsers and deployed infrastructure.
- Do not claim production readiness or security guarantees beyond the evidence.

## 5. Active browser-security milestone

The immediate focus is closing the remaining P0 isolated-browser security integration gaps recorded in `docs/AI_WORK_ORDER.md`. Re-check the latest code and deployment state before acting; the following are investigation targets, not assumptions that they remain open:

- Authenticated, tenant- and errand-scoped browser control channel; prevent unauthorized direct access to the raw browser websocket.
- Deployable egress-proxy topology reachable by the browser container, with no alternate direct internet route and no workspace egress.
- Real Chromium end-to-end verification through the deployed proxy, including redirects, SSRF/private and metadata IPs, DNS rebinding, IPv4/IPv6, direct-IP/DNS bypass, proxy manipulation, WebRTC/alternate routes and cross-tenant/errand attempts.
- Credential expiry/revocation, crash/restart behavior, cancellation, timeout, orphan cleanup, health checks, concurrency/resource limits and operational documentation.

Compare viable architectures before choosing (for example, authenticated browser gateway versus reverse proxy; dedicated proxy service versus host-managed or per-errand proxy). Document threat model, trust boundaries, failure modes and operational consequences. Do not weaken the existing destination validation, IP pinning, origin fence or fail-closed driver selection.

Acceptance requires evidence from the real execution path, not only unit tests: approved destinations work through the proxy; unauthorized destinations and all alternate egress paths fail; raw browser control is authenticated and scoped; tenant/errand isolation holds; failures clean up safely; tests and runbooks are reproducible.

## 6. Communication format

Keep chat updates brief and link to the relevant GitHub file/commit. Use this structure when useful:

- **Found:** verified current state and evidence.
- **Decision needed:** only choices that genuinely require Raja.
- **Next:** the smallest proposed action.
- **Result:** files changed, exact tests/results, commit/branch, remaining risks.

Do not ask Raja to repeat information already present in repository documents. If blocked, state the precise missing information and offer a safe default recommendation.

## 7. Current handoff

**Active work order:** `docs/AI_WORK_ORDER.md`  
**Strategy:** `docs/LIFE_GRAPH_IMPROVEMENT_PLAN.md`

At the beginning of each session, replace this handoff with verified current information:

- **Checked at / branch / base SHA:** record actual values.
- **Current milestone:** identify one active milestone.
- **Verified status:** distinguish code, tests and operational evidence.
- **Open risks/blockers:** list only items re-confirmed against current source/configuration.
- **Next smallest action:** one concrete step.
- **Latest commit:** exact SHA, or state that no commit was made.

Do not preserve stale status as current. Keep historical evidence in the work-order progress log or commit history.

### Current (2026-11-16 08:25 UTC)

- **Checked at / branch / base SHA:** 2026-11-16 08:25 UTC on
  `feat/work-order-browser-operational`, cut from `master` at
  `3d09aed24b3097809924361f6abe416dfafa7848` (merge of slice 3 #246). Working
  tree: `/home/raja/life-graph`.
- **Current milestone:** P0 §3 — integrate browser errands with an actually
  isolated browser runtime. **Operationally verified and Complete**.
- **Verified status:**
  - *Code and configuration:* Slices 1, 2, and 3 are merged to `origin/master`.
    In addition, fixed a bug in `life_graph/services/browser_errand.py` where
    `current_origin()` was queried before navigation when Chromium was still at
    `about:blank` (which returns origin "null" in Chromium). A navigate step is
    now evaluated against its destination origin without prematurely querying the
    unnavigated driver. Added regression test
    `test_navigate_step_does_not_query_driver_origin_before_navigating` in
    `tests/unit/test_jarvis_errands.py`.
  - *Operational verification against live Docker container stack (`compose.sandbox.yaml`):*
    1. Built images (`life-graph-sandbox-browser:dev`, `life-graph-sandbox-egress:dev`)
       and started them on the 4-network topology (`life_graph_sandbox_control`,
       `life_graph_sandbox_egress`, `life_graph_sandbox_outbound`). Both containers
       reported healthy.
    2. Control Channel Token Authentication: Connecting to the browser server
       without a path token (`ws://...:9222/`) or with a wrong token
       (`ws://...:9222/wrong_token`) fails closed with 400 Bad Request and immediate
       WebSocket termination. Connecting with the configured 32-char path token
       (`ws://...:9222/<token>`) succeeds, establishing a session with Chromium
       136.0.7103.25.
    3. Direct Internet Access Bypass: Direct navigation to `https://example.com`
       from inside the browser container without the egress proxy fails immediately
       with `net::ERR_NAME_NOT_RESOLVED`, confirming the browser container has no
       default gateway and cannot route directly to the internet.
    4. Blocked Destinations: Navigation through the egress proxy (`http://egress:8080`)
       to cloud metadata (`http://169.254.169.254/`), loopback (`http://127.0.0.1:9222/`),
       and RFC1918 private IPs (`http://10.0.0.1/`) is refused with HTTP 403 Forbidden,
       and each denial is logged with its exact reason by the egress proxy.
    5. Redirect Target Denial: External redirect to private addresses
       (`https://httpbin.org/redirect-to?url=http://127.0.0.1:9222/`) is intercepted
       at the proxy hop and blocked with HTTP 403 Forbidden.
    6. Live End-to-End Errand: Executed `run_browser_errand` with a `NAVIGATE` to
       `https://example.com` and `READ_PAGE` against the live stack. Completed
       with `status: done`, with extracted text fenced inside `<untrusted>...</untrusted>`.
       Disallowed origins outside the plan fence are rejected before navigation.
    7. Clean teardown: `docker compose -f compose.sandbox.yaml down -v` cleanly stops
       and removes all containers and internal networks.
  - *Tests:* 265 focused unit tests passed in 13.32s; broader suite of 130 tests
    passed in 30.19s (395 passed total across target modules, 0 failures, 0 regressions).
- **Open risks/blockers:**
  1. Shared proxy origin fencing: The deployed shared proxy enforces address/port/scheme
     rules and SSRF/metadata blocking for all requests, while errand origin fencing
     is enforced by `tools/errand.py` plan checking. A per-errand proxy credential or
     per-errand container would provide defense-in-depth at the proxy layer.
  2. Upload and response-size limits: Currently the proxy does not inspect payload
     sizes without terminating TLS.
- **Next smallest action:** Proceed to **P1 §6 — Strengthen evidence lineage and
  confidence evaluation** in `docs/AI_WORK_ORDER.md`.
- **Latest commit:** recorded in the follow-up commit.
