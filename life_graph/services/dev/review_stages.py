"""Review stages: ordered, veto-only reviewers in the second-opinion gate position.

docs/specs/agent-drivers.md, "Autonomy policy" (2026-11-27). The owner lists
up to four stages (services/dev/autonomy_policy.py ``review_stages``); the
dispatcher runs them in order after the verifier chain passes, before landing
(drivers/review_stages.py). Each stage's reviewer is one of:

* ``human`` -- no automatic review: the chain stops there and the task is
  never auto-approved (a person's approval *is* the stage);
* ``pr_agent`` -- PR-Agent over the real diff (services/dev/pr_agent_review.py),
  with the stage's focus as its extra instructions;
* ``model:<id>`` -- one veto-only LLM pass on that model (code only reaches a
  model; never memories), with the stage's focus in the prompt.

Driver-backed reviewers (a second coding agent reading the worktree) wait for
the Phase 3 drivers. A reviewer can only object (CHARTER invariant 1): "no
objection" adds nothing to the trust the change already needs, and a stage
that could not run is recorded as ``unavailable``, which refuses
auto-approval but never fails the task on its own.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any, Protocol

from life_graph.config import settings
from life_graph.services.dev.autonomy_policy import (
    HUMAN_REVIEWER,
    MODEL_PREFIX,
    PR_AGENT_REVIEWER,
    ReviewStage,
)
from life_graph.services.dev.pr_agent_review import PRAgentReviewer, ReviewVerdict
from life_graph.services.llm.client import get_resilient_llm
from life_graph.services.llm.resilient import only_models

logger = logging.getLogger(__name__)

_DIFF_MAX = 30_000

_PROMPT = """You review a code change an AI agent made, as one stage of an \
ordered review. You can stop it; you cannot approve it on your own.

Review stage: {name}
What this stage looks for:
{focus}

The task the agent was given:
{instruction}

The change (unified diff):
{diff}

Object only if you find a concrete, serious problem within this stage's focus \
(or a correctness, security or tenant-isolation problem). Name the file and \
what is wrong.

Answer with JSON only: {{"verdict": "ok" or "object", "reason": "one or two sentences"}}"""


class StageReviewer(Protocol):
    """What a review stage calls. Same verdict shape the dispatcher's reviewer returns."""

    async def review(
        self, task_type: str, instruction: str, diff_text: str | None, focus: str | None = None
    ) -> ReviewVerdict: ...


class ModelStageReviewer:
    """A veto-only LLM pass on one named model, with the stage's focus."""

    def __init__(self, model: str, name: str = "review") -> None:
        self._model = model
        self._name = name

    async def review(
        self, task_type: str, instruction: str, diff_text: str | None, focus: str | None = None
    ) -> ReviewVerdict:
        """Object or not. Any failure is ``ran=False`` (unavailable), never a pass."""
        if not diff_text or not diff_text.strip():
            return ReviewVerdict(approved=True, ran=False, concern="no diff to review")

        prompt = _PROMPT.format(
            name=self._name,
            focus=(focus or "general correctness").strip()[:2000],
            instruction=(instruction or "")[:4000],
            diff=diff_text[:_DIFF_MAX],
        )
        try:
            # Only the named model: a cheap stage must not fall back to a paid one.
            with only_models([self._model]):
                text = await get_resilient_llm().chat(
                    [{"role": "user", "content": prompt}],
                    model=self._model,
                    temperature=0,
                    max_tokens=300,
                )
        except Exception as exc:  # noqa: BLE001 - any failure = the stage did not run
            logger.warning("Review stage %s unavailable: %s", self._name, exc)
            return ReviewVerdict(approved=True, ran=False, concern=f"unavailable ({exc})"[:300])
        return parse_verdict(text)


def parse_verdict(text: str | None) -> ReviewVerdict:
    """The model's JSON answer as a verdict; unreadable = did not run."""
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    try:
        answer = json.loads(match.group(0)) if match else {}
    except json.JSONDecodeError:
        answer = {}
    if not isinstance(answer, dict):
        answer = {}
    verdict = str(answer.get("verdict") or "").strip().lower()
    reason = str(answer.get("reason") or "").strip()[:1000] or None
    if verdict == "ok":
        return ReviewVerdict(approved=True, ran=True, concern=None)
    if verdict in ("object", "block", "objection", "request_changes"):
        return ReviewVerdict(approved=False, ran=True, concern=reason or "objection")
    return ReviewVerdict(approved=True, ran=False, concern="no readable verdict")


def reviewer_for(stage: ReviewStage) -> StageReviewer | None:
    """The reviewer a stage runs; None for a ``human`` stage."""
    if stage.reviewer == HUMAN_REVIEWER:
        return None
    if stage.reviewer == PR_AGENT_REVIEWER:
        # Enabled because the owner configured the stage, whatever the global
        # driver_second_opinion_enabled flag says (that one governs the
        # single default review only).
        return PRAgentReviewer(
            model=settings.driver_second_opinion_model or settings.agent_llm_model,
            enabled=True,
            bin_path=settings.driver_pr_agent_bin,
        )
    return ModelStageReviewer(stage.reviewer.removeprefix(MODEL_PREFIX), name=stage.name)


def stage_record(
    index: int,
    stage: ReviewStage,
    verdict: str,
    *,
    concern: str | None = None,
    fix_round: int = 0,
    note: str | None = None,
) -> dict[str, Any]:
    """One stored stage result (``properties.review_stages`` on the task).

    ``verdict``: ``no_objection`` | ``objection`` | ``unavailable`` | ``human``
    | ``skipped``. ``fix_round`` 0 is the stage's first review; n is the
    review after the n-th review-fix round.
    """
    return {
        "index": index,
        "name": stage.name,
        "reviewer": stage.reviewer,
        "focus": stage.focus,
        "verdict": verdict,
        "concern": (concern or None) and str(concern)[:2000],
        "fix_round": fix_round,
        "note": note,
        "at": datetime.now(UTC).isoformat(),
    }


def latest_per_stage(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The last result of each stage, in stage order (what an approval carries)."""
    latest: dict[int, dict[str, Any]] = {}
    for r in results:
        latest[int(r.get("index", 0))] = r
    return [
        {k: latest[i].get(k) for k in ("index", "name", "reviewer", "verdict", "fix_round")}
        for i in sorted(latest)
    ]
