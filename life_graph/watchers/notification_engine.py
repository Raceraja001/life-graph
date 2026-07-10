"""Notification engine — priority-based routing for watcher events.

Routes events to the appropriate notification channels based on
severity level. Handles immediate dispatch, queued delivery,
and stale-critical re-sends.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)


class NotificationEngine:
    """Routes watcher events to notification channels based on priority.

    Severity routing:
        CRITICAL  → send immediately via ALL enabled channels
        IMPORTANT → queue for same-day delivery via primary channel
        INFO      → mark as digest_pending for daily/weekly digests
    """

    def __init__(self, session_factory=None):
        self._session_factory = session_factory or async_session
        self._channels: dict[str, Any] = {}
        self._loaded = False

    async def _ensure_channels(self) -> None:
        """Lazy-load channel instances."""
        if self._loaded:
            return

        from life_graph.watchers.channels.email_channel import EmailChannel
        from life_graph.watchers.channels.webhook_channel import WebhookChannel
        from life_graph.watchers.channels.terminal_channel import TerminalChannel

        self._channels = {
            "email": EmailChannel(),
            "webhook": WebhookChannel(),
            "terminal": TerminalChannel(),
        }
        self._loaded = True

    async def _load_tenant_channels(self, tenant_id: str) -> list[dict[str, Any]]:
        """Load enabled notification channels for a tenant from DB."""
        try:
            from life_graph.watchers.models import NotificationChannel

            async with self._session_factory() as session:
                result = await session.execute(
                    select(NotificationChannel).where(
                        NotificationChannel.tenant_id == tenant_id,
                        NotificationChannel.enabled == True,  # noqa: E712
                    ).order_by(NotificationChannel.priority.desc())
                )
                rows = result.scalars().all()
                return [
                    {
                        "id": str(row.id),
                        "channel_type": row.channel_type,
                        "config": row.config or {},
                        "priority": row.priority,
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.warning("Failed to load notification channels: %s", e)
            return []

    async def route_event(self, tenant_id: str, event: dict[str, Any]) -> None:
        """Route an event based on its severity.

        Args:
            tenant_id: The tenant this event belongs to.
            event: Event dict with keys: id, severity, title, details,
                   watcher_name, timestamp.
        """
        severity = event.get("severity", "info").lower()

        if severity == "critical":
            await self._send_critical(tenant_id, event)
        elif severity == "important":
            await self._queue_event(tenant_id, event, status="queued")
        else:
            await self._queue_event(tenant_id, event, status="digest_pending")

    async def _send_critical(self, tenant_id: str, event: dict[str, Any]) -> None:
        """Send critical events via ALL enabled channels immediately."""
        channels = await self._load_tenant_channels(tenant_id)

        if not channels:
            logger.warning(
                "No notification channels configured for tenant %s — "
                "critical event '%s' will only be logged",
                tenant_id,
                event.get("title"),
            )
            # Fall back to terminal
            await self._dispatch_terminal(event)
            return

        for ch in channels:
            await self.send(tenant_id, ch["channel_type"], event, ch["config"])

    async def send(
        self,
        tenant_id: str,
        channel_type: str,
        event: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> bool:
        """Dispatch an event to a specific channel type.

        Args:
            tenant_id: The tenant.
            channel_type: 'email', 'webhook', or 'terminal'.
            event: Event dict.
            config: Channel config (loaded from DB if not provided).

        Returns:
            True if send succeeded, False otherwise.
        """
        await self._ensure_channels()

        if config is None:
            channels = await self._load_tenant_channels(tenant_id)
            matched = [c for c in channels if c["channel_type"] == channel_type]
            if not matched:
                logger.warning("No %s channel configured for tenant %s", channel_type, tenant_id)
                return False
            config = matched[0]["config"]

        channel = self._channels.get(channel_type)
        if channel is None:
            logger.error("Unknown channel type: %s", channel_type)
            return False

        try:
            if channel_type == "email":
                return await channel.send(
                    config=config,
                    subject=event.get("title", "Ambient AI Notification"),
                    body=self._build_html_body(event),
                    severity=event.get("severity", "info"),
                )
            elif channel_type == "webhook":
                return await channel.send(
                    config=config,
                    event_id=str(event.get("id", uuid.uuid4())),
                    severity=event.get("severity", "info"),
                    title=event.get("title", ""),
                    details=event.get("details", ""),
                    watcher_name=event.get("watcher_name", "unknown"),
                    timestamp=event.get("timestamp"),
                )
            elif channel_type == "terminal":
                return await channel.send(
                    config=config,
                    severity=event.get("severity", "info"),
                    watcher_name=event.get("watcher_name", "unknown"),
                    title=event.get("title", ""),
                    details=event.get("details", ""),
                )
            else:
                logger.error("Unsupported channel type: %s", channel_type)
                return False
        except Exception as e:
            logger.error("Failed to send via %s: %s", channel_type, e)
            return False

    async def _dispatch_terminal(self, event: dict[str, Any]) -> None:
        """Fallback: dispatch to terminal channel with empty config."""
        await self._ensure_channels()
        channel = self._channels.get("terminal")
        if channel:
            await channel.send(
                config={},
                severity=event.get("severity", "info"),
                watcher_name=event.get("watcher_name", "unknown"),
                title=event.get("title", ""),
                details=event.get("details", ""),
            )

    async def _queue_event(
        self,
        tenant_id: str,
        event: dict[str, Any],
        status: str = "queued",
    ) -> None:
        """Store an event notification in DB for later delivery."""
        try:
            from life_graph.watchers.models import Notification

            async with self._session_factory() as session:
                notif = Notification(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    event_id=event.get("id"),
                    channel_type=self._get_primary_channel_type(tenant_id),
                    title=event.get("title", ""),
                    body=event.get("details", ""),
                    severity=event.get("severity", "info"),
                    status=status,
                )
                session.add(notif)
                await session.commit()
        except Exception as e:
            logger.error("Failed to queue notification: %s", e)

    def _get_primary_channel_type(self, tenant_id: str) -> str:
        """Return the primary channel type (highest priority). Default terminal."""
        # This is a sync helper; in practice the caller should have
        # already loaded channels.  We default to 'terminal'.
        return "terminal"

    async def process_pending(self, tenant_id: str) -> int:
        """Send all queued (non-digest) notifications for a tenant.

        Returns:
            Number of notifications successfully sent.
        """
        try:
            from life_graph.watchers.models import Notification

            async with self._session_factory() as session:
                result = await session.execute(
                    select(Notification).where(
                        Notification.tenant_id == tenant_id,
                        Notification.status == "queued",
                    ).order_by(Notification.created_at)
                )
                pending = result.scalars().all()

            sent_count = 0
            for notif in pending:
                event = {
                    "id": str(notif.event_id) if notif.event_id else str(notif.id),
                    "severity": notif.severity,
                    "title": notif.title,
                    "details": notif.body,
                    "watcher_name": "queued",
                }

                success = await self.send(
                    tenant_id,
                    notif.channel_type or "terminal",
                    event,
                )

                new_status = "sent" if success else "failed"
                async with self._session_factory() as session:
                    await session.execute(
                        update(Notification)
                        .where(Notification.id == notif.id)
                        .values(
                            status=new_status,
                            sent_at=datetime.now(timezone.utc) if success else None,
                        )
                    )
                    await session.commit()

                if success:
                    sent_count += 1

            return sent_count

        except Exception as e:
            logger.error("Failed to process pending notifications: %s", e)
            return 0

    async def check_stale_critical(self, tenant_id: str) -> int:
        """Re-send unacknowledged critical events older than 24h.

        Max 3 retries per event.  Returns number of re-sends attempted.
        """
        try:
            from life_graph.watchers.models import WatchEvent

            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

            async with self._session_factory() as session:
                result = await session.execute(
                    select(WatchEvent).where(
                        WatchEvent.tenant_id == tenant_id,
                        WatchEvent.severity == "critical",
                        WatchEvent.acknowledged == False,  # noqa: E712
                        WatchEvent.created_at <= cutoff,
                        WatchEvent.retry_count < 3,
                    )
                )
                stale = result.scalars().all()

            resent = 0
            for evt in stale:
                event_dict = {
                    "id": str(evt.id),
                    "severity": "critical",
                    "title": evt.title,
                    "details": evt.details or "",
                    "watcher_name": evt.watcher_name or "unknown",
                    "timestamp": evt.created_at,
                }
                await self._send_critical(tenant_id, event_dict)

                # Increment retry counter
                async with self._session_factory() as session:
                    await session.execute(
                        update(WatchEvent)
                        .where(WatchEvent.id == evt.id)
                        .values(retry_count=WatchEvent.retry_count + 1)
                    )
                    await session.commit()

                resent += 1

            if resent:
                logger.info(
                    "Re-sent %d stale critical events for tenant %s",
                    resent,
                    tenant_id,
                )

            return resent

        except Exception as e:
            logger.error("Failed to check stale criticals: %s", e)
            return 0

    @staticmethod
    def _build_html_body(event: dict[str, Any]) -> str:
        """Build a simple HTML body from an event dict."""
        severity = event.get("severity", "info").upper()
        title = event.get("title", "Notification")
        details = event.get("details", "")
        watcher = event.get("watcher_name", "unknown")
        ts = event.get("timestamp", datetime.now(timezone.utc))

        if isinstance(ts, datetime):
            ts = ts.strftime("%Y-%m-%d %H:%M:%S UTC")

        color = {"CRITICAL": "#dc3545", "IMPORTANT": "#fd7e14", "INFO": "#0d6efd"}.get(
            severity, "#6c757d"
        )

        return f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: {color}; color: white; padding: 12px 20px; border-radius: 8px 8px 0 0;">
                <h2 style="margin: 0; font-size: 18px;">{severity}: {title}</h2>
            </div>
            <div style="background: #f8f9fa; padding: 20px; border: 1px solid #dee2e6; border-top: none; border-radius: 0 0 8px 8px;">
                <p style="margin: 0 0 12px 0; color: #495057;"><strong>Watcher:</strong> {watcher}</p>
                <p style="margin: 0 0 12px 0; color: #495057;"><strong>Time:</strong> {ts}</p>
                <div style="background: white; padding: 16px; border-radius: 4px; border: 1px solid #dee2e6; margin-top: 8px;">
                    {details or '<em>No additional details.</em>'}
                </div>
            </div>
        </div>
        """
