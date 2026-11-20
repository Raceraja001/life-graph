"""Session lifecycle management routes (Phase B).

Provides endpoints for starting, ending, listing, and updating
sessions.  Session summaries are generated via the local LLM
on end, with a rule-based fallback.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from life_graph.api.responses import (
    decode_cursor,
    encode_cursor,
    paginated_response,
    success_response,
)
from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.db import Session
from life_graph.models.schemas import SessionCreate, SessionResponse
from life_graph.services import session_lifecycle
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])

# Micro-consolidations in flight: the loop holds tasks only weakly, so an
# unreferenced one can be garbage-collected mid-run (audit L6).
_background: set[asyncio.Task[None]] = set()


# ── Request schemas ──────────────────────────────────────────


class HeartbeatRequest(BaseModel):
    """Body for mid-session context update."""

    context: dict[str, Any] = Field(..., description="Updated session context to merge")


class EndSessionRequest(BaseModel):
    """Optional body for ending a session.

    ``summary`` was added 2026-10-22: the MCP ``end_session`` tool has always
    sent one, but this model only declared ``outcome``, so pydantic dropped
    the caller's summary without a word and the LLM summary replaced it.
    """

    outcome: str | None = Field(
        None,
        description="Session outcome: 'success', 'failure', or 'neutral'",
    )
    summary: str | None = Field(
        None,
        description=(
            "Caller-written summary. When given it is stored as-is and the "
            "LLM summary is skipped; omit it to have one generated."
        ),
    )


async def _own_session_or_404(db: Any, session_id: uuid.UUID) -> Session:
    """Load *session_id* if it belongs to the current tenant, else 404.

    See ``services.session_lifecycle.own_session``: another tenant's session
    is reported as missing, not forbidden, so its existence is not disclosed.
    """
    try:
        return await session_lifecycle.own_session(db, session_id)
    except session_lifecycle.SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.detail) from None


_created_count_stmt = session_lifecycle.created_count_stmt


# ── Routes ───────────────────────────────────────────────────


@router.post(
    "/start",
    status_code=status.HTTP_201_CREATED,
    summary="Start a new session",
)
async def start_session(body: SessionCreate):
    """Start a new conversation/interaction session.

    Creates a Session row with the provided context and returns
    the freshly created session.

    The tenant is set explicitly. It was not before 2026-10-22, so every
    session landed in the column's ``"legacy"`` default: invisible to the
    caller's own ``GET /sessions`` and unreachable by anything tenant-scoped
    (micro-consolidation, impact scoring, memory links).
    """
    new_session = Session(
        context=body.context,
        tenant_id=get_current_tenant_id(),
    )

    async with async_session() as db:
        db.add(new_session)
        await db.commit()
        await db.refresh(new_session)

    logger.info("Started session %s", new_session.id)
    return success_response(data=SessionResponse.model_validate(new_session))


@router.post(
    "/{session_id}/end",
    summary="End a session",
)
async def end_session(
    session_id: uuid.UUID,
    body: EndSessionRequest | None = None,
):
    """End a session and generate an LLM summary.

    Counts memories created during the session, asks the local
    LLM for a two-sentence summary, and sets ``ended_at``.  Falls
    back to a rule-based summary if the LLM call fails.

    Optionally accepts an ``outcome`` for impact scoring and a caller-written
    ``summary``, which is kept verbatim instead of generating one.
    """
    outcome = body.outcome if body else None
    sess = await close_session(session_id, outcome=outcome, summary=body.summary if body else None)
    memory_count = sess.memories_created

    # Update impact scores for recalled memories
    if outcome and outcome in ("success", "failure", "neutral"):
        from life_graph.services.impact import ImpactScorer

        scorer = ImpactScorer()
        await scorer.record_outcome(session_id, outcome)

    # Trigger micro-consolidation (non-blocking background task)
    task = asyncio.create_task(
        _run_micro_consolidation(session_id),
        name=f"micro-consolidate-{session_id}",
    )
    _background.add(task)
    task.add_done_callback(_background.discard)

    logger.info("Ended session %s (memories=%d)", session_id, memory_count)
    return success_response(data=SessionResponse.model_validate(sess))


async def close_session(
    session_id: uuid.UUID,
    *,
    outcome: str | None = None,
    summary: str | None = None,
) -> Session:
    """Mark a current-tenant session ended: count, summarise, set ``ended_at``.

    The body of ``POST /sessions/{id}/end``; the logic is
    ``services.session_lifecycle.close_session``, which the Claude Code
    session closer calls too. Raises the route's 404 for a missing or
    other-tenant session and 409 for one already ended.
    """
    try:
        # _generate_summary is looked up here, at call time, so a patch of
        # this module's name still reaches the summary step.
        return await session_lifecycle.close_session(
            session_id, outcome=outcome, summary=summary, summarize=_generate_summary
        )
    except session_lifecycle.SessionCloseError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from None


async def _run_micro_consolidation(session_id: uuid.UUID) -> None:
    """Background task: run micro-consolidation for a session."""
    await session_lifecycle.run_micro_consolidation(session_id)


@router.get(
    "/{session_id}",
    summary="Get a session by ID",
)
async def get_session(session_id: uuid.UUID):
    """Retrieve a single session with its linked memory count."""
    async with async_session() as db:
        sess = await _own_session_or_404(db, session_id)

        # Populate memories_created from the link table if session is still active
        linked_count = await db.scalar(_created_count_stmt(session_id)) or 0
        sess.memories_created = linked_count

    return success_response(data=SessionResponse.model_validate(sess))


@router.get(
    "/",
    summary="List recent sessions",
)
async def list_sessions(
    limit: int = Query(10, ge=1, le=100, description="Max sessions to return"),
    cursor: str | None = Query(None, description="Cursor for keyset pagination"),
    include_total: bool = Query(False, description="Include total count (may be slow)"),
):
    """Return recent sessions ordered by start time (newest first).

    Supports cursor-based pagination for consistent performance.
    When a cursor is provided, keyset pagination is used.
    """
    stmt = (
        select(Session)
        .where(Session.tenant_id == get_current_tenant_id())
        .order_by(Session.started_at.desc())
        .limit(limit + 1)  # Fetch one extra to detect has_more
    )

    if cursor:
        cursor_data = decode_cursor(cursor)
        stmt = stmt.where(Session.started_at < cursor_data["k"])

    async with async_session() as db:
        result = await db.execute(stmt)
        sessions = result.scalars().all()

    has_more = len(sessions) > limit
    sessions = sessions[:limit]

    sessions_list = [SessionResponse.model_validate(s) for s in sessions]

    # Build next cursor from last item
    next_cursor = None
    if has_more and sessions_list:
        last = sessions_list[-1]
        next_cursor = encode_cursor(
            last.started_at.isoformat(),
            str(last.id),
        )

    # Optional total count
    total = None
    if include_total:
        # Scoped like the page itself: unscoped, this reported every
        # tenant's session count (2026-10-22).
        count_stmt = (
            select(func.count())
            .select_from(Session)
            .where(Session.tenant_id == get_current_tenant_id())
        )
        async with async_session() as db:
            total = await db.scalar(count_stmt)

    return paginated_response(
        data=sessions_list,
        total=total,
        page_size=limit,
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.post(
    "/{session_id}/heartbeat",
    summary="Update session context mid-conversation",
)
async def heartbeat(
    session_id: uuid.UUID,
    body: HeartbeatRequest,
):
    """Update the session's JSONB context with new data.

    Merges the incoming context dict into the existing context,
    preserving keys that are not overwritten.
    """
    async with async_session() as db:
        sess = await _own_session_or_404(db, session_id)

        if sess.ended_at is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Session {session_id} already ended",
            )

        # Merge context (shallow)
        # A new dict, not the loaded one mutated in place: the column is
        # plain JSONB (no MutableDict), so re-assigning the same object
        # need not register as a change.
        sess.context = {**(sess.context or {}), **body.context}

        await db.commit()
        await db.refresh(sess)

    logger.info("Heartbeat for session %s", session_id)
    return success_response(data=SessionResponse.model_validate(sess))


# ── Internal Helpers ─────────────────────────────────────────


# Kept as a module name: tests patch it to prove a caller's summary wins.
_generate_summary = session_lifecycle.generate_summary
