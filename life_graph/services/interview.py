"""Interview engine — the system asks, the user answers.

Hard daily budget (default 3 questions), anti-nag (asked twice without an
answer → never asked again), 7-day TTL. Questions are drawn from four
origins in priority order:

1. ``outcome_resolution`` — predictions past their horizon with no automatic
   resolution (created by :class:`OutcomeResolver.check_expired_predictions`)
2. ``knowledge_gap``      — top unresolved rows from ``knowledge_gaps``
3. ``drift``              — stated intentions with no observed progress in 14 days
4. ``reflection``         — completed kernel tasks that overran their budget >2x

Operates on a caller-provided ``AsyncSession``; the caller commits.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from life_graph.core.events import EventBus, EventType
from life_graph.models.db import (
    AgentTask,
    Intention,
    InterviewQuestion,
    KnowledgeGap,
)
from life_graph.services.capture import CaptureService
from life_graph.services.outcome_resolver import OutcomeResolver

logger = logging.getLogger(__name__)

ORIGIN_ORDER = ["outcome_resolution", "knowledge_gap", "drift", "reflection"]
QUESTION_TTL_DAYS = 7
MAX_ASKS = 2  # asked this many times without an answer → skipped forever
DRIFT_WINDOW_DAYS = 14
OVERRUN_FACTOR = 2.0


class ExpiredQuestionError(Exception):
    """Raised when answering a question that has already expired."""


class InterviewService:
    """Question lifecycle: generate → ask (budgeted) → answer / skip / expire."""

    def __init__(self, session: AsyncSession, event_bus: EventBus | None = None):
        self.session = session
        self.event_bus = event_bus

    # ── Generation (called from the daily brief cron) ─────────

    async def generate_daily(
        self, tenant_id: str, max_questions: int = 3
    ) -> list[InterviewQuestion]:
        """Generate candidates from all origins and ask today's budget.

        Runs the expire sweep first, then creates new candidate questions,
        then promotes the top ``max_questions`` pending questions to
        ``asked`` (emitting ``INTERVIEW_ASKED`` for each).

        Args:
            tenant_id: Tenant scope.
            max_questions: Hard daily budget (never nag).

        Returns:
            The questions selected for today's brief.
        """
        await self.expire_sweep(tenant_id)

        resolver = OutcomeResolver(self.session, self.event_bus)
        await resolver.check_expired_predictions(tenant_id)

        existing_refs = await self._pending_origin_refs(tenant_id)
        await self._generate_gap_questions(tenant_id, existing_refs, limit=2)
        await self._generate_drift_questions(tenant_id, existing_refs, limit=2)
        await self._generate_reflection_questions(tenant_id, existing_refs, limit=1)

        return await self._ask_todays_batch(tenant_id, max_questions)

    async def _pending_origin_refs(self, tenant_id: str) -> set[str]:
        """Origin refs of open questions, to avoid duplicate candidates."""
        result = await self.session.execute(
            select(InterviewQuestion.origin_ref).where(
                InterviewQuestion.tenant_id == tenant_id,
                InterviewQuestion.status.in_(["pending", "asked"]),
            )
        )
        return {str(sorted(ref.items())) for (ref,) in result.all() if ref}

    def _new_question(
        self,
        tenant_id: str,
        question: str,
        origin: str,
        origin_ref: dict,
        priority: float,
    ) -> InterviewQuestion:
        q = InterviewQuestion(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            question=question,
            origin=origin,
            origin_ref=origin_ref,
            priority=priority,
            status="pending",
            expires_at=datetime.now(UTC) + timedelta(days=QUESTION_TTL_DAYS),
        )
        self.session.add(q)
        return q

    async def _generate_gap_questions(
        self, tenant_id: str, existing_refs: set[str], limit: int
    ) -> None:
        result = await self.session.execute(
            select(KnowledgeGap)
            .where(
                KnowledgeGap.tenant_id == tenant_id,
                KnowledgeGap.resolved.is_(False),
            )
            .order_by(KnowledgeGap.query_count.desc())
            .limit(limit * 3)
        )
        created = 0
        for gap in result.scalars():
            ref = {"gap_id": str(gap.id)}
            if str(sorted(ref.items())) in existing_refs:
                continue
            self._new_question(
                tenant_id,
                f"I've been asked about '{gap.topic}' {gap.query_count} time(s) "
                "but don't have a good answer. Can you fill me in?",
                origin="knowledge_gap",
                origin_ref=ref,
                priority=min(0.9, 0.4 + 0.1 * gap.query_count),
            )
            created += 1
            if created >= limit:
                break

    async def _generate_drift_questions(
        self, tenant_id: str, existing_refs: set[str], limit: int
    ) -> None:
        cutoff = datetime.now(UTC) - timedelta(days=DRIFT_WINDOW_DAYS)
        result = await self.session.execute(
            select(Intention)
            .where(
                Intention.tenant_id == tenant_id,
                Intention.status == "pending",
                Intention.created_at < cutoff,
            )
            .order_by(Intention.created_at.asc())
            .limit(limit * 3)
        )
        created = 0
        for intention in result.scalars():
            ref = {"intention_id": str(intention.id)}
            if str(sorted(ref.items())) in existing_refs:
                continue
            self._new_question(
                tenant_id,
                f"{DRIFT_WINDOW_DAYS}+ days ago you intended to: "
                f"'{intention.content[:160]}'. Is this still a goal, "
                "or should I let it go?",
                origin="drift",
                origin_ref=ref,
                priority=0.5,
            )
            created += 1
            if created >= limit:
                break

    async def _generate_reflection_questions(
        self, tenant_id: str, existing_refs: set[str], limit: int
    ) -> None:
        since = datetime.now(UTC) - timedelta(days=7)
        result = await self.session.execute(
            select(AgentTask)
            .where(
                AgentTask.tenant_id == tenant_id,
                AgentTask.status == "completed",
                AgentTask.completed_at >= since,
                AgentTask.started_at.is_not(None),
            )
            .order_by(AgentTask.completed_at.desc())
            .limit(20)
        )
        created = 0
        for task in result.scalars():
            if not task.completed_at or not task.started_at or not task.timeout_seconds:
                continue
            duration = (task.completed_at - task.started_at).total_seconds()
            if duration <= task.timeout_seconds * OVERRUN_FACTOR:
                continue
            ref = {"task_id": str(task.id)}
            if str(sorted(ref.items())) in existing_refs:
                continue
            name = task.title or task.task_name or "a recent task"
            self._new_question(
                tenant_id,
                f"'{name}' took {duration / 60:.0f} min against a "
                f"{task.timeout_seconds / 60:.0f} min budget. "
                "What did the estimate miss?",
                origin="reflection",
                origin_ref=ref,
                priority=0.4,
            )
            created += 1
            if created >= limit:
                break

    async def _ask_todays_batch(
        self, tenant_id: str, max_questions: int
    ) -> list[InterviewQuestion]:
        """Promote the top pending questions to ``asked`` within budget.

        Questions already asked ``MAX_ASKS`` times are retired (anti-nag)
        and their origin's remaining pending questions get halved priority.
        """
        await self.session.flush()
        result = await self.session.execute(
            select(InterviewQuestion).where(
                InterviewQuestion.tenant_id == tenant_id,
                InterviewQuestion.status.in_(["pending", "asked"]),
            )
        )
        open_questions = list(result.scalars())

        # Anti-nag: retire over-asked questions before selection
        retired_origins: set[str] = set()
        candidates: list[InterviewQuestion] = []
        for q in open_questions:
            if q.asked_count >= MAX_ASKS:
                q.status = "skipped"
                retired_origins.add(q.origin)
            else:
                candidates.append(q)
        for q in candidates:
            if q.origin in retired_origins:
                q.priority = q.priority / 2

        candidates.sort(
            key=lambda q: (
                ORIGIN_ORDER.index(q.origin) if q.origin in ORIGIN_ORDER else 99,
                -q.priority,
            )
        )
        batch = candidates[:max_questions]
        for q in batch:
            q.status = "asked"
            q.asked_count += 1
            if self.event_bus:
                await self.event_bus.emit(
                    EventType.INTERVIEW_ASKED,
                    {
                        "question_id": str(q.id),
                        "tenant_id": tenant_id,
                        "origin": q.origin,
                        "asked_count": q.asked_count,
                    },
                )
        return batch

    # ── Answer / Skip ─────────────────────────────────────────

    async def answer(
        self, tenant_id: str, question_id: uuid.UUID, answer: str
    ) -> InterviewQuestion:
        """Record an answer, route it through the capture spine and back
        to the question's origin (gap resolved, prediction resolved,
        reflection stored). Emits ``INTERVIEW_ANSWERED``.

        Raises:
            LookupError: Unknown question.
            ExpiredQuestionError: Question already expired — the caller
                should still capture the answer as a plain memory (this
                method does that before raising).
        """
        q = await self._get(tenant_id, question_id)
        capture_svc = CaptureService(self.session, self.event_bus)
        capture = await capture_svc.ingest(
            tenant_id=tenant_id,
            surface="interview_answer",
            content=answer,
            properties={
                "question_id": str(question_id),
                "origin": q.origin,
                "origin_ref": q.origin_ref,
            },
        )

        if q.status == "expired":
            # Persist the capture despite the error — the API layer's
            # rollback-on-exception must not lose the user's answer.
            await self.session.commit()
            raise ExpiredQuestionError(
                f"Question {question_id} expired; answer captured anyway"
            )

        q.answer = answer
        q.answer_capture_id = capture.id
        q.status = "answered"
        await self._route_to_origin(tenant_id, q, answer)

        if self.event_bus:
            await self.event_bus.emit(
                EventType.INTERVIEW_ANSWERED,
                {
                    "question_id": str(q.id),
                    "tenant_id": tenant_id,
                    "origin": q.origin,
                },
            )
        return q

    async def skip(self, tenant_id: str, question_id: uuid.UUID) -> InterviewQuestion:
        """Skip a question and halve the ask-priority of its origin's
        other open questions — the system must never nag."""
        q = await self._get(tenant_id, question_id)
        q.status = "skipped"

        result = await self.session.execute(
            select(InterviewQuestion).where(
                InterviewQuestion.tenant_id == tenant_id,
                InterviewQuestion.origin == q.origin,
                InterviewQuestion.status.in_(["pending", "asked"]),
            )
        )
        for other in result.scalars():
            other.priority = other.priority / 2
        return q

    # ── Queries ───────────────────────────────────────────────

    async def list_pending(self, tenant_id: str) -> list[InterviewQuestion]:
        """Open questions, highest priority first (rendered by brief/CLI/bot)."""
        result = await self.session.execute(
            select(InterviewQuestion)
            .where(
                InterviewQuestion.tenant_id == tenant_id,
                InterviewQuestion.status.in_(["pending", "asked"]),
            )
            .order_by(InterviewQuestion.priority.desc())
        )
        return list(result.scalars())

    # ── Expiry ────────────────────────────────────────────────

    async def expire_sweep(self, tenant_id: str) -> int:
        """Expire open questions past their TTL.

        For ``outcome_resolution`` questions, the underlying prediction is
        resolved as ``ambiguous`` rather than staying open forever.
        """
        now = datetime.now(UTC)
        result = await self.session.execute(
            select(InterviewQuestion).where(
                InterviewQuestion.tenant_id == tenant_id,
                InterviewQuestion.status.in_(["pending", "asked"]),
                InterviewQuestion.expires_at.is_not(None),
                InterviewQuestion.expires_at < now,
            )
        )
        expired = list(result.scalars())
        resolver = OutcomeResolver(self.session, self.event_bus)
        for q in expired:
            q.status = "expired"
            prediction_id = (q.origin_ref or {}).get("prediction_id")
            if q.origin == "outcome_resolution" and prediction_id:
                try:
                    await resolver.resolve_prediction(
                        tenant_id,
                        uuid.UUID(prediction_id),
                        outcome="ambiguous",
                        source="interview_expired",
                        evidence={"question_id": str(q.id)},
                    )
                except Exception:
                    logger.exception(
                        "Could not ambiguous-resolve prediction %s", prediction_id
                    )
        if expired:
            logger.info("Expired %d interview questions for %s", len(expired), tenant_id)
        return len(expired)

    # ── Internals ─────────────────────────────────────────────

    async def _get(
        self, tenant_id: str, question_id: uuid.UUID
    ) -> InterviewQuestion:
        result = await self.session.execute(
            select(InterviewQuestion).where(
                InterviewQuestion.tenant_id == tenant_id,
                InterviewQuestion.id == question_id,
            )
        )
        q = result.scalars().first()
        if q is None:
            raise LookupError(f"Interview question {question_id} not found")
        return q

    async def _route_to_origin(
        self, tenant_id: str, q: InterviewQuestion, answer: str
    ) -> None:
        """Update the origin the question came from."""
        ref = q.origin_ref or {}
        if q.origin == "outcome_resolution" and ref.get("prediction_id"):
            resolver = OutcomeResolver(self.session, self.event_bus)
            await resolver.resolve_prediction(
                tenant_id,
                uuid.UUID(ref["prediction_id"]),
                outcome=self._infer_outcome(answer),
                source="interview",
                evidence={"answer": answer, "question_id": str(q.id)},
            )
        elif q.origin == "knowledge_gap" and ref.get("gap_id"):
            result = await self.session.execute(
                select(KnowledgeGap).where(
                    KnowledgeGap.tenant_id == tenant_id,
                    KnowledgeGap.id == uuid.UUID(ref["gap_id"]),
                )
            )
            if gap := result.scalars().first():
                gap.resolved = True
        # drift / reflection answers are captured as memories via the spine;
        # no origin mutation needed.

    @staticmethod
    def _infer_outcome(answer: str) -> str:
        """Map a free-text answer to a prediction outcome."""
        lowered = answer.strip().lower()
        positive = ("yes", "correct", "true", "it did", "happened", "done")
        negative = ("no", "incorrect", "false", "didn't", "did not", "wrong", "failed")
        if lowered.startswith(positive):
            return "correct"
        if lowered.startswith(negative):
            return "incorrect"
        return "ambiguous"
