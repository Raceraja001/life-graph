"""Bridge ``AUTONOMOUS_ACTION_PENDING`` into a notification + push + the unified
``Approval`` feed.

When the autonomy pipeline queues an action for human approval (or a
notify-before-execute delay), this producer loads the ``approval_queue`` entry and its
underlying ``AutoAction`` for the command/name/risk, then:

1. Creates a ``Notification`` (priority scaled by risk level) and pushes it to the
   phone immediately via Web Push.
2. Mirrors the action into the generic ``Approval`` feed (``kind="autonomous_action"``)
   so the existing mobile ``/m/approvals`` screen shows it alongside every other
   approval-shaped item in the system, without a dedicated autonomy UI.

A producer failure must never break the autonomy pipeline: every DB/network call here
is guarded, and no exception escapes the event handler.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from life_graph.autonomy.models import ApprovalQueueEntry, AutoAction
from life_graph.core.events import Event, EventType, event_bus
from life_graph.models.db import Approval
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

# risk_level -> notification priority / unified-feed priority.
_NOTIFICATION_PRIORITY_BY_RISK = {"dangerous": "critical", "moderate": "important"}
_FEED_PRIORITY_BY_RISK = {"dangerous": 90, "moderate": 50}


class AutonomousApprovalProducer:
    """Subscribes to ``AUTONOMOUS_ACTION_PENDING``; notifies + mirrors to the Approval feed."""

    def __init__(self) -> None:
        self._subscribed = False
        self._notification_engine: Any | None = None
        self._push_service: Any | None = None

    def _get_notification_engine(self) -> Any:
        if self._notification_engine is None:
            from life_graph.api.dependencies import get_notification_engine

            self._notification_engine = get_notification_engine()
        return self._notification_engine

    def _get_push_service(self) -> Any:
        if self._push_service is None:
            from life_graph.services.webpush import PushService

            self._push_service = PushService(async_session)
        return self._push_service

    def subscribe(self) -> None:
        """Subscribe the handler to ``AUTONOMOUS_ACTION_PENDING`` (idempotent)."""
        if self._subscribed:
            return
        event_bus.subscribe(EventType.AUTONOMOUS_ACTION_PENDING, self._on_pending)
        self._subscribed = True

    async def _on_pending(self, event: Event) -> None:
        """Handle an ``AUTONOMOUS_ACTION_PENDING`` event.

        Payload: ``{"action_id", "approval_id", "project_id", "risk_level"}``. The
        event itself carries no ``tenant_id`` — it is recovered from the loaded
        ``ApprovalQueueEntry`` row (looked up by its globally-unique id) and then used
        to tenant-scope the ``AutoAction`` lookup and the feed insert.
        """
        try:
            data = event.payload
            approval_id = data.get("approval_id")
            action_id = data.get("action_id")
            if not approval_id or not action_id:
                return

            async with async_session() as session:
                approval_entry = (
                    await session.execute(
                        select(ApprovalQueueEntry).where(ApprovalQueueEntry.id == approval_id)
                    )
                ).scalar_one_or_none()
                if approval_entry is None:
                    return
                tenant_id = approval_entry.tenant_id

                auto_action = (
                    await session.execute(
                        select(AutoAction).where(
                            AutoAction.id == action_id,
                            AutoAction.tenant_id == tenant_id,
                        )
                    )
                ).scalar_one_or_none()

                action_name = auto_action.action_name if auto_action else approval_entry.action_name
                command = (
                    auto_action.action_command if auto_action else approval_entry.action_command
                )
                risk = (
                    (auto_action.risk_level if auto_action else None)
                    or approval_entry.risk_level
                    or data.get("risk_level")
                    or "safe"
                )
                trigger_detail = (
                    auto_action.trigger_detail if auto_action else approval_entry.trigger_detail
                )
                kind = (
                    (auto_action.kind if auto_action else None)
                    or approval_entry.kind
                    or "command"
                )
                instruction = (
                    auto_action.instruction if auto_action else approval_entry.instruction
                )

                # The notification/push title is deliberately more explicit than the
                # feed-row title (which must match the plan text exactly) — a push
                # benefits from "needs approval" context that the generic Approval
                # feed's own UI chrome already conveys via kind/status.
                notification_title = f"{risk} action needs approval: {action_name}"
                feed_title = f"{risk} action: {action_name}"
                body = f"{command}\n{trigger_detail}" if trigger_detail else command

                await self._notify(
                    tenant_id, notification_title, body, approval_id, action_id, risk
                )
                await self._mirror_to_feed(
                    session,
                    tenant_id,
                    approval_id,
                    action_id,
                    risk,
                    feed_title,
                    command,
                    kind,
                    instruction,
                )
        except Exception:  # a producer failure must never break the event flow
            logger.warning("Autonomous approval producer failed", exc_info=True)

    async def _notify(
        self,
        tenant_id: str,
        title: str,
        body: str,
        approval_id: str,
        action_id: str,
        risk: str,
    ) -> None:
        """Create a Notification and push it immediately. Failures are swallowed."""
        priority = _NOTIFICATION_PRIORITY_BY_RISK.get(risk, "info")
        try:
            await self._get_notification_engine().create(
                tenant_id,
                title,
                body=body,
                priority=priority,
                source_type="autonomous_action",
                deliver_at_brief=False,
                metadata={
                    "approval_id": str(approval_id),
                    "action_id": str(action_id),
                    "risk_level": risk,
                },
            )
        except Exception:
            logger.warning("Autonomous approval notification create failed", exc_info=True)

        try:
            await self._get_push_service().send_to_tenant(tenant_id, title, body, "/m")
        except Exception:
            logger.warning("Autonomous approval push failed", exc_info=True)

    async def _mirror_to_feed(
        self,
        session: Any,
        tenant_id: str,
        approval_id: str,
        action_id: str,
        risk: str,
        title: str,
        command: str,
        kind: str = "command",
        instruction: str | None = None,
    ) -> None:
        """Insert an ``Approval`` feed row, skipping if one already exists (idempotent)."""
        try:
            existing = (
                await session.execute(
                    select(Approval).where(
                        Approval.tenant_id == tenant_id,
                        Approval.kind == "autonomous_action",
                        Approval.source_ref == str(approval_id),
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                return
            payload: dict[str, Any] = {
                "auto_action_id": str(action_id),
                "approval_id": str(approval_id),
                "risk_level": risk,
                "kind": kind,
            }
            if kind == "agent_task" and instruction:
                payload["instruction"] = instruction
            session.add(
                Approval(
                    tenant_id=tenant_id,
                    kind="autonomous_action",
                    source="autonomy",
                    source_ref=str(approval_id),
                    title=title,
                    detail=command,
                    payload=payload,
                    priority=_FEED_PRIORITY_BY_RISK.get(risk, 10),
                )
            )
            await session.commit()
        except Exception:
            logger.warning("Autonomous approval feed mirror failed", exc_info=True)


autonomous_approval_producer = AutonomousApprovalProducer()
