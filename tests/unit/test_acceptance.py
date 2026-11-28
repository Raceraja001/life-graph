"""Acceptance criteria parsing, task citations, gaps, and test-ref safety."""

from __future__ import annotations

import pytest

from life_graph.services.dev.acceptance import (
    AcceptanceCriterion,
    bound_tests,
    cited_criteria,
    describe,
    is_safe_test_ref,
    parse_criteria,
    spec_gaps,
)

SPEC = (
    "**Requirements:**\n"
    "AC-1: Empty input is rejected — test: tests/unit/test_parser.py::test_empty\n"
    "AC-2: Valid input round-trips — test: `tests/unit/test_parser.py::test_roundtrip`\n"
    "**Design:** a small parser.\n"
    "**Tasks:** 1. Add the parser (AC-1, AC-2) 2. Update the README\n"
)


def test_parse_criteria_reads_ids_text_and_tests():
    assert parse_criteria(SPEC) == [
        AcceptanceCriterion(
            "AC-1", "Empty input is rejected", "tests/unit/test_parser.py::test_empty"
        ),
        AcceptanceCriterion(
            "AC-2", "Valid input round-trips", "tests/unit/test_parser.py::test_roundtrip"
        ),
    ]


def test_parse_criteria_tolerates_bold_and_em_dash_styles():
    spec = "- **AC-3** — WHEN saved THEN persisted (test: tests/unit/test_save.py)"
    [c] = parse_criteria(spec)
    assert c.id == "AC-3"
    assert c.test == "tests/unit/test_save.py"
    assert "WHEN saved" in c.text


def test_parse_criteria_without_a_test_keeps_the_criterion():
    [c] = parse_criteria("AC-1: Something must hold")
    assert c.test is None


def test_first_definition_wins():
    spec = "AC-1: first — test: tests/a.py\nAC-1: second — test: tests/b.py"
    assert [c.text for c in parse_criteria(spec)] == ["first"]


def test_task_citations_are_not_mistaken_for_criteria():
    assert [c.id for c in parse_criteria(SPEC)] == ["AC-1", "AC-2"]


def test_cited_criteria():
    assert cited_criteria("1. Add the parser (AC-1, ac-2, AC-1)") == ["AC-1", "AC-2"]
    assert cited_criteria("2. Update the README") == []


@pytest.mark.parametrize(
    "ref",
    [
        "tests/unit/test_a.py",
        "tests/unit/test_a.py::test_b",
        "tests/unit/test_a.py::TestX::test_y[1-2]",
    ],
)
def test_safe_refs(ref):
    assert is_safe_test_ref(ref)


@pytest.mark.parametrize(
    "ref",
    [
        None,
        "",
        "-p malicious",
        "--rootdir=/",
        "/etc/passwd.py",
        "../outside/test_a.py",
        "tests/../../x.py",
        "tests/unit/test_a.txt",
        "tests/unit/test_a.py; rm -rf /",
        "tests/unit/test a.py",
    ],
)
def test_unsafe_refs(ref):
    assert not is_safe_test_ref(ref)


def test_no_gaps_for_a_complete_spec():
    spec = SPEC.replace("2. Update the README", "2. Update the README (AC-2)")
    assert (
        spec_gaps(parse_criteria(spec), ["Add the parser (AC-1)", "Update the README (AC-2)"]) == []
    )


def test_gaps_name_every_problem():
    criteria = [
        AcceptanceCriterion("AC-1", "a", None),
        AcceptanceCriterion("AC-2", "b", "-p evil"),
        AcceptanceCriterion("AC-3", "c", "tests/test_c.py"),
    ]
    gaps = spec_gaps(criteria, ["do a (AC-1)", "do x (AC-9)", "do nothing"])
    assert "AC-1 has no bound test." in gaps
    assert any("AC-2 test reference" in g for g in gaps)
    assert "Task 2 cites AC-9, which the spec doesn't define." in gaps
    assert "Task 3 cites no acceptance criterion." in gaps
    assert "AC-2 is not covered by any task." in gaps
    assert "AC-3 is not covered by any task." in gaps


def test_no_criteria_is_one_clear_gap():
    [gap] = spec_gaps([], ["do a"])
    assert "No acceptance criteria" in gap


def test_bound_tests_skips_unsafe_and_dedupes():
    criteria = [
        AcceptanceCriterion("AC-1", "a", "tests/t.py::a"),
        AcceptanceCriterion("AC-2", "b", "-p evil"),
        AcceptanceCriterion("AC-3", "c", "tests/t.py::a"),
    ]
    assert bound_tests(criteria, ["AC-1", "AC-2", "AC-3", "AC-9"]) == ["tests/t.py::a"]


def test_describe_names_the_test_only_when_safe():
    criteria = [
        AcceptanceCriterion("AC-1", "a", "tests/t.py::a"),
        AcceptanceCriterion("AC-2", "b", "-p evil"),
    ]
    text = describe(criteria, ["AC-1", "AC-2"])
    assert "AC-1: a (proved by test: tests/t.py::a)" in text
    assert "- AC-2: b" in text
    assert "-p evil" not in text


# ── Exact test names in the instruction (2026-11-28) ─────────────

_EXACT_SPEC = (
    "AC-1: parses — test: tests/unit/test_p.py::test_parse\n"
    "AC-2: grouped — test: tests/unit/test_p.py::TestX::test_y[a-b]\n"
    "AC-3: todo — test: web/todo.test.ts::adds a todo\n"
    "AC-4: file — test: tests/unit/test_q.py\n"
    "AC-5: unbound\n"
    "AC-6: unsafe — test: ../evil.py::test_x\n"
)


def test_exact_test_names_spell_out_file_and_name_per_criterion():
    from life_graph.services.dev.acceptance import exact_test_names, parse_criteria

    crit = parse_criteria(_EXACT_SPEC)
    lines = exact_test_names(crit, ["AC-1", "AC-2", "AC-3", "AC-4", "AC-5", "AC-6"]).splitlines()
    assert lines == [
        "- AC-1: file `tests/unit/test_p.py` (create or update it at exactly this path); "
        "pytest node id exactly `tests/unit/test_p.py::test_parse`: define "
        "`def test_parse(...)` at module level.",
        "- AC-2: file `tests/unit/test_p.py` (create or update it at exactly this path); "
        "pytest node id exactly `tests/unit/test_p.py::TestX::test_y[a-b]`: define "
        "`def test_y(...)` inside `class TestX`, parametrized so one case's id is `[a-b]`.",
        "- AC-3: file `web/todo.test.ts` (create or update it at exactly this path); test "
        'title exactly `adds a todo`: write `test("adds a todo", ...)` (or `it(...)`) with '
        "that title character for character. A `describe(...)` around it is fine, but the "
        "runner filters with `-t` on the full title `<describe> <test>`, which must contain "
        "`adds a todo` verbatim -- so the test's own title is that exact string, not a "
        "variant split across describe and test.",
        "- AC-4: file `tests/unit/test_q.py` (create or update it at exactly this path); the "
        "whole file is run, so every test in it must pass.",
    ]  # AC-5 (no test) and AC-6 (unsafe ref) are not listed


def test_the_criteria_block_carries_the_strict_name_list():
    from life_graph.services.dev.acceptance import criteria_block, parse_criteria

    crit = parse_criteria(_EXACT_SPEC)
    block = criteria_block(crit, ["AC-1"])
    assert block.startswith("\n\n--- ACCEPTANCE CRITERIA THIS TASK MUST SATISFY ---\n- AC-1:")
    assert "--- EXACT TEST NAMES (checked strictly) ---" in block
    assert "do not rename, reword, re-case, pluralise or move them" in block
    assert "AC-3" not in block  # only the cited criteria
    # Criteria without a usable test: the criteria, but no strict list.
    assert "EXACT TEST NAMES" not in criteria_block(crit, ["AC-5"])
    assert criteria_block(crit, ["AC-9"]) == ""
