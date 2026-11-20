"""Approval queue service — create, resolve, expire, escalate.

Manages the Era-8 human-in-the-loop approval queue for autonomous actions,
reconciled to the real ``ApprovalQueueEntry`` model (table ``approval_queue``).
The link to the executed action is the reverse FK ``AutoAction.approval_id``
(there is no ``action_id`` column on the queue). See
docs/specs/era8-autonomy-reconciliation.md.

An entry with a linked ``AutoAction`` also has a copy in the unified feed
(``approvals``, ``kind="autonomous_action"``, ``source_ref`` = the entry id,
written by services/autonomous_approvals.py). Every resolution here closes
that copy in the same transaction, so the two never disagree about whether
the owner decided (docs/specs/approvals-feed.md, "Which store is
authoritative per kind"). Lock order everywhere: the feed copy first, then
the queue entry — the feed side (services/approvals.py) locks its row and
then resolves the queue, so taking them the other way round here could
deadlock the two.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select, update

from life_graph.autonomy.models import ApprovalQueueEntry, AutoAction
from life_graph.models.db import Approval

if TYPE_CHECKING:
    from collections.abc import Iterable

logger = logging.getLogger(__name__)

#: ``approvals.kind`` of a queue entry's copy in the unified feed.
FEED_KIND = "autonomous_action"
#: ``approval_queue.status`` -> ``approvals.status`` (the feed knows only
#: pending/approved/rejected): anything that is not an approval is a refusal.
FEED_STATUS_FOR = {
    "approved": "approved",
    "batch_approved": "approved",
    "rejected": "rejected",
    "expired": "rejected",
    "stale": "rejected",
}


class QueueConflictError(ValueError):
    """The decision clashes with the entry's state or its feed copy (HTTP 409).

    A ``ValueError`` so every caller that already catches that keeps working.
    """


class QueueAlreadyResolvedError(QueueConflictError):
    """The entry is no longer pending. ``status`` is what it was resolved to."""

    def __init__(self, status: str) -> None:
        self.status = status
        # The message is matched by older callers (services/approvals.py).
        super().__init__(f"Approval already resolved: {status}")


def _feed_note(queue_status: str, note: str | None) -> str:
    line = f"Resolved in autonomy queue ({queue_status})"
    return f"{line}\n{note}" if note else line


async def _lock_feed_copies(
    session, tenant_ids: Iterable[str], entry_ids: Iterable[str]
) -> tuple[set[str], set[str]]:
    """Lock the pending feed copies of *entry_ids*; return ``(locked, busy)``.

    Both sets hold queue entry ids (the copies' ``source_ref``). ``busy`` is a
    copy another transaction holds locked (``SKIP LOCKED`` — never waits), or
    one whose execution claim says an attempt is running right now
    (``payload.execution.state == "started"``, services/approvals.py): the
    feed is deciding that entry, so the queue must not.
    """

    ids = sorted({str(i) for i in entry_ids})
    tenants = sorted(set(tenant_ids))
    if not ids or not tenants:
        return set(), set()
    where = (
        Approval.tenant_id.in_(tenants),
        Approval.kind == FEED_KIND,
        Approval.source_ref.in_(ids),
        Approval.status == "pending",
    )
    existing = set((await session.execute(select(Approval.source_ref).where(*where))).scalars())
    if not existing:
        return set(), set()
    rows = (
        await session.execute(
            select(Approval.source_ref, Approval.payload)
            .where(*where)
            .with_for_update(skip_locked=True)
        )
    ).all()
    busy = existing - {ref for ref, _ in rows}
    locked: set[str] = set()
    for ref, payload in rows:
        claim = (payload or {}).get("execution")
        if isinstance(claim, dict) and claim.get("state") == "started":
            busy.add(ref)
        else:
            locked.add(ref)
    return locked, busy


async def _close_feed_copies(
    session,
    tenant_ids: Iterable[str],
    entry_ids: Iterable[str],
    queue_status: str,
    resolved_by: str,
    note: str | None,
    now: datetime,
) -> None:
    """Resolve the pending feed copies of *entry_ids* to match *queue_status*.

    One statement on ``source_ref``, run after the queue rows changed, so it
    also catches a copy the producer committed after :func:`_lock_feed_copies`
    looked. The producer skips an entry that is no longer pending; a copy
    that still races in after this commit is closed by
    :meth:`ApprovalService.reconcile_feed_copies`.
    """

    ids = sorted({str(i) for i in entry_ids})
    tenants = sorted(set(tenant_ids))
    if not ids or not tenants:
        return
    await session.execute(
        update(Approval)
        .where(
            Approval.tenant_id.in_(tenants),
            Approval.kind == FEED_KIND,
            Approval.source_ref.in_(ids),
            Approval.status == "pending",
        )
        .values(
            status=FEED_STATUS_FOR.get(queue_status, "rejected"),
            resolved_by=resolved_by,
            resolved_at=now,
            resolution_note=_feed_note(queue_status, note),
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )


def _serialize(entry) -> dict:
    """Serialize an ``ApprovalQueueEntry`` into the API response shape."""
    return {
        "id": str(entry.id),
        "tenant_id": entry.tenant_id,
        "agent_id": entry.agent_id,
        "project_id": entry.project_id,
        "action_name": entry.action_name,
        "action_command": entry.action_command,
        # B2: agent_task entries carry a natural-language instruction instead of
        # a shell command — without these two fields an API caller sees a null
        # action_command and no way to tell what the entry actually is.
        "kind": getattr(entry, "kind", None) or "command",
        "instruction": getattr(entry, "instruction", None),
        "risk_level": entry.risk_level,
        "category": entry.category,
        "trigger_type": entry.trigger_type,
        "trigger_detail": entry.trigger_detail,
        "estimated_impact": entry.estimated_impact,
        "status": entry.status,
        "priority": entry.priority,
        "resolved_by": entry.resolved_by,
        "requested_by": getattr(entry, "requested_by", None),
        "resolution_note": entry.resolution_note,
        "resolved_at": entry.resolved_at,
        "expires_at": entry.expires_at,
        "timeout_hours": entry.timeout_hours,
        "escalation_sent": entry.escalation_sent or [],
        "created_at": entry.created_at,
    }


class ApprovalService:
    """Manages the approval queue for autonomous actions.

    Supports:
    - Create approval entry with an optional notify-before window
    - Resolve (approve/reject) individual entries
    - Batch resolve by filter
    - Window checks (cron-driven): a passed notify-before window is handed
      to the owner, never auto-approved
    - Escalation at 1h/4h/12h (tracked in ``escalation_sent``)

    Every resolution closes the entry's feed copy in the same transaction
    (see the module docstring).
    """

    # Escalation thresholds in minutes
    ESCALATION_THRESHOLDS = [60, 240, 720]  # 1h, 4h, 12h

    def __init__(self, session_factory, audit_service=None):
        self._session_factory = session_factory
        self._audit_service = audit_service

    async def create(self, tenant_id: str, data: dict):
        """Create an approval queue entry.

        ``data`` carries real ``ApprovalQueueEntry`` field names
        (``action_name``, ``action_command``, ``kind``, ``instruction``,
        ``trigger_type``, ``trigger_detail``, ``risk_level``, ``project_id``,
        ``category``). ``auto_approve_minutes`` (optional; the name is kept
        for callers) sets ``expires_at``, the end of a notify-before window.
        When it passes, :meth:`check_expirations` tells the owner the entry
        still needs them; nothing is approved on a timer.
        """

        auto_approve_minutes = data.pop("auto_approve_minutes", None)
        expires_at = None
        if auto_approve_minutes:
            expires_at = datetime.now(UTC) + timedelta(minutes=auto_approve_minutes)

        # approval_queue.risk_level CHECK allows only moderate/dangerous; a "safe"
        # action queued for approval (e.g. at L0) is clamped to moderate here.
        risk_level = data.get("risk_level")
        if risk_level not in ("moderate", "dangerous"):
            risk_level = "moderate"

        entry_id = str(uuid.uuid4())

        async with self._session_factory() as session:
            entry = ApprovalQueueEntry(
                id=entry_id,
                tenant_id=tenant_id,
                agent_id=data["agent_id"],
                project_id=data.get("project_id"),
                action_name=data["action_name"],
                action_command=data["action_command"],
                kind=data.get("kind", "command"),
                instruction=data.get("instruction"),
                risk_level=risk_level,
                category=data.get("category", "general"),
                trigger_type=data.get("trigger_type", "manual"),
                trigger_detail=data.get("trigger_detail", ""),
                estimated_impact=data.get("estimated_impact"),
                requested_by=data.get("requested_by"),
                status="pending",
                expires_at=expires_at,
                created_at=datetime.now(UTC),
            )
            session.add(entry)
            await session.commit()
            await session.refresh(entry)

        return entry

    async def resolve(
        self,
        tenant_id: str,
        approval_id,
        decision: str,
        note: str | None,
        resolved_by: str,
        guard=None,
        *,
        close_feed: bool = True,
    ):
        """Resolve an approval (approve or reject).

        Sets the queue row's resolution fields and updates the linked
        ``AutoAction`` (found via ``AutoAction.approval_id``) to
        approved/rejected. *guard*, when given, is called with the entry's
        ``requested_by`` before anything is written (the HTTP route's
        self-approval check); if it raises, nothing changes.

        The entry's feed copy is closed in the same transaction. Only the feed
        itself passes ``close_feed=False``: it is resolving that copy, holds
        its lock, and records its own outcome on it.

        This does not run the action: approving here only clears it. The
        single execution path is the feed's approve (services/approvals.py,
        with its at-most-once claim); the HTTP route hands an entry with a
        feed copy to it instead of calling this.

        Raises:
            ValueError: no such entry for this tenant.
            QueueAlreadyResolvedError: the entry is no longer pending.
            QueueConflictError: the feed is resolving this entry right now.
        """

        approval_id = str(approval_id)
        now = datetime.now(UTC)
        # The ``also_trust`` keyword was accepted here and ignored; it is gone
        # (the route refuses it). Trust changes go through the owner-only
        # trust override instead.

        async with self._session_factory() as session:
            if close_feed:
                _, busy = await _lock_feed_copies(session, [tenant_id], [approval_id])
                if busy:
                    raise QueueConflictError(
                        "Approval is being resolved in the approvals feed; try again shortly"
                    )
            result = await session.execute(
                select(ApprovalQueueEntry)
                .where(
                    ApprovalQueueEntry.id == approval_id,
                    ApprovalQueueEntry.tenant_id == tenant_id,
                )
                .with_for_update()
            )
            entry = result.scalar_one_or_none()
            if not entry:
                raise ValueError(f"Approval {approval_id} not found")

            if entry.status != "pending":
                raise QueueAlreadyResolvedError(entry.status)

            if guard is not None:
                guard(getattr(entry, "requested_by", None))

            new_status = "approved" if decision == "approve" else "rejected"
            # Update approval
            await session.execute(
                update(ApprovalQueueEntry)
                .where(ApprovalQueueEntry.id == approval_id)
                .values(
                    status=new_status,
                    resolved_by=resolved_by,
                    resolved_at=now,
                    resolution_note=note,
                )
            )

            # Update the linked auto action (reverse FK: AutoAction.approval_id).
            # auto_actions has no approved/rejected status: approve leaves it
            # "pending" (cleared to run), reject marks it "skipped".
            new_action_status = "pending" if decision == "approve" else "skipped"
            linked = await session.execute(
                select(AutoAction.id).where(
                    AutoAction.approval_id == approval_id,
                    AutoAction.tenant_id == tenant_id,
                )
            )
            action_id = linked.scalars().first()
            if action_id is not None:
                await session.execute(
                    update(AutoAction)
                    .where(AutoAction.id == action_id)
                    .values(status=new_action_status)
                )

            if close_feed:
                await _close_feed_copies(
                    session, [tenant_id], [approval_id], new_status, resolved_by, note, now
                )

            await session.commit()

        # Audit log
        if self._audit_service:
            await self._audit_service.log_approval(
                tenant_id=tenant_id,
                approval_id=approval_id,
                action_id=action_id,
                decision=decision,
                resolved_by=resolved_by,
                note=note,
            )

        return entry

    async def batch_resolve(
        self,
        tenant_id: str,
        filter_criteria: dict,
        decision: str,
        note: str | None,
        resolved_by: str,
        guard=None,
    ):
        """Batch resolve approvals matching filter criteria.

        An ``approval_ids`` list, even an empty one, limits the batch to those
        ids (an empty list resolves nothing — it used to mean "no filter" and
        resolve everything pending). *guard*, when given, is called with each
        matched entry's ``requested_by`` before anything is written; if it
        raises, nothing is resolved (the self-approval check).

        Matching entries' feed copies are closed in the same transaction; if
        the feed is resolving any of them right now, nothing is resolved
        (``QueueConflictError``).
        """

        now = datetime.now(UTC)
        new_status = "approved" if decision == "approve" else "rejected"

        async with self._session_factory() as session:
            matched = [
                str(e.id) for e in await self._match_pending(session, tenant_id, filter_criteria)
            ]
            _, busy = await _lock_feed_copies(session, [tenant_id], matched)
            if busy:
                raise QueueConflictError(
                    f"{len(busy)} of these approvals are being resolved in the approvals"
                    " feed; nothing was resolved, try again shortly"
                )
            entries = []
            if matched:
                result = await session.execute(
                    select(ApprovalQueueEntry)
                    .where(
                        ApprovalQueueEntry.tenant_id == tenant_id,
                        ApprovalQueueEntry.id.in_(matched),
                        ApprovalQueueEntry.status == "pending",
                    )
                    .with_for_update()
                )
                entries = result.scalars().all()

            if guard is not None:
                for entry in entries:
                    guard(getattr(entry, "requested_by", None))

            new_action_status = "pending" if decision == "approve" else "skipped"
            resolved_ids = []
            for entry in entries:
                await session.execute(
                    update(ApprovalQueueEntry)
                    .where(ApprovalQueueEntry.id == entry.id)
                    .values(
                        status=new_status,
                        resolved_by=resolved_by,
                        resolved_at=now,
                        resolution_note=note,
                    )
                )
                await session.execute(
                    update(AutoAction)
                    .where(
                        AutoAction.approval_id == entry.id,
                        AutoAction.tenant_id == tenant_id,
                    )
                    .values(status=new_action_status)
                )
                resolved_ids.append(str(entry.id))

            await _close_feed_copies(
                session, [tenant_id], resolved_ids, new_status, resolved_by, note, now
            )
            await session.commit()

        return {"resolved_count": len(resolved_ids), "resolved_ids": resolved_ids}

    @staticmethod
    async def _match_pending(session, tenant_id: str, filter_criteria: dict) -> list:
        """Pending entries of *tenant_id* matching a batch's ids and filters."""

        q = select(ApprovalQueueEntry).where(
            ApprovalQueueEntry.tenant_id == tenant_id,
            ApprovalQueueEntry.status == "pending",
        )
        if filter_criteria.get("approval_ids") is not None:
            ids = [str(i) for i in filter_criteria["approval_ids"]]
            q = q.where(ApprovalQueueEntry.id.in_(ids))
        if filter_criteria.get("agent_id"):
            q = q.where(ApprovalQueueEntry.agent_id == filter_criteria["agent_id"])
        if filter_criteria.get("project_id"):
            q = q.where(ApprovalQueueEntry.project_id == filter_criteria["project_id"])
        if filter_criteria.get("risk_level"):
            q = q.where(ApprovalQueueEntry.risk_level == filter_criteria["risk_level"])
        return list((await session.execute(q)).scalars().all())

    async def status_of(self, tenant_id: str, approval_id: str) -> str | None:
        """The entry's status, or None when this tenant has no such entry."""

        async with self._session_factory() as session:
            return (
                await session.execute(
                    select(ApprovalQueueEntry.status).where(
                        ApprovalQueueEntry.id == str(approval_id),
                        ApprovalQueueEntry.tenant_id == tenant_id,
                    )
                )
            ).scalar_one_or_none()

    async def match_pending(self, tenant_id: str, filter_criteria: dict) -> list:
        """The pending entries a batch with *filter_criteria* would resolve."""
        async with self._session_factory() as session:
            return await self._match_pending(session, tenant_id, filter_criteria)

    async def pending_feed_copies(self, tenant_id: str, entry_ids: Iterable[str]) -> dict[str, str]:
        """``{entry id: feed approval id}`` for pending entries with a runnable feed copy.

        A copy is runnable when it is pending and names the ``AutoAction`` it
        would execute (``payload.auto_action_id``). Such an entry is decided
        in the feed (services/approvals.py): approving it there runs the
        action under the at-most-once claim and resolves this entry too,
        whereas approving it here alone would clear an action nothing runs.
        """

        ids = sorted({str(i) for i in entry_ids})
        if not ids:
            return {}
        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    select(Approval.source_ref, Approval.id, Approval.payload)
                    .join(
                        ApprovalQueueEntry,
                        (ApprovalQueueEntry.id == Approval.source_ref)
                        & (ApprovalQueueEntry.tenant_id == Approval.tenant_id),
                    )
                    .where(
                        Approval.tenant_id == tenant_id,
                        Approval.kind == FEED_KIND,
                        Approval.status == "pending",
                        Approval.source_ref.in_(ids),
                        ApprovalQueueEntry.status == "pending",
                    )
                )
            ).all()
        return {
            str(ref): str(feed_id)
            for ref, feed_id, payload in rows
            if (payload or {}).get("auto_action_id")
        }

    async def check_expirations(self) -> int:
        """Hand entries whose notify-before window has passed to the owner. Returns count.

        This used to mark them approved ("Auto-approved after timeout") — but
        nothing then ran the action (the only execution path is the feed's
        approve), so the entry said approved, the action stayed pending for
        ever, and its feed copy stayed pending too. It no longer approves
        anything on a timer: CHARTER.md §5, "the failure mode of any missing
        configuration is asking the human, not acting". Running the action
        here instead would make a cron the approver of a moderate host
        command with nobody watching; marking it expired would silently drop
        every L2 action the owner did not answer within five minutes, making
        L2 stricter than L1. So the window simply ends: ``expires_at`` is
        cleared, the entry (and its feed copy) stays pending like any L1
        approval, the owner is notified, and the usual stale rule
        (:meth:`expire_stale`) still applies.

        Intentionally cross-tenant: this runs as a system cron
        (workers.tasks.check_approval_timeouts) with no tenant context, and
        sweeps every tenant in one pass. See tests/unit/test_tenant_scoping.py,
        which allowlists it by name rather than tolerating unscoped queries
        generally.
        """

        now = datetime.now(UTC)

        async with self._session_factory() as session:
            result = await session.execute(
                select(ApprovalQueueEntry)
                .where(
                    ApprovalQueueEntry.status == "pending",
                    ApprovalQueueEntry.expires_at.isnot(None),
                    ApprovalQueueEntry.expires_at <= now,
                )
                .with_for_update(skip_locked=True)
            )
            passed = [(str(e.id), e.tenant_id, e.action_name) for e in result.scalars().all()]
            if passed:
                await session.execute(
                    update(ApprovalQueueEntry)
                    .where(
                        ApprovalQueueEntry.id.in_([entry_id for entry_id, _, _ in passed]),
                        ApprovalQueueEntry.status == "pending",
                    )
                    .values(expires_at=None)
                    .execution_options(synchronize_session=False)
                )
            await session.commit()

        for entry_id, tenant_id, action_name in passed:
            await self._notify_window_passed(tenant_id, entry_id, action_name)

        logger.info(
            "Checked approval windows: %d notify-before window(s) passed, handed to the owner",
            len(passed),
        )
        return len(passed)

    @staticmethod
    async def _notify_window_passed(tenant_id: str, entry_id: str, action_name: str) -> None:
        """Tell the owner a notify-before entry is waiting on them. Never raises."""
        try:
            from life_graph.runtime import get_notification_engine

            await get_notification_engine().create(
                tenant_id,
                f"Needs your approval: {action_name}",
                body=(
                    "Its notify-before window passed. Nothing ran on its own; it waits"
                    " in Approvals until you approve or reject it."
                ),
                priority="important",
                source_type="autonomous_action",
                deliver_at_brief=False,
                metadata={"approval_id": entry_id},
            )
        except Exception:
            logger.warning(
                "Could not notify that approval %s's window passed", entry_id, exc_info=True
            )

    async def expire_stale(self, max_age_days: int) -> int:
        """Mark pending entries older than *max_age_days* ``stale``. Returns count.

        A queue nobody clears is not a gate: an entry that waited two weeks
        was never going to be approved, and it buries the ones that might be.
        Stale is a refusal, never an approval — the linked ``AutoAction`` is
        skipped, as on reject. Asking again files a fresh entry. The feed copy
        is closed as rejected in the same transaction; an entry whose copy the
        feed is resolving right now is left for the next pass.

        Intentionally cross-tenant, like :meth:`check_expirations`: a system
        cron with no tenant context (see tests/unit/test_tenant_scoping.py).
        """

        if max_age_days <= 0:
            return 0
        now = datetime.now(UTC)
        cutoff = now - timedelta(days=max_age_days)
        note = f"No decision in {max_age_days} days; ask again if still wanted"

        async with self._session_factory() as session:
            candidates = (
                await session.execute(
                    select(ApprovalQueueEntry.id, ApprovalQueueEntry.tenant_id).where(
                        ApprovalQueueEntry.status == "pending",
                        ApprovalQueueEntry.created_at <= cutoff,
                    )
                )
            ).all()
            _, busy = await _lock_feed_copies(
                session, {t for _, t in candidates}, [str(i) for i, _ in candidates]
            )
            wanted = [str(i) for i, _ in candidates if str(i) not in busy]
            stale = []
            if wanted:
                stale = (
                    await session.execute(
                        select(ApprovalQueueEntry.id, ApprovalQueueEntry.tenant_id)
                        .where(
                            ApprovalQueueEntry.id.in_(wanted),
                            ApprovalQueueEntry.status == "pending",
                        )
                        .with_for_update(skip_locked=True)
                    )
                ).all()
            for entry_id, tenant_id in stale:
                await session.execute(
                    update(ApprovalQueueEntry)
                    .where(ApprovalQueueEntry.id == entry_id)
                    .values(
                        status="stale",
                        resolved_by="system",
                        resolved_at=now,
                        resolution_note=note,
                    )
                )
                await session.execute(
                    update(AutoAction)
                    .where(AutoAction.approval_id == entry_id, AutoAction.tenant_id == tenant_id)
                    .values(status="skipped")
                )
            await _close_feed_copies(
                session,
                {t for _, t in stale},
                [str(i) for i, _ in stale],
                "stale",
                "system",
                note,
                now,
            )
            await session.commit()

        if stale:
            logger.info("Marked %d approval(s) stale after %d days", len(stale), max_age_days)
        return len(stale)

    async def reconcile_feed_copies(self) -> int:
        """Close feed copies left pending by an entry resolved before copies were closed.

        Until 2026-11-20 nothing on this side touched the copy, so rows exist
        whose entry was approved (by the queue route or the old timeout),
        rejected or marked stale while the copy still says pending. Closed to
        match, except one case left open on purpose: an approved entry whose
        action is still ``pending`` — never run, and approving the copy is
        what runs it (a reject there answers 409, services/approvals.py).
        Returns the number of copies closed.

        Intentionally cross-tenant, like :meth:`check_expirations`: a system
        cron with no tenant context (see tests/unit/test_tenant_scoping.py).
        """

        now = datetime.now(UTC)
        closed = 0
        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    select(
                        ApprovalQueueEntry.id,
                        ApprovalQueueEntry.tenant_id,
                        ApprovalQueueEntry.status,
                        ApprovalQueueEntry.resolved_by,
                    )
                    .join(
                        Approval,
                        (Approval.source_ref == ApprovalQueueEntry.id)
                        & (Approval.tenant_id == ApprovalQueueEntry.tenant_id),
                    )
                    .where(
                        Approval.kind == FEED_KIND,
                        Approval.status == "pending",
                        ApprovalQueueEntry.status != "pending",
                    )
                )
            ).all()
            if not rows:
                return 0
            runnable = set(
                (
                    await session.execute(
                        select(AutoAction.approval_id).where(
                            AutoAction.approval_id.in_([str(r[0]) for r in rows]),
                            AutoAction.tenant_id.in_({r[1] for r in rows}),
                            AutoAction.status == "pending",
                        )
                    )
                ).scalars()
            )
            todo = [
                r
                for r in rows
                if not (FEED_STATUS_FOR.get(r[2]) == "approved" and str(r[0]) in runnable)
            ]
            _, busy = await _lock_feed_copies(
                session, {r[1] for r in todo}, [str(r[0]) for r in todo]
            )
            for entry_id, tenant_id, status, resolved_by in todo:
                if str(entry_id) in busy:
                    continue
                await _close_feed_copies(
                    session,
                    [tenant_id],
                    [str(entry_id)],
                    status,
                    resolved_by or "system",
                    "closed by reconcile: the queue entry was resolved first",
                    now,
                )
                closed += 1
            await session.commit()
        if closed:
            logger.warning("Closed %d feed copies left pending by the autonomy queue", closed)
        return closed

    async def send_escalations(self) -> int:
        """Escalate long-pending approvals at 1h/4h/12h.

        Tracks which thresholds have already fired in the ``escalation_sent``
        JSONB list so each threshold escalates at most once.
        Returns count of entries escalated this pass.
        """

        now = datetime.now(UTC)
        escalated_count = 0

        async with self._session_factory() as session:
            # Cross-tenant by design — a system cron sweeping every tenant.
            result = await session.execute(
                select(ApprovalQueueEntry).where(
                    ApprovalQueueEntry.status == "pending",
                )
            )
            pending = result.scalars().all()

            for entry in pending:
                age_minutes = (now - entry.created_at).total_seconds() / 60
                already = set(entry.escalation_sent or [])
                newly = {
                    t for t in self.ESCALATION_THRESHOLDS if age_minutes >= t and t not in already
                }
                if newly:
                    merged = sorted(already | newly)
                    await session.execute(
                        update(ApprovalQueueEntry)
                        .where(ApprovalQueueEntry.id == entry.id)
                        .values(escalation_sent=merged)
                    )
                    escalated_count += 1
                    logger.warning(
                        "Escalated approval %s (age: %.0f min, thresholds: %s)",
                        entry.id,
                        age_minutes,
                        sorted(newly),
                    )

            await session.commit()

        logger.info("Escalation check: %d entries escalated", escalated_count)
        return escalated_count
