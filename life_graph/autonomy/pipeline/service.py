"""AutoFix pipeline service — classify → route → execute/queue.

Orchestrates the full autonomous action pipeline:
1. Classify the action's risk level via SafetyClassifier
2. Check the project's autonomy level + trust score
3. Route: auto-execute, notify-before-execute, or queue-for-approval
4. Record the result via AuditService
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from life_graph.autonomy.pipeline.executor import CommandExecutor
from life_graph.autonomy.pipeline.schemas import AutoFixRequest, AutoFixResponse, AutoActionResponse
from life_graph.core.events import event_bus, EventType

logger = logging.getLogger(__name__)


class AutoFixService:
    """Orchestrates classify → route → execute/queue for autonomous actions.

    Uses per-project asyncio.Lock to ensure sequential execution
    within a project (never parallel).
    """

    def __init__(
        self,
        session_factory,
        classifier,
        trust_service,
        audit_service,
        approval_service,
        level_service=None,
    ):
        self._session_factory = session_factory
        self._classifier = classifier
        self._trust_service = trust_service
        self._audit_service = audit_service
        self._approval_service = approval_service
        self._level_service = level_service
        self._executor = CommandExecutor()
        self._project_locks: dict[str, asyncio.Lock] = {}

    def _get_lock(self, project_id: str) -> asyncio.Lock:
        """Get or create a per-project execution lock."""
        if project_id not in self._project_locks:
            self._project_locks[project_id] = asyncio.Lock()
        return self._project_locks[project_id]

    async def process(
        self, tenant_id: str, request: AutoFixRequest,
    ) -> AutoFixResponse:
        """Orchestrate: classify → route → execute/queue.

        Args:
            tenant_id: The tenant context.
            request: The auto-fix request.

        Returns:
            AutoFixResponse with action details and routing decision.
        """
        # 1. Classify risk
        classification = await self._classifier.classify(
            action_type=request.action_type,
            command=request.command,
            metadata=request.metadata,
        )
        risk_level = classification.get("risk_level", "high")

        # 2. Find matching safety rule
        rule = classification.get("matched_rule")

        # 3. Create the auto_action record
        from life_graph.models.db import AutoAction

        action_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        async with self._session_factory() as session:
            auto_action = AutoAction(
                id=action_id,
                tenant_id=tenant_id,
                agent_id=request.agent_id,
                project_id=request.project_id,
                action_type=request.action_type,
                command=request.command,
                rollback_command=request.rollback_command,
                description=request.description,
                risk_level=risk_level,
                safety_rule_id=rule.id if rule else None,
                status="pending",
                timeout_seconds=request.timeout_seconds,
                metadata=request.metadata or {},
                created_at=now,
            )
            session.add(auto_action)
            await session.commit()
            await session.refresh(auto_action)

        # 4. Get autonomy level for the project
        autonomy_level = 0
        if self._level_service:
            level_info = await self._level_service.get_level(tenant_id, request.project_id)
            autonomy_level = level_info.current_level

        # 5. Route based on risk + autonomy level
        if risk_level == "safe" and autonomy_level >= 1:
            routing = "auto_executed"
            await self._auto_execute(tenant_id, auto_action, rule)
        elif risk_level == "moderate" and autonomy_level >= 2:
            routing = "notify_before"
            await self._notify_before_execute(tenant_id, auto_action, rule)
        elif risk_level == "safe" and autonomy_level == 0:
            routing = "queued_for_approval"
            await self._queue_for_approval(tenant_id, auto_action, rule)
        else:
            routing = "queued_for_approval"
            await self._queue_for_approval(tenant_id, auto_action, rule)

        # 6. Refresh and return
        async with self._session_factory() as session:
            result = await session.execute(
                select(AutoAction).where(AutoAction.id == action_id)
            )
            refreshed = result.scalar_one()

            action_resp = AutoActionResponse(
                id=refreshed.id,
                tenant_id=refreshed.tenant_id,
                agent_id=refreshed.agent_id,
                project_id=refreshed.project_id,
                action_type=refreshed.action_type,
                command=refreshed.command,
                rollback_command=refreshed.rollback_command,
                description=refreshed.description,
                risk_level=refreshed.risk_level,
                status=refreshed.status,
                exit_code=refreshed.exit_code,
                stdout=refreshed.stdout,
                stderr=refreshed.stderr,
                duration_ms=refreshed.duration_ms,
                approval_id=refreshed.approval_id,
                executed_at=refreshed.executed_at,
                created_at=refreshed.created_at,
                metadata=refreshed.metadata,
            )

        return AutoFixResponse(
            action=action_resp,
            routing=routing,
            message=f"Action {routing.replace('_', ' ')} — risk={risk_level}, level=L{autonomy_level}",
        )

    async def _auto_execute(
        self, tenant_id: str, auto_action, rule,
    ) -> None:
        """L1+ safe action: execute immediately with project lock."""
        from life_graph.models.db import AutoAction

        lock = self._get_lock(auto_action.project_id)
        async with lock:
            result = await self._executor.execute(
                command=auto_action.command,
                timeout_seconds=auto_action.timeout_seconds or 60,
            )

            status = "success" if result.exit_code == 0 else "failed"
            now = datetime.now(timezone.utc)

            async with self._session_factory() as session:
                await session.execute(
                    update(AutoAction)
                    .where(AutoAction.id == auto_action.id)
                    .values(
                        status=status,
                        exit_code=result.exit_code,
                        stdout=result.stdout,
                        stderr=result.stderr,
                        duration_ms=result.duration_ms,
                        executed_at=now,
                    )
                )
                await session.commit()

        # Audit log
        await self._audit_service.log_auto_execute(
            tenant_id=tenant_id,
            action_id=auto_action.id,
            agent_id=auto_action.agent_id,
            project_id=auto_action.project_id,
            action_type=auto_action.action_type,
            risk_level=auto_action.risk_level,
            command=auto_action.command,
            exit_code=result.exit_code,
            duration_ms=result.duration_ms,
            result=status,
        )

        # Record for level promotion tracking
        if self._level_service:
            await self._level_service.record_action(
                tenant_id, auto_action.project_id,
                auto_action.risk_level, status == "success",
            )

        # Emit event
        await event_bus.emit(
            EventType.AUTONOMOUS_ACTION_COMPLETED,
            {
                "action_id": str(auto_action.id),
                "project_id": auto_action.project_id,
                "status": status,
                "risk_level": auto_action.risk_level,
            },
            source="autonomy_pipeline",
        )

    async def _notify_before_execute(
        self, tenant_id: str, auto_action, rule,
    ) -> None:
        """L2 moderate flow: create approval entry but auto-approve after delay."""
        from life_graph.models.db import AutoAction

        approval = await self._approval_service.create(
            tenant_id=tenant_id,
            data={
                "action_id": auto_action.id,
                "agent_id": auto_action.agent_id,
                "project_id": auto_action.project_id,
                "action_type": auto_action.action_type,
                "risk_level": auto_action.risk_level,
                "command": auto_action.command,
                "description": auto_action.description,
                "auto_approve_minutes": 5,
            },
        )

        async with self._session_factory() as session:
            await session.execute(
                update(AutoAction)
                .where(AutoAction.id == auto_action.id)
                .values(
                    status="pending_approval",
                    approval_id=approval.id,
                )
            )
            await session.commit()

        await event_bus.emit(
            EventType.AUTONOMOUS_ACTION_PENDING,
            {
                "action_id": str(auto_action.id),
                "approval_id": str(approval.id),
                "project_id": auto_action.project_id,
                "risk_level": auto_action.risk_level,
            },
            source="autonomy_pipeline",
        )

    async def _queue_for_approval(
        self, tenant_id: str, auto_action, rule,
    ) -> None:
        """Queue the action for human approval."""
        from life_graph.models.db import AutoAction

        approval = await self._approval_service.create(
            tenant_id=tenant_id,
            data={
                "action_id": auto_action.id,
                "agent_id": auto_action.agent_id,
                "project_id": auto_action.project_id,
                "action_type": auto_action.action_type,
                "risk_level": auto_action.risk_level,
                "command": auto_action.command,
                "description": auto_action.description,
            },
        )

        async with self._session_factory() as session:
            await session.execute(
                update(AutoAction)
                .where(AutoAction.id == auto_action.id)
                .values(
                    status="pending_approval",
                    approval_id=approval.id,
                )
            )
            await session.commit()

        await event_bus.emit(
            EventType.AUTONOMOUS_ACTION_PENDING,
            {
                "action_id": str(auto_action.id),
                "approval_id": str(approval.id),
                "project_id": auto_action.project_id,
                "risk_level": auto_action.risk_level,
            },
            source="autonomy_pipeline",
        )

    async def rollback(self, tenant_id: str, auto_action_id: uuid.UUID) -> AutoActionResponse:
        """Execute the rollback command for a previously-executed action."""
        from life_graph.models.db import AutoAction

        async with self._session_factory() as session:
            result = await session.execute(
                select(AutoAction).where(
                    AutoAction.id == auto_action_id,
                    AutoAction.tenant_id == tenant_id,
                )
            )
            action = result.scalar_one_or_none()
            if not action:
                raise ValueError(f"Auto action {auto_action_id} not found")

            if not action.rollback_command:
                raise ValueError("No rollback command defined for this action")

            if action.status not in ("success", "failed"):
                raise ValueError(f"Cannot rollback action in status: {action.status}")

        # Execute rollback
        lock = self._get_lock(action.project_id)
        async with lock:
            result = await self._executor.execute(
                command=action.rollback_command,
                timeout_seconds=action.timeout_seconds or 60,
            )

        rb_status = "rolled_back" if result.exit_code == 0 else "rollback_failed"
        now = datetime.now(timezone.utc)

        async with self._session_factory() as session:
            await session.execute(
                update(AutoAction)
                .where(AutoAction.id == auto_action_id)
                .values(status=rb_status)
            )
            await session.commit()

        # Audit
        await self._audit_service.log_rollback(
            tenant_id=tenant_id,
            action_id=auto_action_id,
            agent_id=action.agent_id,
            project_id=action.project_id,
            exit_code=result.exit_code,
            result=rb_status,
        )

        async with self._session_factory() as session:
            res = await session.execute(
                select(AutoAction).where(AutoAction.id == auto_action_id)
            )
            refreshed = res.scalar_one()

        return AutoActionResponse(
            id=refreshed.id,
            tenant_id=refreshed.tenant_id,
            agent_id=refreshed.agent_id,
            project_id=refreshed.project_id,
            action_type=refreshed.action_type,
            command=refreshed.command,
            rollback_command=refreshed.rollback_command,
            description=refreshed.description,
            risk_level=refreshed.risk_level,
            status=refreshed.status,
            exit_code=refreshed.exit_code,
            stdout=refreshed.stdout,
            stderr=refreshed.stderr,
            duration_ms=refreshed.duration_ms,
            approval_id=refreshed.approval_id,
            executed_at=refreshed.executed_at,
            created_at=refreshed.created_at,
            metadata=refreshed.metadata,
        )
