"""Supersession: one memory replaced by another, and the undo (ADR M8 §5.2).

Every writer that replaces a memory goes through :func:`apply`, and every
writer that takes a replacement back goes through :func:`undo` or
:func:`restore_replaced_by`. Before 2026-11-28 the same few column writes were
copied by hand into five places (``MemoryManager.supersede``,
``tools/memory_search.py`` ``_supersede``, the approvals' deferred supersede,
merge and undo). This module holds them once, with no change in what they
write.

A supersede writes, on rows of ONE tenant only:

- old: ``status = 'superseded'``, ``superseded_by = new.id``,
  ``updated_at = now`` and ``properties.superseded_at`` (when we stopped
  believing it; retrieval.is_known_at reads it), plus any *note* keys
  (a merge adds ``merged_into``);
- new: ``supersedes = old.id``, and ``status = 'active'`` when asked to.

It does NOT write ``valid_until``: a supersede ends our belief, not (by
itself) the old fact's truth in the world. Ending the world time on a real
world change is ADR step 5; the ``world_change`` parameter is its seam and
must stay ``False`` until then.

It writes no approval and emits no event. Each caller still files its own
contradiction approval, as before.

Decisions follow (ADR M8 §5.4, only with ``settings.decision_lifecycle``):
after an applied supersede the caller awaits :func:`mirror_decisions`, and
after an undo :func:`undo_decision_mirror` (:func:`restore_replaced_by` does
it itself). A *candidate* decision linked to the old memory is then
superseded by the new memory's decision, and the undo takes it back. With
the setting off both return at once and read nothing.

Callers keep their own rules through parameters: which old and new statuses
are allowed (``old_statuses`` / ``new_statuses``), whether the new memory is
activated, and whether the rows are locked while they are read (:func:`load`).
The functions only change ORM objects; the caller's session commits or
flushes, so the supersede lands in the caller's one transaction.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select, text

from life_graph.models.db import Memory
from life_graph.services import decision_lifecycle

if TYPE_CHECKING:
    from collections.abc import Mapping

    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Statuses a new memory may have for the approvals' deferred supersede.
PENDING_OR_ACTIVE = ("pending", "active")


def _as_uuid(value: Any) -> uuid.UUID | None:
    """*value* as a UUID, or None when it is not one."""
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


async def load(
    session: AsyncSession,
    tenant_id: str,
    old_id: Any,
    new_id: Any,
    *,
    lock: bool = False,
) -> tuple[Memory | None, Memory | None]:
    """The old and new memories, each only if it belongs to *tenant_id*.

    A missing id, an id that is not a UUID, or a row of another tenant comes
    back as None, so :func:`apply` refuses it. ``lock`` takes a row lock
    (``FOR UPDATE``) on both rows until the caller's transaction ends: what a
    single ``UPDATE ... WHERE status = 'active'`` gave the correction path,
    so two replacements of one fact cannot both win.
    """
    ids = [i for i in (_as_uuid(old_id), _as_uuid(new_id)) if i is not None]
    if not ids:
        return None, None
    query = (
        select(Memory)
        .where(Memory.id.in_(ids), Memory.tenant_id == tenant_id)
        # One order for every caller: two locks taken in the same order
        # cannot deadlock each other.
        .order_by(Memory.id)
    )
    if lock:
        query = query.with_for_update()
    rows = {row.id: row for row in (await session.execute(query)).scalars().all()}
    return rows.get(_as_uuid(old_id)), rows.get(_as_uuid(new_id))


def apply(
    tenant_id: str,
    old: Memory | None,
    new: Memory | None,
    *,
    why: str,
    old_statuses: tuple[str, ...] | None = ("active",),
    new_statuses: tuple[str, ...] | None = None,
    activate_new: bool = False,
    note: Mapping[str, Any] | None = None,
    world_change: bool = False,
    now: datetime | None = None,
) -> bool:
    """Mark *old* replaced by *new*. Returns whether it happened.

    Refused (nothing changes) when either memory is missing, either is not
    *tenant_id*'s, they are the same row, *old*'s status is not in
    ``old_statuses`` or *new*'s is not in ``new_statuses`` (``None`` means
    any status). ``activate_new`` makes *new* active too (the owner agreeing
    that it replaces the old one is agreeing to it). ``note`` adds keys to
    *old*'s properties, such as a merge's ``merged_into``.

    ``why`` is only logged. ``world_change`` is ADR M8 step 5's seam (end the
    old fact's world time at the new one's start); it is not built yet.
    """
    if world_change:
        raise NotImplementedError("Ending the world time on a supersede is ADR M8 step 5.")
    refused = _refusal(tenant_id, old, new, old_statuses, new_statuses)
    if refused is not None or old is None or new is None:
        logger.debug("Supersede refused (%s): %s", refused, why)
        return False
    stamp = now or datetime.now(UTC)
    if activate_new:
        new.status = "active"
    old.status = "superseded"
    old.superseded_by = new.id
    old.updated_at = stamp
    # Reassigned, never mutated: an in-place change of a JSONB dict is not
    # change-tracked by the ORM.
    old.properties = {
        **(old.properties or {}),
        **(note or {}),
        "superseded_at": stamp.isoformat(),
    }
    new.supersedes = old.id
    logger.debug("Superseded %s -> %s: %s", str(old.id)[:8], str(new.id)[:8], why)
    return True


def _refusal(
    tenant_id: str,
    old: Memory | None,
    new: Memory | None,
    old_statuses: tuple[str, ...] | None,
    new_statuses: tuple[str, ...] | None,
) -> str | None:
    """Why :func:`apply` must not act, or None when it may."""
    if old is None or new is None:
        return "missing"
    if old.tenant_id != tenant_id or new.tenant_id != tenant_id:
        return "other tenant"
    if old.id == new.id:
        return "same memory"
    if old_statuses is not None and old.status not in old_statuses:
        return f"old is {old.status}"
    if new_statuses is not None and new.status not in new_statuses:
        return f"new is {new.status}"
    return None


def undo(tenant_id: str, old: Memory | None, new: Memory | None) -> bool:
    """Take back the supersede of *old* by *new* (a rejected contradiction).

    Only while *old* is still in the state :func:`apply` left it: superseded,
    and by *new* when *new* is given (a later edit is never overwritten).
    *old* becomes active again, loses ``superseded_by`` and
    ``properties.superseded_at``, and *new* loses ``supersedes`` when it
    points at *old*. Returns whether anything was restored.
    """
    if old is None or old.tenant_id != tenant_id:
        return False
    if new is not None and new.tenant_id != tenant_id:
        return False  # never read or write another tenant's row
    if old.status != "superseded":
        return False
    if new is not None and old.superseded_by != new.id:
        return False
    old.status = "active"
    old.superseded_by = None
    # Undone on every timeline: without this the restored fact still read as
    # replaced to a question "as of now" (retrieval.is_known_at).
    old.properties = {k: v for k, v in (old.properties or {}).items() if k != "superseded_at"}
    if new is not None and new.supersedes == old.id:
        new.supersedes = None
    return True


async def mirror_decisions(
    session: AsyncSession, tenant_id: str, old: Memory | None, new: Memory | None
) -> bool:
    """After :func:`apply` of *old* by *new*: the linked candidate decision follows.

    services/decision_lifecycle.py ``mirror_memory_supersede``; does nothing
    unless ``settings.decision_lifecycle``. Same session, so the decision
    moves in the memory supersede's own transaction.
    """
    if old is None or new is None:
        return False
    return await decision_lifecycle.mirror_memory_supersede(session, tenant_id, old.id, new.id)


async def undo_decision_mirror(
    session: AsyncSession, tenant_id: str, *, old_id: Any = None, new_id: Any = None
) -> int:
    """After :func:`undo`: the decisions that mirrored that supersede move back.

    services/decision_lifecycle.py ``undo_memory_mirror``; does nothing unless
    ``settings.decision_lifecycle``.
    """
    return await decision_lifecycle.undo_memory_mirror(
        session, tenant_id, old_memory_id=old_id, new_memory_id=new_id
    )


async def restore_replaced_by(session: AsyncSession, tenant_id: str, new_id: Any) -> None:
    """Bring back every memory of *tenant_id* that *new_id* replaced.

    For taking a saved or corrected memory back (api/jarvis.py undo_save,
    the memory page's drop): what it replaced is current again. A
    near-duplicate merged into it (``merged_into``) is not an earlier value
    and stays folded away. *new_id*'s own ``supersedes`` is left as it is.
    Runs in the caller's transaction; the caller commits.
    """
    await session.execute(
        text(
            # superseded_at goes too: an undo restores the old value as
            # current belief on every timeline (retrieval.is_known_at).
            "UPDATE memories SET status = 'active', superseded_by = NULL, updated_at = NOW(),"
            " properties = COALESCE(properties, '{}'::jsonb) - 'superseded_at'"
            " WHERE tenant_id = :t AND superseded_by = :id AND status = 'superseded'"
            " AND NOT (COALESCE(properties, '{}'::jsonb) ? 'merged_into')"
        ),
        {"id": new_id, "t": tenant_id},
    )
    await undo_decision_mirror(session, tenant_id, new_id=new_id)
