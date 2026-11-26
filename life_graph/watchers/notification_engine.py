"""Notification engine — priority-based routing for watcher events.

Routes events to the appropriate notification channels based on
severity level. Handles immediate dispatch, queued delivery,
and stale-critical re-sends.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update

from life_graph.storage.database import async_session
from life_graph.watchers.models import WatcherNotification

logger = logging.getLogger(__name__)

# Watchers whose IMPORTANT events are pushed to the phone at once rather than
# queued: an app down, a certificate about to lapse, a failing backup (Job 7).
URGENT_WATCHERS: frozenset[str] = frozenset({"app_uptime", "server_health"})

#: ``watcher_notifications.status`` once a queued row has been handed to the
#: daily brief (:meth:`NotificationEngine.hold_queued_for_brief`).
HELD_FOR_BRIEF = "held_for_brief"
#: ``watcher_notifications.status`` of a queued row that was too old to send.
EXPIRED = "expired"
#: ``notifications.source_type`` of what this engine holds for the brief.
WATCHER_SOURCE = "watcher"


def _as_text(value: Any) -> str:
    """Render an event's ``details`` for a text column.

    WatchEvent.details is JSONB and genuinely holds either shape: the ad-hoc
    watchers store a string, BaseWatcher.emit_event() stores a dict. The
    notification body is a Text column, so a dict reaching it raises
    asyncpg DataError("expected str, got dict") at insert time.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError):
        return str(value)


def _summary(times: dict[str, int], left: int) -> tuple[str, str]:
    """Title and body of the one notification that gathers queued findings.

    *times* maps each queued title to how often it was queued, oldest first.
    """
    n = sum(times.values())
    first = next(iter(times))
    title = f"{n} watcher finding{'s' if n != 1 else ''}: {first}"
    if len(times) > 1:
        title += f" and {len(times) - 1} more"
    lines = [f"- {t}" + (f" (x{k})" if k > 1 else "") for t, k in times.items()]
    if left:
        lines.append(f"{left} more still queued.")
    return title[:500], "\n".join(lines)


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
        from life_graph.watchers.channels.telegram_channel import TelegramChannel
        from life_graph.watchers.channels.terminal_channel import TerminalChannel
        from life_graph.watchers.channels.webhook_channel import WebhookChannel

        self._channels = {
            "email": EmailChannel(),
            "webhook": WebhookChannel(),
            "terminal": TerminalChannel(),
            "telegram": TelegramChannel(),
        }
        self._loaded = True

    async def _load_tenant_channels(self, tenant_id: str) -> list[dict[str, Any]]:
        """Load enabled notification channels for a tenant from DB."""
        try:
            from life_graph.watchers.models import NotificationChannel

            async with self._session_factory() as session:
                result = await session.execute(
                    select(NotificationChannel)
                    .where(
                        NotificationChannel.tenant_id == tenant_id,
                        NotificationChannel.enabled == True,  # noqa: E712
                    )
                    .order_by(NotificationChannel.priority.desc())
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
            # Not a quiet failure: with no channels, nothing is sent for this tenant.
            logger.error(
                "Failed to load notification channels for tenant %s; its notifications "
                "will not be sent: %s",
                tenant_id,
                e,
                exc_info=True,
            )
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
        elif severity == "important" and event.get("watcher_name") in URGENT_WATCHERS:
            # An app down or a backup failing cannot wait for a queue that
            # nothing drains: it goes to the phone now (Job 7).
            sent = await self._send_urgent(tenant_id, event)
            await self._queue_event(tenant_id, event, status="sent" if sent else "queued")
        elif severity == "important":
            await self._queue_event(tenant_id, event, status="queued")
        else:
            await self._queue_event(tenant_id, event, status="digest_pending")

    async def _send_urgent(self, tenant_id: str, event: dict[str, Any]) -> bool:
        """Web Push and Telegram, as approvals are (services/notifications/approval.py).
        True when at least one reached a device or chat."""
        from life_graph.services.notifications.webpush import PushService
        from life_graph.watchers.channels.telegram_channel import TelegramChannel

        title = str(event.get("title") or "Alert")
        details = event.get("details")
        detail = (
            str(details.get("url") or "") if isinstance(details, dict) else _as_text(details)
        )[:500]
        sent = False
        try:
            sent = (
                await PushService(self._session_factory).send_to_tenant(
                    tenant_id, title, detail, "/m"
                )
            ) > 0
        except Exception:
            logger.warning("Push of urgent event %r failed", title, exc_info=True)
        try:
            ok = await TelegramChannel(session_factory=self._session_factory).send(
                config={},
                tenant_id=tenant_id,
                severity="important",
                title=title,
                details=detail,
                watcher_name=event.get("watcher_name"),
            )
            sent = sent or bool(ok)
        except Exception:
            logger.warning("Telegram of urgent event %r failed", title, exc_info=True)
        if not sent:
            logger.warning("Urgent event %r reached no device or chat (none paired?)", title)
        return sent

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
            elif channel_type == "telegram":
                # The only channel that needs the tenant: its destinations come
                # from telegram_bindings, not from the config blob, because a
                # chat_id only exists after the user pairs a chat.
                return await channel.send(
                    config=config,
                    tenant_id=tenant_id,
                    severity=event.get("severity", "info"),
                    title=event.get("title", ""),
                    details=_as_text(event.get("details")),
                    watcher_name=event.get("watcher_name", "unknown"),
                )
            else:
                logger.error("Unsupported channel type: %s", channel_type)
                return False
        except Exception as e:
            logger.error("Failed to send via %s: %s", channel_type, e, exc_info=True)
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
        """Store an event notification in DB for later delivery.

        ``event_id`` is NOT NULL and a FK to ``watch_events.id``, so an event
        dict without an ``id`` cannot be persisted — watcher event dicts do
        not carry one until the WatchEvent row has been written, so the
        caller must inject it.
        """
        raw_id = event.get("id")
        if not raw_id:
            logger.warning(
                "Skipping notification for tenant %s: event has no id (title=%r)",
                tenant_id,
                event.get("title", ""),
            )
            return

        try:
            event_id = raw_id if isinstance(raw_id, uuid.UUID) else uuid.UUID(str(raw_id))
        except (ValueError, AttributeError, TypeError):
            logger.warning("Skipping notification: event id %r is not a UUID", raw_id)
            return

        try:
            from life_graph.watchers.models import WatcherNotification

            async with self._session_factory() as session:
                notif = WatcherNotification(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    event_id=event_id,
                    channel=self._get_primary_channel_type(tenant_id),
                    subject=event.get("title", ""),
                    body=_as_text(event.get("details")),
                    severity=event.get("severity", "info"),
                    status=status,
                )
                session.add(notif)
                await session.commit()
        except Exception as e:
            logger.error("Failed to queue notification: %s", e, exc_info=True)

    def _get_primary_channel_type(self, tenant_id: str) -> str:
        """Return the primary channel type (highest priority). Default terminal."""
        # This is a sync helper; in practice the caller should have
        # already loaded channels.  We default to 'terminal'.
        return "terminal"

    async def queued_tenants(self) -> list[str]:
        """Tenants with at least one ``queued`` watcher notification."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(WatcherNotification.tenant_id)
                .where(WatcherNotification.status == "queued")
                .distinct()
            )
            return sorted(row[0] for row in result.fetchall())

    async def hold_queued_for_brief(
        self,
        tenant_id: str,
        notifications: Any,
        *,
        max_age_hours: int,
        limit: int,
        now: datetime | None = None,
    ) -> dict[str, int]:
        """Gather a tenant's ``queued`` watcher notifications into the daily brief.

        ``route_event`` queues an important event from a non-urgent watcher,
        and nothing ever sent the queue. Now the fresh ones become **one**
        kernel notification flagged ``deliver_at_brief`` (*notifications* is
        the kernel ``NotificationEngine``), which the next daily brief lists
        under "Needs attention" (services/brief.py
        ``_collect_held_notifications``). That is the path the findings
        bridge and the money reminders use for news that can wait. One row,
        not one per event, because the phone posts every new notifications
        row (api/jarvis.py ``GET /notifications``).

        To keep a backlog from flooding the brief:

        - a row older than *max_age_hours* is marked ``expired`` and never
          sent;
        - at most *limit* rows are gathered per call, oldest first; the rest
          stay queued, and the summary says how many;
        - the same title queued several times (a watcher raising one finding
          every hour) is one line with a count.

        The gathered rows are marked ``held_for_brief`` with ``digest_id``
        set to the summary's id, only after the summary was written; if
        writing fails they stay queued and are tried again.

        Returns:
            Counts: ``held`` (rows gathered), ``lines`` (distinct titles),
            ``expired``, ``left`` (still queued, over *limit*), ``failed``
            (rows left queued because the summary could not be written).
        """
        now = now or datetime.now(UTC)
        cutoff = now - timedelta(hours=max_age_hours)
        queued = (
            WatcherNotification.tenant_id == tenant_id,
            WatcherNotification.status == "queued",
        )
        async with self._session_factory() as session:
            expired = await session.execute(
                update(WatcherNotification)
                .where(*queued, WatcherNotification.created_at < cutoff)
                .values(
                    status=EXPIRED,
                    error_message=f"Queued over {max_age_hours} h; not sent.",
                )
            )
            rows = (
                (
                    await session.execute(
                        select(WatcherNotification)
                        .where(*queued)
                        .order_by(WatcherNotification.created_at, WatcherNotification.id)
                        .limit(max(0, limit))
                    )
                )
                .scalars()
                .all()
            )
            total = await session.scalar(
                select(func.count()).select_from(WatcherNotification).where(*queued)
            )
            await session.commit()

        counts = {
            "held": 0,
            "lines": 0,
            "expired": int(expired.rowcount or 0),
            "left": max(0, int(total or 0) - len(rows)),
            "failed": 0,
        }
        if not rows:
            return counts
        times: dict[str, int] = {}
        for row in rows:
            title = row.subject or "Watcher alert"
            times[title] = times.get(title, 0) + 1
        title, body = _summary(times, counts["left"])
        try:
            created = await notifications.create(
                tenant_id,
                title,
                body=body,
                priority="important",
                source_type=WATCHER_SOURCE,
                metadata={"watcher_notification_ids": [str(r.id) for r in rows]},
                deliver_at_brief=True,
            )
        except Exception:
            logger.warning(
                "Could not hold %d watcher notifications for the brief (tenant %s)",
                len(rows),
                tenant_id,
                exc_info=True,
            )
            counts["failed"] = len(rows)
            return counts
        async with self._session_factory() as session:
            await session.execute(
                update(WatcherNotification)
                .where(WatcherNotification.id.in_([r.id for r in rows]))
                .values(status=HELD_FOR_BRIEF, digest_id=uuid.UUID(str(created["id"])))
            )
            await session.commit()
        counts["held"] = len(rows)
        counts["lines"] = len(times)
        return counts

    async def process_pending(self, tenant_id: str) -> int:
        """Send all queued (non-digest) notifications for a tenant.

        Not scheduled: every queued row's channel is ``terminal`` (see
        ``_get_primary_channel_type``), so this would only log them. The
        daily job (workers/watcher_queue.py) uses :meth:`hold_queued_for_brief`.

        Returns:
            Number of notifications successfully sent.
        """
        try:
            from life_graph.watchers.models import WatcherNotification

            async with self._session_factory() as session:
                result = await session.execute(
                    select(WatcherNotification)
                    .where(
                        WatcherNotification.tenant_id == tenant_id,
                        WatcherNotification.status == "queued",
                    )
                    .order_by(WatcherNotification.created_at)
                )
                pending = result.scalars().all()

            sent_count = 0
            for notif in pending:
                event = {
                    "id": str(notif.event_id) if notif.event_id else str(notif.id),
                    "severity": notif.severity,
                    "title": notif.subject,
                    "details": notif.body,
                    "watcher_name": "queued",
                }

                success = await self.send(
                    tenant_id,
                    notif.channel or "terminal",
                    event,
                )

                new_status = "sent" if success else "failed"
                async with self._session_factory() as session:
                    await session.execute(
                        update(WatcherNotification)
                        .where(WatcherNotification.id == notif.id)
                        .values(
                            status=new_status,
                            sent_at=datetime.now(UTC) if success else None,
                        )
                    )
                    await session.commit()

                if success:
                    sent_count += 1

            return sent_count

        except Exception as e:
            logger.error("Failed to process pending notifications: %s", e, exc_info=True)
            return 0

    _MAX_CRITICAL_RETRIES = 3

    async def check_stale_critical(self, tenant_id: str) -> int:
        """Re-send unacknowledged critical events older than 24h.

        Max 3 retries per event. Returns number of re-sends attempted.

        WatchEvent has neither an ``acknowledged`` flag nor a ``retry_count``
        column — acknowledgement is recorded as ``acknowledged_at``, and the
        retry counter lives on WatcherNotification, which is where deliveries
        are tracked. This method referenced all three of the non-existent
        names; nothing calls it, so nothing ever raised.
        """
        try:
            from life_graph.watchers.models import WatcherNotification, WatchEvent

            cutoff = datetime.now(UTC) - timedelta(hours=24)

            # Highest retry count recorded against each event's notifications.
            retries = (
                select(
                    WatcherNotification.event_id.label("event_id"),
                    func.max(WatcherNotification.retry_count).label("retries"),
                )
                .where(WatcherNotification.tenant_id == tenant_id)
                .group_by(WatcherNotification.event_id)
                .subquery()
            )

            async with self._session_factory() as session:
                result = await session.execute(
                    select(WatchEvent)
                    .outerjoin(retries, retries.c.event_id == WatchEvent.id)
                    .where(
                        WatchEvent.tenant_id == tenant_id,
                        WatchEvent.severity == "critical",
                        WatchEvent.acknowledged_at.is_(None),
                        WatchEvent.created_at <= cutoff,
                        func.coalesce(retries.c.retries, 0) < self._MAX_CRITICAL_RETRIES,
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
                await self._record_retry(tenant_id, evt)
                resent += 1

            if resent:
                logger.info(
                    "Re-sent %d stale critical events for tenant %s",
                    resent,
                    tenant_id,
                )

            return resent

        except Exception as e:
            logger.error("Failed to check stale criticals: %s", e, exc_info=True)
            return 0

    async def _record_retry(self, tenant_id: str, evt: Any) -> None:
        """Bump the retry counter for one event's notifications.

        Creates a row when the event has none — ``_send_critical`` dispatches
        straight to the channels without persisting, so a critical event that
        was never queued has nothing to count.
        """
        from life_graph.watchers.models import WatcherNotification

        async with self._session_factory() as session:
            result = await session.execute(
                select(WatcherNotification).where(
                    WatcherNotification.tenant_id == tenant_id,
                    WatcherNotification.event_id == evt.id,
                )
            )
            existing = result.scalars().all()

            if existing:
                await session.execute(
                    update(WatcherNotification)
                    .where(
                        WatcherNotification.tenant_id == tenant_id,
                        WatcherNotification.event_id == evt.id,
                    )
                    .values(retry_count=WatcherNotification.retry_count + 1)
                )
            else:
                session.add(
                    WatcherNotification(
                        id=uuid.uuid4(),
                        tenant_id=tenant_id,
                        event_id=evt.id,
                        channel=self._get_primary_channel_type(tenant_id),
                        severity="critical",
                        status="sent",
                        subject=evt.title,
                        body=_as_text(evt.details),
                        sent_at=datetime.now(UTC),
                        retry_count=1,
                    )
                )
            await session.commit()

    @staticmethod
    def _build_html_body(event: dict[str, Any]) -> str:
        """Build a simple HTML body from an event dict."""
        severity = event.get("severity", "info").upper()
        title = event.get("title", "Notification")
        details = event.get("details", "")
        watcher = event.get("watcher_name", "unknown")
        ts = event.get("timestamp", datetime.now(UTC))

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
                    {details or "<em>No additional details.</em>"}
                </div>
            </div>
        </div>
        """
