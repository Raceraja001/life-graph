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
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from life_graph.core.events import EventBus, EventType
from life_graph.models.db import InterviewQuestion, Prediction

logger = logging.getLogger(__name__)

# Valid outcome values for resolution
_VALID_OUTCOMES = frozenset({"correct", "incorrect", "ambiguous"})


class OutcomeResolver:
    """Resolves predictions by checking sources and escalating to interviews.

    Operates on a caller-provided ``AsyncSession`` — the API layer
    is responsible for committing the transaction after the service
    method returns.
    """

    def __init__(
        self, session: AsyncSession, event_bus: EventBus | None = None
    ) -> None:
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
                f"Invalid outcome '{outcome}'. "
                f"Must be one of: {', '.join(sorted(_VALID_OUTCOMES))}"
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

        if prediction.outcome != "pending":
            raise ValueError(
                f"Prediction already resolved as '{prediction.outcome}'. "
                "Resolutions are immutable — create a correction instead."
            )

        # Apply resolution
        now = datetime.now(timezone.utc)
        prediction.outcome = outcome
        prediction.resolved_at = now
        prediction.resolution_source = source
        prediction.resolution_evidence = evidence or {}
        prediction.actual_vs_predicted = (
            1.0 if outcome == "correct" else 0.0
        )

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

    async def check_expired_predictions(
        self, tenant_id: str
    ) -> list[InterviewQuestion]:
        """Find predictions past their resolve_by date and escalate.

        Queries for predictions that are still pending but past their
        deadline, and creates interview questions to ask the user for
        resolution.

        Args:
            tenant_id: Tenant scope.

        Returns:
            List of created ``InterviewQuestion`` rows.
        """
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(Prediction).where(
                Prediction.tenant_id == tenant_id,
                Prediction.outcome == "pending",
                Prediction.resolve_by <= now,
            )
        )
        expired = list(result.scalars().all())

        questions: list[InterviewQuestion] = []
        for prediction in expired:
            question = await self._escalate_to_interview(
                tenant_id, prediction
            )
            questions.append(question)

        if expired:
            logger.info(
                "Escalated %d expired predictions to interview for "
                "tenant %s",
                len(expired),
                tenant_id,
            )

        return questions

    # ── Internal ──────────────────────────────────────────────

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
        question = InterviewQuestion(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            question=(
                f"Prediction expired: '{prediction.statement}' "
                f"(confidence: {prediction.confidence:.0%}). "
                f"Did this come true?"
            ),
            origin="outcome_resolution",
            origin_ref={
                "prediction_id": str(prediction.id),
                "statement": prediction.statement,
                "confidence": prediction.confidence,
            },
            priority=0.7,
        )
        self.session.add(question)
        await self.session.flush()

        logger.debug(
            "Created interview question %s for prediction %s",
            question.id,
            prediction.id,
        )
        return question
