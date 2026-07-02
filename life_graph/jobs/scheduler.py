"""Job scheduler for periodic Life Graph maintenance tasks (T-059).

Wraps :class:`ConsolidationPipeline` with error handling, logging,
and an asyncio-based cron scheduler that fires at a configurable
hour (default 03:00 UTC).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time, timedelta, timezone

from life_graph.jobs.consolidation import ConsolidationPipeline, ConsolidationReport

logger = logging.getLogger(__name__)


def _seconds_until(target_hour: int, target_minute: int) -> float:
    """Calculate seconds from now until the next occurrence of HH:MM UTC."""
    now = datetime.now(timezone.utc)
    target_today = datetime.combine(
        now.date(), time(target_hour, target_minute), tzinfo=timezone.utc
    )
    if target_today <= now:
        target_today += timedelta(days=1)
    return (target_today - now).total_seconds()


class JobScheduler:
    """Schedule and run Life Graph maintenance jobs.

    Provides manual invocation via :meth:`run_consolidation` and
    automatic nightly scheduling via :meth:`start_cron`.

    Usage::

        scheduler = JobScheduler(consolidation_pipeline)
        report = await scheduler.run_consolidation()

        # Or start the nightly cron (runs at 03:00 UTC by default)
        scheduler.start_cron()
        # ... later ...
        scheduler.stop()
    """

    def __init__(self, consolidation: ConsolidationPipeline) -> None:
        self._consolidation = consolidation
        self._cron_task: asyncio.Task[None] | None = None
        self._running: bool = False

    # ── Manual run ────────────────────────────────────────────

    async def run_consolidation(self) -> ConsolidationReport:
        """Run the consolidation pipeline with error handling.

        Returns a :class:`ConsolidationReport` on success, or a report
        with only ``duration_seconds`` set on failure.
        """
        logger.info("Starting consolidation run")
        try:
            report = await self._consolidation.run()
            logger.info(
                "Consolidation finished: %d gathered, %d archived, $%.4f cost (%.1fs)",
                report.gathered,
                report.memories_archived,
                report.llm_cost_usd,
                report.duration_seconds,
            )
            return report
        except Exception:
            logger.exception("Consolidation run failed")
            return ConsolidationReport()

    # ── Cron scheduling ───────────────────────────────────────

    def start_cron(self, hour: int = 3, minute: int = 0) -> None:
        """Schedule the consolidation pipeline to run nightly.

        Args:
            hour: UTC hour to run (0–23, default 3).
            minute: UTC minute to run (0–59, default 0).
        """
        if self._cron_task is not None:
            logger.warning("Cron already running — call stop() first")
            return

        self._running = True
        self._cron_task = asyncio.create_task(
            self._cron_loop(hour, minute),
            name="consolidation-cron",
        )
        logger.info("Consolidation cron scheduled for %02d:%02d UTC daily", hour, minute)

    def stop(self) -> None:
        """Cancel the scheduled cron task."""
        self._running = False
        if self._cron_task is not None:
            self._cron_task.cancel()
            self._cron_task = None
            logger.info("Consolidation cron stopped")

    @property
    def is_running(self) -> bool:
        """Whether the cron loop is active."""
        return self._running and self._cron_task is not None

    # ── Internal ──────────────────────────────────────────────

    async def _cron_loop(self, hour: int, minute: int) -> None:
        """Sleep-wake loop that fires consolidation at the target time."""
        try:
            while self._running:
                wait_secs = _seconds_until(hour, minute)
                logger.debug(
                    "Next consolidation in %.0f seconds (%.1f hours)",
                    wait_secs,
                    wait_secs / 3600,
                )
                await asyncio.sleep(wait_secs)

                if not self._running:
                    break

                await self.run_consolidation()
        except asyncio.CancelledError:
            logger.debug("Cron loop cancelled")
        except Exception:
            logger.exception("Cron loop crashed — stopping scheduler")
            self._running = False
