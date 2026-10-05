"""Acceptance criteria parsing, task citations, gaps, and test-ref safety."""

from __future__ import annotations

import pytest

from life_graph.services.acceptance import (
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
        AcceptanceCriterion("AC-1", "Empty input is rejected", "tests/unit/test_parser.py::test_empty"),
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
    assert spec_gaps(parse_criteria(spec), ["Add the parser (AC-1)", "Update the README (AC-2)"]) == []


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
