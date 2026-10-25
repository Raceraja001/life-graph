"""Memory sessions for Claude Code sessions.

The Claude Code hook (integrations/claude_code/hook.py) sends every capture
with the Claude Code session id in ``properties.claude_code_session_id``. That
id meant nothing to the memory layer: the owner's prompts from one coding
session became memories with no common session, so they could not be grouped,
consolidated together or summarised (2026-10-24).

This maps each Claude Code session onto one memory session (a ``sessions``
row, the thing MCP ``start_session``/``end_session`` manage):

* :func:`ensure_session` — on the first memory from a Claude Code session,
  create its row; on every later one, note it was seen. The row's id is
  derived from (tenant, Claude Code id), so it is found again with no lookup
  and two captures racing to create it make one row, not two. The capture
  processor puts that id in the memory's ``properties.session_id``, which is
  the existing link convention (``PostgresMemoryStore._link_to_source_session``).
  A session that carries on after its row was closed (resumed, or idle past
  the timeout) gets a second row, "part 2", and so on.
* :func:`request_end` — the hook's SessionEnd marker asks for the session to
  be closed. It is not closed on the spot: a prompt sent just before quitting
  may still be in extraction, and an ended session accepts no new links. If
  that prompt is the session's first memory, there is no row yet: one is made
  already asked to end, so the session still closes after the grace period.
* :func:`close_due` — the worker cron closes sessions whose end was asked for
  a few minutes ago, and ones that never asked (terminal killed) once idle.
  Closing is ``POST /sessions/{id}/end`` (``api.sessions.close_session``) plus
  the same micro-consolidation, with the summary written by the local model
  only: these are the owner's prompts.

Tenant-scoped throughout; nothing here logs prompt or memory content.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import DateTime, cast, func, literal, or_, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert

from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

#: ``sessions.context.source`` of a session made here.
SOURCE = "claude_code"
#: ``properties.kind`` of the hook's SessionEnd marker capture (hook.SESSION_END_KIND).
SESSION_END_KIND = "session_end"
#: Fixed namespace for the derived session ids. Never change it: existing
#: sessions would stop being found.
_NAMESPACE = uuid.UUID("5b0d6c2e-4f0a-4c1e-9a52-6c6c61756465")
#: Parts (memory sessions) one Claude Code session may run to.
MAX_PARTS = 20
#: Sessions closed per cron run; the rest wait for the next one.
CLOSE_BATCH = 25
#: Memories fed to the local model for a session's summary.
SUMMARY_MEMORIES = 40
SUMMARY_PROMPT = """\
Below are memories saved from one of the owner's coding sessions with their \
coding assistant. Write 1-3 plain sentences: what the session worked on and \
what was decided. Name the project and topics. Only what is in the text; no \
heading, no list."""


def claude_code_session_of(properties: dict[str, Any] | None) -> str | None:
    """The Claude Code session id on a capture's properties, if any.

    ``claude_code_session_id`` since 2026-10-24; captures from an older hook
    (still sitting in a developer's offline spool) carry it as ``session_id``,
    which on this integration was never a memory session.
    """
    props = properties or {}
    if props.get("integration") != SOURCE:
        return None
    raw = props.get("claude_code_session_id") or props.get("session_id")
    return str(raw) if raw else None


def is_session_end(properties: dict[str, Any] | None) -> bool:
    """True for the hook's SessionEnd marker capture."""
    props = properties or {}
    return props.get("kind") == SESSION_END_KIND and claude_code_session_of(props) is not None


def memory_session_id(tenant_id: str, claude_code_session_id: str, part: int = 1) -> uuid.UUID:
    """The id of *part* of a Claude Code session's memory session — stable per tenant.

    Part 1 is the session; a later part exists only if the session went on
    after its memory session was closed (resumed, or idle past the timeout).
    """
    name = f"{tenant_id}:{SOURCE}:{claude_code_session_id}"
    return uuid.uuid5(_NAMESPACE, name if part == 1 else f"{name}:{part}")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _merged(column: Any, values: dict[str, Any]) -> Any:
    """SQL for ``column || values`` on a JSONB column that may be NULL."""
    return func.coalesce(column, literal({}, JSONB)).op("||")(literal(values, JSONB))


async def ensure_session(
    tenant_id: str,
    claude_code_session_id: str,
    *,
    project: str | None = None,
    cwd: str | None = None,
) -> uuid.UUID | None:
    """The open memory session for a Claude Code session, created on first sight.

    One upsert per part: it inserts the part, or marks an open one seen and
    returns it. A part that has ended returns nothing, and the next part is
    tried — a resumed session, or one closed as idle, goes on in a new
    memory session rather than losing its links. Returns None only past
    :data:`MAX_PARTS` (the memory is still kept, just not linked).
    """
    from life_graph.models.db import Session

    seen = _now_iso()
    for part in range(1, MAX_PARTS + 1):
        context: dict[str, Any] = {
            "source": SOURCE,
            "claude_code_session_id": claude_code_session_id,
            "part": part,
            "last_seen_at": seen,
        }
        if project:
            context["project"] = project
        if cwd:
            context["cwd"] = cwd
        stmt = (
            pg_insert(Session)
            .values(
                id=memory_session_id(tenant_id, claude_code_session_id, part),
                tenant_id=tenant_id,
                started_at=datetime.now(UTC),
                context=context,
                memories_created=0,
                memories_accessed=0,
            )
            .on_conflict_do_update(
                index_elements=["id"],
                set_={"context": _merged(Session.context, {"last_seen_at": seen})},
                # Another tenant's row (a uuid5 collision) is never touched.
                where=(Session.tenant_id == tenant_id) & Session.ended_at.is_(None),
            )
            .returning(Session.id)
        )
        async with async_session() as db:
            session_id = (await db.execute(stmt)).scalar()
            await db.commit()
        if session_id is not None:
            return session_id
    logger.warning("Claude Code session has over %d memory sessions; not linking", MAX_PARTS)
    return None


async def request_end(tenant_id: str, claude_code_session_id: str, reason: str | None) -> bool:
    """Ask for a session's open part to be closed (by :func:`close_due`).

    True if there was an open part. If there was none yet (SessionEnd came
    before the first memory finished extraction), the request is kept on a new
    part made already ended-requested: the memory that arrives next joins it
    through :func:`ensure_session`'s upsert, and it closes after the grace
    period rather than the idle timeout. One that never gets a memory closes
    empty, after the same grace.
    """
    from life_graph.models.db import Session

    marker = {"end_requested_at": _now_iso(), "end_reason": reason or "other"}
    async with async_session() as db:
        result = await db.execute(
            update(Session)
            .where(
                Session.tenant_id == tenant_id,
                Session.ended_at.is_(None),
                Session.context["source"].astext == SOURCE,
                Session.context["claude_code_session_id"].astext == claude_code_session_id,
            )
            .values(context=_merged(Session.context, marker))
        )
        await db.commit()
    if result.rowcount:
        return True
    await _record_end_request(tenant_id, claude_code_session_id, marker)
    return False


async def _record_end_request(
    tenant_id: str, claude_code_session_id: str, marker: dict[str, Any]
) -> None:
    """Create the first free part of the session, already asked to end.

    The same upsert walk as :func:`ensure_session`: a part that exists and has
    ended is passed over; one a racing memory opened meanwhile gets the marker
    instead of a new part being made beside it.
    """
    from life_graph.models.db import Session

    seen = _now_iso()
    for part in range(1, MAX_PARTS + 1):
        stmt = (
            pg_insert(Session)
            .values(
                id=memory_session_id(tenant_id, claude_code_session_id, part),
                tenant_id=tenant_id,
                started_at=datetime.now(UTC),
                context={
                    "source": SOURCE,
                    "claude_code_session_id": claude_code_session_id,
                    "part": part,
                    "last_seen_at": seen,
                    **marker,
                },
                memories_created=0,
                memories_accessed=0,
            )
            .on_conflict_do_update(
                index_elements=["id"],
                set_={"context": _merged(Session.context, marker)},
                where=(Session.tenant_id == tenant_id) & Session.ended_at.is_(None),
            )
            .returning(Session.id)
        )
        async with async_session() as db:
            created = (await db.execute(stmt)).scalar()
            await db.commit()
        if created is not None:
            return


def _due_query(now: datetime, *, grace: timedelta, idle: timedelta, tenant_id: str | None = None):
    """Open Claude Code sessions to close: end asked > *grace* ago, or idle > *idle*."""
    from life_graph.models.db import Session

    end_requested = cast(Session.context["end_requested_at"].astext, DateTime(timezone=True))
    last_seen = cast(Session.context["last_seen_at"].astext, DateTime(timezone=True))
    query = select(Session.id, Session.tenant_id).where(
        Session.ended_at.is_(None),
        Session.context["source"].astext == SOURCE,
        or_(end_requested < now - grace, last_seen < now - idle),
    )
    if tenant_id is not None:
        query = query.where(Session.tenant_id == tenant_id)
    return query.order_by(Session.started_at).limit(CLOSE_BATCH)


async def summarize(session_id: uuid.UUID, tenant_id: str, project: str | None) -> str:
    """The session's summary from its memories, local model only; a plain one else."""
    from life_graph.models.db import Memory, MemorySession

    async with async_session() as db:
        rows = (
            await db.execute(
                select(Memory.content)
                .join(MemorySession, MemorySession.memory_id == Memory.id)
                .where(
                    MemorySession.session_id == session_id,
                    MemorySession.role == "created",
                    Memory.tenant_id == tenant_id,
                    Memory.status.in_(("active", "pending")),
                )
                .order_by(Memory.created_at)
                .limit(SUMMARY_MEMORIES)
            )
        ).all()
    where = f" in {project}" if project else ""
    fallback = f"Claude Code session{where}: {len(rows)} memories."
    if not rows:
        return fallback
    try:
        from life_graph.api.dependencies import get_lm_client
        from life_graph.config import settings

        text = "\n".join(f"- {' '.join((content or '').split())[:300]}" for (content,) in rows)
        reply = await get_lm_client().chat_local_only(
            [
                {"role": "system", "content": SUMMARY_PROMPT},
                {"role": "user", "content": f"Project: {project or 'unknown'}\n\n{text}"},
            ],
            model=settings.lm_extraction_model,
            temperature=0.2,
            max_tokens=200,
        )
    except Exception:
        logger.warning("Local summary failed for session %s", session_id, exc_info=True)
        return fallback
    return (reply or "").strip() or fallback


async def close_due(
    now: datetime | None = None, *, tenant_id: str | None = None
) -> list[uuid.UUID]:
    """Close (summarise, end, micro-consolidate) the sessions that are due.

    All tenants, or one (*tenant_id*). Each runs in its own tenant scope;
    one failing does not stop the rest.
    """
    from fastapi import HTTPException

    from life_graph.api import sessions as sessions_api
    from life_graph.config import settings
    from life_graph.core.tenant import tenant_scope
    from life_graph.models.db import Session

    now = now or datetime.now(UTC)
    grace = timedelta(minutes=settings.claude_code_session_end_grace_minutes)
    idle = timedelta(minutes=settings.claude_code_session_idle_minutes)
    async with async_session() as db:
        due = (await db.execute(_due_query(now, grace=grace, idle=idle, tenant_id=tenant_id))).all()

    closed: list[uuid.UUID] = []
    for session_id, owner in due:
        try:
            with tenant_scope(owner, "system"):
                async with async_session() as db:
                    ctx = await db.scalar(
                        select(Session.context).where(
                            Session.id == session_id, Session.tenant_id == owner
                        )
                    )
                project = (ctx or {}).get("project")
                summary = await summarize(session_id, owner, project)
                # A summary is always passed, so the API's own generator (which
                # may route to a cloud model) never sees this session.
                await sessions_api.close_session(session_id, summary=summary)
                await sessions_api._run_micro_consolidation(session_id)
        except HTTPException:
            # Ended meanwhile (409) or gone (404): nothing left to do.
            continue
        except Exception:
            logger.warning("Closing Claude Code session %s failed", session_id, exc_info=True)
            continue
        closed.append(session_id)
    if closed:
        logger.info("Closed %d Claude Code session(s)", len(closed))
    return closed
