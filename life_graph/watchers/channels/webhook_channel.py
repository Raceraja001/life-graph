"""Webhook notification channel — POSTs JSON with HMAC-SHA256 signature.

Config dict keys:
    url (required), secret (for HMAC signing), timeout (default 10).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


class WebhookChannel:
    """Sends notification events as signed JSON POST requests."""

    async def send(
        self,
        config: dict[str, Any],
        event_id: str,
        severity: str,
        title: str,
        details: str,
        watcher_name: str,
        timestamp: datetime | None = None,
    ) -> bool:
        """POST a signed JSON payload to the configured webhook URL.

        Args:
            config: Webhook config (url, secret, timeout).
            event_id: Unique event identifier.
            severity: Event severity level.
            title: Event title.
            details: Event details/body.
            watcher_name: Name of the originating watcher.
            timestamp: Event timestamp (defaults to now UTC).

        Returns:
            True on success (2xx), False on failure.
        """
        try:
            import httpx
        except ImportError:
            logger.error("httpx not installed — cannot send webhook")
            return False

        url = config["url"]
        secret = config.get("secret", "")
        timeout = config.get("timeout", 10)

        ts = timestamp or datetime.now(UTC)

        payload = {
            "event_id": event_id,
            "severity": severity,
            "title": title,
            "details": details,
            "watcher_name": watcher_name,
            "timestamp": ts.isoformat(),
        }

        body = json.dumps(payload, sort_keys=True)

        # HMAC-SHA256 signature
        signature = hmac.new(
            secret.encode(),
            body.encode(),
            hashlib.sha256,
        ).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-Signature-256": f"sha256={signature}",
        }

        # The URL is tenant-supplied: refuse private/local targets on every
        # send (LIFE_GRAPH_FETCH_ALLOW_HOSTS opts a LAN host back in).
        from life_graph.services.safe_fetch import FetchBlockedError, check_url

        try:
            await check_url(url)
        except FetchBlockedError as exc:
            logger.warning("Webhook to %s refused: %s", url, exc)
            return False

        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                resp = await client.post(url, content=body, headers=headers)

            if resp.status_code < 300:
                logger.debug("Webhook delivered to %s — %d", url, resp.status_code)
                return True

            logger.warning(
                "Webhook to %s returned %d: %s",
                url,
                resp.status_code,
                resp.text[:200],
            )
            return False

        except Exception as e:
            logger.error("Webhook send to %s failed: %s", url, e)
            return False
