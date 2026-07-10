"""Append-only audit service for autonomous actions.

Logs all autonomous events: executions, approvals, rollbacks,
rule changes, trust overrides, and level changes.

Design: APPEND-ONLY — no updates, no deletes.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, date, timezone

from sqlalchemy import select

logger = logging.getLogger(__name__)


class AuditService:
    """Append-only audit log service.

    Every method creates a new AuditLog record.
    Query methods support pagination and filtering.
    Export method streams NDJSON for compliance/analytics.
    """

    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def _append(self, tenant_id: str, action_type: str, **kwargs) -> uuid.UUID:
        """Internal: append a single audit entry. Returns the entry ID."""
        from life_graph.models.db import AuditLog

        entry_id = uuid.uuid4()
        async with self._session_factory() as session:
            entry = AuditLog(
                id=entry_id,
                tenant_id=tenant_id,
                action_type=action_type,
                action_id=kwargs.get("action_id"),
                agent_id=kwargs.get("agent_id"),
                project_id=kwargs.get("project_id"),
                risk_level=kwargs.get("risk_level"),
                command=kwargs.get("command"),
                result=kwargs.get("result"),
                details=kwargs.get("details", {}),
                created_at=datetime.now(timezone.utc),
            )
            session.add(entry)
            await session.commit()

        return entry_id

    async def log_auto_execute(
        self,
        tenant_id: str,
        action_id,
        agent_id: str,
        project_id: str,
        action_type: str,
        risk_level: str,
        command: str,
        exit_code: int,
        duration_ms: float,
        result: str,
    ) -> uuid.UUID:
        """Log an autonomous execution."""
        return await self._append(
            tenant_id=tenant_id,
            action_type="auto_execute",
            action_id=action_id,
            agent_id=agent_id,
            project_id=project_id,
            risk_level=risk_level,
            command=command,
            result=result,
            details={
                "original_action_type": action_type,
                "exit_code": exit_code,
                "duration_ms": duration_ms,
            },
        )

    async def log_approval(
        self,
        tenant_id: str,
        approval_id,
        action_id,
        decision: str,
        resolved_by: str,
        note: str | None = None,
    ) -> uuid.UUID:
        """Log an approval decision."""
        return await self._append(
            tenant_id=tenant_id,
            action_type="approval_decision",
            action_id=action_id,
            result=decision,
            details={
                "approval_id": str(approval_id),
                "resolved_by": resolved_by,
                "note": note,
            },
        )

    async def log_rollback(
        self,
        tenant_id: str,
        action_id,
        agent_id: str,
        project_id: str,
        exit_code: int,
        result: str,
    ) -> uuid.UUID:
        """Log a rollback execution."""
        return await self._append(
            tenant_id=tenant_id,
            action_type="rollback",
            action_id=action_id,
            agent_id=agent_id,
            project_id=project_id,
            result=result,
            details={"exit_code": exit_code},
        )

    async def log_rule_change(
        self,
        tenant_id: str,
        rule_id,
        change_type: str,
        changed_by: str,
        old_value: dict | None = None,
        new_value: dict | None = None,
    ) -> uuid.UUID:
        """Log a safety rule modification."""
        return await self._append(
            tenant_id=tenant_id,
            action_type="rule_change",
            action_id=rule_id,
            result=change_type,
            details={
                "changed_by": changed_by,
                "old_value": old_value,
                "new_value": new_value,
            },
        )

    async def log_trust_override(
        self,
        tenant_id: str,
        agent_id: str,
        project_id: str | None,
        old_score: float,
        new_score: float,
        reason: str,
        overridden_by: str,
    ) -> uuid.UUID:
        """Log a trust score manual override."""
        return await self._append(
            tenant_id=tenant_id,
            action_type="trust_override",
            agent_id=agent_id,
            project_id=project_id,
            result="override",
            details={
                "old_score": old_score,
                "new_score": new_score,
                "reason": reason,
                "overridden_by": overridden_by,
            },
        )

    async def log_autonomy_change(
        self,
        tenant_id: str,
        project_id: str,
        old_level: int,
        new_level: int,
        reason: str,
        changed_by: str = "system",
    ) -> uuid.UUID:
        """Log an autonomy level change."""
        return await self._append(
            tenant_id=tenant_id,
            action_type="autonomy_change",
            project_id=project_id,
            result=f"L{old_level}->L{new_level}",
            details={
                "old_level": old_level,
                "new_level": new_level,
                "reason": reason,
                "changed_by": changed_by,
            },
        )

    async def query(
        self,
        tenant_id: str,
        filters: dict | None = None,
    ) -> list:
        """Paginated query of audit log entries."""
        from life_graph.models.db import AuditLog

        filters = filters or {}

        async with self._session_factory() as session:
            q = select(AuditLog).where(AuditLog.tenant_id == tenant_id)

            if filters.get("agent_id"):
                q = q.where(AuditLog.agent_id == filters["agent_id"])
            if filters.get("action_type"):
                q = q.where(AuditLog.action_type == filters["action_type"])
            if filters.get("risk_level"):
                q = q.where(AuditLog.risk_level == filters["risk_level"])
            if filters.get("result"):
                q = q.where(AuditLog.result == filters["result"])
            if filters.get("project_id"):
                q = q.where(AuditLog.project_id == filters["project_id"])
            if filters.get("start_date"):
                q = q.where(AuditLog.created_at >= datetime.combine(
                    filters["start_date"], datetime.min.time(), tzinfo=timezone.utc,
                ))
            if filters.get("end_date"):
                q = q.where(AuditLog.created_at <= datetime.combine(
                    filters["end_date"], datetime.max.time(), tzinfo=timezone.utc,
                ))

            limit = filters.get("limit", 50)
            offset = filters.get("offset", 0)

            q = q.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
            result = await session.execute(q)
            return result.scalars().all()

    async def export_ndjson(
        self,
        tenant_id: str,
        start_date: date,
        end_date: date,
        project_id: str | None = None,
    ) -> str:
        """Export audit log entries as NDJSON string.

        Returns newline-delimited JSON for streaming.
        """
        from life_graph.models.db import AuditLog

        async with self._session_factory() as session:
            q = select(AuditLog).where(
                AuditLog.tenant_id == tenant_id,
                AuditLog.created_at >= datetime.combine(
                    start_date, datetime.min.time(), tzinfo=timezone.utc,
                ),
                AuditLog.created_at <= datetime.combine(
                    end_date, datetime.max.time(), tzinfo=timezone.utc,
                ),
            )

            if project_id:
                q = q.where(AuditLog.project_id == project_id)

            q = q.order_by(AuditLog.created_at.asc())
            result = await session.execute(q)
            entries = result.scalars().all()

        lines = []
        for entry in entries:
            line = json.dumps({
                "id": str(entry.id),
                "tenant_id": entry.tenant_id,
                "action_type": entry.action_type,
                "action_id": str(entry.action_id) if entry.action_id else None,
                "agent_id": entry.agent_id,
                "project_id": entry.project_id,
                "risk_level": entry.risk_level,
                "command": entry.command,
                "result": entry.result,
                "details": entry.details,
                "created_at": entry.created_at.isoformat(),
            })
            lines.append(line)

        return "\n".join(lines)
