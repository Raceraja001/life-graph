# Task specs for the dev pipeline

> **Status:** Written 2026-10-24 against `master` at 6459f6b. Reworked 2026-10-25 (on c978a89)
> after the first runs failed: every instruction now carries its complete test file and a fixed
> five-step order. Only 08 has landed so far (awaiting its PR); nothing else here is built yet.

Each `NN-*.md` file is one pipeline run: one source file and one new test file, pure logic, no
database. Each file holds a ready-to-paste **instruction** that already contains its `## Spec`,
with acceptance criteria bound to pytest node ids, in the format the pipeline parses
(`services/acceptance.py`, `drivers/plan_spec.py::_SPEC_HEADINGS`).

Every bug these tasks fix was reproduced on 6459f6b before the spec was written. On 2026-10-25
every test file was checked twice on a scratch copy of c978a89: it fails on the current code, and
it passes, together with the existing tests named in its STEP 4, against a scratch prototype of
the fix. The test files are `ruff check` and `ruff format` clean.

## What failed on 2026-10-25, and why

Nine specs (01, 03, 04, 05, 07, 08, 09, 10, 11) were queued on `code-fixer-local`
(gpt-oss:20b), then again on `code-fixer-opencode` (qwen3-coder:30b). Two of the second batch
(04, 07) were re-routed to `code-fixer-cloud` (openrouter `cohere/north-mini-code:free`)
because they were queued outside local hours; three (09, 10, 11) were cancelled. One run
landed: 08 on OpenCode (task 81de2480).

| Spec | Engine (task) | Result | What the record shows |
|---|---|---|---|
| 01 | local (d484f3e8) | needs_review | Changed only `money.py`. `diff_coverage` 0.7 (lines 327, 328, 330 uncovered), `change_explained`: no Understanding. Reply was empty. Same after the bounce. |
| 01 | OpenCode (a7a6cf6b) | timeout 1200 s | Wrote the test file first, then spent 20 minutes debugging its own "is due" regex. |
| 03 | local (6564fa8a) | needs_review | Changed only `scrub.py`; `code_read` of the new test file: "Not a file"; six `code_edit` calls failed with "`old` not found". No Understanding. |
| 03 | OpenCode (5f2f86d0) | needs_review | Wrote `tests/unit/test_scrub_more_shapes.py` plus a stray `test_passport_extraction.py` at the repo root; `tests_catch_mutants` 0.2 both attempts. It edited its own tests to match the code. |
| 04 | local (37cc7b9c) | needs_review | Changed only `lead.py`. Reply empty; `change_explained` failed twice. `code_edit` was called with a made-up `replace_whole_file` parameter. |
| 04 | cloud (c20113e9) | out of tool rounds | Every read used a path outside the worktree ("outside the permitted roots"). |
| 05 | local (d9763005) | needs_review | Changed only `episodes.py`; `build_ok_diff`, `lint_clean_diff`, `tests_pass`, `types_clean_diff`, `change_explained` failed. |
| 05 | OpenCode (ea45f838) | timeout 1200 s | Wrote the test file, then debugged its own regex groups until the timeout. |
| 07 | local (d7691169) | needs_review | Attempt 1: only `entities.py`, no Understanding. Attempt 2 created the test file after `code_edit(start_line=1, end_line=200)` failed with "Not a file"; the file did not collect (exit 2). |
| 07 | cloud (80529b7e) | needs_review | Wrote code and test; `change_explained` failed: empty reply. |
| 08 | local (51fd5c9d) | failed | "all 4 edit(s) failed": `old` not found, path "life...". |
| 08 | OpenCode (81de2480) | **completed** | Attempt 1 failed only `change_explained`; the bounce added the Understanding. |
| 09 | local (1fee78f1) | needs_review | `code_edit(path=new test, old="", start_line=1, end_line=200)` → "Not a file"; the model then wrote the tool call as text. It also broke `sources.py` (undefined `settings`). Attempt 2 fixed that; still no test file, no Understanding. |
| 10 | local (a039e6e2) | needs_review | Changed only `worker_templates.py`; lint and tests fail; no Understanding. |
| 11 | local (32a045a2) | failed | `code_edit` with a made-up `patch` parameter, then a whole-function `old` that was not found, then Ollama could not parse the next call (`error parsing tool call: raw='{"old":"def spec_gaps(...`) → BadRequestError. |

### Root causes

1. **The local engine could not create a file.** The code-fixer-local tool set has no
   file-write tool; a new file is made with `code_edit(path, old="", new=<file>)`. gpt-oss:20b
   kept adding `start_line=1, end_line=200` (or 20) to that call. `code_edit`
   (`life_graph/tools/code.py:211-225`) treats any line numbers as a line-range edit of an
   existing file and answers "Not a file: tests/unit/…", with no hint on how to create one
   (tasks 1fee78f1, d7691169). It never created the test files of 01, 03, 04, 05, 09 or 10, so
   `tests_exercise_code` said "no changed test files", `diff_coverage` fell short and
   `tests_catch_mutants` had nothing to run. The user-visible symptom, "edited the source and
   skipped the tests", is this tool trap, not the engine ignoring the instruction.
2. **The engines are not told to write tests first, or that the given test file is required.**
   `code-fixer-local`'s prompt (`life_graph/kernel/personas.py:275-276`) says "If you add or
   change a test, run it", which makes tests optional, and "Do not … touch unrelated files"
   pulls the other way. `code-fixer-opencode`'s prompt (`personas.py:306-312`) says nothing
   about tests, and the OpenCode driver adds "change only the files the task needs"
   (`drivers/opencode.py:387-390`). In the old specs the test file was only a line under
   "Files you may touch" and a "copy them into a parametrized test" note below the change, so
   the source change came first and the run could end without it. Nothing in the harness
   notices a missing named test file: the in-run self-check (`drivers/self_check.py`) runs only
   tests that exist and the cheap checks, and `diff_coverage` / `change_explained` run only
   after the dispatch.
3. **The Understanding section was asked for, but the reply was empty.** The ask is in every
   code-fixer prompt (`personas.py:39-45`), but gpt-oss ends its turn with a tool call and no
   text; four local runs and one cloud run have `output` of 0 characters. The bounce text
   ("Fix exactly these problems … When the fix is in, stop", `drivers/dispatcher.py:877-883`)
   did not help a model that writes no text. On OpenCode the reply kept is only the last text
   part (`drivers/opencode.py:301, 342`): the `## Spec` written at the start of 81de2480 was
   dropped, so its `spec` field is null and `check_spec_conformance` has nothing to re-run.
4. **OpenCode runs out of time debugging regexes it designed itself** (01, 05), and writes weak
   tests when left to write them (03: mutants 0.2).
5. **Long multi-line `old` strings break the local tool call** (11), and gpt-oss invents
   `code_edit` parameters (`patch`, `commentary`, `replace_whole_file`, `line_start`) and calls
   a `search` tool it does not have; each costs a round.

## The new instruction shape

Every instruction now has the same five steps, in this order, before anything else:

1. **STEP 1: create the test file.** The complete file is in the instruction between
   `===== tests/unit/… =====` lines, so the engine only has to write it. The step says exactly
   how: one `code_edit` call with only `path`, `old=""` and `new`, and no `start_line` /
   `end_line` (OpenCode: its `write` tool). The test file comes first so a run that stops early
   still has it, and the in-run self-check then runs it and sends failures back.
2. **STEP 2: run it and see it fail** (`run_tests`; on OpenCode `lg_tests_run_tests`). An
   ImportError or SyntaxError means the copy is wrong; the cases are never changed.
3. **STEP 3: the smallest source change**, with the rules, and for the regexes that took
   OpenCode 20 minutes (01, 02, 10) a pattern that is known to work.
4. **STEP 4: run the new test and the existing tests** named in the spec, and fix the source,
   never the tests.
5. **STEP 5: end with the `## Understanding` template**, pre-filled with the function names, and
   "your last message is text, not a tool call".

Then *Files you may touch*, *Do NOT*, the `## Spec`, and "Start your reply with the ## Spec
section above, copied unchanged. Then do STEP 1." Each spec has one task that cites every
criterion, so a plan fan-out would not create the test file twice.

Spec 11 also tells the engine to make two edits, each with a one-line `old`, and gives the new
code with single quotes only, so the tool call needs no escaping (the run that broke had a
whole-function `old`). The local tools allow either a short unique `old` or a line range
(`start_line`/`end_line` with `old=""`); there is no whole-file write for an existing file.

Spec 07's test file spells the Tamil and Hindi names as `\u` escapes, so the file is ASCII and
survives the JSON of a tool call whichever way the model escapes it.

**Parser check (2026-10-25).** On every instruction: `_extract_spec` → `parse_criteria` →
`_parse_tasks` → `spec_gaps` gives no gaps; every bound test passes `is_safe_test_ref`; no task
is check-only; every AC bound to the new test file names a function that is in the embedded
file; every regression node id exists in the current tests; the embedded file is byte-identical
to the verified one. Instruction sizes: 4.6k to 6.6k characters (limit 8000; the spec-first
prefix the dispatcher adds is about 700 more and is not counted by the API).

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
| 08 | [Page monitors: the price is the currency-marked number](08-page-price-currency.md) | A. Money | — | gates (done: 81de2480, awaiting PR) |
| 09 | [Sourced answers: ignore tracking parameters](09-sources-tracking-params.md) | D. Research and pipeline | — | gates |
| 10 | [Tech watch: model sizes in T, M, NxB and E-numbers](10-memory-gb-units.md) | D. Research and pipeline | — | gates |
| 11 | [Plan review: a bound test must be a test file](11-acceptance-test-file-gap.md) | D. Research and pipeline | — | **Claude** |

The tasks are ordered by value: money figures feed the weekly money check-in (Job 5), and a
wrong debit there is a wrong answer to the owner. Next come the privacy net and the routing
check, which decide what leaves the machine. Then memory recall, then research and pipeline
polish.

**Dependencies.** 01 → 02 and 05 → 06 edit the same function, so the second task of each pair
runs only after the first is **merged**; otherwise its worktree is cut from a base without the
first change and the two conflict (02's and 06's STEP 4 also run the first task's test file). 04
only reads `scrub()` through `is_personal()`; if it runs first, it still passes. Everything else
is independent.

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

**One task at a time.** There is one GPU and one local model; parallel 30B runs have stalled
WSL, and queueing nine at once is what sent two of them to the cloud model on 2026-10-25.

**Local coding hours.** `LIFE_GRAPH_DEV_LOCAL_HOURS=23-7`: the queue runner gives a local
engine a queued task only from 23:00 to 07:00 owner time, and only while the owner is away. At
other times a queued `code-fixer-local` / `code-fixer-opencode` task is re-routed to
`code-fixer-cloud` when a free cloud model is available, or waits (`services/compute_router.py::
decide`). A task *started* rather than queued (`queue: false`, or MCP `start_dev_task`) is
interactive and runs on the engine you named at once, whatever the hour; it still competes with
speech for the GPU. So: queue these in the evening for the night, or start one by hand when the
GPU is free.

**Engine.** Use `code-fixer-opencode` (qwen3-coder:30b) first: in the 2026-10-25 runs it was the
only engine that reliably wrote the test file and the one that landed 08. It needs 12 GB of free
RAM or the task waits. `code-fixer-local` (gpt-oss:20b) is faster but fumbled `code_edit` until
the tool and prompt changes below are made; with the new STEP 1 wording it should now create the
file, so it is the fallback. Avoid `code-fixer-cloud` for these specs: the code would leave the
machine, and its one run here never found the worktree. Neither local engine needs a paid model,
so the budget cap does not apply.

1. Copy the instruction: everything between `<!-- instruction:start -->` and
   `<!-- instruction:end -->` in the task file. From the repo root:

   ```sh
   sed -n '/<!-- instruction:start -->/,/<!-- instruction:end -->/{//!p}' docs/tasks/01-money-alert-not-transactions.md
   ```

2. Start it, with **`spec_first=True`**:
   - MCP: `start_dev_task(instruction=<text>, project="life-graph", persona_name="code-fixer-opencode", spec_first=True)`
   - Or queue it for the night: `POST /api/v1/kernel/drivers/tasks` with
     `{"instruction": ..., "project_id": <life-graph id>, "persona_name": "code-fixer-opencode", "spec_first": true, "queue": true}`.
3. Watch it with `get_dev_task(task_id)`, and `GET /kernel/drivers/tasks/{id}/steps` for the
   tool calls. Check early that the first edit created the test file. A run past 20 minutes has
   failed; re-run it once on the other engine.
4. After it lands, run `check_spec_conformance(task_id)`. Every criterion should be *passing*.
   (On OpenCode the stored spec may be empty until the output fix below is made; then re-run
   the AC tests by hand.) Then review it as the Review column says.

## Proposed engine prompt change

Not made in this branch: these are product-code changes, for a separate reviewed PR. The specs
above work around them; the changes would make any future spec, and plain tasks, work without
the workarounds.

**1. `life_graph/kernel/personas.py:275-276` (`code-fixer-local`) and `:344-345`
(`code-fixer-cloud`)**: replace the sentence "If you add or change a test, run it with run_tests
and fix it until it passes." (split across those two string lines) with

```
" When the task gives a test file, create it FIRST, exactly as given: one"
" code_edit call with only path, old=\"\" and new=<the whole file>, no"
" start_line or end_line. Run it with run_tests and see it fail, then change"
" the source until it passes; never edit the given test to make it pass. If"
" you add or change any other test, run it with run_tests and fix it until it"
" passes."
```

**2. `life_graph/kernel/personas.py:307-311` (`code-fixer-opencode`)**: after `" Read the
relevant code first, edit it in place, and re-read what you changed."` insert

```
" When the task gives a test file, write it FIRST, exactly as given, run it"
" with run_tests and see it fail, then change the source until it passes;"
" never edit the given test to make it pass."
```

**3. `life_graph/kernel/personas.py:39-45` (`_UNDERSTANDING_ASK`)**: begin it with
`" Your last message must be text, not a tool call."` so the ask reads: `" Your last message
must be text, not a tool call. If you changed anything other than tests or docs, end your reply
with a '## Understanding' section …"` (rest unchanged).

**4. `life_graph/drivers/opencode.py:387-390`**: the line `"Do not write runner or scratch
files: change only the files the task needs."` becomes `"Do not write runner or scratch files:
change only the files the task needs, including any new test file it names."`

**5. `life_graph/tools/code.py:211-212` (the file-creation trap, root cause 1)**: replace

```python
        if inserting and int(start_line) == 1 and not p.exists():
            start_line = end_line = None
```

with

```python
        if old == "" and not p.exists():
            # Creating a file: line numbers mean nothing yet. gpt-oss:20b
            # passed start_line=1, end_line=200 and got "Not a file" (2026-10-25).
            start_line = end_line = None
```

and at `code.py:224-225` make the error teach the right call:
`{"error": f"Not a file: {path}. To create it, call code_edit with only path, old=\"\" and the
whole file as new."}`. Add a unit test for both next to the existing `code_edit` tests.

**6. `life_graph/drivers/local.py:178-214` (`keep_going`) and `drivers/opencode.py:320-336`**:
after the self-check passes, two one-time nudges before the run may end:
- if the instruction names a test file as new (`(new)` in *Files you may touch*, or
  `Create the new file <path>`) and that file does not exist in the worktree: `"You have not
  created <path> yet. Create it now exactly as the task gives it (code_edit with only path,
  old=\"\" and new), run it, then finish the task."`;
- if a non-test file changed and the reply so far has no `## Understanding`: send
  `services/proof_checks.py::UNDERSTANDING_HINT`.
Both are cheap and in-session, where the model still has the context; today both failures
surface only after the dispatch, and the bounce is a fresh, shorter attempt.

**7. `life_graph/drivers/opencode.py:301` and `:342`**: keep every text part, not only the last:
`output="\n\n".join(texts)[-20000:]`. 81de2480 wrote its `## Spec` and its `## Understanding` in
separate parts; only the last was kept, so the task's spec is null.

## What each task file contains, and why

The engines are reliable on scoped, pure-logic tasks with clear tests. They miss edge cases the
spec does not list, and they fail on DB-mocked tests, large refactors and vague goals. So every
instruction has:

- **STEP 1 with the whole test file.** The cases are the spec; the engine never writes or
  changes them. A test file written by the engine was weak (03: mutants 0.2) or never written.
- **STEP 3 rules:** the behaviour, rule by rule, including the order the rules apply in, and
  where a regex has cost a run before, a pattern known to work.
- **Files you may touch:** one source file and the one *new* test file. `diff_within_scope`
  takes its scope from the files the instruction names. New tests go in a new file, so the
  large shared test files are never rewritten.
- **Do NOT:** what an engine has done wrong before: editing other modules, weakening existing
  tests (`no_test_weakening` is always on), mocking what needs no mock.
- **`## Spec`:** `**Requirements:**` with `AC-n: <criterion> — test: tests/unit/<file>.py::<test>`,
  then `**Design:**` and `**Tasks:**` (one task citing every criterion). At least one criterion
  points at an *existing* test that must keep passing: the regression guard.

The gates on life-graph also need:
- assertions on exact values, because up to 10 mutants of each function a changed test imports
  must be killed (≥ 0.6);
- at least 80% of the changed lines run by the tests;
- the `## Understanding` section at the end of the reply, naming every function changed or
  added.

## Running the tests by hand

Unit tests need no database. From WSL, with ruff on the PATH:

```sh
REPO=/mnt/h/DevTools/Projects/life-graph
cd /tmp && ~/.venvs/life-graph/bin/python -m pytest -q \
  -c $REPO/pyproject.toml --rootdir $REPO \
  $REPO/tests/unit/test_money_alert_not_transactions.py
```

## Writing more of these

Keep to the shape above. Before writing a spec, reproduce the bug on the current base. Then
write the test file, and check on a scratch copy (never the live checkout) that it fails on the
current code and passes against a prototype of the fix, together with the existing tests you
name in STEP 4. A spec with a wrong expected value costs a run and teaches the engine nothing.
Run the parsers on the finished instruction (`_extract_spec`, `parse_criteria`, `_parse_tasks`,
`spec_gaps`, `is_safe_test_ref`) and keep it under 8000 characters. Good candidates are pure
functions on a live path, outside the protected paths (drivers, verifiers, sandbox, autonomy,
approvals, github_pr, dev_outcomes, change_policy, governor, compute_router, redaction, models,
config, main, core tenant/auth/budget/trust, docker, scripts). A change in a protected path waits
for a person whatever the gates say.

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
