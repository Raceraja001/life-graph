"""Judgment Engine API routes.

Decision tracking, prediction calibration, and adversarial advisor.
Manages the full lifecycle of decisions and predictions.

Prefix: /judgment
Tags: [judgment-engine]
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from life_graph.api.responses import success_response
from life_graph.core.events import event_bus
from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.schemas import (
    ChallengeRequest,
    ChallengeResolveRequest,
    ChallengeResponse,
    DecisionCreate,
    DecisionResponse,
    JudgmentStatsResponse,
    PredictionAcceptRequest,
    PredictionCreate,
    PredictionResolveRequest,
    PredictionResponse,
)
from life_graph.services.judgment import JudgmentService
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/judgment", tags=["judgment-engine"])


# ── Dependencies ──────────────────────────────────────────────


async def _get_judgment_service() -> AsyncGenerator[JudgmentService, None]:
    """Yield a JudgmentService bound to a request-scoped session.

    Commits on successful completion; rolls back automatically on error
    via the ``async_session`` context manager.
    """
    async with async_session() as session:
        svc = JudgmentService(session, event_bus)
        yield svc
        await session.commit()


async def _get_outcome_resolver() -> AsyncGenerator:
    """Yield an OutcomeResolver bound to a request-scoped session.

    Commits on successful completion; rolls back automatically on error
    via the ``async_session`` context manager.
    """
    from life_graph.services.outcome_resolver import OutcomeResolver

    async with async_session() as session:
        svc = OutcomeResolver(session, event_bus)
        yield svc
        await session.commit()


async def _get_adversarial_advisor() -> AsyncGenerator:
    """Yield an AdversarialAdvisor bound to a request-scoped session.

    Commits on successful completion; rolls back automatically on error
    via the ``async_session`` context manager.
    """
    from life_graph.services.adversarial_advisor import AdversarialAdvisor

    async with async_session() as session:
        svc = AdversarialAdvisor(session, event_bus)
        yield svc
        await session.commit()


# ── Decision Routes ──────────────────────────────────────────


@router.post(
    "/decisions",
    status_code=status.HTTP_201_CREATED,
    summary="Create a decision",
)
async def create_decision(
    body: DecisionCreate,
    svc: JudgmentService = Depends(_get_judgment_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Create a tracked decision (explicit or candidate).

    Records the decision with options, reasoning, and domain tags.
    Emits a DECISION_RECORDED event for downstream consumers.
    """
    decision = await svc.create_decision(
        tenant_id=tenant_id,
        title=body.title,
        reasoning=body.reasoning,
        options=body.options,
        chosen_option=body.chosen_option,
        status=body.status,
        source=body.source,
        domain_tags=body.domain_tags,
        importance=body.importance,
        capture_event_id=body.capture_event_id,
        review_at=body.review_at,
    )
    return success_response(data=DecisionResponse.model_validate(decision))


@router.get(
    "/decisions",
    summary="List decisions",
)
async def list_decisions(
    svc: JudgmentService = Depends(_get_judgment_service),
    tenant_id: str = Depends(get_current_tenant_id),
    domain: str | None = Query(None, description="Filter by domain tag"),
    decision_status: str | None = Query(None, alias="status", description="Filter by status"),
    limit: int = Query(50, ge=1, le=200, description="Max results to return"),
):
    """List decisions for the current tenant.

    Supports filtering by domain tag and status. Returns newest first.
    """
    decisions = await svc.list_decisions(
        tenant_id=tenant_id,
        domain=domain,
        status=decision_status,
        limit=limit,
    )
    return success_response(
        data=[DecisionResponse.model_validate(d) for d in decisions],
    )


@router.get(
    "/decisions/{decision_id}",
    summary="Get decision with predictions",
)
async def get_decision(
    decision_id: UUID,
    svc: JudgmentService = Depends(_get_judgment_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Get a single decision by ID with its linked predictions inline.

    Returns the full decision dossier including all associated predictions.
    """
    decision = await svc.get_decision(tenant_id=tenant_id, decision_id=decision_id)
    if not decision:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Decision not found")

    predictions = await svc.get_predictions_for_decision(
        tenant_id=tenant_id, decision_id=decision_id
    )
    decision_data = DecisionResponse.model_validate(decision).model_dump()
    decision_data["predictions"] = [
        PredictionResponse.model_validate(p).model_dump() for p in predictions
    ]
    return success_response(data=decision_data)


# ── Prediction Routes ─────────────────────────────────────────


@router.post(
    "/predictions",
    status_code=status.HTTP_201_CREATED,
    summary="Create a prediction",
)
async def create_prediction(
    body: PredictionCreate,
    svc: JudgmentService = Depends(_get_judgment_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Create a falsifiable prediction with confidence normalization.

    If confidence < 0.5, the statement is automatically negated and
    confidence flipped (e.g., 30% → 70% of "NOT: <statement>").
    """
    prediction = await svc.create_prediction(
        tenant_id=tenant_id,
        statement=body.statement,
        confidence=body.confidence,
        decision_id=body.decision_id,
        domain_tags=body.domain_tags,
        resolve_by=body.resolve_by,
        resolution_criteria=body.resolution_criteria,
        capture_event_id=body.capture_event_id,
    )
    return success_response(data=PredictionResponse.model_validate(prediction))


@router.get(
    "/predictions",
    summary="List predictions",
)
async def list_predictions(
    svc: JudgmentService = Depends(_get_judgment_service),
    tenant_id: str = Depends(get_current_tenant_id),
    prediction_status: str | None = Query(
        None, alias="status", description="Filter by outcome status"
    ),
    due_before: datetime | None = Query(None, description="Only predictions due before this date"),
    limit: int = Query(50, ge=1, le=200, description="Max results to return"),
):
    """List predictions for the current tenant.

    Supports filtering by outcome status and resolve_by deadline.
    Returns newest first.
    """
    predictions = await svc.list_predictions(
        tenant_id=tenant_id,
        status=prediction_status,
        due_before=due_before,
        limit=limit,
    )
    return success_response(
        data=[PredictionResponse.model_validate(p) for p in predictions],
    )


@router.post(
    "/predictions/{prediction_id}/accept",
    summary="Accept a suggested prediction",
)
async def accept_prediction(
    prediction_id: UUID,
    body: PredictionAcceptRequest,
    svc: JudgmentService = Depends(_get_judgment_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Confirm a prediction detected in a capture, optionally correcting it.

    Until accepted, a suggestion is excluded from calibration and expiry.
    """
    try:
        prediction = await svc.accept_suggestion(
            tenant_id,
            prediction_id,
            statement=body.statement,
            confidence=body.confidence,
            resolve_by=body.resolve_by,
            domain_tags=body.domain_tags,
        )
    except ValueError as exc:
        code = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    return success_response(data=PredictionResponse.model_validate(prediction))


@router.post(
    "/predictions/{prediction_id}/dismiss",
    summary="Dismiss a suggested prediction",
)
async def dismiss_prediction(
    prediction_id: UUID,
    svc: JudgmentService = Depends(_get_judgment_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Delete a suggestion that isn't really a prediction."""
    try:
        await svc.dismiss_suggestion(tenant_id, prediction_id)
    except ValueError as exc:
        code = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    return success_response(data={"id": str(prediction_id), "dismissed": True})


# ── Prediction Resolution ─────────────────────────────────────


@router.post(
    "/predictions/{prediction_id}/resolve",
    summary="Resolve a prediction",
)
async def resolve_prediction(
    prediction_id: UUID,
    body: PredictionResolveRequest,
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Manually resolve a prediction with outcome and evidence.

    Sets the prediction as correct, incorrect, or ambiguous.
    Resolutions are immutable — once resolved, cannot be changed.
    Today's calibration snapshots are refreshed afterwards, so the advisor
    and agents see the new outcome without waiting for the nightly run.
    """
    from life_graph.services.outcome_resolver import OutcomeResolver

    async with async_session() as session:
        resolver = OutcomeResolver(session, event_bus)
        try:
            prediction = await resolver.resolve_prediction(
                tenant_id=tenant_id,
                prediction_id=prediction_id,
                outcome=body.outcome,
                source=body.source,
                evidence=body.evidence,
            )
            await session.commit()
        except ValueError as exc:
            msg = str(exc)
            if "not found" in msg.lower():
                raise HTTPException(status_code=404, detail=msg) from exc
            raise HTTPException(status_code=400, detail=msg) from exc

    await _refresh_calibration(tenant_id)
    return success_response(data=PredictionResponse.model_validate(prediction))


async def _refresh_calibration(tenant_id: str) -> None:
    """Best-effort snapshot refresh; the resolution itself is already committed."""
    from life_graph.services.calibration import CalibrationService

    try:
        async with async_session() as session:
            await CalibrationService(session, event_bus).recompute(tenant_id)
            await session.commit()
    except Exception:
        logger.warning("Calibration refresh failed for %s", tenant_id, exc_info=True)


# ── Calibration Routes ────────────────────────────────────────


@router.get(
    "/calibration",
    summary="Get calibration data",
)
async def get_calibration(
    tenant_id: str = Depends(get_current_tenant_id),
    domain: str | None = Query(None, description="Domain tag; omitted means overall"),
    window: int = Query(90, ge=1, le=365, description="Window in days"),
):
    """Current calibration, computed live from resolved predictions.

    Below 20 resolved predictions ``status`` is ``insufficient_data`` and the
    response carries progress (``resolved_count`` of ``required``) instead
    of a curve. Otherwise it has the Brier score, buckets, bias findings,
    and a ``trend`` against the preceding window when that had enough data.
    """
    from life_graph.services.calibration import CalibrationService

    async with async_session() as session:
        report = await CalibrationService(session).report(tenant_id, domain, window)
    return success_response(data=report)


@router.get(
    "/calibration/curve",
    summary="Get calibration curve data",
)
async def get_calibration_curve(
    tenant_id: str = Depends(get_current_tenant_id),
    domain: str | None = Query(None, description="Domain tag; omitted means overall"),
    window: int = Query(90, ge=1, le=365, description="Window in days"),
):
    """Bucket data for plotting claimed vs actual, with the identity line.

    ``buckets`` is empty until there is enough data for a curve.
    """
    from life_graph.services.calibration import CalibrationService

    async with async_session() as session:
        report = await CalibrationService(session).report(tenant_id, domain, window)
    return success_response(
        data={
            "domain": report["domain"],
            "buckets": report["buckets"],
            "identity": [[0.5, 0.5], [1.0, 1.0]],
        }
    )


@router.post(
    "/calibration/recompute",
    summary="Recompute calibration snapshots now",
)
async def recompute_calibration(
    tenant_id: str = Depends(get_current_tenant_id),
    window: int = Query(90, ge=1, le=365, description="Window in days"),
):
    """Write today's snapshots (overall + per domain) without waiting for the night."""
    from life_graph.services.calibration import CalibrationService

    async with async_session() as session:
        summary = await CalibrationService(session, event_bus).recompute(tenant_id, window)
        await session.commit()
    return success_response(data=summary)


# ── Stats Route ───────────────────────────────────────────────


@router.get(
    "/stats",
    summary="Judgment dashboard stats",
)
async def get_stats(
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Get summary statistics for the judgment engine dashboard.

    Returns counts of decisions, pending/resolved predictions,
    and average Brier score across calibration snapshots.
    """
    from sqlalchemy import func
    from sqlalchemy import select as sa_select

    from life_graph.models.db import Decision, Prediction
    from life_graph.services.calibration import RESOLVED_OUTCOMES, latest_snapshot
    from life_graph.services.judgment import SUGGESTED

    async with async_session() as session:
        # Total decisions
        total_dec = await session.execute(
            sa_select(func.count()).select_from(Decision).where(Decision.tenant_id == tenant_id)
        )
        total_decisions = total_dec.scalar() or 0

        # Pending predictions
        pending = await session.execute(
            sa_select(func.count())
            .select_from(Prediction)
            .where(
                Prediction.tenant_id == tenant_id,
                Prediction.outcome == "pending",
            )
        )
        pending_predictions = pending.scalar() or 0

        # Resolved predictions. "!= pending" also counted unconfirmed
        # suggestions as resolved.
        resolved = await session.execute(
            sa_select(func.count())
            .select_from(Prediction)
            .where(
                Prediction.tenant_id == tenant_id,
                Prediction.outcome.in_(RESOLVED_OUTCOMES),
            )
        )
        resolved_predictions = resolved.scalar() or 0

        suggested = await session.execute(
            sa_select(func.count())
            .select_from(Prediction)
            .where(
                Prediction.tenant_id == tenant_id,
                Prediction.outcome == SUGGESTED,
            )
        )
        suggested_predictions = suggested.scalar() or 0

        # The current overall Brier score. This used to average every snapshot
        # ever written, across domains and days, which is not a score of
        # anything.
        snap = await latest_snapshot(session, tenant_id)
        brier = snap.brier_score if snap else None

    return success_response(
        data=JudgmentStatsResponse(
            total_decisions=total_decisions,
            pending_predictions=pending_predictions,
            resolved_predictions=resolved_predictions,
            suggested_predictions=suggested_predictions,
            avg_brier=(round(brier, 4) if brier is not None else None),
            sufficient_data=snap is not None,
        )
    )


# ── Challenge Routes ──────────────────────────────────────────


@router.post(
    "/challenge",
    status_code=status.HTTP_201_CREATED,
    summary="Create adversarial challenge",
)
async def create_challenge(
    body: ChallengeRequest,
    advisor=Depends(_get_adversarial_advisor),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Generate an adversarial challenge report for a proposal.

    Creates a structured devil's advocate analysis with 5 sections:
    similar decisions, base rates, calibration, belief conflicts,
    and LLM-generated dissent. Each challenge also creates a tracked
    prediction.
    """
    challenge = await advisor.challenge(tenant_id=tenant_id, proposal=body.proposal)
    return success_response(data=ChallengeResponse.model_validate(challenge))


@router.post(
    "/challenge/{challenge_id}/resolve",
    summary="Resolve a challenge",
)
async def resolve_challenge(
    challenge_id: UUID,
    body: ChallengeResolveRequest,
    advisor=Depends(_get_adversarial_advisor),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Record the action taken on a challenge.

    Records whether the user followed, ignored, or modified their
    approach based on the adversarial challenge report.
    """
    try:
        challenge = await advisor.resolve_challenge(
            tenant_id=tenant_id,
            challenge_id=challenge_id,
            action_taken=body.action_taken,
        )
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg) from exc
        raise HTTPException(status_code=400, detail=msg) from exc

    return success_response(data=ChallengeResponse.model_validate(challenge))
