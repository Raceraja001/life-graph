"""The night shift report's formatting (services/night_shift.py)."""

from __future__ import annotations

from life_graph.services.night_shift import lines, short_title


def test_short_title_for_nightly_test_tasks():
    title = (
        "Write unit tests, in a new file tests/unit/test_money_merchant_from.py, for "
        "`merchant_from` in life_graph/services/money.py, which has none. Read the function…"
    )
    assert short_title(title) == "tests for merchant_from (services/money.py)"
    assert short_title("Fix the 422 in kernel.py") == "Fix the 422 in kernel.py"
    assert short_title("x" * 120).endswith("…") and len(short_title("x" * 120)) == 78


def _rep(merged=(), waiting=(), failed=(), queued=0):
    return {
        "since": "2026-10-20T00:00:00+00:00",
        "merged": list(merged),
        "waiting": list(waiting),
        "failed": list(failed),
        "queued": queued,
    }


def test_lines_name_each_task_with_its_outcome():
    rep = _rep(
        merged=[{"title": "tests for f", "pr_url": "https://github.com/o/r/pull/1"}],
        waiting=[
            {
                "title": "Fix x",
                "reason": "needs review: touches protected paths: uv.lock",
                "pr_url": None,
            }
        ],
        failed=[{"title": "tests for g", "reason": "Ran out of rounds; handed to OpenCode"}],
        queued=2,
    )
    assert lines(rep) == [
        "1 merged, 1 waiting for you, 1 failed, 2 queued",
        "merged: tests for f — https://github.com/o/r/pull/1",
        "waiting: Fix x — needs review: touches protected paths: uv.lock",
        "failed: tests for g — Ran out of rounds; handed to OpenCode",
    ]


def test_nothing_to_report_is_silence():
    assert lines(_rep()) == []


def test_long_lists_are_cut_with_a_pointer():
    rep = _rep(merged=[{"title": f"t{i}", "pr_url": None} for i in range(11)])
    out = lines(rep)
    assert out[-1] == "(and 3 more on the Dev tasks page)"
    assert len(out) == 1 + 8 + 1
