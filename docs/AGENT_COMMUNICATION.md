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

### Current (2026-11-17 08:00 UTC)

- **Checked at / branch / base SHA:** 2026-11-17 08:00 UTC on
  `feat/track-a-production-pipeline-wiring`, cut from `master` at `74d3002`.
  Working tree: `/home/raja/lg-wt/track-a` (git worktree).
- **Current milestone:** Track A — production pipeline wiring & CI regression
  gates. Orders 1-6 shipped the *mechanisms* (`drivers/execution_guard.py`,
  `services/local_model_registry.py`, the two evaluation laboratories) but
  three of them were not on any production path. Track A wires them in.
- **Verified status:**
  - **Durable execution guard wired into the dispatcher:** *Implemented,
    Integrated, Unit-tested.* `drivers/dispatcher.py` now builds an
    `ExecutionCheckpointTracker` in `_prepare_packet` and records all eight
    `ORDERED_DISPATCH_STAGES` across the pipeline (`prepared`,
    `budget_checked`, `driver_executed`, `worktree_verified`, `files_checked`,
    `verifier_completed`, `landed`, `finished`), with the tampered-worktree
    path recording `ok=False`. Step 6c calls
    `verify_independent_completion` before `_land_verified_work`, so a driver
    that claims success cannot land without an independent verifier verdict
    and an observed file change.
  - **Two wiring defects found and fixed while integrating:**
    1. The gate first read the *pre-bounce* verifier verdicts, which vetoed
       every task the one-bounce rule had rescued. `_DispatchRun` now carries
       `verifier_results`, and `_bounce_task` replaces them with its own
       re-verification.
    2. The file list was only read for `code`/`code_change`, so `bugfix`,
       `refactor` and `feature` tasks reached the gate with no evidence and
       were vetoed as "zero files". `_observe_files_changed` now reads the
       diff for all five code task types (never for `plan`/`general`, which
       legitimately change nothing) and is re-read after a bounce.
    `files_changed` stays `None` where there is no worktree to read a diff
    from; "not observed" is not reported to the gate as "observed nothing"
    (`require_file_changes_for_code=False` for that one caller). The verifier
    half of the gate still applies there.
  - **Strict personal-data routing wired into the compute router:**
    *Implemented, Integrated, Unit-tested.* `services/compute_router.decide`
    now checks `carries_personal_data` ahead of every other rule, including
    the routing-disabled and `interactive` short-circuits, and answers
    local-or-wait via `select_backend_for_task` called with an empty cloud
    model list. The cloud persona is refused outright. A test enumerates
    every (persona x active x cloud-availability) combination and asserts
    `where != "cloud"`.
  - **Evaluation gates in CI:** *Implemented, Integrated.* The `unit-tests`
    job runs `scripts/eval_memory_benchmark.py --verify` and
    `scripts/eval_confidence_calibration.py --verify` after the unit suite.
    Both pass locally (exit 0).
  - **Tests:** `tests/unit/test_dispatcher_execution_guard.py` (new, 24
    tests). Full unit suite: 5386 passed, 2 failed, 24 skipped — the same two
    `test_diff_scoped_verifiers.py` failures as the pre-change baseline on
    this machine, unrelated to Track A. `ruff check life_graph/` clean.
    Each of the three fixes above was mutation-checked: reverting it fails
    exactly the test that describes it.
- **Open risks/blockers:**
  - Not operationally verified. Every test is in-process with the driver,
    verifier chain, governor and worktree stubbed; no real agent dispatch has
    been run through the new gate.
  - The checkpoint trail is held in memory on `_DispatchRun` and is not yet
    persisted to the task row, so `recover_interrupted_dispatch` has nothing
    to read after a real worker restart. The tracker serializes via
    `to_dict()`; the write to `agent_tasks.properties` is the next slice.
  - Both `--verify` scripts rewrite their report JSON and their numbers drift
    slightly between runs on the same input, so CI will leave a dirty tree in
    the runner. The gates compare thresholds, not reports, so this does not
    make CI flaky, but the non-determinism is worth tracking down.
- **Next smallest action:** Persist `run.tracker.to_dict()` into the task row
  at each checkpoint, so crash recovery can actually read it.
- **Latest commit:** see the Track A commit on
  `feat/track-a-production-pipeline-wiring`.
