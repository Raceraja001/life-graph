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

### Current (2026-11-17 08:10 UTC)

- **Checked at / branch / base SHA:** 2026-11-17 08:10 UTC on `master`, merging Track A (`8f4d140`) and Track B (`d3703b9`) from base `74d3002`.
- **Current milestone:** Parallel Execution of Track A (Production Pipeline Wiring & CI Regression Gates) and Track B (Improvement Plan §3 Research Directions A, C and §3.B Decision Revisit Delivery).
- **Verified status:**
  - **Track A — Durable execution guard wired into dispatcher:** *Implemented, Integrated, Unit-tested.* `drivers/dispatcher.py` builds an `ExecutionCheckpointTracker` in `_prepare_packet` and records all eight `ORDERED_DISPATCH_STAGES` across the pipeline (`prepared`, `budget_checked`, `driver_executed`, `worktree_verified`, `files_checked`, `verifier_completed`, `landed`, `finished`), with the tampered-worktree path recording `ok=False`. Step 6c calls `verify_independent_completion` before `_land_verified_work`, so a driver that claims success cannot land without an independent verifier verdict and an observed file change.
  - **Track A — Two wiring defects fixed during integration:**
    1. Gate read pre-bounce verifier verdicts (vetoed rescued tasks); `_DispatchRun` now carries `verifier_results`, and `_bounce_task` updates them.
    2. File list was only read for `code`/`code_change`; `_observe_files_changed` now reads diff for all five code task types (`code`, `code_change`, `bugfix`, `refactor`, `feature`) and re-reads after a bounce.
  - **Track A — Strict personal-data routing wired into compute router:** *Implemented, Integrated, Unit-tested.* `services/compute_router.decide` checks `carries_personal_data` ahead of other rules, refusing cloud outright and answering local-or-wait via `select_backend_for_task` with empty cloud model list.
  - **Track A — Evaluation gates in CI:** *Implemented, Integrated.* `.github/workflows/ci.yml` runs `scripts/eval_memory_benchmark.py --verify` and `scripts/eval_confidence_calibration.py --verify` after the unit suite. Both pass locally (exit 0).
  - **Track B — §3.C adaptive early exit:** *Implemented, Integrated, Unit-tested.* `life_graph/services/memory/retrieval.py` — `assess_hit_evidence` scores the top hybrid hit on calibrated confidence (`decompose_memory_confidence`) and entailment (`verify_claim_support`); at `>= 0.92` confidence with `>= 0.85` entailment or full keyword coverage, entity expansion and `_with_neighbours` are skipped.
  - **Track B — §3.C abstention indicator:** *Implemented, Integrated, Unit-tested.* `retrieve` returns `RetrievalResult` (a `list` subclass) carrying `abstain`, `abstention_reason` (`contradictory_evidence` / `unresolvable_missing_evidence`), per-memory assessment, and `early_exit`; returned rows carry `retrieval_evidence`.
  - **Track B — §3.A epistemic status & lineage:** *Implemented, Integrated, Unit-tested.* `POST /search/ask` returns `epistemic_status` (`explicitly_stated` / `inferred` / `stale` / `contradicted` / `unsupported`, worst-first) and `source_lineage` (`resolve_memory_lineage` per cited memory).
  - **Track B — §3.B decision revisit delivery:** *Implemented, Integrated, Unit-tested.* `BriefComposer._decision_revisit_lines` queries active decisions with predictions and flagged memories, calls `assess_decision_revisit`, and renders a "Revisit a decision" section in the daily brief body, metadata, and evidence.
- **Evidence:**
  - Track A: `tests/unit/test_dispatcher_execution_guard.py` (24 tests passed).
  - Track B: `tests/unit/test_adaptive_retrieval.py` (16 passed) + `tests/unit/test_brief_decision_revisit.py` (15 passed) + `tests/unit/test_decision_experience_workflow.py` (4 passed) = 35 passed.
  - CI verification scripts: `python scripts/eval_memory_benchmark.py --verify` (exit 0) and `python scripts/eval_confidence_calibration.py --verify` (exit 0).
  - Full unit suite: 5410 passed, 2 pre-existing environment-related failed (`test_diff_scoped_verifiers.py::test_lint_clean_diff_*`), 24 skipped.
  - Code hygiene: `ruff check life_graph/` clean; `python scripts/gen_state.py --html --check` clean.
- **Open risks/blockers:**
  - The checkpoint trail is currently held in memory on `_DispatchRun` during dispatch execution; persisting `tracker.to_dict()` into `agent_tasks.properties` across restarts is the next operational slice for full crash recovery.
  - Section 3 early-exit latency/cost savings are reasoned (2 fewer round-trips); empirical latency benchmark measurement on large memory set is pending.
- **Next smallest action:** Persist `run.tracker.to_dict()` into task row properties and run memory benchmark comparison.
- **Latest commits:** `8f4d140` (Track A) and `d3703b9` (Track B) merged into `master`.
