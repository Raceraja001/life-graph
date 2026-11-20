"""Procedural skills: the recipes the distiller wrote, as a reviewable list.

``services/skill_distiller.py`` turns a coding session that went wrong and
then right into one markdown recipe stored as a ``Memory`` row. Those rows
were only reachable through recall, so a skill the model got wrong stayed in
the corpus and kept being injected into every dev persona's prompt
(``services/persona_context.py``). These endpoints are the review surface:
list them, read one, approve a pending one, archive a bad one.

No new table. A skill *is* a memory — ``skill_clause()`` in the distiller is
the single definition of which ones, so the API, the persona block and the
writer cannot drift apart.
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import any_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from life_graph.api.responses import success_response
from life_graph.core.tenant import get_current_tenant_id, get_scoped
from life_graph.models.db import Memory
from life_graph.services.skill_distiller import (
    skill_body,
    skill_clause,
    skill_project,
    skill_title,
)
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/skills", tags=["skills"])

#: ``memories.status`` values that a human review can promote to ``active``.
REVIEWABLE = ("pending", "needs_review")

#: What :func:`archive_skill` sets instead of deleting the row. A skill is
#: expensive to produce (a harvest, a gate, an LLM call) and still useful as
#: evidence of what the distiller decided, so nothing here deletes one.
ARCHIVED = "archived"

MAX_LIMIT = 200


def serialize(memory: Memory) -> dict[str, Any]:
    """One skill as the dashboard and the API clients read it.

    ``content`` is the whole recipe: a skill is a few hundred words, and
    sending it with the list is what lets the UI open the detail drawer
    without a second request.
    """
    props = memory.properties or {}
    tags = list(memory.tags or [])
    return {
        "id": str(memory.id),
        "title": skill_title(memory.content, props),
        "content": memory.content,
        "body": skill_body(memory.content),
        "status": memory.status,
        # So the UI's Approve button follows the API's rule, not its own copy of it.
        "reviewable": memory.status in REVIEWABLE,
        "tags": tags,
        "project": skill_project(tags, props),
        "origin_agent": props.get("origin_agent"),
        "session_id": props.get("session_id"),
        "source_type": memory.source_type,
        "reasoning": memory.reasoning,
        "importance": memory.importance,
        "confidence": memory.confidence,
        "patch_count": int(props.get("patch_count") or 0),
        "created_at": memory.created_at.isoformat() if memory.created_at else None,
        "updated_at": memory.updated_at.isoformat() if memory.updated_at else None,
        "distilled_at": props.get("distilled_at"),
    }


async def _load(db: AsyncSession, skill_id: uuid.UUID) -> Memory:
    """The current tenant's skill; another tenant's id reads as a 404."""
    try:
        memory = await get_scoped(db, Memory, skill_id)
    except LookupError:
        memory = None
    if memory is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill {skill_id} not found",
        )
    return memory


@router.get("/", summary="List procedural skills")
# Both spellings, so a client that omits the trailing slash is answered
# rather than redirected (307) on every page load.
@router.get("", include_in_schema=False)
async def list_skills(
    # Annotated, not `= Query(...)`: these defaults are then real values, so
    # the endpoint is also callable as a plain function (tests/unit/fakes.py).
    status_filter: Annotated[
        str | None, Query(alias="status", description="active, pending, needs_review or archived")
    ] = None,
    tag: Annotated[str | None, Query(description="Filter by tag")] = None,
    project: Annotated[
        str | None, Query(description="Filter by the project it was distilled from")
    ] = None,
    search: Annotated[str | None, Query(description="Substring of the recipe's text")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Every distilled skill for this tenant, newest first.

    No status filter means every status, archived included — the dashboard's
    "All" tab. ``total`` counts the filtered set, not the page.
    """
    where = [Memory.tenant_id == get_current_tenant_id(), skill_clause()]
    if status_filter:
        where.append(Memory.status == status_filter)
    # any_(col) == v renders the same `:v = ANY (memories.tags)` as the
    # ARRAY comparator's .any(v), which SQLAlchemy 2.1 deprecates.
    if tag:
        where.append(any_(Memory.tags) == tag)
    if project:
        # A project is both a tag and (on newer rows) a property; match either.
        where.append(
            or_(
                any_(Memory.tags) == project,
                Memory.properties["project"].astext == project,
            )
        )
    if search:
        where.append(Memory.content.ilike(f"%{search}%"))

    async with async_session() as db:
        total = await db.scalar(select(func.count()).select_from(Memory).where(*where))
        rows = (
            (
                await db.execute(
                    select(Memory)
                    .where(*where)
                    .options(defer(Memory.embedding))
                    .order_by(Memory.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
            )
            .scalars()
            .all()
        )

    return success_response(
        data={
            "items": [serialize(m) for m in rows],
            "total": int(total or 0),
            "limit": limit,
            "offset": offset,
        }
    )


@router.get("/{skill_id}", summary="Get one procedural skill")
async def get_skill(skill_id: uuid.UUID):
    """One skill's full recipe."""
    async with async_session() as db:
        memory = await _load(db, skill_id)
        return success_response(data=serialize(memory))


@router.post("/{skill_id}/approve", summary="Approve a skill into active recall")
async def approve_skill(skill_id: uuid.UUID, request: Request):
    """Promote a skill to ``active`` so recall and the persona block use it.

    Idempotent, and it also un-archives: approving is the only way back from
    a mistaken archive, and the alternative (a 409 on anything but pending)
    would leave a row with no route to active at all.

    An active skill is injected into every dev persona's prompt, so this is
    an approval like any other (api/approval_identity.py): with
    ``approvals_require_owner`` on only the owner may approve (403), and
    ``approved_by`` records who did as the server saw them — it said
    ``"human"`` for any caller, the MCP server and agents included.
    """
    from life_graph.api.approval_identity import require_owner, resolver

    require_owner(request)
    async with async_session() as db:
        memory = await _load(db, skill_id)
        if memory.status != "active":
            logger.info("Approving skill %s (was %s)", skill_id, memory.status)
            memory.status = "active"
            memory.properties = {**(memory.properties or {}), "approved_by": resolver(request)}
            await db.commit()
        return success_response(data=serialize(memory))


@router.delete("/{skill_id}", summary="Archive a skill")
async def archive_skill(skill_id: uuid.UUID):
    """Soft-delete: the row stays, but nothing recalls or injects it any more."""
    async with async_session() as db:
        memory = await _load(db, skill_id)
        if memory.status != ARCHIVED:
            logger.info("Archiving skill %s (was %s)", skill_id, memory.status)
            memory.status = ARCHIVED
            await db.commit()
        return success_response(data={"id": str(skill_id), "status": ARCHIVED})
