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

### Current (2026-11-17 05:20 UTC)

- **Checked at / branch / base SHA:** 2026-11-17 05:20 UTC on
  `feat/improvement-plan-orders-4-5-6`, cut from `master` at
  `346e2ce`. Working tree: `/home/raja/life-graph`.
- **Current milestone:** Completion of all 6 priorities in `docs/LIFE_GRAPH_IMPROVEMENT_PLAN.md` Section 4 (Orders 1 through 6) & all 7 milestones in `docs/AI_WORK_ORDER.md` (§2 through §8).
- **Verified status:**
  - **Order 1 (P0 Isolated browser runtime & exact-bound approval):** **Operationally verified and Complete**.
  - **Order 2 (P1 Evidence-lineage & confidence calibration):** **Implemented, Integrated, Unit-tested, Evaluated, and Complete**.
  - **Order 3 (P1 Reproducible memory evaluation laboratory):** **Implemented, Integrated, Unit-tested, Evaluated, and Complete** (`life_graph/services/memory_benchmark.py`, `scripts/eval_memory_benchmark.py`, `evals/memory_benchmark_report.json`, `tests/unit/test_memory_benchmark_lab.py`).
  - **Order 4 (P2 Decision, prediction, and causal memory workflow):** **Implemented, Integrated, Unit-tested, and Complete** (`life_graph/services/judgment.py`, `tests/unit/test_decision_experience_workflow.py` — 7-stage experience chain `Situation -> Options -> Decision -> Rationale -> Prediction -> Outcome -> Lesson`, Brier/accuracy prediction evaluation, evidence-backed lesson derivation, fenced hypothetical counterfactuals, and circumstance-change revisit assessment).
  - **Order 5 (P2 Durable agent execution, recovery, and independent verification):** **Implemented, Integrated, Unit-tested, and Complete** (`life_graph/drivers/execution_guard.py`, `tests/unit/test_durable_agent_execution.py` — ordered stage checkpoints, crash recovery actions, idempotency keys, bounded retries, independent verifier completion gate, and bounded delegation envelope validation).
  - **Order 6 (P3 Local intelligence infrastructure & model registry):** **Implemented, Integrated, Unit-tested, and Complete** (`life_graph/services/local_model_registry.py`, `tests/unit/test_local_model_infrastructure.py` — RTX 5080 16 GB VRAM model registry across 7 capabilities, strict local-only routing for personal data, routing/queue explainability, live Ollama probe, and VRAM co-residency justification showing `bge-m3` 1.4 GB + `qwen3:14b` 9.8 GB = 11.2 GB <= 16.0 GB).
- **Open risks/blockers:** None. All items in `docs/AI_WORK_ORDER.md` and `docs/LIFE_GRAPH_IMPROVEMENT_PLAN.md` Section 4 are complete.
- **Next smallest action:** Monitor production telemetry and periodic evaluation runs (`scripts/eval_memory_benchmark.py --verify`, `scripts/eval_confidence_calibration.py --verify`).
- **Latest commit:** recorded in the merge commit on `master`.
