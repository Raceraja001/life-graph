"""Daily, just before the brief: gather queued watcher notifications into it.

``watchers/notification_engine.py`` ``route_event`` queues an important event
from a watcher that is not urgent, and nothing ever delivered that queue. This
job gathers each tenant's queued rows into one notification held for the
daily brief (``NotificationEngine.hold_queued_for_brief``): one line under
"Needs attention", and one phone notification, however many were queued.
Rows older than ``watcher_queue_max_age_hours`` are marked expired without
being sent, and at most ``watcher_queue_max_per_run`` per tenant are gathered
per run.

A tenant whose owner pulled the kill switch is skipped, and so is one whose
pause flag cannot be read (fail closed, as ``run_watchers`` does): its queue
waits, and what grows too old while paused expires.
"""

from __future__ import annotations

import logging

from life_graph.autonomy.kill_switch import autonomy_stopped
from life_graph.config import settings
from life_graph.core.tenant import set_tenant_context
from life_graph.runtime import get_notification_engine, get_watcher_notification_engine

logger = logging.getLogger(__name__)


async def deliver_queued_watcher_notifications(ctx: dict | None = None) -> dict:
    """Per tenant with queued watcher notifications: gather them for the brief."""
    engine = get_watcher_notification_engine()
    results: dict[str, dict] = {}
    for tid in await engine.queued_tenants():
        set_tenant_context(tid, "system")
        if await autonomy_stopped(tid):
            logger.warning(
                "Queued watcher notifications left for tenant %s: autonomy is paused", tid
            )
            results[tid] = {"skipped": "autonomy_paused"}
            continue
        try:
            results[tid] = await engine.hold_queued_for_brief(
                tid,
                get_notification_engine(),
                max_age_hours=settings.watcher_queue_max_age_hours,
                limit=settings.watcher_queue_max_per_run,
            )
        except Exception:
            logger.exception("Holding queued watcher notifications failed for tenant %s", tid)
            results[tid] = {"error": 1}
    if results:
        logger.info("Queued watcher notifications: %s", results)
    return {"tenants": len(results), "results": results}
