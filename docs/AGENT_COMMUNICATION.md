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

### Current (2026-11-17 08:05 UTC)

- **Checked at / branch / base SHA:** 2026-11-17 08:05 UTC on
  `feat/track-b-adaptive-retrieval-and-limitations`, cut from `master` at
  `74d3002`. Working tree: `/home/raja/lg-wt/track-b` (git worktree).
- **Current milestone:** Track B — `docs/LIFE_GRAPH_IMPROVEMENT_PLAN.md`
  Section 3 research directions A (memory that understands its limitations)
  and C (retrieval that knows when to stop), plus the delivery path for B
  (decision experience) through the daily brief.
- **Verified status:**
  - **§3.C adaptive early exit:** **Implemented, Integrated, Unit-tested.**
    `life_graph/services/memory/retrieval.py` — `assess_hit_evidence` scores
    the top hybrid hit on calibrated confidence (`decompose_memory_confidence`,
    no similarity in it) and entailment (`verify_claim_support`); at
    `>= 0.92` confidence with `>= 0.85` entailment or full keyword coverage,
    entity expansion and `_with_neighbours` are both skipped.
  - **§3.C abstention indicator:** **Implemented, Integrated, Unit-tested.**
    `retrieve` now returns a `RetrievalResult` (a `list` subclass, so every
    existing caller is unchanged) carrying `abstain`,
    `abstention_reason` (`contradictory_evidence` /
    `unresolvable_missing_evidence`), the full per-memory assessment, and
    `early_exit`; each returned row also carries `retrieval_evidence`.
  - **§3.A epistemic status:** **Implemented, Integrated, Unit-tested.**
    `POST /search/ask` returns `epistemic_status`
    (`explicitly_stated` / `inferred` / `stale` / `contradicted` /
    `unsupported`, worst-first) and `source_lineage`
    (`resolve_memory_lineage` per cited memory, read from the retrieved rows
    so the capture event, excerpt and span survive the projection).
  - **§3.B revisit delivery:** **Implemented, Integrated, Unit-tested.**
    `BriefComposer._decision_revisit_lines` queries active decisions with
    their predictions and flagged recent memories, calls
    `assess_decision_revisit`, and renders a "Revisit a decision" section in
    the daily brief body, metadata and "why am I seeing this?" evidence.
- **Evidence:**
  `pytest tests/unit/test_adaptive_retrieval.py tests/unit/test_brief_decision_revisit.py tests/unit/test_decision_experience_workflow.py -v`
  → 35 passed. Full `pytest tests/unit/ -q` → 5393 passed, 2 failed, 24
  skipped; both failures (`test_diff_scoped_verifiers.py::test_lint_clean_diff_*`,
  "ruff not available for this project") reproduce unchanged at `74d3002`
  in a clean worktree, so they are environmental and pre-existing.
  `ruff check life_graph/` clean; `docs/STATE.md` regenerated
  (`scripts/gen_state.py --html --check` → OK).
- **Open risks/blockers:**
  - Unit-tested only. No integration or operational evidence yet: the early
    exit's claimed latency/cost win is reasoned (two fewer round trips), **not
    measured** — it needs a run through `scripts/eval_memory_benchmark.py` on
    real memories to show quality is not traded for it.
  - `EARLY_EXIT_CONFIDENCE = 0.92` / `EARLY_EXIT_ENTAILMENT = 0.85` are the
    work order's figures, not measured thresholds. In practice only a fresh,
    high-trust, owner-stated memory clears them, so the gate is narrow by
    construction; widening it must wait for calibration evidence.
  - Nothing in the codebase writes `Decision.reviewed_at`, so a reached review
    date repeats daily until the owner acts (the approvals line behaves the
    same way, by design). `_review_recorded` already honours the column for
    when a review-recording path exists.
  - The brief passes `assess_decision_revisit` only memories whose properties
    explicitly flag an invalidation: its free-text "changed"/"no longer" rule
    would otherwise fire on ordinary captures. Precision over recall,
    deliberately — a text-only circumstance change is not surfaced.
- **Next smallest action:** Measure the early exit — run
  `scripts/eval_memory_benchmark.py` with and without it and record
  first-result accuracy, candidate count and latency in `evals/`.
- **Latest commit:** recorded in the Track B commit on this branch.
