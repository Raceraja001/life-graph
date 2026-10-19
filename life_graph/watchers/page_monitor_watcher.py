"""Watcher that checks the tenant's page monitors (services/page_monitors.py).

Runs on the hourly watcher cron; each monitor is fetched only when its own
interval has passed, so a 6-hour monitor is fetched four times a day however
often this runs.
"""

from __future__ import annotations

from life_graph.services import page_monitors
from life_graph.watchers.base import BaseWatcher, Severity


class PageMonitorWatcher(BaseWatcher):
    name = "page_monitor"
    display_name = "Page monitors"
    default_schedule = "0 * * * *"

    async def execute(self) -> None:
        now = page_monitors.now_utc()
        async with self.session_factory() as session:
            monitors = await page_monitors.due_monitors(session, self.tenant_id, now)
            for monitor in monitors:
                event = await page_monitors.check(monitor, now)
                if event is None:
                    continue
                severity = (
                    Severity.IMPORTANT
                    if event.get("severity") == "important" or monitor.mode != "change"
                    else Severity.INFO
                )
                self.emit_event(
                    severity,
                    event["title"],
                    details={**event.get("details", {}), "monitor_id": str(monitor.id)},
                    summary=event.get("summary"),
                )
            await session.commit()
