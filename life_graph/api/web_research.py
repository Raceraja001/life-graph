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


@router.get("/tech-watch/ideas", summary="Ideas for Jarvis: features other apps shipped, judged")
async def list_ideas(
    status_: str = Query(
        "open", alias="status", pattern="^(open|considering|decided|flagged|all)$"
    ),
    limit: int = Query(100, ge=1, le=300),
):
    """``open`` new ideas · ``considering`` · ``decided`` (not for us, dismissed) ·
    ``flagged`` findings from a suspicious source (kept for the record, never
    offered as ideas) · ``all``. Only features: pricing, payments and news are left out.

    Most worth first (high, medium, low, not rated), then newest. A finding that
    repeats an earlier one is not listed: its link is under the earlier one's
    ``also_from``."""
    from sqlalchemy import case

    from life_graph.models.assistant import TopicFinding
    from life_graph.services.web_research import to_dict

    tenant = get_current_tenant_id()
    query = select(TopicFinding).where(TopicFinding.tenant_id == tenant)
    if status_ == "flagged":
        query = query.where(TopicFinding.trust == "suspicious")
    else:
        query = query.where(
            TopicFinding.is_feature.is_(True),
            TopicFinding.trust != "suspicious",
            TopicFinding.duplicate_of.is_(None),
        )
        if status_ == "open":
            query = query.where(TopicFinding.status == "new")
        elif status_ == "considering":
            query = query.where(TopicFinding.status == "considering")
        elif status_ == "decided":
            query = query.where(TopicFinding.status.in_(("not_for_us", "dismissed")))
    rank = case({"high": 0, "medium": 1, "low": 2}, value=TopicFinding.worth, else_=3)
    async with async_session() as session:
        rows = list(
            (
                await session.execute(
                    query.order_by(rank, TopicFinding.published_on.desc().nullslast()).limit(limit)
                )
            ).scalars()
        )
        dupes = (
            await session.execute(
                select(TopicFinding.duplicate_of, TopicFinding.source_url).where(
                    TopicFinding.tenant_id == tenant,
                    TopicFinding.duplicate_of.in_([r.id for r in rows]),
                )
            )
        ).all()
    also: dict[str, list[str]] = {}
    for of, url in dupes:
        also.setdefault(str(of), []).append(url)
    return success_response(
        data=[{**to_dict(r), "also_from": also.get(str(r.id), [])} for r in rows]
    )


class DecisionBody(BaseModel):
    decision: str = Field(..., pattern="^(consider|not_for_us|dismiss|reset)$")


@router.post("/tech-watch/{finding_id}/decision", summary="Consider, rule out or dismiss an idea")
async def decide_idea(finding_id: str, body: DecisionBody):
    """Marks the finding only: "consider" starts no task (the text came from a web page)."""
    from life_graph.services import feature_ideas
    from life_graph.services.web_research import to_dict

    async with async_session() as session:
        row = await feature_ideas.decide(
            session, get_current_tenant_id(), finding_id, body.decision
        )
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Finding not found")
        return success_response(data=to_dict(row))
