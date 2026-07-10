"""Results Loop — processes driver results through capture spine.

After a driver completes:
1. Report result through capture spine (CAPTURE_RECEIVED)
2. Update trust scores
3. Update driver_stats
4. Emit events for downstream consumers
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from life_graph.core.events import EventBus, EventType
from life_graph.drivers.base import DriverResult

logger = logging.getLogger(__name__)


class ResultsLoop:
    """Processes driver results and feeds them back through the capture spine.

    The results loop is the feedback channel — it takes raw driver output,
    pipes it through the capture system for extraction and storage,
    updates trust/stats, and emits events for downstream consumers.
    """

    def __init__(self, session_factory: callable) -> None:
        self._session_factory = session_factory

    async def process_result(
        self,
        tenant_id: str,
        task_id: str,
        driver_name: str,
        result: DriverResult,
        session: AsyncSession | None = None,
        event_bus: EventBus | None = None,
    ) -> dict:
        """Main entry point — process a completed driver result.

        Steps:
        1. Capture the result through the capture spine
        2. Update driver stats
        3. Emit events for downstream consumers

        Args:
            tenant_id: Tenant scope.
            task_id: The task that produced this result.
            driver_name: Name of the driver that executed the task.
            result: The DriverResult from the dispatch.
            session: Optional session (creates one if None).
            event_bus: Optional event bus for emitting events.

        Returns:
            Dict with processing summary.
        """
        owns_session = session is None
        if owns_session:
            session = self._session_factory()

        try:
            summary = {
                "task_id": task_id,
                "driver": driver_name,
                "success": result.success,
                "captured": False,
                "stats_updated": False,
            }

            # Step 1: Capture result through capture spine
            if result.output:
                captured = await self._capture_result(
                    tenant_id, task_id, driver_name, result, session, event_bus
                )
                summary["captured"] = captured

            # Step 2: Update driver stats
            stats_ok = await self._update_stats(
                tenant_id, driver_name, "general", result, session
            )
            summary["stats_updated"] = stats_ok

            # Step 3: Emit downstream event
            if event_bus:
                await event_bus.emit(
                    EventType.DRIVER_RESULT,
                    {
                        "task_id": task_id,
                        "driver": driver_name,
                        "success": result.success,
                        "cost_usd": result.cost_usd,
                        "duration_ms": result.duration_ms,
                        "captured": summary["captured"],
                    },
                    source="results_loop",
                )

            if owns_session:
                await session.commit()

            return summary

        except Exception as e:
            logger.error(
                "Results loop failed for task %s: %s", task_id, e, exc_info=True
            )
            if owns_session:
                await session.rollback()
            return {
                "task_id": task_id,
                "driver": driver_name,
                "success": False,
                "error": str(e),
            }
        finally:
            if owns_session:
                await session.close()

    async def _capture_result(
        self,
        tenant_id: str,
        task_id: str,
        driver_name: str,
        result: DriverResult,
        session: AsyncSession,
        event_bus: EventBus | None,
    ) -> bool:
        """Pipe driver output through CaptureService for extraction and storage.

        Creates a capture event with surface='agent_driver' so the
        capture spine processors can extract facts, decisions, etc.

        Returns:
            True if capture succeeded.
        """
        try:
            from life_graph.services.capture import CaptureService

            svc = CaptureService(session, event_bus)
            await svc.ingest(
                tenant_id=tenant_id,
                surface=f"agent_driver:{driver_name}",
                content=result.output[:10000],  # Cap at 10k chars
                modality="text",
                properties={
                    "task_id": task_id,
                    "driver": driver_name,
                    "success": result.success,
                    "cost_usd": result.cost_usd,
                    "duration_ms": result.duration_ms,
                    "artifact_count": len(result.artifacts),
                },
            )
            return True
        except Exception:
            logger.warning(
                "Failed to capture result for task %s", task_id, exc_info=True
            )
            return False

    async def _update_stats(
        self,
        tenant_id: str,
        driver_name: str,
        task_type: str,
        result: DriverResult,
        session: AsyncSession,
    ) -> bool:
        """Update the DriverStat row (day-bucketed) with this result.

        Creates the row if it doesn't exist. Increments counters
        and accumulates cost/duration totals.

        Returns:
            True if stats were updated successfully.
        """
        try:
            from life_graph.models.db import DriverStat

            today = datetime.now(timezone.utc).date()

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

            return True
        except Exception:
            logger.warning("Failed to update driver stats", exc_info=True)
            return False
