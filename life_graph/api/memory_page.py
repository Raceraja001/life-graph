"""The "What Jarvis knows about me" page: one read, and the owner's fixes.

Registered before api/memories.py, whose ``GET /memories/{memory_id}`` would
otherwise take ``/memories/overview`` and answer 422 for a non-UUID id.
See services/memory_page.py for what each action reuses.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from life_graph.api.dependencies import get_store
from life_graph.api.responses import success_response
from life_graph.core.tenant import get_current_tenant_id
from life_graph.services import memory_page
from life_graph.storage.postgres import PostgresMemoryStore

router = APIRouter(prefix="/memories", tags=["memory-page"])


class CorrectBody(BaseModel):
    content: str = Field(..., min_length=1, max_length=memory_page.MAX_CORRECTION_CHARS)


async def _act(coro):
    try:
        return success_response(data=await coro)
    except memory_page.PageActionError as exc:
        raise HTTPException(exc.status, exc.message) from None


@router.get("/overview", summary="What Jarvis knows: review queue, form, notes, older memories")
async def overview(
    q: str = Query("", max_length=200, description="Substring filter (no model call)"),
    kind: str | None = Query(None, description="Notes: fact, preference, rule, decision, episode"),
    evidence: str | None = Query(
        None, description="Notes: said, document, observed, inferred, summary, outside"
    ),
    topic: str | None = Query(None, description="Form: one topic of core/slots.TOPICS"),
    notes_limit: int = Query(memory_page.NOTES_DEFAULT, ge=1, le=memory_page.NOTES_MAX),
    cold_limit: int = Query(memory_page.COLD_DEFAULT, ge=0, le=memory_page.COLD_MAX),
):
    """Tenant-scoped. The cold tier leaves out what the owner took back
    (forgotten/undone), bulk clean-ups and anything before MEMORY_START_AT."""
    if kind is not None and kind not in memory_page.KINDS:
        raise HTTPException(422, f"kind must be one of {', '.join(memory_page.KINDS)}")
    from life_graph.core import evidence as ev
    from life_graph.core import slots

    if evidence is not None and evidence not in ev.KINDS:
        raise HTTPException(422, f"evidence must be one of {', '.join(ev.KINDS)}")
    if topic is not None and topic not in slots.TOPICS:
        raise HTTPException(422, f"topic must be one of {', '.join(slots.TOPICS)}")
    return success_response(
        data=await memory_page.overview(
            get_current_tenant_id(),
            q=q,
            kind=kind,
            evidence=evidence,
            topic=topic,
            notes_limit=notes_limit,
            cold_limit=cold_limit,
        )
    )


@router.get("/{memory_id}/connections", summary="One memory's links, history and mentions")
async def connections(memory_id: uuid.UUID):
    found = await memory_page.connections(get_current_tenant_id(), memory_id)
    if found is None:
        raise HTTPException(404, "Memory not found.")
    return success_response(data=found)


@router.post("/{memory_id}/correct", summary="Correct a memory: the old one is kept as history")
async def correct(memory_id: uuid.UUID, body: CorrectBody):
    """Undo with POST /jarvis/memories/{new id}/undo (the old one comes back)."""
    return await _act(memory_page.correct(get_current_tenant_id(), memory_id, body.content))


@router.post("/{memory_id}/archive", summary="Archive a memory (kept, shown under older memories)")
async def archive(memory_id: uuid.UUID):
    return await _act(memory_page.archive(get_current_tenant_id(), memory_id))


@router.post("/{memory_id}/restore", summary="Bring an archived memory back into use")
async def restore(memory_id: uuid.UUID):
    """Archived only: a replaced memory stays history (correct the current one instead)."""
    return await _act(memory_page.restore(get_current_tenant_id(), memory_id))


@router.post("/{memory_id}/drop", summary="Drop a memory: reject if pending, take back if active")
async def drop(memory_id: uuid.UUID, store: PostgresMemoryStore = Depends(get_store)):
    """Never deleted. A dropped active memory is archived as forgotten; restore undoes it."""
    return await _act(memory_page.drop(get_current_tenant_id(), memory_id, store))
