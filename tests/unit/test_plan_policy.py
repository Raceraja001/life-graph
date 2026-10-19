"""When a plan approves itself, and the planner rules that keep tasks useful."""

from __future__ import annotations

import pytest

from life_graph.services.acceptance import is_check_only_task, parse_criteria, spec_gaps
from life_graph.services.plan_policy import decide

TRUSTED = {"established": True, "merge_rate": 0.9, "merged": 9, "total": 10}
SPEC = "**Requirements:**\nAC-1: lists todos — test: tests/t.test.mjs::lists\n"


def _decide(**over):
    kw = dict(
        opted_in=True,
        spec=SPEC,
        tasks=["1. add list (AC-1)"],
        gaps=[],
        record=TRUSTED,
        merge_bar=0.8,
    )
    kw.update(over)
    return decide(**kw)


def test_a_small_clean_plan_from_a_trusted_driver_approves_itself():
    d = _decide()
    assert d.approve is True and "9/10 merged" in d.summary


@pytest.mark.parametrize(
    ("over", "reason"),
    [
        ({"opted_in": False}, "opted into"),
        ({"tasks": ["a", "b", "c", "d"]}, "4 tasks"),
        ({"gaps": ["AC-2 is not covered"]}, "spec gap"),
        ({"record": {"established": False, "merge_rate": 1.0, "merged": 1, "total": 1}}, "record"),
        ({"record": {**TRUSTED, "merge_rate": 0.5}}, "record"),
        ({"spec": SPEC + "Store the token in .env and add an alembic/ migration"}, "sensitive"),
        ({"spec": SPEC + "Loosen the approval gate"}, "sensitive"),
    ],
)
def test_any_failing_rule_leaves_the_plan_for_a_person(over, reason):
    d = _decide(**over)
    assert d.approve is False
    assert reason in d.summary


@pytest.mark.parametrize(
    "task",
    [
        "Run `ruff check life_graph/`, `ruff format` on the touched files, then the full pytest",
        "Verify the suite passes",
        "re-run the tests",
    ],
)
def test_check_only_tasks_are_recognised(task):
    assert is_check_only_task(task)


@pytest.mark.parametrize(
    "task",
    [
        "Regenerate the inventory with `python scripts/gen_state.py --html`",
        "Add a remove() method and test it",
        "Run the migration script and update the docs",  # it also changes something
    ],
)
def test_tasks_that_change_something_are_kept(task):
    assert not is_check_only_task(task)


def test_a_check_only_task_is_a_spec_gap():
    spec = SPEC + "**Tasks:**\n1. add list (AC-1)\n2. Run the full test suite\n"
    gaps = spec_gaps(parse_criteria(spec), ["add list (AC-1)", "Run the full test suite"])
    assert any("Task 2 only runs checks" in g for g in gaps)


def test_the_plan_prompt_states_the_rules():
    from life_graph.drivers.dispatcher import _PLAN_ONLY_PREFIX

    assert "No task that only runs checks" in _PLAN_ONLY_PREFIX
    assert "regenerate it inside that same task" in _PLAN_ONLY_PREFIX
