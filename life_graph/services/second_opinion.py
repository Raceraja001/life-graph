"""Second-opinion reviewer (Agent Drivers spec).

A dissenting cheap-model pass that runs *after* a task passes its automated
verifier chain but *before* it auto-lands. The reviewer is a skeptic: it only
blocks (routes to human approval) when it finds a concrete serious problem —
correctness bug, security issue, or wrong-task. Anything else approves.

Fail-open by design: if disabled, no model is configured, or the LLM call
errors, the reviewer approves (``ran=False``) so it never becomes a silent
gate that strands work.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_PROMPT = (
    "You are a skeptical senior reviewer. The following agent output already "
    "passed automated checks (tests/lint/build). Look ONLY for a serious "
    "problem that should block auto-landing: a correctness bug, a security "
    "issue, or work that does not match the task. If you find none, approve.\n\n"
    "Return strict JSON: {{\"approved\": bool, \"concern\": string}}. "
    "Leave concern empty when approved.\n\n"
    "TASK ({task_type}): {instruction}\n\nOUTPUT:\n{output}"
)


@dataclass
class ReviewVerdict:
    """Outcome of a second-opinion review."""

    approved: bool
    concern: str | None = None
    ran: bool = True


class SecondOpinionReviewer:
    """Cheap-model dissenting reviewer for verified driver output."""

    def __init__(self, *, llm=None, model: str | None = None, enabled: bool = True) -> None:
        self._llm = llm
        self._model = model
        self._enabled = enabled

    async def review(
        self, task_type: str, instruction: str, output: str | None
    ) -> ReviewVerdict:
        """Review verified output. Approves unless a concrete concern is found."""
        if not self._enabled or self._llm is None or not output:
            return ReviewVerdict(approved=True, ran=False)

        prompt = _PROMPT.format(
            task_type=task_type,
            instruction=(instruction or "")[:2000],
            output=output[:6000],
        )
        try:
            raw = await self._llm.chat(
                [{"role": "user", "content": prompt}],
                model=self._model,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
        except Exception:
            logger.warning("Second-opinion LLM call failed — approving", exc_info=True)
            return ReviewVerdict(approved=True, ran=False)

        return self._parse(raw)

    @staticmethod
    def _parse(raw: str) -> ReviewVerdict:
        """Parse the reviewer JSON. Fail-open: unparseable → approved."""
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Second-opinion returned non-JSON — approving")
            return ReviewVerdict(approved=True, ran=False)
        if not isinstance(data, dict):
            return ReviewVerdict(approved=True, ran=False)

        approved = data.get("approved", True)
        if not isinstance(approved, bool):
            approved = str(approved).strip().lower() in (
                "true", "yes", "1", "approve", "approved",
            )
        concern = data.get("concern") or None
        return ReviewVerdict(
            approved=approved,
            concern=str(concern) if concern else None,
            ran=True,
        )
