"""Deliver the daily brief to the phone via Web Push when BRIEF_COMPOSED fires."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select

from life_graph.core.events import Event, EventType, event_bus
from life_graph.core.tenant import set_tenant_context
from life_graph.models.db import Notification
from life_graph.services.webpush import PushService
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)


class PushDeliveryHandler:
    """Subscribes to BRIEF_COMPOSED and pushes the brief to the tenant's devices."""

    def __init__(self) -> None:
        self._subscribed = False
        self._push = PushService(async_session)

    def subscribe(self) -> None:
        if self._subscribed:
            return
        event_bus.subscribe(EventType.BRIEF_COMPOSED, self._on_brief)
        self._subscribed = True

    async def _on_brief(self, event: Event) -> None:
        try:
            data = event.payload
            tenant_id = data.get("tenant_id")
            title = data.get("title") or "Daily brief"
            notif_id = data.get("notification_id")
            body = title
            if notif_id and tenant_id:
                set_tenant_context(tenant_id, "system")
                async with async_session() as session:
                    row = (
                        await session.execute(
                            select(Notification).where(Notification.id == uuid.UUID(str(notif_id)))
                        )
                    ).scalar_one_or_none()
                    if row and row.body:
                        body = row.body
            if tenant_id:
                await self._push.send_to_tenant(tenant_id, title, body, "/m")
        except Exception:  # pragma: no cover - delivery must never break the brief flow
            logger.warning("Push delivery of brief failed", exc_info=True)


push_delivery_handler = PushDeliveryHandler()
