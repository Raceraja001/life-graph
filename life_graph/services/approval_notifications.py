"""Notify the user when a new approval needs them.

driver_pr, driver_merge, driver_plan and driver_deploy all land in the same
``approvals`` table (see services/approvals.py), but until this, none of them
told anyone they existed — a human only found out by opening the dashboard
or asking. Modelled on push_delivery.py / telegram_delivery.py (which do the
same job for BRIEF_COMPOSED): one handler covering both channels, since an
approval needing someone is exactly the kind of thing that should reach
whichever one they have configured, not just whichever one happened to be
built first.
"""

from __future__ import annotations

import logging

from life_graph.core.events import Event, EventType, event_bus
from life_graph.storage.database import async_session
from life_graph.watchers.channels.telegram_channel import TelegramChannel

logger = logging.getLogger(__name__)

_MOBILE_APPROVALS_URL = "/m/approvals"


class ApprovalNotificationHandler:
    """Subscribes to APPROVAL_FILED and pushes/Telegrams a summary."""

    def __init__(self, session_factory=None, push=None, channel=None) -> None:  # noqa: ANN001
        self._subscribed = False
        self._session_factory = session_factory or async_session
        if push is None:
            from life_graph.services.webpush import PushService

            push = PushService(self._session_factory)
        self._push = push
        self._channel = channel or TelegramChannel(session_factory=self._session_factory)

    def subscribe(self) -> None:
        if self._subscribed:
            return
        event_bus.subscribe(EventType.APPROVAL_FILED, self._on_approval_filed)
        self._subscribed = True

    async def _on_approval_filed(self, event: Event) -> None:
        data = event.payload
        tenant_id = data.get("tenant_id")
        if not tenant_id:
            return
        title = data.get("title") or "Approval needed"
        # `detail` is deliberately the full approval detail (by this point
        # already the real content — the spec, the deploy command, etc. —
        # not just a description of the step), truncated for a push/chat
        # message rather than a full review surface.
        detail = (data.get("detail") or "")[:500]

        try:
            await self._push.send_to_tenant(tenant_id, title, detail, _MOBILE_APPROVALS_URL)
        except Exception:
            logger.warning("Push delivery of approval notification failed", exc_info=True)

        try:
            await self._channel.send(
                config={},
                tenant_id=tenant_id,
                # Not "info" (that's forced silent) and not "critical" (reserved
                # for actual incidents) -- this needs attention, soon, but isn't
                # an emergency.
                severity="important",
                title=title,
                details=detail,
                watcher_name=None,
            )
        except Exception:
            logger.warning("Telegram delivery of approval notification failed", exc_info=True)


approval_notification_handler = ApprovalNotificationHandler()
