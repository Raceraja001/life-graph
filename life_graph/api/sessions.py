"""Session lifecycle management routes (Phase B).

Provides endpoints for starting, ending, listing, and updating
sessions.  Session summaries are generated via the local LLM
on end, with a rule-based fallback.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from life_graph.api.dependencies import get_lm_client
from life_graph.api.responses import success_response, paginated_response, encode_cursor, decode_cursor
from life_graph.models.db import MemorySession, Session
from life_graph.models.schemas import SessionCreate, SessionResponse
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])


# ── Request schemas ──────────────────────────────────────────


class HeartbeatRequest(BaseModel):
    """Body for mid-session context update."""

    context: dict[str, Any] = Field(
        ..., description="Updated session context to merge"
    )


class EndSessionRequest(BaseModel):
    """Optional body for ending a session."""

    outcome: str | None = Field(
        None,
        description="Session outcome: 'success', 'failure', or 'neutral'",
    )


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
    """
    new_session = Session(
        context=body.context,
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

    Optionally accepts an ``outcome`` for impact scoring.
    """
    async with async_session() as db:
        sess = await db.get(Session, session_id)
        if sess is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found",
            )

        if sess.ended_at is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Session {session_id} already ended",
            )

        # Count memories linked to this session
        count_stmt = (
            select(func.count())
            .select_from(MemorySession)
            .where(MemorySession.session_id == session_id)
        )
        memory_count = await db.scalar(count_stmt) or 0

        # Generate summary via LLM
        summary = await _generate_summary(sess, memory_count)

        sess.ended_at = datetime.now(timezone.utc)
        sess.summary = summary
        sess.memories_created = memory_count

        # Record outcome for impact scoring
        outcome = body.outcome if body else None
        if outcome and outcome in ("success", "failure", "neutral"):
            sess.outcome = outcome

        await db.commit()
        await db.refresh(sess)

    # Update impact scores for recalled memories
    if outcome and outcome in ("success", "failure", "neutral"):
        from life_graph.services.impact import ImpactScorer
        scorer = ImpactScorer()
        await scorer.record_outcome(session_id, outcome)

    # Trigger micro-consolidation (non-blocking background task)
    asyncio.create_task(
        _run_micro_consolidation(session_id),
        name=f"micro-consolidate-{session_id}",
    )

    logger.info("Ended session %s (memories=%d)", session_id, memory_count)
    return success_response(data=SessionResponse.model_validate(sess))


async def _run_micro_consolidation(session_id: uuid.UUID) -> None:
    """Background task: run micro-consolidation for a session."""
    try:
        from life_graph.api.dependencies import get_micro_consolidator
        consolidator = get_micro_consolidator()
        report = await consolidator.run(session_id)
        logger.info(
            "Micro-consolidation %s complete: %d processed, %d deduped (%.2fs)",
            session_id, report.memories_processed,
            report.duplicates_removed, report.duration_seconds,
        )
    except Exception:
        logger.exception("Micro-consolidation failed for session %s", session_id)


@router.get(
    "/{session_id}",
    summary="Get a session by ID",
)
async def get_session(session_id: uuid.UUID):
    """Retrieve a single session with its linked memory count."""
    async with async_session() as db:
        sess = await db.get(Session, session_id)
        if sess is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found",
            )

        # Populate memories_created from the link table if session is still active
        count_stmt = (
            select(func.count())
            .select_from(MemorySession)
            .where(MemorySession.session_id == session_id)
        )
        linked_count = await db.scalar(count_stmt) or 0
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
        count_stmt = select(func.count()).select_from(Session)
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
        sess = await db.get(Session, session_id)
        if sess is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found",
            )

        if sess.ended_at is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Session {session_id} already ended",
            )

        # Merge context (shallow)
        existing = sess.context or {}
        existing.update(body.context)
        sess.context = existing

        await db.commit()
        await db.refresh(sess)

    logger.info("Heartbeat for session %s", session_id)
    return success_response(data=SessionResponse.model_validate(sess))


# ── Internal Helpers ─────────────────────────────────────────


async def _generate_summary(sess: Session, memory_count: int):
    """Generate a session summary via the local LLM.

    Falls back to a simple template string if the LLM is
    unavailable or returns an empty response.
    """
    fallback = f"Session with {memory_count} memories created"

    try:
        lm_client = get_lm_client()
        context_str = str(sess.context) if sess.context else "no context"
        prompt = (
            f"Summarize this coding session in exactly 2 sentences.\n"
            f"Context: {context_str}\n"
            f"Memories created: {memory_count}\n"
            f"Summary:"
        )
        summary = await lm_client.chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=128,
        )
        return summary.strip() if summary.strip() else fallback
    except Exception:
        logger.warning("LLM summary generation failed, using fallback")
        return fallback
