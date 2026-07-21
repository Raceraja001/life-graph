"""AutoFix pipeline service — classify → route → execute/queue.

Orchestrates the full autonomous action pipeline:
1. Classify the action's risk level via SafetyClassifier
2. Check the project's autonomy level + trust score
3. Route: auto-execute, notify-before-execute, or queue-for-approval
4. Record the result via AuditService

Reconciled to the real ``AutoAction`` model (``action_name`` / ``action_command`` /
``trigger_type`` / ``trigger_detail`` / ``started_at`` / ``completed_at``). The friendly
request fields (``action_type`` / ``command`` / ``description`` / ``timeout_seconds``) are
mapped here; ``timeout_seconds`` and ``metadata`` are not persisted (no columns for them).
See docs/specs/era8-autonomy-reconciliation.md.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update

from life_graph.autonomy.pipeline.executor import CommandExecutor
from life_graph.autonomy.pipeline.schemas import AutoActionResponse, AutoFixRequest, AutoFixResponse
from life_graph.autonomy.shadow.service import shadow_service
from life_graph.core.events import EventType, event_bus

logger = logging.getLogger(__name__)


def _to_response(action) -> AutoActionResponse:
    """Serialize a real ``AutoAction`` ORM row into the API response shape."""
    return AutoActionResponse(
        id=str(action.id),
        tenant_id=action.tenant_id,
        agent_id=action.agent_id,
        project_id=action.project_id,
        action_name=action.action_name,
        action_command=action.action_command,
        rollback_command=action.rollback_command,
        trigger_type=action.trigger_type,
        trigger_detail=action.trigger_detail,
        risk_level=action.risk_level,
        status=action.status,
        exit_code=action.exit_code,
        stdout=action.stdout,
        stderr=action.stderr,
        error_message=action.error_message,
        duration_ms=action.duration_ms,
        approval_id=str(action.approval_id) if action.approval_id else None,
        started_at=action.started_at,
        completed_at=action.completed_at,
        created_at=action.created_at,
    )


class AutoFixService:
    """Orchestrates classify → route → execute/queue for autonomous actions.

    Uses per-project asyncio.Lock to ensure sequential execution
    within a project (never parallel).
    """

    def __init__(
        self,
        session_factory,
        audit_service,
        approval_service,
        level_service=None,
        classifier=None,
        trust_service=None,
    ):
        # classifier is built per-request in process() (it needs a live session),
        # so it is optional here; trust_service is likewise unused by the pipeline.
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

        The classifier already folds risk × autonomy level into a
        ``recommendation`` (auto-execute / notify-before / queue-for-approval),
        so routing keys off that. The classifier takes a live session, so it is
        built per-request rather than injected as a singleton.
        """
        from life_graph.autonomy.models import AutoAction
        from life_graph.autonomy.safety.classifier import ActionClassifier, Recommendation

        # 1. Classify (rule match → trust → autonomy level → recommendation)
        async with self._session_factory() as session:
            classifier = ActionClassifier(session)
            classification = await classifier.classify(
                tenant_id=tenant_id,
                agent_id=request.agent_id,
                action_name=request.action_type,
                action_command=request.command,
                project_id=request.project_id,
            )
            risk_level = classification.risk_level.value
            recommendation = classification.recommendation
            autonomy_level = classification.autonomy_level
            rule_id = classification.matched_rule.id if classification.matched_rule else None
            reasoning = classification.reasoning

        # 2. Create the auto_action record (real AutoAction fields)
        action_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        async with self._session_factory() as session:
            auto_action = AutoAction(
                id=action_id,
                tenant_id=tenant_id,
                agent_id=request.agent_id,
                project_id=request.project_id,
                action_name=request.action_type,
                action_command=request.command,
                rollback_command=request.rollback_command,
                is_reversible=bool(request.rollback_command),
                trigger_type="manual",
                trigger_detail=request.description or request.action_type,
                risk_level=risk_level,
                safety_rule_id=rule_id,
                status="pending",
                queued_at=now,
                created_at=now,
            )
            session.add(auto_action)
            await session.commit()
            await session.refresh(auto_action)

        # 3. Route on the classifier's recommendation
        if recommendation == Recommendation.AUTO_EXECUTE:
            # Shadow gate: a NEW actor (no trust record) records a would-have-done
            # instead of acting for real, until it graduates (see core/shadow).
            shadow = await shadow_service.intercept(tenant_id, request.agent_id)
            if shadow.shadow:
                routing = "shadow_recorded"
                await self._record_shadow(
                    tenant_id, auto_action, shadow.enrollment_id,
                    {"reasoning": reasoning},
                )
            else:
                routing = "auto_executed"
                await self._auto_execute(
                    tenant_id, auto_action, rule_id, request.timeout_seconds,
                )
        elif recommendation == Recommendation.NOTIFY_BEFORE:
            routing = "notify_before"
            await self._notify_before_execute(tenant_id, auto_action, rule_id)
        else:
            routing = "queued_for_approval"
            await self._queue_for_approval(tenant_id, auto_action, rule_id)

        # 4. Refresh and return
        async with self._session_factory() as session:
            result = await session.execute(
                select(AutoAction).where(AutoAction.id == action_id)
            )
            refreshed = result.scalar_one()
            action_resp = _to_response(refreshed)

        return AutoFixResponse(
            action=action_resp,
            routing=routing,
            message=f"Action {routing.replace('_', ' ')} — risk={risk_level}, level={autonomy_level}",
        )

    async def _record_shadow(
        self, tenant_id: str, auto_action, enrollment_id: str, classification: dict,
    ) -> None:
        """Shadowed actor: record what it WOULD have done; do NOT execute."""
        from life_graph.autonomy.models import AutoAction

        await shadow_service.record_would_have_done(
            tenant_id,
            auto_action.agent_id,
            enrollment_id,
            action_type=auto_action.action_name,
            command=auto_action.action_command,
            risk_level=auto_action.risk_level,
            project_id=auto_action.project_id,
            would_have_routed="auto_executed",
            rationale={"risk_level": auto_action.risk_level,
                       "classification": classification.get("reasoning")},
        )
        async with self._session_factory() as session:
            await session.execute(
                update(AutoAction)
                .where(AutoAction.id == auto_action.id)
                .values(status="skipped")  # ck_aa_status: shadow-recorded → skipped
            )
            await session.commit()

    async def _auto_execute(
        self, tenant_id: str, auto_action, rule, timeout_seconds: int = 60,
    ) -> None:
        """L1+ safe action: execute immediately with project lock."""
        from life_graph.autonomy.models import AutoAction

        lock = self._get_lock(auto_action.project_id)
        started = datetime.now(UTC)
        async with lock:
            result = await self._executor.execute(
                command=auto_action.action_command,
                timeout_seconds=timeout_seconds or 60,
            )

            status = "success" if result.exit_code == 0 else "failure"
            now = datetime.now(UTC)

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
                        started_at=started,
                        completed_at=now,
                    )
                )
                await session.commit()

        # Audit log
        await self._audit_service.log_auto_execute(
            tenant_id=tenant_id,
            action_id=auto_action.id,
            agent_id=auto_action.agent_id,
            project_id=auto_action.project_id,
            action_type=auto_action.action_name,
            risk_level=auto_action.risk_level,
            command=auto_action.action_command,
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
        from life_graph.autonomy.models import AutoAction

        approval = await self._approval_service.create(
            tenant_id=tenant_id,
            data={
                "agent_id": auto_action.agent_id,
                "project_id": auto_action.project_id,
                "action_name": auto_action.action_name,
                "action_command": auto_action.action_command,
                "risk_level": auto_action.risk_level,
                "trigger_type": auto_action.trigger_type,
                "trigger_detail": auto_action.trigger_detail,
                "category": "pipeline",
                "auto_approve_minutes": 5,
            },
        )

        async with self._session_factory() as session:
            await session.execute(
                update(AutoAction)
                .where(AutoAction.id == auto_action.id)
                .values(
                    status="pending",  # ck_aa_status has no 'pending_approval'
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
        from life_graph.autonomy.models import AutoAction

        approval = await self._approval_service.create(
            tenant_id=tenant_id,
            data={
                "agent_id": auto_action.agent_id,
                "project_id": auto_action.project_id,
                "action_name": auto_action.action_name,
                "action_command": auto_action.action_command,
                "risk_level": auto_action.risk_level,
                "trigger_type": auto_action.trigger_type,
                "trigger_detail": auto_action.trigger_detail,
                "category": "pipeline",
            },
        )

        async with self._session_factory() as session:
            await session.execute(
                update(AutoAction)
                .where(AutoAction.id == auto_action.id)
                .values(
                    status="pending",  # ck_aa_status has no 'pending_approval'
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

    async def rollback(self, tenant_id: str, auto_action_id: str) -> AutoActionResponse:
        """Execute the rollback command for a previously-executed action."""
        from life_graph.autonomy.models import AutoAction

        async with self._session_factory() as session:
            result = await session.execute(
                select(AutoAction).where(
                    AutoAction.id == str(auto_action_id),
                    AutoAction.tenant_id == tenant_id,
                )
            )
            action = result.scalar_one_or_none()
            if not action:
                raise ValueError(f"Auto action {auto_action_id} not found")

            if not action.rollback_command:
                raise ValueError("No rollback command defined for this action")

            if action.status not in ("success", "failure"):
                raise ValueError(f"Cannot rollback action in status: {action.status}")

            project_id = action.project_id
            agent_id = action.agent_id
            rollback_command = action.rollback_command

        # Execute rollback
        lock = self._get_lock(project_id)
        async with lock:
            result = await self._executor.execute(
                command=rollback_command,
                timeout_seconds=60,
            )

        rb_status = "rolled_back" if result.exit_code == 0 else "failure"
        now = datetime.now(UTC)

        async with self._session_factory() as session:
            await session.execute(
                update(AutoAction)
                .where(AutoAction.id == str(auto_action_id))
                .values(status=rb_status, rolled_back_at=now)
            )
            await session.commit()

        # Audit
        await self._audit_service.log_rollback(
            tenant_id=tenant_id,
            action_id=auto_action_id,
            agent_id=agent_id,
            project_id=project_id,
            exit_code=result.exit_code,
            result=rb_status,
        )

        async with self._session_factory() as session:
            res = await session.execute(
                select(AutoAction).where(AutoAction.id == str(auto_action_id))
            )
            refreshed = res.scalar_one()
            return _to_response(refreshed)
