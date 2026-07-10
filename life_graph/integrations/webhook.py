"""Webhook delivery system for Life Graph tenant notifications.

Provides:
- HMAC-SHA256 signed payload delivery to registered webhook URLs.
- Circuit breaker: webhooks are auto-deactivated after consecutive failures.
- ARQ task ``deliver_webhook`` for reliable background delivery with retries.
- ``WebhookEventHandler`` that subscribes to the EventBus and enqueues
  delivery jobs via ARQ, never blocking the event loop.

Usage::

    from life_graph.core.events import event_bus
    from life_graph.integrations.webhook import WebhookEventHandler

    handler = WebhookEventHandler(event_bus)
    handler.set_arq_pool(arq_pool)   # call after ARQ pool is ready
    handler.start()                   # subscribe to all events
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select

from life_graph.core.events import Event, EventBus, EventType
from life_graph.models.db import TenantWebhook
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────

CIRCUIT_BREAKER_THRESHOLD: int = 10
"""Consecutive delivery failures before the webhook is auto-deactivated."""

DELIVERY_TIMEOUT: float = 10.0
"""HTTP timeout (seconds) for outbound webhook requests."""


# ── Payload Signing ──────────────────────────────────────────


def sign_payload(secret: str, payload: bytes) -> str:
    """Generate an HMAC-SHA256 hex-digest signature for *payload*.

    The receiving server should compute the same HMAC using its copy
    of the shared secret and compare it to the ``X-Webhook-Signature``
    header to verify authenticity.

    Args:
        secret: The shared secret string (stored on the TenantWebhook).
        payload: Raw JSON body bytes to sign.

    Returns:
        Hex-encoded HMAC-SHA256 digest.
    """
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


# ── ARQ Task ─────────────────────────────────────────────────


async def deliver_webhook(
    ctx: dict,
    webhook_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """ARQ task: deliver a single webhook notification.

    Constructs a signed JSON payload and POSTs it to the webhook URL.
    On success, resets the failure counter and records the delivery time.
    On failure, increments the failure counter and — if it exceeds
    ``CIRCUIT_BREAKER_THRESHOLD`` — deactivates the webhook entirely.

    The task is automatically retried by ARQ on exception (up to
    ``max_tries`` configured in WorkerSettings).

    Args:
        ctx: ARQ worker context (contains ``redis`` connection).
        webhook_id: UUID of the :class:`TenantWebhook` to deliver to.
        event_type: String event type (e.g. ``"memory:created"``).
        payload: Event payload dictionary.

    Returns:
        Dict with ``status`` (``"delivered"`` or ``"skipped"``) and
        additional metadata.

    Raises:
        Exception: Re-raised after recording the failure so ARQ retries.
    """
    async with async_session() as session:
        webhook = await session.get(TenantWebhook, webhook_id)
        if not webhook or not webhook.active:
            return {"status": "skipped", "reason": "webhook inactive or not found"}

        # Build the signed envelope
        body = json.dumps(
            {
                "event": event_type,
                "payload": payload,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "webhook_id": str(webhook.id),
            },
            default=str,
        ).encode()

        signature = sign_payload(webhook.secret, body)

        try:
            async with httpx.AsyncClient(timeout=DELIVERY_TIMEOUT) as client:
                resp = await client.post(
                    webhook.url,
                    content=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Webhook-Signature": signature,
                        "X-Event-Type": event_type,
                    },
                )
                resp.raise_for_status()

            # Success — reset failure counter
            webhook.failure_count = 0
            webhook.last_delivered_at = datetime.now(timezone.utc)
            await session.commit()

            logger.debug(
                "Webhook %s delivered successfully (HTTP %d)",
                webhook.id,
                resp.status_code,
            )
            return {"status": "delivered", "http_status": resp.status_code}

        except Exception as exc:
            webhook.failure_count += 1

            if webhook.failure_count >= CIRCUIT_BREAKER_THRESHOLD:
                webhook.active = False
                logger.warning(
                    "Webhook %s deactivated after %d consecutive failures",
                    webhook.id,
                    webhook.failure_count,
                )

            await session.commit()

            logger.error(
                "Webhook %s delivery failed (attempt failure_count=%d): %s",
                webhook.id,
                webhook.failure_count,
                exc,
            )
            # Re-raise so ARQ retries
            raise


# ── EventBus → ARQ Bridge ───────────────────────────────────


class WebhookEventHandler:
    """Subscribes to :class:`EventBus` and enqueues webhook delivery jobs.

    This handler never blocks the event bus.  It queries the database
    for active webhooks that match the event and enqueues an ARQ job
    for each one.

    The ARQ pool must be provided via :meth:`set_arq_pool` before
    events can be enqueued.  If no pool is available, events are
    logged and silently skipped.

    Args:
        event_bus: The application-wide :class:`EventBus` instance.

    Example::

        handler = WebhookEventHandler(event_bus)
        handler.set_arq_pool(arq_pool)
        handler.start()
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._arq_pool: Any | None = None

    def set_arq_pool(self, pool: Any) -> None:
        """Set the ARQ Redis pool used for enqueuing jobs.

        Should be called during application startup once the ARQ
        connection pool has been created.

        Args:
            pool: An :class:`arq.ArqRedis` connection pool.
        """
        self._arq_pool = pool
        logger.info("WebhookEventHandler: ARQ pool configured")

    def start(self) -> None:
        """Subscribe to all events on the event bus.

        Call this once during application startup.  After this call,
        every event emitted on the bus will trigger :meth:`_handle_event`.
        """
        self._event_bus.subscribe_all(self._handle_event)
        logger.info("WebhookEventHandler subscribed to event bus")

    async def _handle_event(self, event: Event) -> None:
        """Query webhooks for the current tenant and enqueue delivery jobs.

        Resolves the tenant from the tenant context.  If no tenant
        context is active (e.g. system-level events), the event is
        silently skipped.

        For each active webhook that subscribes to the event type,
        an ARQ job is enqueued via ``deliver_webhook``.

        Args:
            event: The :class:`Event` emitted by the bus.
        """
        # Resolve tenant — skip system events with no tenant context
        try:
            from life_graph.core.tenant import get_current_tenant_id

            tenant_id = get_current_tenant_id()
        except Exception:
            return

        if self._arq_pool is None:
            logger.debug(
                "WebhookEventHandler: ARQ pool not set, skipping enqueue for event %s",
                event.type,
            )
            return

        # Resolve event type to a string for matching
        event_str = (
            event.type.value
            if isinstance(event.type, EventType)
            else str(event.type)
        )

        # Find active webhooks for this tenant
        async with async_session() as session:
            result = await session.execute(
                select(TenantWebhook).where(
                    TenantWebhook.tenant_id == tenant_id,
                    TenantWebhook.active == True,  # noqa: E712
                )
            )
            webhooks = result.scalars().all()

        # Enqueue a delivery job for each matching webhook
        for webhook in webhooks:
            # Check if the webhook subscribes to this event type
            if webhook.events != "*" and event_str not in webhook.events.split(","):
                continue

            try:
                await self._arq_pool.enqueue_job(
                    "deliver_webhook",
                    str(webhook.id),
                    event_str,
                    event.payload,
                )
                logger.debug(
                    "Enqueued webhook delivery: webhook=%s event=%s",
                    webhook.id,
                    event_str,
                )
            except Exception:
                logger.warning(
                    "Failed to enqueue webhook delivery for %s",
                    webhook.id,
                    exc_info=True,
                )
