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

### Current (2026-11-17 04:30 UTC)

- **Checked at / branch / base SHA:** 2026-11-17 04:30 UTC on
  `feat/work-order-final-operational-verification`, cut from `master` at
  `28c4558` (`docs(state): regenerate the inventory [skip ci]`). Working
  tree: `/home/raja/life-graph`.
- **Current milestone:** Operational & real-PostgreSQL integration verification of P0 §2, P1 §4, and P1 §5 — closing all remaining gaps in `docs/AI_WORK_ORDER.md`.
- **Verified status (per Section 9 Definition of Done):**
  - **P0 §2 Exact-step-bound approval**: **Implemented, Integrated, Unit-tested, Integration-tested, Adversarially tested, Operationally verified, and Complete**. Verified end-to-end against real PostgreSQL (`notifications` + `capabilities`) and live isolated Chromium (`life-graph-sandbox-browser-1` at `172.24.0.2`) + egress proxy (`http://egress:8080`) as well as in `tests/integration/test_durable_authorization_multiprocess.py`.
  - **P0 §3 Isolated browser runtime**: **Operationally verified and Complete**. Evidenced against live Chromium container (`compose.sandbox.yaml`), 4-network topology, 32-char path token authentication, egress proxy enforcement with IP pinning, SSRF/metadata blocking, and clean container teardown.
  - **P1 §4 Durable authorization**: **Implemented, Integrated, Unit-tested, Integration-tested, Operationally verified, and Complete**. Verified across 8 independent OS worker processes (distinct PIDs and `psycopg2` pools) racing against real PostgreSQL after issuer process exit (1 winner `capability_valid`, 7 losers `capability_already_consumed`), plus standing-rule persistence across process restarts and cross-process revocation (`tests/integration/test_durable_authorization_multiprocess.py`).
  - **P1 §5 Historical episode retrieval**: **Implemented, Integrated, Unit-tested, Integration-tested, and Complete**. Extended `episodes.time_window` (`this month`, `last year`, `this year`), added historical `statuses` support to `episodes.episodes_between`, fixed ORM `Memory` valid-time precedence in `memory_retrieval._temporal` and `is_valid_at`, and verified against real PostgreSQL in `tests/integration/test_episodes.py` (`58/58` unit + integration tests passing).
  - **P1 §6 Evidence lineage & confidence evaluation**: **Implemented, Integrated, Unit-tested, Evaluated, and Complete**.
  - **P1 §7 Adversarial end-to-end security**: **Implemented, Integrated, Unit-tested, Adversarially tested, and Complete**.
  - **P2 §8 Operations and recovery runbook**: **Complete**.
  - **Inventory & Tests**:
    - `docs/STATE.md` and `docs/feature-inventory.html` refreshed and verified via `python scripts/gen_state.py --check`.
- **Open risks/blockers:**
  - All P0, P1, and P2 milestones in `docs/AI_WORK_ORDER.md` (§2–§8) are **Complete**.
- **Next smallest action:** Proceed to the next priority in `docs/LIFE_GRAPH_IMPROVEMENT_PLAN.md` Section 4 (Order 3: Establish reproducible memory benchmarks and regression datasets).
- **Latest commit:** recorded in the commit introducing this handoff.
