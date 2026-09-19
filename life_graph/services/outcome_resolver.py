"""Outcome Resolver — resolves predictions via multiple strategies.

4 resolver kinds:
1. kernel_based — checks kernel task outcomes (completed/failed)
2. git_based — checks git merge/revert status
3. metric_based — checks watcher data / metrics
4. interview — escalates to user via interview question

Rules:
- Never auto-resolve on absence of evidence → create interview question
- Immutable resolutions (corrections create history, never overwrite)

Follows the CaptureService pattern: operates on a caller-provided
``AsyncSession`` and emits events via ``EventBus``.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select

from life_graph.core.events import EventBus, EventType
from life_graph.models.db import InterviewQuestion, Prediction

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Matches interview.QUESTION_TTL_DAYS (not imported: interview imports this module).
QUESTION_TTL_DAYS = 7

# Valid outcome values for resolution
_VALID_OUTCOMES = frozenset({"correct", "incorrect", "ambiguous"})


class OutcomeResolver:
    """Resolves predictions by checking sources and escalating to interviews.

    Operates on a caller-provided ``AsyncSession`` — the API layer
    is responsible for committing the transaction after the service
    method returns.
    """

    def __init__(self, session: AsyncSession, event_bus: EventBus | None = None) -> None:
        self.session = session
        self.event_bus = event_bus

    # ── Public API ────────────────────────────────────────────

    async def resolve_prediction(
        self,
        tenant_id: str,
        prediction_id: uuid.UUID,
        outcome: str,
        source: str,
        evidence: dict | None = None,
    ) -> Prediction:
        """Resolve a prediction with an outcome and evidence.

        Sets the prediction outcome, records the resolution source and
        evidence, and emits a PREDICTION_RESOLVED event. Never overwrites
        an already-resolved prediction.

        Args:
            tenant_id: Tenant scope.
            prediction_id: The prediction UUID to resolve.
            outcome: Resolution result (correct, incorrect, ambiguous).
            source: Where the resolution came from (manual, kernel, git, etc.).
            evidence: Supporting evidence dict.

        Returns:
            The resolved ``Prediction``.

        Raises:
            ValueError: If prediction not found, already resolved, or
                outcome is invalid.
        """
        if outcome not in _VALID_OUTCOMES:
            raise ValueError(
                f"Invalid outcome '{outcome}'. Must be one of: {', '.join(sorted(_VALID_OUTCOMES))}"
            )

        result = await self.session.execute(
            select(Prediction).where(
                Prediction.tenant_id == tenant_id,
                Prediction.id == prediction_id,
            )
        )
        prediction = result.scalars().first()

        if not prediction:
            raise ValueError("Prediction not found")

        if prediction.outcome == "suggested":
            raise ValueError("Prediction is still a suggestion; accept it before resolving it.")
        if prediction.outcome != "pending":
            raise ValueError(
                f"Prediction already resolved as '{prediction.outcome}'. "
                "Resolutions are immutable — create a correction instead."
            )

        # Apply resolution
        now = datetime.now(UTC)
        prediction.outcome = outcome
        prediction.resolved_at = now
        prediction.resolution_source = source
        prediction.resolution_evidence = evidence or {}
        prediction.actual_vs_predicted = 1.0 if outcome == "correct" else 0.0

        if self.event_bus:
            await self.event_bus.emit(
                EventType.PREDICTION_RESOLVED,
                {
                    "prediction_id": str(prediction.id),
                    "tenant_id": tenant_id,
                    "outcome": outcome,
                    "source": source,
                    "confidence": prediction.confidence,
                    "actual_vs_predicted": prediction.actual_vs_predicted,
                },
            )

        logger.info(
            "Resolved prediction %s as %s (source=%s)",
            prediction_id,
            outcome,
            source,
        )
        return prediction

    async def check_expired_predictions(self, tenant_id: str) -> list[InterviewQuestion]:
        """Find predictions past their resolve_by date and escalate.

        Queries for predictions that are still pending but past their
        deadline, and creates interview questions to ask the user for
        resolution. Each prediction is asked about once: this runs daily,
        and without the check every unanswered prediction gained another
        identical question each morning. An unanswered question expires
        after QUESTION_TTL_DAYS and resolves the prediction ``ambiguous``
        (``InterviewService.expire_sweep``); a skipped one leaves it pending,
        still resolvable from the Calibration page.

        Args:
            tenant_id: Tenant scope.

        Returns:
            List of created ``InterviewQuestion`` rows.
        """
        now = datetime.now(UTC)
        result = await self.session.execute(
            select(Prediction).where(
                Prediction.tenant_id == tenant_id,
                Prediction.outcome == "pending",
                Prediction.resolve_by <= now,
            )
        )
        expired = list(result.scalars().all())
        if expired:
            asked = await self.session.execute(
                select(InterviewQuestion.origin_ref).where(
                    InterviewQuestion.tenant_id == tenant_id,
                    InterviewQuestion.origin == "outcome_resolution",
                )
            )
            already_asked = {(ref or {}).get("prediction_id") for (ref,) in asked.all()}
            expired = [p for p in expired if str(p.id) not in already_asked]

        questions: list[InterviewQuestion] = []
        for prediction in expired:
            question = await self._escalate_to_interview(tenant_id, prediction)
            questions.append(question)

        if expired:
            logger.info(
                "Escalated %d expired predictions to interview for tenant %s",
                len(expired),
                tenant_id,
            )

        return questions

    # ── Internal ──────────────────────────────────────────────

    @staticmethod
    async def _connector_hints(tenant_id: str, prediction: Prediction) -> list[str]:
        """Mail/events that may bear on the prediction — shown, never acted on.

        Cloud-rendered (the question can reach the brief and Telegram), and a
        connector problem never blocks the question.
        """
        from life_graph.config import settings

        if not settings.connectors_enabled:
            return []
        try:
            from life_graph.connectors.assist import prediction_hints

            since = prediction.created_at or (datetime.now(UTC) - timedelta(days=30))
            return await prediction_hints(tenant_id, prediction.statement, since)
        except Exception:
            logger.debug("Connector hints failed for %s", prediction.id, exc_info=True)
            return []

    async def _escalate_to_interview(
        self, tenant_id: str, prediction: Prediction
    ) -> InterviewQuestion:
        """Create an interview question for an unresolved prediction.

        Args:
            tenant_id: Tenant scope.
            prediction: The expired prediction to escalate.

        Returns:
            The created ``InterviewQuestion``.
        """
        hints = await self._connector_hints(tenant_id, prediction)
        text = (
            f"Prediction expired: '{prediction.statement}' "
            f"(confidence: {prediction.confidence:.0%}). "
            f"Did this come true?"
        )
        if hints:
            text += " Possibly related: " + "; ".join(hints) + "."
        question = InterviewQuestion(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            question=text,
            origin="outcome_resolution",
            origin_ref={
                "prediction_id": str(prediction.id),
                "statement": prediction.statement,
                "confidence": prediction.confidence,
                **({"evidence_hints": hints} if hints else {}),
            },
            priority=0.7,
            # Without an expiry the question stayed open forever and the
            # spec's "unanswered for 7 days → ambiguous" never happened.
            expires_at=datetime.now(UTC) + timedelta(days=QUESTION_TTL_DAYS),
        )
        self.session.add(question)
        await self.session.flush()

        logger.debug(
            "Created interview question %s for prediction %s",
            question.id,
            prediction.id,
        )
        return question
