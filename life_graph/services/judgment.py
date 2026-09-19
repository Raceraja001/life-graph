"""Judgment Engine — decision tracking, prediction calibration, and candidate listener.

Manages the lifecycle of decisions and predictions. Subscribes to
DECISION_CANDIDATE events from the Capture Spine to auto-create
candidate decisions.

Follows the CaptureService pattern: operates on a caller-provided
``AsyncSession`` and emits events via ``EventBus``.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from life_graph.core.events import Event, EventBus, EventType, event_bus
from life_graph.models.db import Decision, Prediction
from life_graph.storage.database import async_session

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Outcome of a prediction detected in a capture but not yet confirmed.
SUGGESTED = "suggested"

# ── Big-decision detection ─────────────────────────────────────────
# High-importance signals (judgment-engine spec Story 6): money,
# commitments longer than ~2 weeks, and irreversibility keywords. A
# candidate matching any category is "big" and earns a one-time challenge
# suggestion in the daily brief — small decisions are never challenged.
BIG_DECISION_TAG = "big_decision"
BIG_DECISION_IMPORTANCE = 0.85

_BIG_DECISION_SIGNALS: list[tuple[str, re.Pattern[str]]] = [
    (
        "money",
        re.compile(
            r"(?i)(\$\s*\d|₹\s*\d|\b\d+\s*(?:k|lakh|crore|dollars?|usd|rupees?)\b"
            r"|\b(?:budget|invest(?:ment)?|funding|salary|raise|mortgage|loan|"
            r"revenue|price|pay)\b)"
        ),
    ),
    (
        "commitment",
        re.compile(
            r"(?i)(\b\d+\s*(?:months?|years?|quarters?)\b|\b(?:months?|years?|"
            r"quarter|long[- ]term|lease|contract|full[- ]time|permanent(?:ly)?)\b)"
        ),
    ),
    (
        "irreversible",
        re.compile(
            r"(?i)\b(irreversible|can'?t\s+undo|no\s+going\s+back|quit|resign|"
            r"hire|fire|lay\s*off|sell|buy\s+a|relocat|move\s+to|shut\s+down|"
            r"delete|migrat|rewrite|rebuild|marriage|marry|divorce)\b"
        ),
    ),
]


def detect_big_decision(title: str | None, reasoning: str | None = None) -> tuple[bool, list[str]]:
    """Heuristically decide whether a decision is "big".

    Args:
        title: Decision title / statement.
        reasoning: Optional reasoning text (also scanned).

    Returns:
        ``(is_big, matched_signal_categories)``.
    """
    text = " ".join(p for p in (title, reasoning) if p).strip()
    if not text:
        return False, []
    matched = [name for name, pat in _BIG_DECISION_SIGNALS if pat.search(text)]
    return bool(matched), matched


class JudgmentService:
    """Core service for decisions and predictions.

    Operates on a caller-provided ``AsyncSession`` — the API layer
    is responsible for committing the transaction after the service
    method returns.
    """

    def __init__(self, session: AsyncSession, event_bus: EventBus | None = None) -> None:
        self.session = session
        self.event_bus = event_bus

    # ── Decisions ─────────────────────────────────────────────

    async def create_decision(
        self,
        tenant_id: str,
        title: str,
        reasoning: str | None = None,
        options: list[dict] | None = None,
        chosen_option: str | None = None,
        status: str = "decided",
        source: str = "explicit",
        domain_tags: list[str] | None = None,
        importance: float = 0.5,
        capture_event_id: uuid.UUID | None = None,
        review_at: datetime | None = None,
    ) -> Decision:
        """Create a tracked decision and emit DECISION_RECORDED.

        Args:
            tenant_id: Tenant scope.
            title: Decision title.
            reasoning: Why this decision was made.
            options: List of option dicts [{label, pros, cons}].
            chosen_option: The selected option label.
            status: Initial status (candidate or decided).
            source: Origin (conversation, explicit, challenge).
            domain_tags: Tags for the decision domain.
            importance: Importance score [0, 1].
            capture_event_id: Optional link to originating capture event.
            review_at: When to schedule a review.

        Returns:
            The persisted ``Decision``.
        """
        now = datetime.now(UTC)
        decision = Decision(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            title=title,
            reasoning=reasoning,
            options=options or [],
            chosen_option=chosen_option,
            status=status,
            source=source,
            domain_tags=domain_tags or [],
            importance=importance,
            capture_event_id=capture_event_id,
            review_at=review_at,
            decided_at=now if status == "decided" else None,
        )
        self.session.add(decision)
        await self.session.flush()

        if self.event_bus:
            await self.event_bus.emit(
                EventType.DECISION_RECORDED,
                {
                    "decision_id": str(decision.id),
                    "tenant_id": tenant_id,
                    "title": title,
                    "status": status,
                    "source": source,
                },
            )
        return decision

    async def list_decisions(
        self,
        tenant_id: str,
        domain: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[Decision]:
        """List decisions with optional domain and status filters.

        Args:
            tenant_id: Tenant scope.
            domain: Filter by domain tag (any match).
            status: Filter by status value.
            limit: Maximum rows to return.

        Returns:
            List of ``Decision`` rows, newest first.
        """
        stmt = (
            select(Decision)
            .where(Decision.tenant_id == tenant_id)
            .order_by(Decision.created_at.desc())
            .limit(limit)
        )
        if status:
            stmt = stmt.where(Decision.status == status)
        if domain:
            stmt = stmt.where(Decision.domain_tags.any(domain))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_decision(
        self,
        tenant_id: str,
        decision_id: uuid.UUID,
    ) -> Decision | None:
        """Get a single decision by ID, scoped to tenant.

        Args:
            tenant_id: Tenant scope.
            decision_id: The decision UUID.

        Returns:
            The ``Decision`` if found, else ``None``.
        """
        result = await self.session.execute(
            select(Decision).where(
                Decision.tenant_id == tenant_id,
                Decision.id == decision_id,
            )
        )
        return result.scalars().first()

    async def supersede_decision(
        self,
        tenant_id: str,
        old_id: uuid.UUID,
        new_id: uuid.UUID,
    ) -> None:
        """Mark old decision as superseded by a new one.

        Args:
            tenant_id: Tenant scope.
            old_id: The decision being superseded.
            new_id: The replacement decision.
        """
        result = await self.session.execute(
            select(Decision).where(
                Decision.tenant_id == tenant_id,
                Decision.id == old_id,
            )
        )
        old = result.scalars().first()
        if old:
            old.status = "superseded"
            old.superseded_by = new_id

            if self.event_bus:
                await self.event_bus.emit(
                    EventType.DECISION_SUPERSEDED,
                    {
                        "old_decision_id": str(old_id),
                        "new_decision_id": str(new_id),
                        "tenant_id": tenant_id,
                    },
                )

    # ── Predictions ───────────────────────────────────────────

    async def create_prediction(
        self,
        tenant_id: str,
        statement: str,
        confidence: float,
        decision_id: uuid.UUID | None = None,
        domain_tags: list[str] | None = None,
        resolve_by: datetime | None = None,
        resolution_criteria: dict | None = None,
        capture_event_id: uuid.UUID | None = None,
        suggested: bool = False,
    ) -> Prediction:
        """Create a prediction with confidence normalization.

        If confidence < 0.5, the statement is negated and confidence
        becomes 1 - original (e.g., 30% → 70% of "NOT: <statement>").

        ``suggested=True`` stores it with outcome ``suggested``: detected in a
        capture, not yet confirmed by the user. Suggestions are invisible to
        calibration, expiry and default listings until ``accept_suggestion``.

        Args:
            tenant_id: Tenant scope.
            statement: The prediction statement.
            confidence: Raw confidence [0, 1].
            decision_id: Optional linked decision.
            domain_tags: Tags for the prediction domain.
            resolve_by: When to resolve by.
            resolution_criteria: Criteria for resolution.
            capture_event_id: Optional link to capture event.

        Returns:
            The persisted ``Prediction``.
        """
        # Normalize confidence: if < 0.5, negate statement and flip
        if confidence < 0.5:
            statement = f"NOT: {statement}"
            confidence = 1.0 - confidence

        # Clamp to [0.5, 0.99]
        confidence = max(0.5, min(0.99, confidence))

        prediction = Prediction(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            decision_id=decision_id,
            statement=statement,
            confidence=confidence,
            domain_tags=domain_tags or [],
            resolve_by=resolve_by,
            resolution_criteria=resolution_criteria or {},
            capture_event_id=capture_event_id,
            outcome=SUGGESTED if suggested else "pending",
        )
        self.session.add(prediction)
        await self.session.flush()

        if not suggested:
            await self._emit_created(prediction)
        return prediction

    async def accept_suggestion(
        self,
        tenant_id: str,
        prediction_id: uuid.UUID,
        *,
        statement: str | None = None,
        confidence: float | None = None,
        resolve_by: datetime | None = None,
        domain_tags: list[str] | None = None,
    ) -> Prediction:
        """Confirm a suggested prediction, optionally correcting it first.

        Raises:
            ValueError: If not found or not a suggestion.
        """
        prediction = await self._get_prediction(tenant_id, prediction_id)
        if prediction.outcome != SUGGESTED:
            raise ValueError(f"Prediction is '{prediction.outcome}', not a suggestion")
        if statement:
            prediction.statement = statement
        if confidence is not None:
            prediction.confidence = max(0.5, min(0.99, confidence))
        if resolve_by is not None:
            prediction.resolve_by = resolve_by
        if domain_tags is not None:
            prediction.domain_tags = domain_tags
        prediction.outcome = "pending"
        await self.session.flush()
        await self._emit_created(prediction)
        return prediction

    async def dismiss_suggestion(self, tenant_id: str, prediction_id: uuid.UUID) -> None:
        """Delete a suggested prediction. Real predictions are never deleted here.

        Raises:
            ValueError: If not found or not a suggestion.
        """
        prediction = await self._get_prediction(tenant_id, prediction_id)
        if prediction.outcome != SUGGESTED:
            raise ValueError(f"Prediction is '{prediction.outcome}', not a suggestion")
        await self.session.delete(prediction)
        await self.session.flush()

    async def has_open_prediction(self, tenant_id: str, statement: str) -> bool:
        """Whether a suggested or pending prediction with this statement exists."""
        result = await self.session.execute(
            select(Prediction.id)
            .where(
                Prediction.tenant_id == tenant_id,
                Prediction.outcome.in_([SUGGESTED, "pending"]),
                func.lower(Prediction.statement) == statement.lower(),
            )
            .limit(1)
        )
        return result.first() is not None

    async def _get_prediction(self, tenant_id: str, prediction_id: uuid.UUID) -> Prediction:
        result = await self.session.execute(
            select(Prediction).where(
                Prediction.tenant_id == tenant_id,
                Prediction.id == prediction_id,
            )
        )
        prediction = result.scalars().first()
        if prediction is None:
            raise ValueError("Prediction not found")
        return prediction

    async def _emit_created(self, prediction: Prediction) -> None:
        if self.event_bus:
            await self.event_bus.emit(
                EventType.PREDICTION_CREATED,
                {
                    "prediction_id": str(prediction.id),
                    "tenant_id": prediction.tenant_id,
                    "statement": prediction.statement,
                    "confidence": prediction.confidence,
                    "decision_id": (
                        str(prediction.decision_id) if prediction.decision_id else None
                    ),
                },
            )

    async def list_predictions(
        self,
        tenant_id: str,
        status: str | None = None,
        due_before: datetime | None = None,
        limit: int = 50,
    ) -> list[Prediction]:
        """List predictions with optional status and deadline filters.

        Args:
            tenant_id: Tenant scope.
            status: Filter by outcome status (pending, correct, etc.).
                Suggestions are listed only when asked for by name.
            due_before: Only predictions due before this date.
            limit: Maximum rows to return.

        Returns:
            List of ``Prediction`` rows, newest first.
        """
        stmt = (
            select(Prediction)
            .where(Prediction.tenant_id == tenant_id)
            .order_by(Prediction.created_at.desc())
            .limit(limit)
        )
        if status:
            stmt = stmt.where(Prediction.outcome == status)
        else:
            stmt = stmt.where(Prediction.outcome != SUGGESTED)
        if due_before:
            stmt = stmt.where(Prediction.resolve_by <= due_before)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_predictions_for_decision(
        self,
        tenant_id: str,
        decision_id: uuid.UUID,
    ) -> list[Prediction]:
        """Get all predictions linked to a specific decision.

        Args:
            tenant_id: Tenant scope.
            decision_id: The decision UUID.

        Returns:
            List of ``Prediction`` rows for that decision.
        """
        result = await self.session.execute(
            select(Prediction)
            .where(
                Prediction.tenant_id == tenant_id,
                Prediction.decision_id == decision_id,
            )
            .order_by(Prediction.created_at.desc())
        )
        return list(result.scalars().all())


# ── DECISION_CANDIDATE subscriber (module-level singleton) ──────────


class _DecisionCandidateListener:
    """Subscribes to DECISION_CANDIDATE from Capture Spine.

    Auto-creates candidate decisions when the capture processors
    detect decision-like statements in captured text.
    """

    def __init__(self, bus: EventBus | None = None) -> None:
        self._bus = bus or event_bus
        self._subscribed = False

    def subscribe(self) -> None:
        """Register as a DECISION_CANDIDATE handler. Idempotent."""
        if self._subscribed:
            return
        self._bus.subscribe(EventType.DECISION_CANDIDATE, self._on_decision_candidate)
        self._subscribed = True
        logger.info("JudgmentService subscribed to DECISION_CANDIDATE")

    def unsubscribe(self) -> None:
        """Remove subscription."""
        if not self._subscribed:
            return
        self._bus.unsubscribe(EventType.DECISION_CANDIDATE, self._on_decision_candidate)
        self._subscribed = False

    async def _on_decision_candidate(self, event: Event) -> None:
        """Handle DECISION_CANDIDATE — auto-create a candidate decision."""
        payload = event.payload
        tenant_id = payload.get("tenant_id")
        title = payload.get("title", "")
        reasoning = payload.get("reasoning")
        source = payload.get("source", "conversation")
        capture_event_id = payload.get("capture_event_id")

        if not tenant_id or not title:
            logger.warning("DECISION_CANDIDATE missing tenant_id or title: %s", payload)
            return

        is_big, signals = detect_big_decision(title, reasoning)

        try:
            async with async_session() as session:
                svc = JudgmentService(session, self._bus)
                await svc.create_decision(
                    tenant_id=tenant_id,
                    title=title,
                    reasoning=reasoning,
                    status="candidate",
                    source=source,
                    domain_tags=[BIG_DECISION_TAG] if is_big else None,
                    importance=BIG_DECISION_IMPORTANCE if is_big else 0.5,
                    capture_event_id=(uuid.UUID(capture_event_id) if capture_event_id else None),
                )
                await session.commit()
                logger.info(
                    "Auto-created %scandidate decision: %s",
                    "BIG " if is_big else "",
                    title[:80],
                )
        except Exception:
            logger.error(
                "Failed to auto-create decision from DECISION_CANDIDATE",
                exc_info=True,
            )


# Module-level singleton
judgment_service = _DecisionCandidateListener()
