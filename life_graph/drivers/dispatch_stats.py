"""Driver statistics and limits: WIP caps, the day-bucketed ``driver_stats``
rows trust scoring reads, and persona loading. A mixin: ``TaskDispatcher``
inherits these methods unchanged (split out of dispatcher.py, 2026-10-25).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from life_graph.drivers.errors import DispatchError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from life_graph.drivers.base import DriverResult

logger = logging.getLogger(__name__)

MAX_WIP_PER_PROJECT = 2
MAX_WIP_PER_TENANT = 5


def _coerce_project_uuid(project_id: str | uuid.UUID | None) -> uuid.UUID | None:
    """Best-effort ``project_id`` → ``uuid.UUID``; ``None`` when not a real UUID.

    Not every caller has a real ``projects`` row: the ambient action pipeline
    stamps its proposals with the pseudo-project ``"ambient"``
    (``life_graph/services/action_proposal_bridge.py::AMBIENT_PROJECT_ID``),
    which is a plain string. Parsing that with ``uuid.UUID()`` raises
    ``ValueError`` and would abort the whole dispatch, so a non-UUID project id
    degrades to "no project context" instead of crashing.
    """
    if project_id is None:
        return None
    if isinstance(project_id, uuid.UUID):
        return project_id
    try:
        return uuid.UUID(str(project_id))
    except (ValueError, AttributeError, TypeError):
        logger.warning(
            "dispatch: project_id %r is not a UUID — treating as no project",
            project_id,
        )
        return None


class DriverStatsMixin:
    """Persona lookup, WIP limits and driver stats for ``TaskDispatcher``."""

    async def _load_persona(
        self,
        tenant_id: str,
        persona_name: str | None,
        session: AsyncSession,
    ):
        """Load the active ``AgentPersona`` row for ``persona_name``, or None.

        Never raises: a personaless (or unresolvable) dispatch must still
        proceed — it simply carries no persona prompt/tool scoping, which is
        exactly the pre-existing behavior for every non-persona caller.
        """
        if not persona_name:
            return None
        try:
            from life_graph.models.db import AgentPersona

            result = await session.execute(
                select(AgentPersona).where(
                    AgentPersona.tenant_id == tenant_id,
                    AgentPersona.name == persona_name,
                    AgentPersona.is_active.is_(True),
                )
            )
            persona = result.scalar_one_or_none()
            if persona is None:
                logger.warning(
                    "Persona %r not found for tenant %s — dispatching without "
                    "persona prompt/tool scoping",
                    persona_name,
                    tenant_id,
                )
            return persona
        except Exception:
            logger.warning(
                "Failed to load persona %r — dispatching without persona prompt/tool scoping",
                persona_name,
                exc_info=True,
            )
            return None

    async def _check_wip_limits(
        self,
        tenant_id: str,
        project_id: str | uuid.UUID | None,
        session: AsyncSession,
        exclude_task_id: str | uuid.UUID | None = None,
    ) -> None:
        """Enforce WIP concurrency limits.

        ``project_id`` is normally already normalized by ``dispatch_task``; it
        is re-coerced here (idempotent) so the project-level check still works
        for any other caller passing a raw string.

        Raises:
            DispatchError: If WIP limits are exceeded.
        """
        project_uuid = _coerce_project_uuid(project_id)
        try:
            from life_graph.models.db import AgentTask

            # A caller that records its own run as a running AgentTask (the
            # dashboard dev-task runner) must not count against itself.
            own = _coerce_project_uuid(exclude_task_id)
            not_self = [AgentTask.id != own] if own is not None else []

            # Tenant-level WIP
            result = await session.execute(
                select(func.count(AgentTask.id)).where(
                    AgentTask.tenant_id == tenant_id,
                    AgentTask.status == "running",
                    *not_self,
                )
            )
            tenant_wip = result.scalar() or 0

            if tenant_wip >= MAX_WIP_PER_TENANT:
                raise DispatchError(f"Tenant WIP limit reached ({tenant_wip}/{MAX_WIP_PER_TENANT})")

            # Project-level WIP
            if project_uuid is not None:
                result = await session.execute(
                    select(func.count(AgentTask.id)).where(
                        AgentTask.tenant_id == tenant_id,
                        AgentTask.project_id == project_uuid,
                        AgentTask.status == "running",
                        *not_self,
                    )
                )
                project_wip = result.scalar() or 0

                if project_wip >= MAX_WIP_PER_PROJECT:
                    raise DispatchError(
                        f"Project WIP limit reached ({project_wip}/{MAX_WIP_PER_PROJECT})"
                    )
        except DispatchError:
            raise
        except Exception:
            logger.warning("Failed to check WIP limits — proceeding", exc_info=True)

    async def _get_driver_stats(
        self,
        tenant_id: str,
        driver_name: str,
        session: AsyncSession,
    ) -> dict:
        """Get aggregated driver stats for trust scoring.

        Sums across all day-bucketed rows for this driver.

        Returns:
            Dict with success_rate, total_tasks, etc.
        """
        try:
            from life_graph.models.db import DriverStat

            result = await session.execute(
                select(
                    func.sum(DriverStat.dispatched),
                    func.sum(DriverStat.verified_landed),
                    func.sum(DriverStat.failed),
                    func.sum(DriverStat.total_cost_usd),
                    func.sum(DriverStat.total_duration_ms),
                ).where(
                    DriverStat.tenant_id == tenant_id,
                    DriverStat.driver == driver_name,
                )
            )
            row = result.one_or_none()
            if row and row[0]:  # dispatched sum exists
                dispatched = row[0] or 0
                landed = row[1] or 0
                total = dispatched
                return {
                    "success_rate": landed / total if total > 0 else 1.0,
                    "total_tasks": total,
                    "avg_cost_usd": (row[3] or 0) / total if total > 0 else 0.0,
                    "avg_duration_ms": (row[4] or 0) / total if total > 0 else 0,
                }
        except Exception:
            logger.debug("No stats for driver %s — using defaults", driver_name)

        return {"success_rate": 1.0, "total_tasks": 0}

    async def _record_stats(
        self,
        tenant_id: str,
        driver_name: str,
        task_type: str,
        result: DriverResult,
        session: AsyncSession,
    ) -> None:
        """Update driver_stats row (day-bucketed) with latest dispatch result."""
        try:
            from life_graph.models.db import DriverStat

            today = datetime.now(UTC).date()

            existing = await session.execute(
                select(DriverStat).where(
                    DriverStat.tenant_id == tenant_id,
                    DriverStat.driver == driver_name,
                    DriverStat.task_type == task_type,
                    DriverStat.window_start == today,
                )
            )
            stat = existing.scalar_one_or_none()

            if stat:
                stat.dispatched += 1
                if result.success:
                    stat.verified_landed += 1
                else:
                    stat.failed += 1
                stat.total_cost_usd += result.cost_usd
                stat.total_duration_ms += result.duration_ms
            else:
                stat = DriverStat(
                    tenant_id=tenant_id,
                    driver=driver_name,
                    task_type=task_type,
                    window_start=today,
                    dispatched=1,
                    verified_landed=1 if result.success else 0,
                    failed=0 if result.success else 1,
                    total_cost_usd=result.cost_usd,
                    total_duration_ms=result.duration_ms,
                )
                session.add(stat)
        except Exception:
            logger.warning("Failed to record driver stats", exc_info=True)
