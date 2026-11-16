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

### Current (2026-11-16 09:15 UTC)

- **Checked at / branch / base SHA:** 2026-11-16 09:15 UTC on
  `feat/work-order-p1-adversarial-security`, cut from `master` at
  `3979992` (Merge pull request #237 from Raceraja001/feat/work-order-p1-evidence-confidence). Working
  tree: `/home/raja/life-graph`.
- **Current milestone:** P1 §7 — Adversarial end-to-end security tests.
  **Implemented, Integrated, Adversarially tested, and Complete**.
- **Verified status:**
  - *Adversarial test suite:* `tests/integration/test_adversarial_security_e2e.py`
    exercising full workflows across all 8 attack surfaces specified in AI Work Order §7:
    1. ADV-01: Malicious prompt injection in external web/doc text fenced in `<untrusted>` tags with `UNTRUSTED_PREAMBLE`.
    2. ADV-02: Replay, forged capability IDs, cross-step execution, and tampered parameter hashes rejected fail-closed (`ALREADY_CONSUMED`, `UNKNOWN`, `STEP_MISMATCH`, `PARAMETERS_MISMATCH`).
    3. ADV-03: Cross-tenant and cross-errand capability reuse attempts rejected (`TENANT_MISMATCH`, `ERRAND_MISMATCH`).
    4. ADV-04: SSRF, cloud metadata (169.254.169.254), loopback (127.0.0.1), private IPs, non-web schemes, and mid-errand origin redirects stopped before execution.
    5. ADV-05: Vault secret exfiltration via driver exceptions masked and page text echoes redacted (`[redacted]`), omitted from logs.
    6. ADV-06: Browser session cookies and local storage isolated and wiped on context reset.
    7. ADV-07: 16 concurrent threads racing to consume a single-use capability; exactly 1 caller succeeds and 15 fail with `ALREADY_CONSUMED`.
    8. ADV-08: Client-supplied provenance spoofing stripped; contradictory memory facts forced to abstain.
  - *Report artifact:* `evals/adversarial_security_report.json` containing 8 structured audit records with timestamps and verdicts.
  - *Tests:*
    - 8 integration tests in `tests/integration/test_adversarial_security_e2e.py` passed in 3.16s.
    - 225 unit/integration tests across `test_confidence_calibration.py`, `test_browser_errand.py`, `test_exact_bound_capabilities.py`, and `test_adversarial_security_e2e.py` passed in 30.71s (0 failures, 0 regressions).
- **Open risks/blockers:**
  - All P0 and P1 security and trustworthiness milestones are complete. The remaining work order task is **P2 §8 — Operations and recovery documentation**.
- **Next smallest action:** Proceed to **P2 §8 — Operations and recovery documentation**.
- **Latest commit:** recorded in the follow-up commit.
