"""Approve / reject a memory: the review queue's state machine.

It lived in ``api/memories.py`` as ``_transition``, and the memory page
(services/memory/page.py) imported that router to reject a pending memory
(audit M12). It lives here now; ``POST /memories/{id}/approve|reject``, the
bulk endpoint, the memory page and ``/jarvis`` all go through
:func:`transition`. Failures are :class:`MemoryTransitionError`, carrying the
HTTP status the routes always answered (404 missing, 409 invalid move).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from life_graph.core.events import EventType, event_bus
from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.schemas import MemoryUpdate

if TYPE_CHECKING:
    import uuid

    from life_graph.models.db import Memory
    from life_graph.storage.postgres import PostgresMemoryStore

logger = logging.getLogger(__name__)


class MemoryTransitionError(Exception):
    """A transition that cannot apply: ``status`` is the HTTP code to answer with."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


async def settle_contradictions(memory_id: uuid.UUID, *, approved: bool) -> None:
    """Apply (approve) or close (reject) the memory's deferred supersedes.

    A pending memory that contradicts an active one supersedes nothing until
    the owner approves it (review 2026-10-22: the old one used to be marked
    superseded at ingest, and rejecting the new memory never restored it).
    Logged, never raised: the approve/reject itself has already happened,
    and an unapplied supersede stays on the contradiction approval for the
    owner to apply there.
    """
    from life_graph.services.approvals import ApprovalService
    from life_graph.storage.database import async_session

    try:
        async with async_session() as session:
            service = ApprovalService(session)
            tenant_id = get_current_tenant_id()
            if approved:
                await service.on_memory_approved(tenant_id, str(memory_id))
            else:
                await service.on_memory_rejected(tenant_id, str(memory_id))
            await session.commit()
    except Exception:
        logger.warning("Failed to settle contradictions for %s", memory_id, exc_info=True)


async def learn_names(row: Memory) -> None:
    """Learn other names and roles ("my wife Priya") from a memory the owner
    has just approved. At storage time only active facts in the owner's own
    words teach names (MemoryManager._learn_names), and most captured facts wait
    for review, so the people table never learned a role in real use (prod,
    2026-11-02: 0 of 41 entities had one). The owner has now read and kept this
    exact sentence. Hedged or negated memories still teach nothing.
    Best-effort: a failure costs the alias, never the approval."""
    from life_graph.core.memory_manager import HEDGED

    props = row.properties or {}
    content = row.content or ""
    if (
        not content
        or props.get("polarity") == "negate"
        or props.get("certainty") == "hedged"
        or HEDGED.search(content)
    ):
        return
    from life_graph.services import entities

    try:
        await entities.learn_aliases(row.tenant_id, content, evidence=content)
    except Exception:  # noqa: BLE001
        logger.warning("Name learning failed for approved memory %s", row.id, exc_info=True)


async def transition(
    memory_id: uuid.UUID,
    action: str,
    store: PostgresMemoryStore,
    *,
    confirm_as_owner_fact: bool = False,
    actor: str | None = None,
) -> Memory:
    """Move a memory between pending/rejected/active, emitting the matching event.

    Idempotent when already in the target status.

    Raises:
        MemoryTransitionError: 404 if missing; 409 if the requested
            transition isn't valid from the memory's current status.
    """
    row = await store.retrieve(memory_id)
    if row is None:
        raise MemoryTransitionError(404, "Memory not found")
    from life_graph.services import profile_card

    profile_card.invalidate(row.tenant_id)  # Keep or Drop changes what the card holds
    if action == "approve":
        if row.status == "active":
            return row  # idempotent
        if row.status not in ("pending", "rejected"):
            raise MemoryTransitionError(409, f"Cannot approve a {row.status} memory")
        if confirm_as_owner_fact:
            # The owner read this in the review queue and says it is their own
            # fact. Stamped server-side (``server_side=True``, never from a
            # properties patch) so it records who confirmed, and only here:
            # nothing promotes outside content to the owner's word on its own.
            # ``actor`` is how the server recognised the caller, so the record
            # names a credential rather than the bare word "owner" — the
            # endpoint has already refused any ingress that is not the
            # owner's, and this is the audit trail of which one it was.
            from life_graph.core import evidence as ev

            confirmed = ev.confirm_from_owner(
                row.properties or {},
                by=actor or "owner",
                target_id=str(memory_id),
                evidence=ev.confirmation_evidence(
                    row.content, row.source_type, row.trust_tier, row.properties
                ),
            )
            updated = await store.update(
                memory_id,
                MemoryUpdate(status="active", properties=confirmed),
                server_side=True,
            )
        else:
            updated = await store.update(memory_id, MemoryUpdate(status="active"))
        await settle_contradictions(memory_id, approved=True)
        await learn_names(row)
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
        raise MemoryTransitionError(409, f"Cannot reject a {row.status} memory")
    updated = await store.update(memory_id, MemoryUpdate(status="rejected"))
    await settle_contradictions(memory_id, approved=False)
    try:
        await event_bus.emit(
            EventType.MEMORY_REJECTED,
            {"id": str(memory_id), "tenant_id": get_current_tenant_id()},
            source="memories",
        )
    except Exception:
        logger.warning("Failed to emit MEMORY_REJECTED for %s", memory_id, exc_info=True)
    return updated
