# Task specs for the dev pipeline

> **Status:** Written 2026-10-24 against `master` at 6459f6b. These are tasks for Life Graph's own
> dev pipeline (free local engines) to run unattended. Nothing here is built yet.

Each `NN-*.md` file is one pipeline run: one or two source files and one new test file, pure
logic, no database, under 20 minutes on `code-fixer-local` (gpt-oss:20b). Each file holds a
ready-to-paste **instruction** that already contains its `## Spec`, with acceptance criteria
bound to pytest node ids, in the format the pipeline parses (`services/acceptance.py`,
`drivers/dispatcher.py::_SPEC_HEADINGS`).

Every bug these tasks fix was reproduced on 6459f6b before the spec was written. The expected
values in each spec were checked against a scratch prototype of the change, alongside the
existing tests for the same function, so the cases agree with each other and with what is
already there.

## The tasks

| # | Task | Theme | Depends on | Review |
|---|---|---|---|---|
| 01 | [Bank alerts: skip messages that are not a transaction](01-money-alert-not-transactions.md) | A. Money | — | gates |
| 02 | [Bank alerts: the amount is not the balance](02-money-alert-skip-balance.md) | A. Money | 01 | gates |
| 03 | [Scrub: UPI ids, vehicle numbers, passport and voter ids](03-scrub-upi-vehicle-ids.md) | B. Privacy and routing | — | **Claude** |
| 04 | [Jarvis routing: money questions are personal](04-lead-money-words.md) | B. Privacy and routing | 03 (soft) | **Claude** |
| 05 | [Memory recall: more relative time phrases](05-time-window-relative.md) | C. Memory recall | — | gates |
| 06 | [Memory recall: explicit dates](06-time-window-dates.md) | C. Memory recall | 05 | gates |
| 07 | [Entity keys keep Tamil and Hindi vowel signs](07-entity-indic-names.md) | C. Memory recall | — | gates, then **human** backfill |
| 08 | [Page monitors: the price is the currency-marked number](08-page-price-currency.md) | A. Money | — | gates |
| 09 | [Sourced answers: ignore tracking parameters](09-sources-tracking-params.md) | D. Research and pipeline | — | gates |
| 10 | [Tech watch: model sizes in T, M, NxB and E-numbers](10-memory-gb-units.md) | D. Research and pipeline | — | gates |
| 11 | [Plan review: a bound test must be a test file](11-acceptance-test-file-gap.md) | D. Research and pipeline | — | **Claude** |

The tasks are ordered by value: money figures feed the weekly money check-in (Job 5), and a
wrong debit there is a wrong answer to the owner. Next come the privacy net and the routing
check, which decide what leaves the machine. Then memory recall, then research and pipeline
polish.

**Dependencies.** 01 → 02 and 05 → 06 edit the same function, so the second task of each pair
runs only after the first is **merged**; otherwise its worktree is cut from a base without the
first change and the two conflict. 04 only reads `scrub()` through `is_personal()`; if it runs
first, it still passes. Everything else is independent. Any order within these rules is safe.

**Review column.**
- *gates*: the normal Tier 1–3 gates decide (tests_pass, diff_coverage ≥ 0.8,
  tests_catch_mutants ≥ 0.6, change_explained, types_clean_diff, second_opinion). Auto-merge
  can land it if the engine's trust record allows.
- ***Claude***: the change touches the privacy net, the cloud/local routing check or the
  pipeline's own plan checks. Leave it at `awaiting_merge` for Claude, or the owner, to read
  the diff, even if auto-merge would allow it. The task file says what to look at.
- ***human***: needs a step the pipeline must not take, such as a live-data job. The task file
  says which step.

## How to run one

One task at a time. There is one GPU and one local model, and parallel 30B runs have stalled
WSL.

1. Copy the instruction: everything between `<!-- instruction:start -->` and
   `<!-- instruction:end -->` in the task file. From the repo root:

   ```sh
   sed -n '/<!-- instruction:start -->/,/<!-- instruction:end -->/{//!p}' docs/tasks/01-money-alert-not-transactions.md
   ```

2. Start it, with **`spec_first=True`**:
   - MCP: `start_dev_task(instruction=<text>, project="life-graph", persona_name="code-fixer-local", spec_first=True)`
   - Or queue it for the unattended runner: `POST /api/v1/kernel/drivers/tasks` with
     `{"instruction": ..., "project_id": <life-graph id>, "persona_name": "code-fixer-local", "spec_first": true, "queue": true}`.

   The instruction tells the engine to start its reply with the `## Spec` it contains, unchanged.
   That spec, with its `AC-n … — test: …` lines, is what `check_spec_conformance` re-runs later.
3. Watch it with `get_dev_task(task_id)`. A run that goes past 20 minutes has failed. Re-run it
   once on `code-fixer-opencode`, and only when WSL swap is not full.
4. After it lands, run `check_spec_conformance(task_id)`. Every criterion should be *passing*.
   Then review it as the Review column says.

**Engine.** `code-fixer-local` (gpt-oss:20b) by default: it takes 2–4 minutes on tasks
scoped to named files. `code-fixer-opencode` (qwen3-coder:30b) is the fallback. Neither engine
needs a paid model, so the budget cap does not apply.

**Instruction size.** The API accepts at most 8000 characters
(`api/drivers.py::DevTaskCreate.instruction`). Every instruction here is under 5000.

## What each task file contains, and why

The engines are reliable on scoped, pure-logic tasks with clear tests. They miss edge cases the
spec does not list, and they fail on DB-mocked tests, large refactors and vague goals. So every
instruction has:

- **Read first:** the exact files and functions, so the engine does not guess.
- **Change:** the behaviour, rule by rule, including the order the rules apply in.
- **Cases:** every edge case as an input with its exact expected output. The engine copies them
  into a parametrized test. These cases are the spec; the engine must not invent different ones.
- **Files you may touch:** one source file and one *new* test file. `diff_within_scope` takes
  its scope from the files the instruction names. New tests go in a new file, so the large
  shared test files are never rewritten.
- **Do NOT:** what an engine has done wrong before: editing other modules, weakening existing
  tests (`no_test_weakening` is always on), tests that only call `callable()`, mocking what
  needs no mock, and helpers with no caller.
- **`## Spec`:** `**Requirements:**` with `AC-n: <criterion> — test: tests/unit/<file>.py::<test>`,
  then `**Design:**` and `**Tasks:**`, each task citing its criteria. One criterion per task
  points at an *existing* test that must keep passing: that is the regression guard.

The gates on life-graph also need:
- assertions on exact values, because up to 10 mutants of each function a changed test imports
  must be killed (≥ 0.6);
- at least 80% of the changed lines run by the tests;
- the `## Understanding` section at the end of the reply. The code-fixer prompts already ask
  for it.

## Running the tests by hand

Unit tests need no database. From WSL, with ruff on the PATH:

```sh
REPO=/mnt/h/DevTools/Projects/life-graph
cd /tmp && ~/.venvs/life-graph/bin/python -m pytest -q \
  -c $REPO/pyproject.toml --rootdir $REPO \
  $REPO/tests/unit/test_money_alert_not_transactions.py
```

## Writing more of these

Keep to the shape above. Before writing a spec, reproduce the bug on the current base and check
every expected value. A spec with a wrong expected value costs a run and teaches the engine
nothing. Good candidates are pure functions on a live path, outside the protected paths
(drivers, verifiers, sandbox, autonomy, approvals, github_pr, dev_outcomes, change_policy,
governor, compute_router, redaction, models, config, main, core tenant/auth/budget/trust, docker,
scripts). A change in a protected path waits for a person whatever the gates say.

Left out on purpose, as too big or too vague for one run (each needs a design pass first, or a
DB-backed test, or a protected path):

- **Heavy mode** (three models plus critique, docs/design/11): orchestration over live LLM
  calls. There is no pure core to split out until its design names the deterministic check.
- **Personal envelope for workers** and **worker templates for scout/admin/tutor/cody/ops**: these
  are `services/workers.py` plus persona seeding and scheduled runs, and tests would need the
  orchestrator fakes.
- **Hash-chained audit log** and **egress allowlist for driver subprocesses**
  (docs/design/09, Track 1 increments): they live in `autonomy/` and `drivers/`, which are
  protected. A pure helper alone would be dead code, which the quality gate counts against.
- **Shadow demotion after a post-graduation failure** (docs/design/09, Track 3): a pure policy is
  easy, but it is unused until `autonomy/shadow/service.py` (protected) calls it. Build both
  together, with a person reviewing.
- **Governor ROI ranking and per-category sub-caps**: `services/governor.py` and
  `core/budget.py` are protected.
- **Rebuilding the recall eval set** after the 2026-10-23 fresh start: it is personal data in
  `evals/local/`, and it needs the owner.
- **Claude Code hook session ids and notifications**: other branches (`batch/sess`,
  `batch/notif`) are working there now.
- **Weekly sample review of merged agent PRs** (quality gate, "not done"): a judgement task for
  Claude, not code.
- **Android app work**: its PLAN.md has its own task rules, and OkHttp and serialization work
  timed out at 20 minutes.
