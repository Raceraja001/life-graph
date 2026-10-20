"""Free LLM offers (docs/specs/free-llm-offers.md, AC-7.2).

``GET /llm-offers`` lists what Job 1 found, with terms and evaluation;
``POST /llm-offers/{id}/evaluate`` queues one for the hourly evaluation job.
Adoption goes through the approvals API (kind ``model_adoption``).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from life_graph.api.responses import success_response
from life_graph.core.tenant import get_current_tenant_id
from life_graph.storage.database import async_session

router = APIRouter(prefix="/llm-offers", tags=["llm-offers"])


@router.get("", summary="Free LLM models, tiers and credits found, with their evaluation")
async def list_offers(status_filter: str | None = Query(None, alias="status", max_length=16)):
    from life_graph.models.assistant import LlmOffer
    from life_graph.services.llm_offers import to_dict

    tenant_id = get_current_tenant_id()
    query = select(LlmOffer).where(LlmOffer.tenant_id == tenant_id)
    if status_filter:
        query = query.where(LlmOffer.status == status_filter)
    async with async_session() as session:
        rows = (await session.execute(query.order_by(LlmOffer.last_seen_at.desc()))).scalars()
        return success_response(data=[to_dict(o) for o in rows])


@router.post("/{offer_id}/evaluate", summary="Queue an offer for evaluation")
async def queue_evaluation(offer_id: str):
    from life_graph.models.assistant import LlmOffer
    from life_graph.services.llm_offers import reachable, to_dict

    try:
        pk = uuid.UUID(offer_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "offer not found") from None
    async with async_session() as session:
        offer = await session.get(LlmOffer, pk)
        if offer is None or offer.tenant_id != get_current_tenant_id():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "offer not found")
        if not reachable(offer.model_id):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "no free model id we hold a key for: it cannot be evaluated",
            )
        offer.status = "queued"
        await session.commit()
        await session.refresh(offer)
        return success_response(data=to_dict(offer))
