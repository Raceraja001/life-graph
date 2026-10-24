# 11: Plan review, a bound test must be a test file

| | |
|---|---|
| Theme | D. Research and pipeline |
| Engine | `code-fixer-local`, `spec_first=True` |
| Depends on | none |
| Review | **Claude**: the pipeline is changing its own plan checks |
| Size | ~8 lines in `acceptance.py`, one new test file |

## Why

When a plan is filed for approval, `services/acceptance.py::spec_gaps` lists the problems a
reviewer should see. A criterion bound to a file that is not a test passes as "safe", for example
`AC-2: ... — test: life_graph/services/x.py`. pytest then collects nothing (exit 5), and the
`acceptance_tests_pass` verifier fails the task after the run, with no warning at approval time.
Reproduced on 6459f6b: `spec_gaps` returns `[]` for such a spec.

## Instruction

<!-- instruction:start -->
Plan review: spec_gaps must flag an acceptance criterion bound to a file that is not a test file

Read first:
- life_graph/services/acceptance.py: is_safe_test_ref, is_js_test_ref and spec_gaps.
- tests/unit/test_acceptance.py (must keep passing unchanged).

Change (life_graph/services/acceptance.py, spec_gaps only, plus one small private helper):
Inside the loop over criteria in spec_gaps, for a criterion whose test is safe (is_safe_test_ref) and is NOT a JS/TS ref (is_js_test_ref), take the file part (before "::") and its basename. If the basename does not match test_*.py or *_test.py, add exactly this gap:
f"{c.id} test reference {c.test!r} is not a test file (test_*.py) — pytest would collect nothing."
An unsafe ref keeps only its existing "is not a plain pytest path" gap, not this one as well. A criterion with no test keeps only "has no bound test."

Cases (copy exactly; use AcceptanceCriterion(id, text, test), and each task list covers every criterion, so coverage gaps do not appear):
- [AcceptanceCriterion("AC-1", "a", "life_graph/services/x.py")] with tasks ["do a (AC-1)"] -> the gaps are exactly ["AC-1 test reference 'life_graph/services/x.py' is not a test file (test_*.py) — pytest would collect nothing."]
- the same for "tests/conftest.py" and for "tests/unit/helpers.py::test_x": one such gap each
- no gap for "tests/unit/test_a.py::test_a", "tests/unit/a_test.py", "tests/test_c.py" or the JS ref "web/a.test.ts::adds a todo"
- AcceptanceCriterion("AC-1", "a", "-p evil") -> exactly one gap that mentions AC-1, the existing "not a plain pytest path" gap

Files you may touch:
- life_graph/services/acceptance.py (spec_gaps and one private helper)
- tests/unit/test_acceptance_test_file_gap.py (new)

Do NOT:
- change parse_criteria, is_safe_test_ref, bound_tests, describe or is_check_only_task;
- change life_graph/drivers/dispatcher.py or life_graph/services/approvals.py (protected; they call spec_gaps unchanged);
- make the gap blocking: gaps stay advisory text;
- edit tests/unit/test_acceptance.py or any other existing test.

## Spec
**Requirements:**
AC-1: A safe pytest reference to a file not named test_*.py or *_test.py is reported as a gap — test: tests/unit/test_acceptance_test_file_gap.py::test_non_test_file_reference_is_a_gap
AC-2: Test files, JS/TS test refs, unsafe refs and missing tests get no extra gap — test: tests/unit/test_acceptance_test_file_gap.py::test_test_files_are_not_flagged
AC-3: The existing gaps are unchanged — test: tests/unit/test_acceptance.py::test_gaps_name_every_problem
**Design:** A private _is_test_file(ref) helper on the basename; one extra elif branch in the criteria loop of spec_gaps.
**Tasks:**
1. Add the helper and the gap to spec_gaps, and write tests/unit/test_acceptance_test_file_gap.py with the cases above (AC-1, AC-2, AC-3)

Start your reply with the ## Spec section above, copied unchanged, then implement it.
<!-- instruction:end -->

## Reviewer notes (Claude)

- Confirm that the gap is advisory only: `bound_tests` still returns such refs, and the
  verifier still runs them and fails. Stopping such refs from being bound is a separate change
  in a protected path.
- This task's own spec must produce no gaps. Use it as a smoke test: file a plan containing it
  and check the approval detail.
