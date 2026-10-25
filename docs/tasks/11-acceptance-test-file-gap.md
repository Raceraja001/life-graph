# 11: Plan review, a bound test must be a test file

| | |
|---|---|
| Theme | D. Research and pipeline |
| Engine | `code-fixer-opencode`, else `code-fixer-local`; `spec_first=True` (README: How to run) |
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

Do these five steps in order. Each one is required: without the test file (STEP 1) and the Understanding section (STEP 5) the task fails verification, however good the code is.

STEP 1. Create the new file tests/unit/test_acceptance_test_file_gap.py with exactly the text between the ===== lines: nothing added, nothing left out. Do it first, before you read or change anything else.
- With code_edit: ONE call with only path="tests/unit/test_acceptance_test_file_gap.py", old="" and new=<the whole text>. Do not pass start_line or end_line; with them the call fails with "Not a file".
- With OpenCode's tools: use write.
===== tests/unit/test_acceptance_test_file_gap.py =====
import pytest

from life_graph.services.acceptance import AcceptanceCriterion, spec_gaps


def gaps_for(test):
    return spec_gaps([AcceptanceCriterion("AC-1", "a", test)], ["do a (AC-1)"])


@pytest.mark.parametrize(
    "test",
    ["life_graph/services/x.py", "tests/conftest.py", "tests/unit/helpers.py::test_x"],
)
def test_non_test_file_reference_is_a_gap(test):
    assert gaps_for(test) == [
        f"AC-1 test reference {test!r} is not a test file (test_*.py) — pytest would collect nothing."
    ]


@pytest.mark.parametrize(
    "test",
    [
        "tests/unit/test_a.py::test_a",
        "tests/unit/a_test.py",
        "tests/test_c.py",
        "web/a.test.ts::adds a todo",
    ],
)
def test_test_files_are_not_flagged(test):
    assert gaps_for(test) == []
    unsafe = gaps_for("-p evil")
    assert len(unsafe) == 1
    assert "AC-1" in unsafe[0]
    assert "not a plain pytest path" in unsafe[0]
    assert gaps_for(None) == ["AC-1 has no bound test."]
===== end of tests/unit/test_acceptance_test_file_gap.py =====

STEP 2. Run it: run_tests with paths ["tests/unit/test_acceptance_test_file_gap.py"] (on OpenCode the tool is lg_tests_run_tests). Some cases must fail now, because the source is not changed yet. An ImportError or SyntaxError means STEP 1 was copied wrong: fix the copy, never the cases.

STEP 3. Make the smallest change in life_graph/services/acceptance.py (spec_gaps) that makes those cases pass. Read the code first.
Make exactly two small edits. On the last run a code_edit call whose `old` was the whole multi-line spec_gaps function could not be parsed by the model server, and the run died. So keep every `old` to ONE line copied from the file, and write the new code with single quotes only, as below (no escaping needed; the formatter fixes the quotes later).
Edit A: old is the one line
def spec_gaps(criteria: list[AcceptanceCriterion], tasks: list[str]) -> list[str]:
and new is this helper, two blank lines, then that same line again:
def _is_test_file(ref: str) -> bool:
    name = ref.split('::', 1)[0].rsplit('/', 1)[-1]
    return name.endswith('.py') and (name.startswith('test_') or name.endswith('_test.py'))
Edit B: old is the one line in spec_gaps that appends the "is not a plain pytest path" gap; new is that same line followed by (same indentation as its elif above it):
        elif not is_js_test_ref(c.test) and not _is_test_file(c.test):
            gaps.append(
                f'{c.id} test reference {c.test!r} is not a test file (test_*.py)'
                ' — pytest would collect nothing.'
            )
An unsafe ref keeps only its existing gap, and a criterion with no test keeps only "has no bound test.". After each edit, code_read the lines you changed.

STEP 4. Run run_tests with paths ["tests/unit/test_acceptance_test_file_gap.py", "tests/unit/test_acceptance.py"]. If anything fails, fix the SOURCE and run again until all pass. Never edit tests/unit/test_acceptance_test_file_gap.py to make it pass, and never edit any other test file.

STEP 5. Your last message is text, not a tool call. End it with this section, every line filled in, naming every function you added or changed:
## Understanding
Current behaviour: <what spec_gaps did before, in your words>
Change: <what you changed in spec_gaps (and any helper you added), and why>
Risk: <what could break, and which test in tests/unit/test_acceptance_test_file_gap.py or tests/unit/test_acceptance.py shows it does not>

Files you may touch:
- life_graph/services/acceptance.py (spec_gaps, and a new private helper _is_test_file)
- tests/unit/test_acceptance_test_file_gap.py (new; created in STEP 1)

Do NOT:
- change parse_criteria, is_safe_test_ref, bound_tests, describe or is_check_only_task;
- change life_graph/drivers/ or life_graph/services/approvals.py (protected);
- make the gap blocking: gaps stay advisory text;
- edit, rename or delete any existing test file;
- add a database, a mock or a new dependency (this is pure logic).

## Spec
**Requirements:**
AC-1: A safe pytest reference to a file not named test_*.py or *_test.py is reported as a gap — test: tests/unit/test_acceptance_test_file_gap.py::test_non_test_file_reference_is_a_gap
AC-2: Test files, JS/TS test refs, unsafe refs and missing tests get no extra gap — test: tests/unit/test_acceptance_test_file_gap.py::test_test_files_are_not_flagged
AC-3: The existing gaps are unchanged — test: tests/unit/test_acceptance.py::test_gaps_name_every_problem
**Design:** A private _is_test_file(ref) helper on the basename; one extra elif branch in the criteria loop of spec_gaps.
**Tasks:**
1. Create tests/unit/test_acceptance_test_file_gap.py exactly as given, then add the helper and the gap to spec_gaps until it and the existing acceptance tests pass (AC-1, AC-2, AC-3)

Start your reply with the ## Spec section above, copied unchanged. Then do STEP 1.
<!-- instruction:end -->

## Reviewer notes (Claude)

- Confirm that the gap is advisory only: `bound_tests` still returns such refs, and the
  verifier still runs them and fails. Stopping such refs from being bound is a separate change
  in a protected path.
- This task's own spec must produce no gaps. Use it as a smoke test: file a plan containing it
  and check the approval detail.
