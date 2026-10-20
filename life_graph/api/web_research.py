"""Research on demand and the tech watch (docs/specs/research-and-tech-watch.md).

``POST /research`` answers a question from pages fetched now, every claim with
its source (AC-6.4); ``GET /tech-watch`` lists what the tech watch found
(AC-10.5). The preference research engine's routes live in api/research.py
under ``/research/runs`` and ``/research/trigger``.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from life_graph.api.responses import success_response
from life_graph.core.tenant import get_current_tenant_id
from life_graph.storage.database import async_session

router = APIRouter(tags=["research"])


class ResearchRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)


@router.post("/research", summary="Answer a question from web pages read now, with sources")
async def ask_research(body: ResearchRequest):
    from life_graph.services.web_research import research
    from life_graph.services.workers import WorkerError

    try:
        data = await research(body.question, get_current_tenant_id())
    except WorkerError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from None
    return success_response(data=data)


@router.get("/tech-watch", summary="What the tech watch found new on your topics")
async def list_findings(
    topic: str | None = Query(None, max_length=120),
    limit: int = Query(50, ge=1, le=200),
):
    from life_graph.models.assistant import TopicFinding
    from life_graph.services.web_research import to_dict

    query = select(TopicFinding).where(TopicFinding.tenant_id == get_current_tenant_id())
    if topic:
        query = query.where(TopicFinding.topic == topic)
    async with async_session() as session:
        rows = (
            await session.execute(query.order_by(TopicFinding.found_at.desc()).limit(limit))
        ).scalars()
        return success_response(data=[to_dict(r) for r in rows])
