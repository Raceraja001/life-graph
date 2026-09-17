"""Memory CRUD routes (T-043).

Provides create, read, update, delete, and list endpoints for
memories. Text-based creation is routed through the full ingestion
pipeline (extraction → scoring → contradiction → store); structured
creation goes directly to the store.
"""

from __future__ import annotations

import hashlib
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from life_graph.api.dependencies import get_memory_manager, get_recall_engine, get_store
from life_graph.api.openapi_examples import MEMORY_CREATED
from life_graph.api.responses import encode_cursor, paginated_response, success_response
from life_graph.api.token_meta import token_meta
from life_graph.config import settings
from life_graph.core.events import EventType, event_bus
from life_graph.core.memory_manager import MemoryManager
from life_graph.core.tenant import get_current_tenant_id
from life_graph.core.trust import classify_surface
from life_graph.models.db import Memory
from life_graph.models.schemas import MemoryCreate, MemoryResponse, MemoryUpdate
from life_graph.services.recall import RecallEngine
from life_graph.storage.postgres import PostgresMemoryStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memories", tags=["memories"])


async def _store_verbatim(
    body: MemoryCreate,
    *,
    manager: MemoryManager,
    store: PostgresMemoryStore,
    tier: str,
) -> Memory:
    """Store *body* as the caller supplied it, without running extraction.

    Both verbatim paths bypass ``MemoryManager.ingest()``, so they must apply
    what it would have: the exact-hash dedup check (without it, re-submitting
    the same note inserted another identical pending row each time) and an
    embedding (without it the memory is invisible to vector search forever —
    only the extraction-fallback path computed one; structured input skipped
    it, so memories saved with tags and importance could only be found by
    keyword). Returns the existing row when the content is a duplicate.
    """
    content_hash = hashlib.sha256(body.content.strip().lower().encode()).hexdigest()
    existing = await store.find_exact_duplicate(content_hash)
    if existing is not None:
        return existing

    embedding = await manager.generate_embedding(body.content)
    return await store.store(body, embedding=embedding, trust_tier=tier, extraction_tier="manual")


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Create memories from text or structured input",
    responses=MEMORY_CREATED,
)
async def create_memory(
    body: MemoryCreate,
    manager: MemoryManager = Depends(get_memory_manager),
    store: PostgresMemoryStore = Depends(get_store),
):
    """Create one or more memories.

    If the body contains free-form text, it is routed through the
    full ingestion pipeline (extraction → importance scoring →
    contradiction detection → storage). Otherwise, the memory is
    stored directly.
    """
    # Provenance is decided server-side from the declared source, never taken
    # from the client. An unrecognised or absent source_type falls to EXTERNAL
    # (default-deny in classify_surface), so content arriving over the API
    # without a first-party source is fenced when an agent reads it. Omitting
    # this let PostgresMemoryStore.store() apply its "verified" default, which
    # marked arbitrary third-party text as trusted.
    tier = classify_surface(body.source_type).value

    # Heuristic: if tags/properties already provided and content is short,
    # treat as structured input and store directly.
    is_structured = (
        body.tags is not None and body.importance is not None and len(body.content.split()) <= 20
    )

    if is_structured:
        row = await _store_verbatim(body, manager=manager, store=store, tier=tier)
        # All three exits below return the same shape. Two of them previously
        # returned a bare list while the third wrapped in success_response(),
        # so the response shape depended on whether extraction happened to
        # yield anything — the caller could not know which it would get.
        return success_response(data=[MemoryResponse.model_validate(row)])

    # Full ingestion pipeline for free-form text
    memories = await manager.ingest(
        text=body.content,
        context=body.properties,
        source=body.source_type,
        capture=True,
        trust_tier=tier,
    )

    if not memories:
        # Nothing extracted — store as-is so the user's input isn't lost.
        row = await _store_verbatim(body, manager=manager, store=store, tier=tier)
        return success_response(data=[MemoryResponse.model_validate(row)])

    return success_response(
        data=[MemoryResponse.model_validate(m) for m in memories],
    )


# Cap on one expand request. Recall hands back at most a few dozen index
# lines, so a caller with a legitimate reason to expand more than this is
# really asking for a list endpoint.
#
# Tune with LIFE_GRAPH_MEMORY_BATCH_MAX. Read once at import because it is
# baked into the request schema's max_length below.
_BATCH_EXPAND_MAX: int = settings.memory_batch_max


class MemoryBatchRequest(BaseModel):
    """Payload for expanding a set of memory ids to full objects."""

    ids: list[uuid.UUID] = Field(
        ...,
        min_length=1,
        max_length=_BATCH_EXPAND_MAX,
        description=f"Memory ids to expand (1–{_BATCH_EXPAND_MAX})",
    )
    record_access: bool = Field(
        True,
        description=(
            "Whether this expand counts as the memories being surfaced: writes "
            "the recall cooldown and increments access_count/last_accessed. "
            "On by default — expanding is the disclosure the bookkeeping is "
            "about. Turn it off for inspection that should leave no trace "
            "(dashboards, admin tooling)."
        ),
    )


@router.post(
    "/batch",
    summary="Expand memory ids to full memories (progressive-disclosure step 2)",
)
async def batch_get_memories(
    body: MemoryBatchRequest,
    store: PostgresMemoryStore = Depends(get_store),
    engine: RecallEngine = Depends(get_recall_engine),
):
    """Fetch several memories by id in one round trip.

    The expand half of progressive disclosure. A caller runs recall or search
    with ``index_only`` — a compact ``{id, content, tags, score, status}``
    line per memory — then comes back here for the few it actually wants.

    **This is where surfacing is recorded.** The recall cooldown and the
    access count (which feed decay and the ``frequency`` ranking signal) fire
    on the expand, not on the index: an index-only recall discloses nothing,
    so recording it there would burn a week of cooldown and inflate
    ``access_count`` on memories nobody read. Full (non-index) recall still
    records at recall time, because there the content *is* in the response.

    Unknown or other-tenant ids are silently absent from the result rather
    than an error — ``meta.requested`` vs ``meta.found`` tells the caller.
    """
    rows = await store.retrieve_many(body.ids)
    memories = [MemoryResponse.model_validate(r) for r in rows]

    if body.record_access and memories:
        # A pull, not a push: it must not consume the session surface cap,
        # or a caller reading its own memories would lock itself out of
        # proactive recall.
        await engine.record_disclosure([m.id for m in memories])

    return success_response(
        data=memories,
        meta=token_meta(
            memories,
            requested=len(body.ids),
            found=len(memories),
        ),
    )


class BulkApprovalBody(BaseModel):
    """Payload for batch-approving/rejecting pending memories."""

    approve: list[uuid.UUID] = []
    reject: list[uuid.UUID] = []


async def _transition(memory_id: uuid.UUID, action: str, store: PostgresMemoryStore) -> Memory:
    """Move a memory between pending/rejected/active, emitting the matching event.

    Idempotent when already in the target status; 404 if missing; 409 if the
    requested transition isn't valid from the memory's current status.
    """
    row = await store.retrieve(memory_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    if action == "approve":
        if row.status == "active":
            return row  # idempotent
        if row.status not in ("pending", "rejected"):
            raise HTTPException(status_code=409, detail=f"Cannot approve a {row.status} memory")
        updated = await store.update(memory_id, MemoryUpdate(status="active"))
        try:
            await event_bus.emit(
                EventType.MEMORY_APPROVED,
                {"id": str(memory_id), "tenant_id": get_current_tenant_id()},
                source="memories",
            )
        except Exception:
            logger.warning("Failed to emit MEMORY_APPROVED for %s", memory_id, exc_info=True)
        return updated
    # reject
    if row.status == "rejected":
        return row  # idempotent
    if row.status != "pending":
        raise HTTPException(status_code=409, detail=f"Cannot reject a {row.status} memory")
    updated = await store.update(memory_id, MemoryUpdate(status="rejected"))
    try:
        await event_bus.emit(
            EventType.MEMORY_REJECTED,
            {"id": str(memory_id), "tenant_id": get_current_tenant_id()},
            source="memories",
        )
    except Exception:
        logger.warning("Failed to emit MEMORY_REJECTED for %s", memory_id, exc_info=True)
    return updated


@router.get(
    "/pending/count",
    summary="Count memories awaiting approval",
)
async def pending_count(store: PostgresMemoryStore = Depends(get_store)):
    """Number of memories awaiting approval for this tenant."""
    count = await store.count_memories(filters={"status": "pending"})
    return success_response(data={"count": count})


@router.post(
    "/approvals/bulk",
    summary="Approve/reject memories in batch",
)
async def bulk_approvals(
    body: BulkApprovalBody,
    store: PostgresMemoryStore = Depends(get_store),
):
    """Approve/reject memories in batch (distillation review will lean on this)."""
    approved = rejected = 0
    errors: list[str] = []
    for mid in body.approve:
        try:
            await _transition(mid, "approve", store)
            approved += 1
        except HTTPException:
            errors.append(str(mid))
    for mid in body.reject:
        try:
            await _transition(mid, "reject", store)
            rejected += 1
        except HTTPException:
            errors.append(str(mid))
    return success_response(data={"approved": approved, "rejected": rejected, "errors": errors})


@router.post(
    "/{memory_id}/approve",
    summary="Approve a memory",
)
async def approve_memory(
    memory_id: uuid.UUID,
    store: PostgresMemoryStore = Depends(get_store),
):
    """Approve a pending (or rejected) memory — it becomes active/usable."""
    row = await _transition(memory_id, "approve", store)
    return success_response(data=MemoryResponse.model_validate(row))


@router.post(
    "/{memory_id}/reject",
    summary="Reject a memory",
)
async def reject_memory(
    memory_id: uuid.UUID,
    store: PostgresMemoryStore = Depends(get_store),
):
    """Reject a pending memory — hidden everywhere, re-capture allowed."""
    row = await _transition(memory_id, "reject", store)
    return success_response(data=MemoryResponse.model_validate(row))


@router.get(
    "/{memory_id}",
    summary="Get a memory by ID",
)
async def get_memory(
    memory_id: uuid.UUID,
    store: PostgresMemoryStore = Depends(get_store),
):
    """Retrieve a single memory by its UUID."""
    row = await store.retrieve(memory_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        )
    return success_response(data=MemoryResponse.model_validate(row))


@router.patch(
    "/{memory_id}",
    summary="Update a memory",
)
async def update_memory(
    memory_id: uuid.UUID,
    body: MemoryUpdate,
    store: PostgresMemoryStore = Depends(get_store),
):
    """Apply a partial update to an existing memory."""
    if body.status in ("pending", "rejected", "active"):
        raise HTTPException(
            status_code=422,
            detail="Approval status changes must use the approve/reject endpoints",
        )
    try:
        row = await store.update(memory_id, body)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        ) from exc
    return success_response(data=MemoryResponse.model_validate(row))


@router.delete(
    "/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a memory",
    response_class=Response,
)
async def delete_memory(
    memory_id: uuid.UUID,
    store: PostgresMemoryStore = Depends(get_store),
):
    """Delete a memory and cascade to association tables."""
    deleted = await store.delete(memory_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{memory_id}/unarchive",
    summary="Unarchive a memory",
)
async def unarchive_memory(
    memory_id: uuid.UUID,
    store: PostgresMemoryStore = Depends(get_store),
):
    """Restore an archived memory back to active status.

    Changes the memory's status from 'archived' to 'active',
    making it available for search and recall again.
    """
    try:
        row = await store.unarchive(memory_id)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Memory {memory_id} not found",
            )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        ) from exc
    return success_response(data=MemoryResponse.model_validate(row))


@router.get(
    "/",
    summary="List memories with optional filters",
)
async def list_memories(
    store: PostgresMemoryStore = Depends(get_store),
    memory_status: str | None = Query(None, alias="status", description="Filter by status"),
    tags: str | None = Query(None, description="Comma-separated tags (array overlap)"),
    min_importance: float | None = Query(None, ge=0.0, le=1.0, description="Minimum importance"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    cursor: str | None = Query(None, description="Cursor for keyset pagination"),
    include_total: bool = Query(False, description="Include total count (may be slow)"),
):
    """List memories with optional status, tag, and importance filters.

    Supports both offset and cursor-based pagination. When a cursor is
    provided, offset is ignored and keyset pagination is used for
    consistent performance on large datasets.
    """
    filters: dict = {}

    if memory_status is not None:
        filters["status"] = memory_status
    else:
        # No explicit status filter: show everything except rejected.
        filters["statuses"] = (
            "active",
            "pending",
            "archived",
            "superseded",
            "uncertain",
            "retired",
        )
    if tags is not None:
        filters["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
    if min_importance is not None:
        filters["min_importance"] = min_importance

    rows, has_more = await store.list_memories(
        filters=filters or None,
        offset=offset,
        limit=limit,
        cursor=cursor,
        include_embedding=False,  # MemoryResponse never serializes it
    )
    memories = [MemoryResponse.model_validate(r) for r in rows]

    # Build next cursor from last item
    next_cursor = None
    if has_more and memories:
        last = memories[-1]
        next_cursor = encode_cursor(
            last.created_at.isoformat(),
            str(last.id),
        )

    # Optional total count
    total = None
    if include_total:
        total = await store.count_memories(filters=filters or None)

    return paginated_response(
        data=memories,
        total=total,
        page_size=limit,
        next_cursor=next_cursor,
        has_more=has_more,
    )


# ── Confidence Decay (Feature 4) ─────────────────────────────────────────────


class DenyRequest(BaseModel):
    """Payload for denying a memory — optionally replacing it with a new fact."""

    replacement: str | None = Field(None, description="New content that replaces the denied memory")


@router.post(
    "/{memory_id}/reinforce",
    summary="Reinforce a memory — confirm it is still accurate",
)
async def reinforce_memory(
    memory_id: uuid.UUID,
    store: PostgresMemoryStore = Depends(get_store),
):
    """Confirm that a memory is still accurate.

    Resets confidence to 0.9, updates last_reinforced timestamp,
    and increments the reinforcement counter. Use this when the
    system asks "is this still true?" and the user confirms.
    """
    try:
        row = await store.reinforce(memory_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        ) from exc
    return success_response(data=MemoryResponse.model_validate(row))


@router.post(
    "/{memory_id}/deny",
    summary="Deny a memory — mark as no longer accurate",
)
async def deny_memory(
    memory_id: uuid.UUID,
    body: DenyRequest | None = None,
    store: PostgresMemoryStore = Depends(get_store),
):
    """Mark a memory as superseded because the user says it is no longer true.

    If a replacement string is provided, creates a new memory that
    supersedes the old one (with full provenance chain). The old memory
    is kept in the supersession chain for history.
    """
    body = body or DenyRequest()
    try:
        denied, replacement = await store.deny(memory_id, body.replacement)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        ) from exc

    result = {
        "denied": MemoryResponse.model_validate(denied),
        "replacement": MemoryResponse.model_validate(replacement) if replacement else None,
    }
    return success_response(data=result)
