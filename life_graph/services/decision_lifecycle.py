"""The decision lifecycle: who may move a decision, and the audit trail (ADR M8 §5.4).

Statuses (``models.schemas.DECISION_STATUSES``): ``candidate`` (proposed, not
decided), ``decided`` (the owner confirmed it), ``reviewed`` (the owner looked
back at it), ``superseded`` (replaced by a newer decision) and ``discarded``
(the owner said it is not a decision). The vocabulary is the existing one:
"confirmed" is ``decided`` and "rejected" is ``discarded``.

:data:`TRANSITIONS` is every allowed move and who may make it:

==========================  ==========================================
candidate -> decided        the owner only
candidate -> discarded      the owner only
decided   -> reviewed       the owner only
decided   -> superseded     the owner only
reviewed  -> superseded     the owner only
candidate -> superseded     the system, only to mirror a memory
                            supersede that was applied
superseded -> candidate     the system, only to undo its own mirror
==========================  ==========================================

Anything else is refused. Inferred context never becomes the owner's intent:
a rule, the model, an auto-kept memory or an API key that is not the owner's
never moves a decision to ``decided``.

Every move appends ``{from, to, at, by, owner}`` to
``decisions.properties.lifecycle``. ``by`` is who the server saw
(api/approval_identity.py ``resolver``), never a name from a request body.
Nothing outside the server writes a decision's ``properties``, so the trail
can be trusted by its readers (the snapshot's ``confirmed``, change
detection's ``acknowledged``).

The memory side (behind ``settings.decision_lifecycle``, off by default):

- :func:`link_capture_memory` ties a decision the capture listener created to
  the one ``decision`` memory stored from the same message:
  ``Decision.properties.memory_id`` and the memory's
  ``properties.decision_id``. JSONB references, no foreign key, read only
  inside the tenant. Lookups go by the decision side, because a memory's
  properties can be patched by clients and a decision's cannot.
- :func:`mirror_memory_supersede` / :func:`undo_memory_mirror`: when a memory
  supersede is applied (services/memory/supersession.py), a *candidate*
  decision linked to the old memory is superseded by the decision linked to
  the new one, and the undo of that memory supersede takes it back. It
  promotes nothing: the new decision keeps its own status.
- :func:`follow_memory_review`: the owner keeping a linked decision memory in
  review confirms the candidate; the owner dropping it discards it.

None of this is read by autonomy, approvals or any execution path: a confirmed
decision is context, not permission.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from life_graph.config import settings
from life_graph.core.errors import (
    ConflictError,
    DomainError,
    ForbiddenError,
    InvalidInputError,
    NotFoundError,
)
from life_graph.models.db import Decision, Memory
from life_graph.storage.database import async_session

if TYPE_CHECKING:
    import uuid
    from collections.abc import Mapping

    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

CANDIDATE = "candidate"
DECIDED = "decided"
REVIEWED = "reviewed"
SUPERSEDED = "superseded"
DISCARDED = "discarded"

#: Who may make a move.
OWNER = "owner"
MIRROR = "mirror"
MIRROR_UNDO = "mirror_undo"

#: Every allowed (from, to) and who may make it.
TRANSITIONS: dict[tuple[str, str], str] = {
    (CANDIDATE, DECIDED): OWNER,
    (CANDIDATE, DISCARDED): OWNER,
    (DECIDED, REVIEWED): OWNER,
    (DECIDED, SUPERSEDED): OWNER,
    (REVIEWED, SUPERSEDED): OWNER,
    (CANDIDATE, SUPERSEDED): MIRROR,
    (SUPERSEDED, CANDIDATE): MIRROR_UNDO,
}

#: Where the trail lives in ``Decision.properties``.
LIFECYCLE = "lifecycle"
#: The decision-side and memory-side cross references.
MEMORY_ID = "memory_id"
DECISION_ID = "decision_id"
#: ``by`` for the system's mirror of a memory supersede, and for its undo.
MIRROR_BY = "system:memory_supersede"
MIRROR_UNDO_BY = "system:memory_supersede_undo"
#: Statuses the owner's confirmation leaves the decision in.
CONFIRMED_STATUSES = (DECIDED, REVIEWED)


def is_owner_label(by: Any) -> bool:
    """A ``by`` that names the owner (api/approval_identity.resolver labels)."""
    who = str(by or "")
    return who == "owner" or who.startswith(("owner:", "phone:"))


def check(current: str, to: str, *, owner: bool, mirror: bool = False) -> None:
    """Refuse a move that :data:`TRANSITIONS` does not allow for this caller.

    Raises:
        ConflictError: the move does not exist (409).
        ForbiddenError: it exists, but the caller may not make it (403): an
            owner move by someone else, or a system move outside a mirror.
    """
    who = TRANSITIONS.get((current, to))
    if who is None:
        raise ConflictError(f"A {current} decision cannot become {to}")
    if who == OWNER and not owner:
        raise ForbiddenError(f"Only the owner can move a decision from {current} to {to}")
    if who in (MIRROR, MIRROR_UNDO) and not mirror:
        raise ForbiddenError(
            f"A {current} decision becomes {to} only by following a memory supersede"
        )


def trail(props: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """The lifecycle trail in *props*, oldest first; [] when there is none."""
    raw = (props or {}).get(LIFECYCLE)
    return [e for e in raw if isinstance(e, dict)] if isinstance(raw, list) else []


def with_entry(
    props: Mapping[str, Any] | None,
    current: str | None,
    to: str,
    *,
    by: str,
    owner: bool,
    at: datetime,
    **extra: Any,
) -> dict[str, Any]:
    """*props* with one more trail entry. A new dict: JSONB is not change-tracked."""
    entry: dict[str, Any] = {
        "from": current,
        "to": to,
        "at": at.isoformat(),
        "by": by,
        "owner": bool(owner),
    }
    entry.update({k: v for k, v in extra.items() if v is not None})
    return {**(props or {}), LIFECYCLE: [*trail(props), entry]}


def owner_confirmed(d: Any) -> bool:
    """Decided or reviewed, and the trail shows the owner moved it to ``decided``.

    A decided row with no trail (made before the lifecycle, or by a caller that
    was not the owner) is not confirmed: we cannot tell who decided it.
    """
    if str(getattr(d, "status", "") or "") not in CONFIRMED_STATUSES:
        return False
    return any(
        e.get("to") == DECIDED and e.get("owner") is True and is_owner_label(e.get("by"))
        for e in trail(getattr(d, "properties", None))
    )


def last_move_to(d: Any, status: str) -> dict[str, Any] | None:
    """The newest trail entry that moved *d* to *status*, or None."""
    for entry in reversed(trail(getattr(d, "properties", None))):
        if entry.get("to") == status:
            return entry
    return None


def apply_move(d: Any, to: str, *, by: str, owner: bool, now: datetime, **extra: Any) -> None:
    """Write the move on the row: status, its timestamp and the trail entry.

    The caller has already called :func:`check`.
    """
    current = d.status
    d.status = to
    if to == DECIDED:
        d.decided_at = now
    elif to == REVIEWED:
        d.reviewed_at = now
    d.properties = with_entry(
        getattr(d, "properties", None), current, to, by=by, owner=owner, at=now, **extra
    )


async def get(session: AsyncSession, tenant_id: str, decision_id: Any) -> Decision | None:
    """The decision *decision_id* of *tenant_id*, or None."""
    result = await session.execute(
        select(Decision).where(Decision.tenant_id == tenant_id, Decision.id == decision_id)
    )
    return result.scalars().first()


async def move(
    session: AsyncSession,
    tenant_id: str,
    decision_id: Any,
    to: str,
    *,
    by: str,
    owner: bool,
    now: datetime | None = None,
) -> Decision:
    """Confirm, discard or review one decision of *tenant_id*; returns the row.

    Raises NotFoundError (404) for a decision that is not this tenant's, and
    :func:`check`'s errors for a move that is not allowed. A supersede needs
    its replacement: :func:`supersede`.
    """
    if to == SUPERSEDED:
        raise InvalidInputError("A supersede names its replacement")
    d = await get(session, tenant_id, decision_id)
    if d is None:
        raise NotFoundError("Decision not found")
    check(d.status, to, owner=owner)
    apply_move(d, to, by=by, owner=owner, now=now or datetime.now(UTC))
    return d


#: How far :func:`supersede` follows the replacement's own chain for a loop.
MAX_CHAIN = 50


async def supersede(
    session: AsyncSession,
    tenant_id: str,
    old_id: uuid.UUID,
    new_id: uuid.UUID,
    *,
    by: str,
    owner: bool = False,
    mirror: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> Decision:
    """Mark *old_id* superseded by *new_id*, both of *tenant_id*; returns the old row.

    Fails closed, writing nothing: a self-supersede (400), a replacement or an
    old decision that is not this tenant's (404), a move the caller may not
    make (403/409, :func:`check`: the owner supersedes a decided or reviewed
    decision, the system only a candidate, and only as a *mirror* of a memory
    supersede), or a replacement whose own chain leads back to the old one
    (409). Sets ``superseded_at`` and appends the trail entry, which names the
    replacement (``replaced_by``) and, for a mirror, the two memories.
    """
    if new_id == old_id:
        raise InvalidInputError("A decision cannot supersede itself")
    new = await get(session, tenant_id, new_id)
    if new is None:
        raise NotFoundError("Replacement decision not found")
    old = await get(session, tenant_id, old_id)
    if old is None:
        raise NotFoundError("Decision not found")
    check(old.status, SUPERSEDED, owner=owner, mirror=mirror is not None)
    hop, seen = new, {new.id}
    for _ in range(MAX_CHAIN):
        nxt = getattr(hop, "superseded_by", None)
        if nxt is None:
            break
        if nxt == old.id:
            raise ConflictError("The replacement is itself replaced by this decision")
        if nxt in seen:
            break  # an older loop elsewhere; not this supersede's to fix
        seen.add(nxt)
        hop = await get(session, tenant_id, nxt)
        if hop is None:
            break
    stamp = now or datetime.now(UTC)
    old.superseded_by = new.id
    old.superseded_at = stamp
    apply_move(
        old, SUPERSEDED, by=by, owner=owner, now=stamp, replaced_by=str(new.id), **(mirror or {})
    )
    return old


# ── The memory side (settings.decision_lifecycle) ─────────────


def enabled() -> bool:
    """The memory side of the lifecycle is on (``settings.decision_lifecycle``)."""
    return bool(settings.decision_lifecycle)


async def _linked(
    session: AsyncSession,
    tenant_id: str,
    memory_id: Any,
    statuses: tuple[str, ...] | None = None,
) -> Decision | None:
    """The one decision of *tenant_id* whose ``properties.memory_id`` is *memory_id*.

    None when there is none or more than one (an ambiguous link moves nothing).
    """
    if memory_id is None:
        return None
    stmt = (
        select(Decision)
        .where(Decision.tenant_id == tenant_id)
        .where(Decision.properties[MEMORY_ID].astext == str(memory_id))
        .limit(2)
    )
    if statuses is not None:
        stmt = stmt.where(Decision.status.in_(statuses))
    rows = list((await session.execute(stmt)).scalars().all())
    return rows[0] if len(rows) == 1 else None


async def link_capture_memory(
    session: AsyncSession, tenant_id: str, decision: Any, capture_event_id: Any
) -> bool:
    """Tie *decision* to the one ``decision`` memory saved from the same capture.

    Only when exactly one such memory of the tenant exists and it is not
    linked yet; two decision memories from one message are ambiguous and
    nothing is linked. Returns whether a link was written. Off unless
    ``settings.decision_lifecycle``.
    """
    if not enabled() or capture_event_id is None:
        return False
    stmt = (
        select(Memory)
        .where(Memory.tenant_id == tenant_id)
        .where(Memory.capture_event_id == capture_event_id)
        .where(Memory.properties["fact_type"].astext == "decision")
        .limit(2)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    if len(rows) != 1:
        return False
    memory = rows[0]
    if memory.tenant_id != tenant_id or (memory.properties or {}).get(DECISION_ID):
        return False
    decision.properties = {**(decision.properties or {}), MEMORY_ID: str(memory.id)}
    memory.properties = {**(memory.properties or {}), DECISION_ID: str(decision.id)}
    return True


async def mirror_memory_supersede(
    session: AsyncSession, tenant_id: str, old_memory_id: Any, new_memory_id: Any
) -> bool:
    """Follow an applied memory supersede: the old memory's candidate is superseded.

    Only a *candidate* linked to the old memory moves, and only when the new
    memory has its own linked decision. A decided or reviewed decision is the
    owner's to supersede. Returns whether a decision moved. Off unless
    ``settings.decision_lifecycle``. A refusal (a loop, a vanished row) is
    logged, never raised: the memory supersede has already happened.
    """
    if not enabled():
        return False
    old = await _linked(session, tenant_id, old_memory_id, (CANDIDATE,))
    new = await _linked(session, tenant_id, new_memory_id)
    if old is None or new is None:
        return False
    try:
        await supersede(
            session,
            tenant_id,
            old.id,
            new.id,
            by=MIRROR_BY,
            mirror={"memory_old": str(old_memory_id), "memory_new": str(new_memory_id)},
        )
    except DomainError:
        logger.info("Decision mirror of a memory supersede refused", exc_info=True)
        return False
    return True


async def undo_memory_mirror(
    session: AsyncSession,
    tenant_id: str,
    *,
    old_memory_id: Any = None,
    new_memory_id: Any = None,
) -> int:
    """Take back the decision mirrors of a memory supersede that was undone.

    A decision moves back to ``candidate`` only while its newest trail entry is
    the system's own mirror for these memories: a later owner move is never
    overwritten. Give *old_memory_id*, *new_memory_id* or both. Returns how
    many decisions moved back. Off unless ``settings.decision_lifecycle``.
    """
    if not enabled() or (old_memory_id is None and new_memory_id is None):
        return 0
    stmt = (
        select(Decision)
        .where(Decision.tenant_id == tenant_id)
        .where(Decision.status == SUPERSEDED)
        .where(Decision.properties.has_key(LIFECYCLE))
    )
    rows = list((await session.execute(stmt)).scalars().all())
    now = datetime.now(UTC)
    moved = 0
    for d in rows:
        entries = trail(d.properties)
        last = entries[-1] if entries else {}
        if last.get("by") != MIRROR_BY or last.get("to") != SUPERSEDED:
            continue
        if old_memory_id is not None and last.get("memory_old") != str(old_memory_id):
            continue
        if new_memory_id is not None and last.get("memory_new") != str(new_memory_id):
            continue
        check(d.status, CANDIDATE, owner=False, mirror=True)
        d.superseded_by = None
        d.superseded_at = None
        apply_move(d, CANDIDATE, by=MIRROR_UNDO_BY, owner=False, now=now)
        moved += 1
    return moved


async def follow_memory_review(tenant_id: str, memory_id: Any, action: str, by: str | None) -> bool:
    """The owner kept (approve) or dropped (reject) a linked decision memory.

    Keep confirms the linked candidate (``decided``); drop discards it. Only
    for an owner ``by`` (a review stamp from api/approval_identity.resolver):
    an auto-kept memory never comes through here, and a service key's review
    moves nothing. Runs in its own session; logged, never raised, since the
    memory review has already happened. Off unless
    ``settings.decision_lifecycle``.
    """
    to = {"approve": DECIDED, "reject": DISCARDED}.get(action)
    if not enabled() or to is None or not is_owner_label(by):
        return False
    try:
        async with async_session() as session:
            d = await _linked(session, tenant_id, memory_id, (CANDIDATE,))
            if d is None:
                return False
            check(d.status, to, owner=True)
            apply_move(d, to, by=str(by), owner=True, now=datetime.now(UTC), via="memory_review")
            await session.commit()
            return True
    except Exception:  # noqa: BLE001 — the memory review itself stands
        logger.warning("Decision did not follow the memory review of %s", memory_id, exc_info=True)
        return False
