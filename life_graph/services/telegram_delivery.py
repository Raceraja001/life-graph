"""Deliver the daily brief to Telegram when BRIEF_COMPOSED fires.

Modelled on :mod:`life_graph.services.push_delivery`, which does the same job
for Web Push. Kept as a separate handler rather than folded into that one so
that a tenant with no paired chat, or no push subscription, still gets the
other channel.

Subscribed in *both* the API lifespan and the ARQ worker's ``on_startup``:
the 03:00 cron composes briefs in the worker, and the EventBus is per-process
(its Redis bridge is one-way fan-out to WebSocket clients, not a cross-process
re-emit), so a handler registered only in the API would never hear the cron.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select

from life_graph.core.events import Event, EventType, event_bus
from life_graph.models.db import Notification
from life_graph.storage.database import async_session
from life_graph.watchers.channels.telegram_channel import TelegramChannel

logger = logging.getLogger(__name__)


class TelegramDeliveryHandler:
    """Subscribes to BRIEF_COMPOSED and sends the brief to paired chats."""

    def __init__(self, session_factory=None, channel=None) -> None:  # noqa: ANN001
        self._subscribed = False
        self._session_factory = session_factory or async_session
        self._channel = channel or TelegramChannel(session_factory=self._session_factory)

    def subscribe(self) -> None:
        if self._subscribed:
            return
        event_bus.subscribe(EventType.BRIEF_COMPOSED, self._on_brief)
        self._subscribed = True

    async def _on_brief(self, event: Event) -> None:
        try:
            data = event.payload
            tenant_id = data.get("tenant_id")
            if not tenant_id:
                return

            title = data.get("title") or "Daily brief"
            body = await self._brief_body(tenant_id, data.get("notification_id"))

            await self._channel.send(
                config={},
                tenant_id=tenant_id,
                # The brief is a scheduled summary, not an alert: 'info' keeps
                # it silent so it waits rather than waking the user at 03:00.
                severity="info",
                title=title,
                details=body,
                watcher_name=None,
            )
        except Exception:  # pragma: no cover - delivery must never break the brief flow
            logger.warning("Telegram delivery of brief failed", exc_info=True)

    async def _brief_body(self, tenant_id: str, notif_id: object) -> str | None:
        """Load the brief's stored body, scoped to its tenant."""
        if not notif_id:
            return None
        try:
            async with self._session_factory() as session:
                row = (
                    await session.execute(
                        select(Notification).where(
                            Notification.id == uuid.UUID(str(notif_id)),
                            Notification.tenant_id == tenant_id,
                        )
                    )
                ).scalar_one_or_none()
                return row.body if row else None
        except (ValueError, AttributeError, TypeError):
            logger.warning("Brief notification id %r is not a UUID", notif_id)
            return None


telegram_delivery_handler = TelegramDeliveryHandler()
