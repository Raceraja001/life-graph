"""Ending a memory session: count, summarise, set ``ended_at``, micro-consolidate.

The body of ``POST /sessions/{id}/end``. It lived in ``api/sessions.py``, and
the Claude Code session closer (services/claude_code_sessions.py) imported
that router -- and FastAPI's ``HTTPException`` -- to call it (audit M12). It
lives here now; the route and the closer both call it, so a session ended by
a hook is still ended exactly like one ended over the API.

Failures are domain errors, not HTTP ones: :class:`SessionNotFoundError` for a
missing or other-tenant session, :class:`SessionAlreadyEndedError` for one
already ended. The route maps them to the 404/409 it always answered.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from life_graph import runtime
from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.db import MemorySession, Session
from life_graph.storage.database import async_session

if TYPE_CHECKING:
    import uuid
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

# Link rows whose memory was written in the session, as opposed to ones the
# session merely recalled. ``memories_created`` counts only these.
CREATED_ROLE = "created"


class SessionCloseError(Exception):
    """A session that cannot be closed. ``status`` is the HTTP code for it."""

    status = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class SessionNotFoundError(SessionCloseError):
    """Missing, or another tenant's (its existence is not disclosed)."""

    status = 404


class SessionAlreadyEndedError(SessionCloseError):
    status = 409


def _refuse_if_ended(sess: Session, session_id: uuid.UUID) -> None:
    if sess.ended_at is not None:
        raise SessionAlreadyEndedError(f"Session {session_id} already ended")


async def own_session(db: Any, session_id: uuid.UUID, *, for_update: bool = False) -> Session:
    """Load *session_id* if it belongs to the current tenant.

    end/get/heartbeat used ``db.get(Session, id)``, which is a primary-key
    lookup with no tenant in it: any tenant that knew (or guessed) a session
    id could read, end or rewrite another tenant's session (review finding,
    2026-10-22). Another tenant's session is reported as missing, not
    forbidden, so its existence is not disclosed.

    Raises:
        SessionNotFoundError: Missing or another tenant's.
    """
    stmt = select(Session).where(
        Session.id == session_id,
        Session.tenant_id == get_current_tenant_id(),
    )
    if for_update:
        stmt = stmt.with_for_update()
    sess = await db.scalar(stmt)
    if sess is None:
        raise SessionNotFoundError(f"Session {session_id} not found")
    return sess


def created_count_stmt(session_id: uuid.UUID) -> Any:
    """Count of memories *created* in a session (recalled links excluded).

    Recall now writes ``role='recalled'`` links into the same table, so a
    plain count of link rows would report recalled memories as created.
    """
    return (
        select(func.count())
        .select_from(MemorySession)
        .where(
            MemorySession.session_id == session_id,
            MemorySession.role == CREATED_ROLE,
        )
    )


async def close_session(
    session_id: uuid.UUID,
    *,
    outcome: str | None = None,
    summary: str | None = None,
    summarize: Callable[[Session, int], Awaitable[str]] | None = None,
) -> Session:
    """Mark a current-tenant session ended: count, summarise, set ``ended_at``.

    A non-blank *summary* is kept verbatim; otherwise *summarize* (default
    :func:`generate_summary`) writes one. Impact scoring and
    micro-consolidation are left to the caller.

    Raises:
        SessionNotFoundError: Missing or another tenant's session.
        SessionAlreadyEndedError: Already ended.

    The summary is generated with no transaction open (audit H7): read and
    close, ask the model, then reopen, lock the row and write. The "already
    ended" check is repeated under that lock, so two concurrent ends give one
    success and one SessionAlreadyEndedError instead of both writing.
    """
    summarize = summarize or generate_summary
    given = (summary or "").strip()

    async with async_session() as db:
        sess = await own_session(db, session_id)
        _refuse_if_ended(sess, session_id)
        memory_count = await db.scalar(created_count_stmt(session_id)) or 0
    # Transaction closed: the LLM call below may take minutes on a local model.

    generated = None if given else await summarize(sess, memory_count)

    async with async_session() as db:
        sess = await own_session(db, session_id, for_update=True)
        _refuse_if_ended(sess, session_id)
        # Recounted under the lock: memories stored while the summary was
        # being written still belong to this session.
        memory_count = await db.scalar(created_count_stmt(session_id)) or 0

        sess.summary = given or generated
        sess.ended_at = datetime.now(UTC)
        sess.memories_created = memory_count

        # Record outcome for impact scoring
        if outcome and outcome in ("success", "failure", "neutral"):
            sess.outcome = outcome

        await db.commit()
        await db.refresh(sess)
    return sess


async def run_micro_consolidation(session_id: uuid.UUID) -> None:
    """Run micro-consolidation for a session; logged, never raised."""
    try:
        consolidator = runtime.get_micro_consolidator()
        report = await consolidator.run(session_id)
        logger.info(
            "Micro-consolidation %s complete: %d processed, %d deduped (%.2fs)",
            session_id,
            report.memories_processed,
            report.duplicates_removed,
            report.duration_seconds,
        )
    except Exception:
        logger.exception("Micro-consolidation failed for session %s", session_id)


async def generate_summary(sess: Session, memory_count: int) -> str:
    """Generate a session summary via the LLM.

    Falls back to a simple template string if the LLM is
    unavailable or returns an empty response.
    """
    fallback = f"Session with {memory_count} memories created"

    try:
        lm_client = runtime.get_lm_client()
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
        logger.warning("LLM summary generation failed, using fallback", exc_info=True)
        return fallback
