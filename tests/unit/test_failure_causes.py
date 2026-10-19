"""Failure causes: one primary cause per failed run, by rules, in precedence order.

Error strings here are the real ones failed runs left behind on 2026-10-13.
"""

from __future__ import annotations

import pytest

from life_graph.services.failure_causes import CAUSES, classify, failed_verifiers


@pytest.mark.parametrize(
    ("error", "cause"),
    [
        ("budget: monthly budget exhausted; autonomous spend denied", "budget_exhausted"),
        (
            "claude_code sandbox unavailable: claude_code sandbox could not start: docker: ...",
            "sandbox_unavailable",
        ),
        ("Interrupted: the API restarted while this task was running", "interrupted"),
        ("claude_code timed out after 300s", "timeout"),
        ("Not run: task 1 of this plan was rejected", "plan_not_run"),
        ("Plan dispatch produced no '## Spec' section to review", "plan_no_spec"),
    ],
)
def test_error_strings_map_to_their_cause(error, cause):
    assert classify(status="failed", error=error)["cause"] == cause


def test_a_plan_that_wrote_files_is_named_as_such_not_just_verification_failed():
    verification = [{"attempt": 1, "results": [{"verifier": "no_diff_in_plan", "passed": False}]}]
    result = classify(
        status="failed",
        error="Verification failed after bounce — needs human review",
        verification=verification,
    )
    assert result["cause"] == "plan_wrote_files"


def test_empty_tool_arguments_are_found_in_the_steps():
    # The local qwen run recorded 2026-10-13.
    steps = [
        {"kind": "tool_call", "tool": "code_read", "content": "{}"},
        {
            "kind": "tool_result",
            "tool": "code_read",
            "content": '{"error": "Tool execution failed: missing argument path"}',
        },
    ]
    result = classify(status="failed", error="Plan failed", steps=steps)
    assert {k: result[k] for k in ("cause", "label", "detail")} == {
        "cause": "empty_tool_args",
        "label": CAUSES["empty_tool_args"],
        "detail": "code_read",
    }


def test_model_unavailable_wins_over_the_tool_error_it_caused():
    steps = [
        {"kind": "tool_call", "tool": "code_read", "content": '{"path": "a"}'},
        {"kind": "tool_result", "tool": "code_read", "content": '{"error": "boom"}'},
        {"kind": "error", "content": "All models are currently unavailable. Please try again."},
    ]
    assert classify(status="failed", error="x", steps=steps)["cause"] == "model_unavailable"


def test_verification_failure_names_the_failing_verifiers_and_skips_inconclusive():
    verification = [
        {
            "attempt": 1,
            "results": [
                {"verifier": "tests_pass", "passed": False},
                {"verifier": "lint_clean_diff", "passed": False, "inconclusive": True},
            ],
        },
        {
            "attempt": 2,
            "results": [
                {"verifier": "tests_pass", "passed": False},
                {"verifier": "acceptance_tests_pass", "passed": False},
            ],
        },
    ]
    assert failed_verifiers(verification) == ["tests_pass", "acceptance_tests_pass"]
    result = classify(status="failed", error="Verification failed", verification=verification)
    assert result["cause"] == "verification_failed"
    assert result["detail"] == "tests_pass, acceptance_tests_pass"


def test_tool_error_flag_counts_even_without_an_error_json():
    steps = [
        {
            "kind": "tool_result",
            "tool": "Bash",
            "content": "exit 1",
            "properties": {"is_error": True},
        }
    ]
    assert classify(status="failed", error="", steps=steps)["cause"] == "tool_error"


def test_cancelled_and_other():
    assert classify(status="cancelled", error="Held by reviewer")["cause"] == "cancelled"
    assert classify(status="failed", error="something new")["cause"] == "other"


def test_signals_keep_every_matching_rule_behind_the_primary_cause():
    # The real local run: filed under "no spec", but it also sent empty
    # arguments and lost its model -- the study wants all three.
    steps = [
        {"kind": "tool_call", "tool": "code_read", "content": "{}"},
        {"kind": "tool_result", "tool": "code_read", "content": '{"error": "missing path"}'},
        {"kind": "error", "content": "All models are currently unavailable."},
    ]
    result = classify(
        status="failed", error="Plan dispatch produced no '## Spec' section to review", steps=steps
    )
    assert result["cause"] == "plan_no_spec"
    assert result["signals"] == [
        "plan_no_spec",
        "model_unavailable",
        "empty_tool_args",
        "tool_error",
    ]
