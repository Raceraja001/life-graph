"""Turn an ops scheduled run's proposed-actions JSON into autonomy engine requests.

The ``ops`` ambient-action persona runs read-only, then ends its reply with a JSON
array of proposed shell-command actions. This bridge (sibling of ``FindingsBridge``)
picks each proposal up on ``TASK_COMPLETED`` and feeds it into ``AutoFixService.process``,
which classifies and routes it (auto-execute / shadow / queue for approval). The engine
itself is the safety gate — this module never executes commands directly.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select

from life_graph.autonomy.pipeline.schemas import AutoFixRequest
from life_graph.core.events import Event, EventType, event_bus
from life_graph.kernel.ambient import AMBIENT_ACTION
from life_graph.services.findings_bridge import _extract_json_array

logger = logging.getLogger(__name__)

AMBIENT_PROJECT_ID = "ambient"

# The scheduler ticker (life_graph.workers.tasks.tick_scheduled_jobs ->
# ApprovalService... kernel.scheduler.SchedulerService.fire_job) spawns every
# fired job's task with task_name=f"schedule:{job['name']}" (see
# ``fire_job``). Interactive ops chat instead spawns with task_name=
# f"chat:{target_agent}" (life_graph.api.kernel.chat_stream). Propose-mode
# dispatch is scheduled-only, so this prefix is the real, load-bearing marker
# that distinguishes the two — gate on it in addition to agent_name so an
# interactive ops reply whose text happens to contain a JSON array is never
# treated as an autonomy proposal.
_SCHEDULED_TASK_NAME_PREFIX = "schedule:"


class ActionProposalBridge:
    """Convert an ops run's proposed actions into ``AutoFixService`` requests."""

    def __init__(self, autofix_service: Any, notification_engine: Any) -> None:
        self._autofix = autofix_service
        self._notifications = notification_engine

    async def process_result(
        self, tenant_id: str, agent_name: str, task_id: str, result_text: str
    ) -> int:
        """Parse proposed actions and dispatch each to ``AutoFixService.process``.

        Skips proposals missing ``name`` or ``command``; one bad proposal never
        drops the rest. When no JSON array is present at all (and the reply is
        non-empty), creates a single advisory notification instead of dispatching
        anything. Returns the number of proposals dispatched.
        """
        raw_array = _extract_json_array(result_text)
        if raw_array is None:
            if result_text.strip():
                try:
                    await self._notifications.create(
                        tenant_id,
                        "ops proposed actions could not be parsed",
                        body=result_text.strip()[:2000],
                        priority="info",
                        source_type="ops",
                        deliver_at_brief=True,
                    )
                except Exception:  # advisory delivery must never break the flow
                    logger.warning("ActionProposalBridge: advisory notify failed", exc_info=True)
            return 0

        dispatched = 0
        for item in raw_array:
            if not isinstance(item, dict) or not item.get("name") or not item.get("command"):
                continue
            try:
                request = AutoFixRequest(
                    agent_id=agent_name,
                    project_id=AMBIENT_PROJECT_ID,
                    action_type=item["name"],
                    command=item["command"],
                    description=item.get("rationale", ""),
                )
                await self._autofix.process(tenant_id, request)
                dispatched += 1
            except Exception:  # one bad proposal must not drop the rest
                logger.warning("ActionProposalBridge: proposal dispatch failed", exc_info=True)
                continue
        return dispatched


async def _load_task_row(tenant_id: str, task_id: str) -> Any:
    """Load the completed ``AgentTask`` row, tenant-scoped."""
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    async with async_session() as session:
        return (
            await session.execute(
                select(AgentTask).where(
                    AgentTask.id == uuid.UUID(task_id),
                    AgentTask.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()


async def _load_task_result(tenant_id: str, task_id: str) -> str | None:
    """Load a completed, SCHEDULED AgentTask's response text, tenant-scoped.

    Returns ``None`` (skip) for a task that wasn't fired by the scheduler
    ticker — see ``_SCHEDULED_TASK_NAME_PREFIX``.
    """
    row = await _load_task_row(tenant_id, task_id)
    if row is None or not isinstance(row.result, dict):
        return None
    if not (row.task_name or "").startswith(_SCHEDULED_TASK_NAME_PREFIX):
        return None
    return row.result.get("response")


class ActionProposalHandler:
    """Subscribes TASK_COMPLETED and bridges SCHEDULED ops proposal runs to the autonomy engine.

    Gated on ``agent_name in AMBIENT_ACTION`` AND the completed task being a
    scheduler-fired run (``_SCHEDULED_TASK_NAME_PREFIX``) — an interactive
    ops chat completion is never dispatched, even if its reply happens to
    contain a JSON array.
    """

    def __init__(self) -> None:
        self._subscribed = False
        self._bridge: ActionProposalBridge | None = None

    def _get_bridge(self) -> ActionProposalBridge:
        if self._bridge is None:
            from life_graph.api.dependencies import get_autofix_service, get_notification_engine

            self._bridge = ActionProposalBridge(
                autofix_service=get_autofix_service(),
                notification_engine=get_notification_engine(),
            )
        return self._bridge

    def subscribe(self) -> None:
        """Subscribe the handler to TASK_COMPLETED (idempotent)."""
        if self._subscribed:
            return
        event_bus.subscribe(EventType.TASK_COMPLETED, self._on_task_completed)
        self._subscribed = True

    async def _on_task_completed(self, event: Event) -> None:
        try:
            data = event.payload
            agent_name = data.get("agent_name", "")
            if agent_name not in AMBIENT_ACTION:
                return
            tenant_id = data.get("tenant_id")
            task_id = data.get("task_id")
            if not tenant_id or not task_id:
                return
            result_text = await _load_task_result(tenant_id, task_id)
            if result_text is None:
                return
            await self._get_bridge().process_result(tenant_id, agent_name, task_id, result_text)
        except Exception:  # a bridge failure must never break task completion
            logger.warning("ActionProposalBridge handler failed", exc_info=True)


action_proposal_handler = ActionProposalHandler()
