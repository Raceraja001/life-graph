"""Approval queue service — create, resolve, expire, escalate.

Manages the Era-8 human-in-the-loop approval queue for autonomous actions,
reconciled to the real ``ApprovalQueueEntry`` model (table ``approval_queue``).
The link to the executed action is the reverse FK ``AutoAction.approval_id``
(there is no ``action_id`` column on the queue). See
docs/specs/era8-autonomy-reconciliation.md.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

logger = logging.getLogger(__name__)


def _serialize(entry) -> dict:
    """Serialize an ``ApprovalQueueEntry`` into the API response shape."""
    return {
        "id": str(entry.id),
        "tenant_id": entry.tenant_id,
        "agent_id": entry.agent_id,
        "project_id": entry.project_id,
        "action_name": entry.action_name,
        "action_command": entry.action_command,
        "risk_level": entry.risk_level,
        "category": entry.category,
        "trigger_type": entry.trigger_type,
        "trigger_detail": entry.trigger_detail,
        "estimated_impact": entry.estimated_impact,
        "status": entry.status,
        "priority": entry.priority,
        "resolved_by": entry.resolved_by,
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
    - Create approval entry with optional auto-approve expiration
    - Resolve (approve/reject) individual entries
    - Batch resolve by filter
    - Expiration checks (cron-driven)
    - Escalation at 1h/4h/12h (tracked in ``escalation_sent``)
    """

    # Escalation thresholds in minutes
    ESCALATION_THRESHOLDS = [60, 240, 720]  # 1h, 4h, 12h

    def __init__(self, session_factory, audit_service=None):
        self._session_factory = session_factory
        self._audit_service = audit_service

    async def create(self, tenant_id: str, data: dict):
        """Create an approval queue entry.

        ``data`` carries real ``ApprovalQueueEntry`` field names
        (``action_name``, ``action_command``, ``trigger_type``, ``trigger_detail``,
        ``risk_level``, ``project_id``, ``category``). ``auto_approve_minutes``
        (optional) sets an auto-approve ``expires_at``.
        """
        from life_graph.autonomy.models import ApprovalQueueEntry

        auto_approve_minutes = data.pop("auto_approve_minutes", None)
        expires_at = None
        if auto_approve_minutes:
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=auto_approve_minutes)

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
                risk_level=risk_level,
                category=data.get("category", "general"),
                trigger_type=data.get("trigger_type", "manual"),
                trigger_detail=data.get("trigger_detail", ""),
                estimated_impact=data.get("estimated_impact"),
                status="pending",
                expires_at=expires_at,
                created_at=datetime.now(timezone.utc),
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
        also_trust: bool = False,
    ):
        """Resolve an approval (approve or reject).

        Sets the queue row's resolution fields and updates the linked
        ``AutoAction`` (found via ``AutoAction.approval_id``) to
        approved/rejected.
        """
        from life_graph.autonomy.models import ApprovalQueueEntry, AutoAction

        approval_id = str(approval_id)
        now = datetime.now(timezone.utc)

        async with self._session_factory() as session:
            result = await session.execute(
                select(ApprovalQueueEntry).where(
                    ApprovalQueueEntry.id == approval_id,
                    ApprovalQueueEntry.tenant_id == tenant_id,
                )
            )
            entry = result.scalar_one_or_none()
            if not entry:
                raise ValueError(f"Approval {approval_id} not found")

            if entry.status != "pending":
                raise ValueError(f"Approval already resolved: {entry.status}")

            # Update approval
            await session.execute(
                update(ApprovalQueueEntry)
                .where(ApprovalQueueEntry.id == approval_id)
                .values(
                    status="approved" if decision == "approve" else "rejected",
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
    ):
        """Batch resolve approvals matching filter criteria."""
        from life_graph.autonomy.models import ApprovalQueueEntry, AutoAction

        now = datetime.now(timezone.utc)

        async with self._session_factory() as session:
            q = select(ApprovalQueueEntry).where(
                ApprovalQueueEntry.tenant_id == tenant_id,
                ApprovalQueueEntry.status == "pending",
            )

            if filter_criteria.get("approval_ids"):
                ids = [str(i) for i in filter_criteria["approval_ids"]]
                q = q.where(ApprovalQueueEntry.id.in_(ids))
            if filter_criteria.get("agent_id"):
                q = q.where(ApprovalQueueEntry.agent_id == filter_criteria["agent_id"])
            if filter_criteria.get("project_id"):
                q = q.where(ApprovalQueueEntry.project_id == filter_criteria["project_id"])
            if filter_criteria.get("risk_level"):
                q = q.where(ApprovalQueueEntry.risk_level == filter_criteria["risk_level"])

            result = await session.execute(q)
            entries = result.scalars().all()

            new_action_status = "pending" if decision == "approve" else "skipped"
            resolved_ids = []
            for entry in entries:
                await session.execute(
                    update(ApprovalQueueEntry)
                    .where(ApprovalQueueEntry.id == entry.id)
                    .values(
                        status="approved" if decision == "approve" else "rejected",
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

            await session.commit()

        return {"resolved_count": len(resolved_ids), "resolved_ids": resolved_ids}

    async def check_expirations(self) -> int:
        """Auto-approve expired (notify-before) entries. Returns count."""
        from life_graph.autonomy.models import ApprovalQueueEntry, AutoAction

        now = datetime.now(timezone.utc)
        expired_count = 0

        async with self._session_factory() as session:
            result = await session.execute(
                select(ApprovalQueueEntry).where(
                    ApprovalQueueEntry.status == "pending",
                    ApprovalQueueEntry.expires_at.isnot(None),
                    ApprovalQueueEntry.expires_at <= now,
                )
            )
            expired = result.scalars().all()

            for entry in expired:
                await session.execute(
                    update(ApprovalQueueEntry)
                    .where(ApprovalQueueEntry.id == entry.id)
                    .values(
                        status="approved",  # ck_aq_status has no 'auto_approved'
                        resolved_by="system",
                        resolved_at=now,
                        resolution_note="Auto-approved after timeout",
                    )
                )
                await session.execute(
                    update(AutoAction)
                    .where(
                        AutoAction.approval_id == entry.id,
                        AutoAction.tenant_id == entry.tenant_id,
                    )
                    .values(status="pending")  # cleared to run
                )
                expired_count += 1

            await session.commit()

        logger.info("Checked approval expirations: %d auto-approved", expired_count)
        return expired_count

    async def send_escalations(self) -> int:
        """Escalate long-pending approvals at 1h/4h/12h.

        Tracks which thresholds have already fired in the ``escalation_sent``
        JSONB list so each threshold escalates at most once.
        Returns count of entries escalated this pass.
        """
        from life_graph.autonomy.models import ApprovalQueueEntry

        now = datetime.now(timezone.utc)
        escalated_count = 0

        async with self._session_factory() as session:
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
                    t for t in self.ESCALATION_THRESHOLDS
                    if age_minutes >= t and t not in already
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
                        entry.id, age_minutes, sorted(newly),
                    )

            await session.commit()

        logger.info("Escalation check: %d entries escalated", escalated_count)
        return escalated_count
