"""Why a dev task failed: one primary cause per run, by deterministic rules.

No LLM (charter invariant 1). The order below is the precedence: the first
matching rule wins, so a run that timed out *because* its model kept
erroring is filed under the earlier, more specific rule. Rules read three
things a failed run leaves behind: the task's ``error`` string, its
verification attempts, and its recorded steps (services/trajectories.py).

A cause is a plain string key with a label, not an enum (invariant 2), so a
new rule is one entry in ``CAUSES`` and one branch in :func:`classify`.
"""

from __future__ import annotations

import json
from typing import Any

CAUSES: dict[str, str] = {
    "budget_exhausted": "Budget exhausted",
    "sandbox_unavailable": "Sandbox could not start",
    "interrupted": "Interrupted by a restart",
    "timeout": "Timed out",
    "stuck": "Stuck in a loop",
    "out_of_rounds": "Ran out of tool rounds",
    "plan_not_run": "Not run: an earlier plan task stopped",
    "plan_no_spec": "Plan produced no spec",
    "plan_wrote_files": "Plan-only run changed files",
    "model_unavailable": "Model unavailable",
    "empty_tool_args": "Tool called with no arguments",
    "tool_error": "A tool call failed",
    "verification_failed": "Verification failed",
    "cancelled": "Cancelled",
    "other": "Other",
}

_EMPTY_INPUTS = {"", "{}", "null", "[]"}


def _failed_result(step: dict) -> bool:
    if step.get("kind") != "tool_result":
        return False
    if (step.get("properties") or {}).get("is_error") or step.get("is_error"):
        return True
    content = (step.get("content") or "").lstrip()
    if content.startswith("{"):
        try:
            return "error" in json.loads(content)
        except (ValueError, TypeError):
            return content.startswith('{"error"')
    return False


def failed_verifiers(verification: list[dict]) -> list[str]:
    """Names of the verifiers that failed (not inconclusive), across attempts."""
    names: list[str] = []
    for attempt in verification or []:
        for r in attempt.get("results") or []:
            if not r.get("passed") and not r.get("inconclusive"):
                name = r.get("verifier")
                if name and name not in names:
                    names.append(name)
    return names


def classify(
    *,
    status: str | None,
    error: str | None,
    verification: list[dict] | None = None,
    steps: list[dict] | None = None,
) -> dict[str, Any]:
    """The primary cause of one failed run, plus every rule that matched.

    ``{"cause", "label", "detail", "signals"}``: ``cause`` is the first match
    in precedence order; ``signals`` lists all matches in that order, so a
    run filed under "no spec" still shows that it also sent empty tool
    arguments (which is usually *why* there was no spec).
    """
    err = (error or "").strip()
    low = err.lower()
    steps = steps or []
    verifiers = failed_verifiers(verification or [])
    matches: list[tuple[str, str | None]] = []

    if low.startswith("budget:"):
        matches.append(("budget_exhausted", err))
    if "sandbox unavailable" in low:
        matches.append(("sandbox_unavailable", err[:300]))
    if low.startswith("interrupted"):
        matches.append(("interrupted", err))
    if "timed out" in low:
        matches.append(("timeout", err))
    if "stuck in a loop" in low or any(
        s.get("kind") == "stuck" and '"stopped"' in (s.get("content") or "") for s in steps
    ):
        matches.append(("stuck", err[:300] or None))
    if "ran out of tool rounds" in low:
        matches.append(("out_of_rounds", None))
    if low.startswith("not run:"):
        matches.append(("plan_not_run", err[:300]))
    if "no '## spec'" in low:
        matches.append(("plan_no_spec", err))
    if "no_diff_in_plan" in verifiers:
        matches.append(("plan_wrote_files", None))
    if "models are currently unavailable" in low or any(
        s.get("kind") == "error" and "unavailable" in (s.get("content") or "").lower()
        for s in steps
    ):
        matches.append(("model_unavailable", None))
    for i, step in enumerate(steps):
        if (
            step.get("kind") == "tool_call"
            and (step.get("content") or "").strip() in _EMPTY_INPUTS
            and i + 1 < len(steps)
            and _failed_result(steps[i + 1])
        ):
            matches.append(("empty_tool_args", step.get("tool")))
            break
    failing = [s for s in steps if _failed_result(s)]
    if failing:
        matches.append(("tool_error", failing[0].get("tool")))
    if verifiers or "verification failed" in low:
        matches.append(("verification_failed", ", ".join(verifiers) or None))
    if status == "cancelled":
        matches.append(("cancelled", err or None))
    if not matches:
        matches.append(("other", err[:300] or None))

    # A failing tool result alongside a verdict is the verdict's story, not a
    # separate cause: verification failures always involve tools that failed.
    primary = next((m for m in matches if not (m[0] == "tool_error" and verifiers)), matches[0])
    return {
        "cause": primary[0],
        "label": CAUSES[primary[0]],
        "detail": primary[1],
        "signals": [m[0] for m in matches],
    }
