"""Multi-model advisor endpoints (Phase 4 — Personal AI).

Provides routes to query multiple LLMs for comparative recommendations,
list/view advisor sessions, and record user choices.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from life_graph.api.dependencies import get_multi_model_advisor
from life_graph.api.responses import success_response
from life_graph.core.tenant import get_current_tenant_id
from life_graph.services.multi_model_advisor import MultiModelAdvisor

router = APIRouter(prefix="/advisor", tags=["advisor"])


# ── Request/Response Schemas ──────────────────────────────────


class AskRequest(BaseModel):
    """Request body for querying the multi-model advisor."""

    question: str = Field(..., min_length=5, description="The question to ask the models")
    models: list[str] | None = Field(
        None, description="Specific models to query (defaults to configured models)"
    )


class ChooseRequest(BaseModel):
    """Request body for recording a user's model choice."""

    chosen_model: str = Field(..., description="Which model's recommendation was chosen")
    notes: str | None = Field(None, description="Optional notes about the choice")


# ── Endpoints ─────────────────────────────────────────────────


@router.post(
    "/ask",
    summary="Query multiple models for a recommendation",
    status_code=status.HTTP_200_OK,
)
async def ask_advisor(
    body: AskRequest,
    advisor: MultiModelAdvisor = Depends(get_multi_model_advisor),
):
    """Query 2-3 LLMs with the same question and return comparative results.

    Models are queried in parallel with timeout. The response includes
    each model's recommendation, pros/cons, confidence, and a consensus
    score indicating agreement level.
    """
    tenant_id = get_current_tenant_id()
    result = await advisor.ask(
        tenant_id=tenant_id,
        question=body.question,
        models=body.models,
    )

    # Serialize dataclass responses
    responses_out = []
    for r in result.responses:
        responses_out.append({
            "model": r.model,
            "recommendation": r.recommendation,
            "pros": r.pros,
            "cons": r.cons,
            "confidence": r.confidence,
            "reasoning": r.reasoning,
            "tokens_used": r.tokens_used,
            "latency_ms": r.latency_ms,
            "cost_usd": r.cost_usd,
            "status": r.status,
        })

    return success_response(data={
        "session_id": str(result.session_id),
        "question": result.question,
        "responses": responses_out,
        "consensus_score": result.consensus_score,
        "consensus_label": result.consensus_label,
        "winning_choice": result.winning_choice,
        "total_tokens": result.total_tokens,
        "total_cost_usd": result.total_cost_usd,
        "total_latency_ms": result.total_latency_ms,
        "context_used": result.context_used,
    })


@router.get(
    "/sessions",
    summary="List advisor sessions",
)
async def list_sessions(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    advisor: MultiModelAdvisor = Depends(get_multi_model_advisor),
):
    """List past advisor sessions for the current tenant, most recent first."""
    tenant_id = get_current_tenant_id()
    sessions = await advisor.list_sessions(tenant_id, limit=limit, offset=offset)
    return success_response(data=sessions)


@router.get(
    "/sessions/{session_id}",
    summary="Get an advisor session by ID",
)
async def get_session(
    session_id: uuid.UUID,
    advisor: MultiModelAdvisor = Depends(get_multi_model_advisor),
):
    """Retrieve a single advisor session with full model responses."""
    tenant_id = get_current_tenant_id()
    session = await advisor.get_session(tenant_id, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Advisor session {session_id} not found",
        )
    return success_response(data=session)


@router.post(
    "/sessions/{session_id}/choose",
    summary="Record which model's recommendation was chosen",
)
async def choose_model(
    session_id: uuid.UUID,
    body: ChooseRequest,
    advisor: MultiModelAdvisor = Depends(get_multi_model_advisor),
):
    """Record the user's choice for an advisor session.

    This feedback is used to improve future recommendations by
    tracking which models produce the most useful advice.
    """
    tenant_id = get_current_tenant_id()
    result = await advisor.choose(
        tenant_id=tenant_id,
        session_id=session_id,
        chosen_model=body.chosen_model,
        notes=body.notes,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Advisor session {session_id} not found",
        )
    return success_response(data=result)
