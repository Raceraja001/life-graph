"""Webhook Notifier Plugin — forwards Life Graph events to an HTTP webhook.

Configuration (``config.yaml``)::

    webhook_url: https://example.com/webhook
    events:
      - memory:created
      - memory:updated
    timeout_seconds: 5

The plugin subscribes to the configured event types and POSTs each
event payload as JSON to the webhook URL. Failures are logged but
never crash the application.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register(event_bus: Any, config: dict[str, Any]) -> None:
    """Register the webhook notifier with the event bus.

    Args:
        event_bus: The application :class:`EventBus` instance.
        config: Plugin configuration loaded from ``config.yaml``.
    """
    webhook_url = config.get("webhook_url", "")
    events = config.get("events", [])
    timeout = config.get("timeout_seconds", 5)

    if not webhook_url:
        logger.warning("webhook_notifier: No webhook_url configured — plugin disabled")
        return

    if not events:
        logger.warning("webhook_notifier: No events configured — plugin disabled")
        return

    # Import EventType here to resolve the enum values
    from life_graph.core.events import EventType

    # Build the handler closure
    async def _forward_event(event: Any) -> None:
        """POST event payload to the configured webhook URL."""
        try:
            import httpx

            payload = {
                "event_type": event.type.value,
                "source": event.source,
                "timestamp": event.timestamp.isoformat(),
                "payload": event.payload,
            }
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(webhook_url, json=payload)
                if response.status_code >= 400:
                    logger.warning(
                        "webhook_notifier: HTTP %d from %s",
                        response.status_code,
                        webhook_url,
                    )
                else:
                    logger.debug(
                        "webhook_notifier: Forwarded %s to %s (HTTP %d)",
                        event.type.value,
                        webhook_url,
                        response.status_code,
                    )
        except ImportError:
            logger.error("webhook_notifier: httpx is not installed")
        except Exception:
            logger.exception("webhook_notifier: Failed to forward event %s", event.type.value)

    # Subscribe to each configured event type
    for event_name in events:
        try:
            event_type = EventType(event_name)
            event_bus.subscribe(event_type, _forward_event)
            logger.info("webhook_notifier: Subscribed to %s", event_name)
        except ValueError:
            logger.warning("webhook_notifier: Unknown event type '%s' — skipping", event_name)

    logger.info(
        "webhook_notifier: Registered (%d events → %s)",
        len(events),
        webhook_url,
    )
