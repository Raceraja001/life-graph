"""Second-opinion reviewer (Agent Drivers spec).

A dissenting cheap-model pass that runs *after* a task passes its automated
verifier chain but *before* it auto-lands. The reviewer is a skeptic: it only
blocks (routes to human approval) when it finds a concrete serious problem —
correctness bug, security issue, or wrong-task.

Fail-closed (router council decision, 2026-11-28): when the review is turned
on but cannot produce a verdict — the model call errors or times out, no
model is configured, the reply is not JSON, or ``approved`` is missing or not
a recognisable yes/no — the verdict is :attr:`ReviewStatus.NOT_REVIEWED`.
That is neither an approval nor an objection, and it must never auto-land:
the task goes to a person. Only when the feature is off, or there is nothing
to review, is the verdict :attr:`ReviewStatus.SKIPPED` (lands as before).

The contract callers act on is :attr:`ReviewVerdict.may_auto_land` /
:attr:`ReviewVerdict.needs_human`; ``approved`` and ``ran`` remain for older
callers, and ``ran and not approved`` alone is NOT a safe gate (it lets a
not-reviewed task through).
"""

from __future__ import annotations

import json
import logging
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)

_PROMPT = (
    "You are a skeptical senior reviewer. The following agent output already "
    "passed automated checks (tests/lint/build). Look ONLY for a serious "
    "problem that should block auto-landing: a correctness bug, a security "
    "issue, or work that does not match the task. If you find none, approve.\n\n"
    'Return strict JSON: {{"approved": bool, "concern": string}}. '
    "Leave concern empty when approved.\n\n"
    "TASK ({task_type}): {instruction}\n\nOUTPUT:\n{output}"
)

_YES = frozenset({"true", "yes", "1", "approve", "approved"})
_NO = frozenset({"false", "no", "0", "reject", "rejected", "object", "objected", "block"})


class ReviewStatus(StrEnum):
    """What a second-opinion review concluded. Exactly one applies."""

    APPROVED = "approved"
    """The reviewer ran and found no blocking problem. May auto-land."""

    OBJECTED = "objected"
    """The reviewer ran and raised a concern. Goes to a person."""

    NOT_REVIEWED = "not_reviewed"
    """The review was on but produced no verdict. Goes to a person, never auto-lands."""

    SKIPPED = "skipped"
    """The review is off, or there was nothing to review. Lands as it did before."""


class ReviewVerdict:
    """Outcome of a second-opinion review.

    Build one with :meth:`approve`, :meth:`objected`, :meth:`not_reviewed` or
    :meth:`skipped`. The legacy keyword form ``ReviewVerdict(approved=…,
    ran=…)`` still works and maps ``ran=False, approved=True`` to
    ``SKIPPED`` and ``ran=False, approved=False`` to ``NOT_REVIEWED``.

    ``concern`` is the objection for ``OBJECTED`` and the reason the review
    did not happen for ``NOT_REVIEWED`` (and, optionally, ``SKIPPED``).
    """

    __slots__ = ("concern", "issues", "status")

    def __init__(
        self,
        approved: bool | None = None,
        concern: str | None = None,
        ran: bool = True,
        issues: list[dict[str, Any]] | None = None,
        *,
        status: ReviewStatus | str | None = None,
    ) -> None:
        if status is None:
            if approved is None:
                raise TypeError("ReviewVerdict needs status= or approved=")
            if ran:
                status = ReviewStatus.APPROVED if approved else ReviewStatus.OBJECTED
            else:
                status = ReviewStatus.SKIPPED if approved else ReviewStatus.NOT_REVIEWED
        self.status = ReviewStatus(status)
        self.concern = concern
        self.issues: list[dict[str, Any]] = list(issues or [])

    # ── constructors ──

    @classmethod
    def approve(cls) -> ReviewVerdict:
        return cls(status=ReviewStatus.APPROVED)

    @classmethod
    def objected(
        cls, concern: str | None, issues: list[dict[str, Any]] | None = None
    ) -> ReviewVerdict:
        return cls(status=ReviewStatus.OBJECTED, concern=concern, issues=issues)

    @classmethod
    def not_reviewed(cls, reason: str) -> ReviewVerdict:
        return cls(status=ReviewStatus.NOT_REVIEWED, concern=reason)

    @classmethod
    def skipped(cls, reason: str | None = None) -> ReviewVerdict:
        return cls(status=ReviewStatus.SKIPPED, concern=reason)

    # ── what callers act on ──

    @property
    def may_auto_land(self) -> bool:
        """True only for APPROVED and SKIPPED. Anything else waits for a person."""
        return self.status in (ReviewStatus.APPROVED, ReviewStatus.SKIPPED)

    @property
    def needs_human(self) -> bool:
        """True for OBJECTED and NOT_REVIEWED."""
        return not self.may_auto_land

    @property
    def reviewed(self) -> bool:
        """False for NOT_REVIEWED only: the review was due and did not happen."""
        return self.status is not ReviewStatus.NOT_REVIEWED

    # ── legacy view (kept for older callers; not a safe gate on its own) ──

    @property
    def approved(self) -> bool:
        return self.may_auto_land

    @property
    def ran(self) -> bool:
        """The reviewer produced a verdict (APPROVED or OBJECTED)."""
        return self.status in (ReviewStatus.APPROVED, ReviewStatus.OBJECTED)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ReviewVerdict):
            return NotImplemented
        return (self.status, self.concern, self.issues) == (
            other.status,
            other.concern,
            other.issues,
        )

    __hash__ = None  # type: ignore[assignment]  # mutable, like the dataclass it replaces

    def __repr__(self) -> str:
        return f"ReviewVerdict(status={self.status.value!r}, concern={self.concern!r})"


class SecondOpinionReviewer:
    """Cheap-model dissenting reviewer for verified driver output."""

    def __init__(self, *, llm=None, model: str | None = None, enabled: bool = True) -> None:
        self._llm = llm
        self._model = model
        self._enabled = enabled

    async def review(self, task_type: str, instruction: str, output: str | None) -> ReviewVerdict:
        """Review verified output. Fail-closed: no verdict means NOT_REVIEWED."""
        if not self._enabled:
            return ReviewVerdict.skipped("second opinion disabled")
        if not output:
            return ReviewVerdict.skipped("nothing to review")
        if self._llm is None:
            logger.warning("Second opinion is on but has no model — not reviewed")
            return ReviewVerdict.not_reviewed("no reviewer model configured")

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
        except Exception as exc:  # noqa: BLE001 - any failure = not reviewed
            logger.warning("Second-opinion LLM call failed — not reviewed", exc_info=True)
            name = type(exc).__name__
            return ReviewVerdict.not_reviewed(f"review call failed ({name}: {exc})"[:300])

        return self._parse(raw)

    @staticmethod
    def _parse(raw: str) -> ReviewVerdict:
        """Parse the reviewer JSON. Fail-closed: unreadable → NOT_REVIEWED."""
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Second-opinion returned non-JSON — not reviewed")
            return ReviewVerdict.not_reviewed("reviewer reply was not JSON")
        if not isinstance(data, dict):
            return ReviewVerdict.not_reviewed("reviewer reply was not a JSON object")
        if "approved" not in data:
            return ReviewVerdict.not_reviewed("reviewer reply had no 'approved' field")

        approved = data["approved"]
        if not isinstance(approved, bool):
            word = str(approved).strip().lower()
            if word in _YES:
                approved = True
            elif word in _NO:
                approved = False
            else:
                return ReviewVerdict.not_reviewed(
                    f"reviewer 'approved' was unreadable: {word[:50]!r}"
                )
        concern = data.get("concern") or None
        if approved:
            return ReviewVerdict.approve()
        return ReviewVerdict.objected(str(concern) if concern else None)
