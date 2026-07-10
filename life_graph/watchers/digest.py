"""Digest generator — compiles INFO events into daily/weekly summaries.

Groups events by watcher, counts per severity, and sends a single
digest notification via the NotificationEngine.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, update

from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)


class DigestGenerator:
    """Compiles pending INFO events into daily or weekly digest notifications."""

    def __init__(self, session_factory=None, notification_engine=None):
        self._session_factory = session_factory or async_session
        self._notification_engine = notification_engine

    async def _get_notification_engine(self):
        """Lazy-load notification engine to avoid circular imports."""
        if self._notification_engine is None:
            from life_graph.watchers.notification_engine import NotificationEngine
            self._notification_engine = NotificationEngine(self._session_factory)
        return self._notification_engine

    async def generate_daily(self, tenant_id: str) -> dict[str, Any]:
        """Compile digest_pending events from the last 24 hours.

        Groups by watcher, generates a readable summary, and sends
        as a single 'info' notification.

        Returns:
            Summary dict with counts.
        """
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        return await self._generate_digest(tenant_id, since, "daily")

    async def generate_weekly(self, tenant_id: str) -> dict[str, Any]:
        """Compile digest_pending events from the last 7 days.

        Returns:
            Summary dict with counts.
        """
        since = datetime.now(timezone.utc) - timedelta(days=7)
        return await self._generate_digest(tenant_id, since, "weekly")

    async def _generate_digest(
        self,
        tenant_id: str,
        since: datetime,
        period: str,
    ) -> dict[str, Any]:
        """Core digest generation logic.

        Args:
            tenant_id: Tenant to generate digest for.
            since: Only include events after this timestamp.
            period: 'daily' or 'weekly' — used in the digest title.

        Returns:
            Summary dict.
        """
        try:
            from life_graph.watchers.models import WatchEvent, Notification

            # Fetch digest-pending events
            async with self._session_factory() as session:
                result = await session.execute(
                    select(WatchEvent).where(
                        WatchEvent.tenant_id == tenant_id,
                        WatchEvent.created_at >= since,
                        WatchEvent.severity == "info",
                    ).order_by(WatchEvent.created_at)
                )
                events = result.scalars().all()

            if not events:
                logger.debug("No events for %s digest (tenant %s)", period, tenant_id)
                return {"period": period, "events": 0, "sent": False}

            # Group by watcher
            by_watcher: dict[str, list[Any]] = defaultdict(list)
            for evt in events:
                watcher = evt.watcher_name or "unknown"
                by_watcher[watcher].append(evt)

            # Build digest body
            body = self._format_digest(by_watcher, period, since)

            # Send as single notification
            engine = await self._get_notification_engine()
            digest_event = {
                "severity": "info",
                "title": f"Ambient AI — {period.capitalize()} Digest",
                "details": body,
                "watcher_name": "digest",
                "timestamp": datetime.now(timezone.utc),
            }

            await engine.route_event(tenant_id, digest_event)

            # Mark processed notifications as sent
            async with self._session_factory() as session:
                await session.execute(
                    update(Notification)
                    .where(
                        Notification.tenant_id == tenant_id,
                        Notification.status == "digest_pending",
                        Notification.created_at >= since,
                    )
                    .values(status="digested")
                )
                await session.commit()

            return {
                "period": period,
                "events": len(events),
                "watchers": len(by_watcher),
                "sent": True,
            }

        except Exception as e:
            logger.error("Failed to generate %s digest: %s", period, e)
            return {"period": period, "events": 0, "sent": False, "error": str(e)}

    @staticmethod
    def _format_digest(
        by_watcher: dict[str, list[Any]],
        period: str,
        since: datetime,
    ) -> str:
        """Format the digest as a readable HTML summary."""
        total = sum(len(events) for events in by_watcher.values())
        since_str = since.strftime("%Y-%m-%d %H:%M UTC")

        sections = []
        for watcher, events in sorted(by_watcher.items()):
            severity_counts: dict[str, int] = defaultdict(int)
            titles = []
            for evt in events:
                severity_counts[evt.severity or "info"] += 1
                if evt.title and len(titles) < 5:
                    titles.append(evt.title)

            counts_str = ", ".join(
                f"{count} {sev}" for sev, count in sorted(severity_counts.items())
            )

            titles_html = "".join(f"<li>{t}</li>" for t in titles)
            if len(events) > 5:
                titles_html += f"<li><em>...and {len(events) - 5} more</em></li>"

            sections.append(
                f"<h3>{watcher}</h3>"
                f"<p>{len(events)} events ({counts_str})</p>"
                f"<ul>{titles_html}</ul>"
            )

        return (
            f"<h2>{period.capitalize()} Digest</h2>"
            f"<p><strong>{total}</strong> events since {since_str} "
            f"across <strong>{len(by_watcher)}</strong> watchers.</p>"
            + "".join(sections)
        )
