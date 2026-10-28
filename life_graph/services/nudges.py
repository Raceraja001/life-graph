"""Nudges from the owner's own words (web-chat-wave1 F2).

A promise found in what the owner said (services/commitments.py) is a
``nudge`` Intention: ``trigger_time`` is when to start nudging, ``expires_at``
a couple of days after its deadline. Every 30 minutes ``run`` sends the ones
whose time has come (services/nudge_pick.py: at most a few a day, none in
quiet hours) as notifications with Done / Tomorrow / Drop; each is nudged
once, then waits for the owner. Tomorrow brings it back at 09:00; Drop and
Done end it; one never answered lapses once it expires.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select

logger = logging.getLogger(__name__)

SOURCE_TYPE = "nudge"
TITLE = "You said you would"
OPEN = ("pending", "nudged")
ACTIONS = ("done", "snooze_1d", "drop")


def _local_midnight(now: datetime, tz: Any) -> datetime:
    return datetime.combine(now.astimezone(tz).date(), time(0, 0), tzinfo=tz).astimezone(UTC)


def say_said(said_at: str | None, now: datetime, tz: Any) -> str:
    """ "today", "yesterday", or the weekday the promise was made."""
    if not said_at:
        return ""
    try:
        said = datetime.fromisoformat(said_at).astimezone(tz).date()
    except ValueError:
        return ""
    days = (now.astimezone(tz).date() - said).days
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    return f"on {said:%A}" if days < 7 else f"on {said:%d %b}"


def body_for(row: Any, now: datetime, tz: Any) -> str:
    ctx = row.context_match or {}
    said = say_said(ctx.get("said_at"), now, tz)
    return f"“{row.content}”" + (f" — you said so {said}." if said else "")


async def run_tenant(session, tenant_id: str, now: datetime, tz: Any) -> dict[str, int]:
    from life_graph.models.db import Intention, Notification
    from life_graph.services.nudge_pick import pick

    lapsed = 0
    rows = (
        (
            await session.execute(
                select(Intention).where(
                    Intention.tenant_id == tenant_id,
                    Intention.trigger_type == "nudge",
                    Intention.status == "pending",
                )
            )
        )
        .scalars()
        .all()
    )
    candidates = []
    by_id = {}
    for row in rows:
        if row.expires_at is not None and row.expires_at <= now:
            row.status = "expired"
            lapsed += 1
            continue
        by_id[str(row.id)] = row
        candidates.append(
            {
                "id": str(row.id),
                "due_from": row.trigger_time or now,
                "due_by": datetime.fromisoformat((row.context_match or {}).get("due_by"))
                if (row.context_match or {}).get("due_by")
                else (row.expires_at or now),
                "snoozed_until": None,
                "state": "open",
            }
        )
    sent_today = int(
        await session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.tenant_id == tenant_id,
                Notification.source_type == SOURCE_TYPE,
                Notification.created_at >= _local_midnight(now, tz),
            )
        )
        or 0
    )
    chosen = pick(candidates, now.astimezone(tz), sent_today=sent_today)
    for c in chosen:
        row = by_id[c["id"]]
        session.add(
            Notification(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                priority="info",
                title=TITLE,
                body=body_for(row, now, tz),
                extra_metadata={"kind": SOURCE_TYPE, "item_id": str(row.id)},
                source_type=SOURCE_TYPE,
                source_id=row.id,
                # The phone polls for these, as for due notifications.
                is_delivered=True,
                delivered_at=now,
            )
        )
        await _say_in_chat(session, tenant_id, row, now, tz)
        row.status, row.triggered_at = "nudged", now
    await session.commit()
    return {"sent": len(chosen), "lapsed": lapsed}


async def _say_in_chat(session, tenant_id: str, row: Any, now: datetime, tz: Any) -> None:
    """The nudge as a Jarvis message in the chat the promise was made in (AC-W2.3).

    A completed top-level turn with a reply and no message: the messages list
    shows it as Jarvis speaking (with ``nudge`` for its buttons), the history a
    persona is shown and the episodes skip it (both need the owner's words),
    and it cannot be asked again. A conversation that is gone, someone else's
    or temporary gets the notification only.
    """
    from life_graph.models.db import AgentSession, AgentTask

    conversation_id = (row.context_match or {}).get("conversation_id")
    try:
        conversation = (
            await session.get(AgentSession, uuid.UUID(str(conversation_id)))
            if conversation_id
            else None
        )
    except ValueError:
        conversation = None
    if (
        conversation is None
        or conversation.tenant_id != tenant_id
        or (conversation.context or {}).get("temporary") is True
    ):
        return
    said = say_said((row.context_match or {}).get("said_at"), now, tz)
    session.add(
        AgentTask(
            tenant_id=tenant_id,
            agent_name="jarvis",
            task_name="nudge",
            status="completed",
            session_id=conversation.id,
            input={"origin": SOURCE_TYPE, "nudge_id": str(row.id)},
            result={
                "response": f"You said you would: “{row.content}”"
                + (f" — you said so {said}." if said else "."),
                "nudge_id": str(row.id),
            },
            started_at=now,
            completed_at=now,
            created_at=now,
            updated_at=now,
        )
    )


async def open_count(session, tenant_id: str) -> int:
    from life_graph.models.db import Intention

    return int(
        await session.scalar(
            select(func.count())
            .select_from(Intention)
            .where(
                Intention.tenant_id == tenant_id,
                Intention.trigger_type == "nudge",
                Intention.status.in_(OPEN),
            )
        )
        or 0
    )


def brief_line(open_: int) -> str | None:
    """The brief leaves the machine: how many, never the owner's words."""
    if not open_:
        return None
    things = "thing" if open_ == 1 else "things"
    return f"{TITLE}: {open_} {things} open — Done, Tomorrow or Drop in chat"


async def run(session_factory, now: datetime | None = None) -> dict[str, Any]:
    """Every active tenant's nudges due now."""
    from life_graph.connectors.tools import user_tz
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
    out: dict[str, Any] = {}
    for tenant_id in tenants:
        try:
            async with session_factory() as session:
                result = await run_tenant(session, tenant_id, now, user_tz())
        except Exception:  # one tenant never stops the rest
            logger.exception("Nudges for %s failed", tenant_id)
            continue
        if result["sent"] or result["lapsed"]:
            out[tenant_id] = result
    return out


async def act(session, tenant_id: str, intention_id: str, action: str, now: datetime, tz: Any):
    """Done, Tomorrow (09:00, owner's day) or Drop; returns the row, or None if not theirs."""
    from life_graph.models.db import Intention
    from life_graph.services.notification_actions import ActionRefusedError, snooze_until

    if action not in ACTIONS:
        raise ActionRefusedError("That button isn't offered for this nudge.")
    try:
        ident = uuid.UUID(str(intention_id))
    except ValueError:
        return None
    row = (
        await session.execute(
            select(Intention)
            .where(
                Intention.tenant_id == tenant_id,
                Intention.id == ident,
                Intention.trigger_type == "nudge",
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    if row.status not in OPEN:
        raise ActionRefusedError("Already settled.")
    if action == "done":
        row.status, row.completed_at = "completed", now
    elif action == "drop":
        row.status, row.completed_at = "dropped", now
    else:
        at = snooze_until("snooze_1d", now, tz)
        row.status, row.trigger_time = "pending", at.astimezone(UTC)
        # Still nudged once more if the deadline has passed by then.
        if row.expires_at is not None and row.expires_at < at:
            row.expires_at = at + timedelta(days=1)
    return row


def as_listed(row: Any) -> dict[str, Any]:
    ctx = row.context_match or {}
    return {
        "id": str(row.id),
        "what": row.content,
        "when": ctx.get("when"),
        "due_by": ctx.get("due_by"),
        "status": row.status,
        "next_nudge_at": row.trigger_time.isoformat() if row.trigger_time else None,
        "said_at": ctx.get("said_at"),
    }
