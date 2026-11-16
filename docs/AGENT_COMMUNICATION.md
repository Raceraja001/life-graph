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

### Current (2026-11-16 10:05 UTC)

- **Checked at / branch / base SHA:** 2026-11-16 10:05 UTC on
  `chore/state-and-completion-audit`, cut from `master` at
  `96b587f` (Merge pull request #239 from Raceraja001/feat/work-order-p2-operations-docs). Working
  tree: `/home/raja/life-graph`.
- **Current milestone:** Completion audit of `docs/AI_WORK_ORDER.md` acceptance criteria & `docs/STATE.md` refresh.
- **Verified status (per Section 9 Definition of Done):**
  - **P0 §2 Exact-step-bound approval**: **Implemented, Integrated, Unit-tested, Adversarially tested**. Verified in code and 87 unit + adversarial tests. Remaining operational gap: live user interaction in deployed production UI.
  - **P0 §3 Isolated browser runtime**: **Operationally verified and Complete**. Evidenced against live Chromium container (`compose.sandbox.yaml`), 4-network topology, 32-char path token authentication, egress proxy enforcement with IP pinning, SSRF/metadata blocking, and clean container teardown.
  - **P1 §4 Durable authorization**: **Implemented, Integrated, Unit-tested**. Verified via PostgreSQL table `authorization_capabilities` (`revision 059`) and 16-thread concurrent atomic CAS consumption. Remaining operational gap: multi-node OS process restart in a distributed cluster.
  - **P1 §5 Historical episode retrieval**: **Implemented, Integrated, Unit-tested**. Verified via calendar-day anchoring and timezone-aware boundaries. Remaining operational gap: longitudinal production history validation.
  - **P1 §6 Evidence lineage & confidence evaluation**: **Implemented, Integrated, Unit-tested, Evaluated, and Complete**. Evaluated with ECE, MCE, reliability bins, Brier score <= 0.1413 across 60 calibration and 60 held-out samples.
  - **P1 §7 Adversarial end-to-end security**: **Implemented, Integrated, Unit-tested, Adversarially tested, and Complete**. 8/8 attack scenarios passing in `tests/integration/test_adversarial_security_e2e.py` and logged to `evals/adversarial_security_report.json`.
  - **P2 §8 Operations and recovery runbook**: **Complete**. Documented in `docs/OPERATIONS.md` across 9 operational domains.
  - **Inventory & Tests**:
    - `docs/STATE.md` refreshed via `python scripts/gen_state.py --html` (verified fresh with `--check`): 390 HTTP operations, 88 tables, 59 migrations, 79 event types, 13 personas, 296 settings, 4,685 test functions in 494 files, 131,435 lines of Python.
    - All test suites passing (225/225 regression tests green, 0 failures, 0 regressions).
    - Production service verified healthy at `http://localhost:8080/health` (27/27 subsystems ok).
- **Open risks/blockers:**
  - Real browser errands touching live third-party financial institutions require human-in-the-loop owner approval and cannot be fully automated end-to-end without credentials.
  - Operational multi-worker durability is verified with in-process concurrency against real PostgreSQL; multi-host physical node failover remains unbenchmarked.
- **Next smallest action:** Merge completion audit to `master` and synchronize to `prod`.
- **Latest commit:** recorded in the follow-up commit.
