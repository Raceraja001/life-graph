"""The Memory check: Jarvis asks the owner to keep or drop what it noted.

What the owner states firmly is kept at once (core/memory_manager.py
``_auto_approved``); the rest (plans, hedged thoughts, clashes, anything an
agent or tool reported) waits as ``pending``. Before 2026-10-28 it waited for a
dashboard visit that never came, and pending memories expired unseen 14 days
later: five days after the fresh start only day summaries were active.

Once a day ``run`` puts up to ``PER_DAY`` of the oldest not-yet-asked pending
memories in one Jarvis message in the owner's "Memory check" chat. The messages
list attaches them (``memory_check``) with their status now, and the app shows
Keep / Drop for each, i.e. POST /memories/{id}/approve|reject. Each memory is
asked about once; ``review_offered_at`` stamps when, and expiry
(workers/decay.py) counts from then, so nothing is dropped without being shown.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select

logger = logging.getLogger(__name__)

TITLE = "Memory check"
KIND = "memory_check"
#: A few a day: a long list is one nobody answers.
PER_DAY = 5


def _ask(count: int) -> str:
    things = "thing" if count == 1 else "things"
    return (
        f"I noted {count} {things} about you that I wasn't sure of. "
        "Keep what's right and drop the rest — I'll only use what you keep."
    )


async def _conversation(session, tenant_id: str, now: datetime):
    """The owner's Memory check chat, made the first time it is needed."""
    from life_graph.models.db import AgentSession
    from life_graph.services.lead import LEAD

    found = (
        await session.execute(
            select(AgentSession)
            .where(
                AgentSession.tenant_id == tenant_id,
                AgentSession.routed_to == LEAD,
                AgentSession.context["kind"].astext == KIND,
            )
            .order_by(AgentSession.created_at)
            .limit(1)
        )
    ).scalar_one_or_none()
    if found is not None:
        return found
    conversation = AgentSession(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_message=TITLE,
        routed_to=LEAD,
        status="active",
        context={"title": TITLE, "kind": KIND},
        created_at=now,
    )
    session.add(conversation)
    await session.flush()
    return conversation


async def run_tenant(session, tenant_id: str, now: datetime) -> int:
    """Ask about the oldest pending memories not asked about yet; how many were asked."""
    from life_graph.models.db import AgentTask, Memory

    rows = (
        (
            await session.execute(
                select(Memory)
                .where(
                    Memory.tenant_id == tenant_id,
                    Memory.status == "pending",
                    Memory.properties["review_offered_at"].astext.is_(None),
                )
                .order_by(Memory.created_at)
                .limit(PER_DAY)
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return 0
    conversation = await _conversation(session, tenant_id, now)
    ids = [str(m.id) for m in rows]
    session.add(
        AgentTask(
            tenant_id=tenant_id,
            agent_name="jarvis",
            task_name=KIND,
            status="completed",
            session_id=conversation.id,
            # No owner message: the list shows it as Jarvis speaking, and the
            # episodes and the history a persona is shown skip it.
            input={"origin": KIND, "memory_ids": ids},
            result={"response": _ask(len(ids)), KIND: ids},
            started_at=now,
            completed_at=now,
            created_at=now,
            updated_at=now,
        )
    )
    for m in rows:
        # A new dict: an in-place change to a JSONB column is not tracked.
        m.properties = {**(m.properties or {}), "review_offered_at": now.isoformat()}
    await session.commit()
    return len(ids)


async def states(session, tenant_id: str, ids: list[str]) -> dict[str, dict[str, Any]]:
    """``{memory id: {"id", "content", "status", "evidence"}}`` for the memories a check asked about.

    ``evidence`` (core/evidence.py) lets the chat say "you said" or "my guess"."""
    from life_graph.core.evidence import evidence_of
    from life_graph.models.db import Memory

    wanted = []
    for i in ids:
        try:
            wanted.append(uuid.UUID(str(i)))
        except ValueError:
            continue
    if not wanted:
        return {}
    rows = (
        await session.execute(
            select(
                Memory.id,
                Memory.content,
                Memory.status,
                Memory.source_type,
                Memory.trust_tier,
                Memory.properties,
            ).where(Memory.tenant_id == tenant_id, Memory.id.in_(wanted))
        )
    ).all()
    # A correction waiting for review names the fact it replaces (tools/memory_search.py).
    replaces = {str(i): (props or {}).get("replaces_id") for i, *_, props in rows}
    old_ids = []
    for r in replaces.values():
        try:
            old_ids.append(uuid.UUID(str(r)))
        except ValueError:
            continue
    old_text: dict[str, str] = {}
    if old_ids:
        old_text = {
            str(i): c
            for i, c in (
                await session.execute(
                    select(Memory.id, Memory.content).where(
                        Memory.tenant_id == tenant_id, Memory.id.in_(old_ids)
                    )
                )
            ).all()
        }
    out: dict[str, dict[str, Any]] = {}
    for i, c, s, src, tier, props in rows:
        item = {"id": str(i), "content": c, "status": s, "evidence": evidence_of(src, tier, props)}
        if (old := old_text.get(str(replaces[str(i)]))) is not None:
            item["replaces"] = old
        out[str(i)] = item
    return out


async def waiting(session, tenant_id: str) -> int:
    """Asked about and not yet answered."""
    from life_graph.models.db import Memory

    return int(
        await session.scalar(
            select(func.count())
            .select_from(Memory)
            .where(
                Memory.tenant_id == tenant_id,
                Memory.status == "pending",
                Memory.properties["review_offered_at"].astext.is_not(None),
            )
        )
        or 0
    )


async def run(session_factory, now: datetime | None = None) -> dict[str, int]:
    """Every active tenant's Memory check for today."""
    from life_graph.models.db import TenantConfig

    now = now or datetime.now(UTC)
    async with session_factory() as session:
        tenants = [
            r[0]
            for r in (
                await session.execute(
                    select(TenantConfig.tenant_id).where(TenantConfig.status == "active")
                )
            ).all()
        ]
    out: dict[str, int] = {}
    for tenant_id in tenants:
        try:
            async with session_factory() as session:
                asked = await run_tenant(session, tenant_id, now)
        except Exception:  # one tenant never stops the rest
            logger.exception("Memory check for %s failed", tenant_id)
            continue
        if asked:
            out[tenant_id] = asked
    return out
