"""PR description drafting (best-effort, falls back cleanly) and the PR body:
it uses the drafted description, and is honest about an unverified landing.
"""

from __future__ import annotations

import asyncio

import pytest

from life_graph.services.github_pr import _pr_body, _verification_line
from life_graph.services.pr_description import draft_pr_description

GOOD = "## What changed\n- Added `foo()` in a.py\n## Why\nNeeded.\n## Review notes\nNone"
DIFF = "diff --git a/a.py b/a.py\n+def foo():\n+    return 1\n"


def _chat(reply="", *, raises=None, delay=0.0, seen=None):
    async def chat(messages, **kwargs):
        if seen is not None:
            seen.append(messages[0]["content"])
        if delay:
            await asyncio.sleep(delay)
        if raises:
            raise raises
        return reply

    return chat


@pytest.mark.asyncio
async def test_returns_the_description_from_its_first_heading():
    text = await draft_pr_description(DIFF, "add foo", chat=_chat("Sure! Here it is:\n\n" + GOOD))
    assert text == GOOD


@pytest.mark.asyncio
async def test_think_blocks_are_stripped():
    text = await draft_pr_description(
        DIFF, "add foo", chat=_chat("<think>long reasoning ## What changed</think>\n" + GOOD)
    )
    assert text == GOOD


@pytest.mark.asyncio
async def test_reply_without_the_format_is_ignored():
    assert await draft_pr_description(DIFF, "add foo", chat=_chat("I added a function.")) is None


@pytest.mark.asyncio
async def test_model_failure_falls_back():
    assert await draft_pr_description(DIFF, "x", chat=_chat(raises=RuntimeError("down"))) is None


@pytest.mark.asyncio
async def test_timeout_falls_back():
    text = await draft_pr_description(DIFF, "x", chat=_chat(GOOD, delay=1.0), timeout=0.05)
    assert text is None


@pytest.mark.asyncio
async def test_empty_diff_never_calls_the_model():
    seen = []
    assert await draft_pr_description("  ", "x", chat=_chat(GOOD, seen=seen)) is None
    assert seen == []


@pytest.mark.asyncio
async def test_long_diff_is_truncated_in_the_prompt():
    seen = []
    await draft_pr_description("+x\n" * 20000, "x", chat=_chat(GOOD, seen=seen))
    assert "(diff truncated)" in seen[0]
    assert len(seen[0]) < 15000


# ── The PR body ──


def test_body_uses_the_drafted_description():
    body = _pr_body({"instruction": "add foo", "summary": "agent narrative", "pr_description": GOOD})
    assert GOOD in body
    assert "agent narrative" not in body


def test_body_falls_back_to_the_agent_summary():
    body = _pr_body({"instruction": "add foo", "summary": "agent narrative"})
    assert "## Agent summary" in body
    assert "agent narrative" in body


def test_verified_body_lists_passed_checks():
    line = _verification_line({"verified": True, "checks": ["build_ok_diff", "tests_pass"]})
    assert line == "Passed: `build_ok_diff`, `tests_pass`"


def test_unverified_body_does_not_claim_checks_passed():
    """It used to say "Passed: <every check>" about checks that never ran."""
    line = _verification_line(
        {
            "verified": False,
            "checks": ["build_ok_diff", "no_vulnerable_deps_in_diff"],
            "unverifiable_checks": ["no_vulnerable_deps_in_diff"],
        }
    )
    assert line.startswith("**Not verified:** `no_vulnerable_deps_in_diff` could not run")
    assert "Passed: `build_ok_diff`." in line
