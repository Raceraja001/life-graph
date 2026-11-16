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

### Current (2026-11-16 07:36 UTC)

- **Checked at / branch / base SHA:** 2026-11-16 07:36 UTC on
  `feat/work-order-browser-slice3`, cut from `master` at
  `33523b16e92d9513a7c28e1eb1b2d49f05053b83` (`master` and the branch were
  identical at the start of the session). Working tree:
  `/home/raja/life-graph`.
- **Current milestone:** P0 §3 — integrate browser errands with an actually
  isolated browser runtime. Slice 3 of that milestone: the authenticated
  control channel and a deployable egress service.
- **Verified status:**
  - *Code and configuration:* all three §3 controls that slice 1 left open
    are now closed in code. The browser server runs with
    `--path /<token>`; `control_endpoint()` in
    `life_graph/services/browser_sandbox_driver.py` is the single place that
    decides what the driver may connect to and refuses an endpoint with no
    usable token (`browser_sandbox_require_token`, on by default, and a
    *missing* setting reads as on). The egress proxy is now runnable as a
    service (`python -m life_graph.services.browser_egress_proxy`) and
    `compose.sandbox.yaml` ships it as `egress` on a four-network topology:
    exactly one network has a gateway, only the proxy is on it, the browser
    reaches the proxy but has no route of its own, and the workspace shares
    no bridge with either.
  - *Tests:* 470 passed in the focused set. Full unit suite 26 failed /
    5306 passed / 5 skipped, against a stashed baseline of 26 failed / 5254
    passed / 5 skipped in the same tree — FAILED lists diffed and identical,
    so 0 regressions and +52 passing. Thirteen mutation checks, each applied
    and reverted, each caught by a named test. The integration suite was run
    against a throwaway database, because its conftest TRUNCATEs whatever
    database the settings name and on this machine that is the developer's
    `life_graph_dev`.
  - *Operational:* the **proxy half only**. `docker compose config` resolves
    the four-network topology as intended; `Dockerfile.egress` builds; the
    container runs as uid 65534 on a read-only root filesystem with every
    capability dropped; and asked from a peer container on the same bridge
    (the browser's position) it answered 403 to all eleven adversarial
    destinations tried — metadata by address and by name, loopback v4 and
    v6, RFC1918, the docker bridge gateway, the browser's own 9222, ssh,
    postgres, loopback as a bare decimal and as hex — while relaying
    `example.com:443` and `:80`, and logged each denial with its reason.
    The **browser half has not been observed at all**: no stack has been
    brought up with a token and no browser errand has reached a real site
    through a real Chromium. The browser container chassis was
    operationally checked on 2026-11-16 for the previous *single-bridge*
    shape only.
- **Open risks/blockers:**
  1. No operational evidence for any of it (the blocking item).
  2. The deployed shared proxy enforces the address, port and scheme rules
     on every request but does **not** carry the per-errand origin fence — a
     long-lived shared proxy does not know which errand a connection belongs
     to. Closing that needs a design decision: a per-errand credential on
     the proxy hop, or a per-errand proxy container.
  3. A path token is a bearer secret in a URL. It is never committed, baked
     into an image or logged, but rotation, revocation and distribution do
     not exist yet.
  4. The compose network rename leaves `life_graph_sandbox_internal`
     orphaned on a machine that brought up the old file
     (`docker network rm life_graph_sandbox_internal`).
  5. Still not implemented: upload and response-size limits. The proxy
     cannot enforce them without terminating TLS, which it deliberately does
     not do.
- **Next smallest action:** one operational session for the browser half —
  build the Playwright image, generate a token, bring
  `compose.sandbox.yaml` up with `SANDBOX_BROWSER_PATH` set, point the
  application at `ws://<browser>:9222/<token>` and `http://egress:8080`, and
  run a single browser errand to a real site. Then the §3 verification list
  against that running stack: proxy bypass from inside the browser container,
  a redirect to a blocked destination, a real rebinding zone, a wrong token,
  no token, and a cross-tenant attempt.
- **Latest commit:** `58952fb` ("feat(browser): authenticated control channel
  and deployable egress service (Slice 3)") on
  `feat/work-order-browser-slice3`. Nothing pushed — the push is the
  developer's call.
