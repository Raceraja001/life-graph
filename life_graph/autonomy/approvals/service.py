"""Approval queue service — create, resolve, expire, escalate.

Manages the human-in-the-loop approval queue for autonomous actions.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

logger = logging.getLogger(__name__)


class ApprovalService:
    """Manages approval queue for autonomous actions.

    Supports:
    - Create approval entry with expiration
    - Resolve (approve/reject) individual entries
    - Batch resolve by filter
    - Expiration checks (cron-driven)
    - Escalation at 1h/4h/12h
    """

    # Escalation thresholds in minutes
    ESCALATION_THRESHOLDS = [60, 240, 720]  # 1h, 4h, 12h

    def __init__(self, session_factory, audit_service=None):
        self._session_factory = session_factory
        self._audit_service = audit_service

    async def create(self, tenant_id: str, data: dict):
        """Create an approval queue entry.

        Args:
            tenant_id: The tenant context.
            data: Dict with action_id, agent_id, project_id, etc.

        Returns:
            The created ApprovalQueue record.
        """
        from life_graph.models.db import ApprovalQueue

        auto_approve_minutes = data.pop("auto_approve_minutes", None)
        expires_at = None
        if auto_approve_minutes:
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=auto_approve_minutes)

        entry_id = uuid.uuid4()

        async with self._session_factory() as session:
            entry = ApprovalQueue(
                id=entry_id,
                tenant_id=tenant_id,
                action_id=data["action_id"],
                agent_id=data["agent_id"],
                project_id=data["project_id"],
                action_type=data["action_type"],
                risk_level=data["risk_level"],
                command=data["command"],
                description=data.get("description", ""),
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
        approval_id: uuid.UUID,
        decision: str,
        note: str | None,
        resolved_by: str,
        also_trust: bool = False,
    ):
        """Resolve an approval (approve or reject).

        If approved, triggers execution of the associated auto action.
        """
        from life_graph.models.db import ApprovalQueue, AutoAction

        now = datetime.now(timezone.utc)

        async with self._session_factory() as session:
            result = await session.execute(
                select(ApprovalQueue).where(
                    ApprovalQueue.id == approval_id,
                    ApprovalQueue.tenant_id == tenant_id,
                )
            )
            entry = result.scalar_one_or_none()
            if not entry:
                raise ValueError(f"Approval {approval_id} not found")

            if entry.status != "pending":
                raise ValueError(f"Approval already resolved: {entry.status}")

            # Update approval
            await session.execute(
                update(ApprovalQueue)
                .where(ApprovalQueue.id == approval_id)
                .values(
                    status=f"{decision}d",  # approved / rejected
                    resolved_by=resolved_by,
                    resolved_at=now,
                    decision_note=note,
                )
            )

            # Update the auto action status
            new_action_status = "approved" if decision == "approve" else "rejected"
            await session.execute(
                update(AutoAction)
                .where(AutoAction.id == entry.action_id)
                .values(status=new_action_status)
            )

            await session.commit()

        # Audit log
        if self._audit_service:
            await self._audit_service.log_approval(
                tenant_id=tenant_id,
                approval_id=approval_id,
                action_id=entry.action_id,
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
        from life_graph.models.db import ApprovalQueue

        now = datetime.now(timezone.utc)

        async with self._session_factory() as session:
            q = select(ApprovalQueue).where(
                ApprovalQueue.tenant_id == tenant_id,
                ApprovalQueue.status == "pending",
            )

            if filter_criteria.get("approval_ids"):
                q = q.where(ApprovalQueue.id.in_(filter_criteria["approval_ids"]))
            if filter_criteria.get("agent_id"):
                q = q.where(ApprovalQueue.agent_id == filter_criteria["agent_id"])
            if filter_criteria.get("project_id"):
                q = q.where(ApprovalQueue.project_id == filter_criteria["project_id"])
            if filter_criteria.get("risk_level"):
                q = q.where(ApprovalQueue.risk_level == filter_criteria["risk_level"])

            result = await session.execute(q)
            entries = result.scalars().all()

            resolved_ids = []
            for entry in entries:
                await session.execute(
                    update(ApprovalQueue)
                    .where(ApprovalQueue.id == entry.id)
                    .values(
                        status=f"{decision}d",
                        resolved_by=resolved_by,
                        resolved_at=now,
                        decision_note=note,
                    )
                )
                resolved_ids.append(entry.id)

            await session.commit()

        return {"resolved_count": len(resolved_ids), "resolved_ids": resolved_ids}

    async def check_expirations(self) -> int:
        """Mark expired approval entries. Returns count of expired."""
        from life_graph.models.db import ApprovalQueue, AutoAction

        now = datetime.now(timezone.utc)
        expired_count = 0

        async with self._session_factory() as session:
            result = await session.execute(
                select(ApprovalQueue).where(
                    ApprovalQueue.status == "pending",
                    ApprovalQueue.expires_at.isnot(None),
                    ApprovalQueue.expires_at <= now,
                )
            )
            expired = result.scalars().all()

            for entry in expired:
                # Auto-approve expired entries (they were notify-before type)
                await session.execute(
                    update(ApprovalQueue)
                    .where(ApprovalQueue.id == entry.id)
                    .values(
                        status="auto_approved",
                        resolved_by="system",
                        resolved_at=now,
                        decision_note="Auto-approved after timeout",
                    )
                )
                await session.execute(
                    update(AutoAction)
                    .where(AutoAction.id == entry.action_id)
                    .values(status="approved")
                )
                expired_count += 1

            await session.commit()

        logger.info("Checked approval expirations: %d auto-approved", expired_count)
        return expired_count

    async def send_escalations(self) -> int:
        """Send escalation notifications for long-pending approvals.

        Escalates at 1h, 4h, and 12h thresholds.
        Returns count of escalated entries.
        """
        from life_graph.models.db import ApprovalQueue

        now = datetime.now(timezone.utc)
        escalated_count = 0

        async with self._session_factory() as session:
            result = await session.execute(
                select(ApprovalQueue).where(
                    ApprovalQueue.status == "pending",
                )
            )
            pending = result.scalars().all()

            for entry in pending:
                age_minutes = (now - entry.created_at).total_seconds() / 60
                current_level = entry.escalation_level or 0

                # Check if we need to escalate
                new_level = current_level
                for i, threshold in enumerate(self.ESCALATION_THRESHOLDS):
                    if age_minutes >= threshold and current_level <= i:
                        new_level = i + 1

                if new_level > current_level:
                    await session.execute(
                        update(ApprovalQueue)
                        .where(ApprovalQueue.id == entry.id)
                        .values(escalation_level=new_level)
                    )
                    escalated_count += 1
                    logger.warning(
                        "Escalated approval %s to level %d (age: %.0f min)",
                        entry.id, new_level, age_minutes,
                    )

            await session.commit()

        logger.info("Escalation check: %d entries escalated", escalated_count)
        return escalated_count
