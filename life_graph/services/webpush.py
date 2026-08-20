"""Web Push delivery via VAPID (pywebpush)."""

from __future__ import annotations

import asyncio
import json
import logging

from pywebpush import WebPushException, webpush
from sqlalchemy import delete, select

from life_graph.config import settings
from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.db import PushSubscription

logger = logging.getLogger(__name__)

_MAX_BODY = 200


class PushService:
    """Persist push subscriptions and deliver Web Push notifications."""

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    async def save_subscription(self, sub: dict, user_agent: str | None = None) -> None:
        tenant_id = get_current_tenant_id()
        endpoint = sub["endpoint"]
        keys = sub.get("keys", sub)
        async with self._session_factory() as session:
            existing = await session.execute(
                select(PushSubscription).where(PushSubscription.endpoint == endpoint)
            )
            row = existing.scalar_one_or_none()
            if row is None:
                session.add(
                    PushSubscription(
                        tenant_id=tenant_id,
                        endpoint=endpoint,
                        p256dh=keys["p256dh"],
                        auth=keys["auth"],
                        user_agent=user_agent,
                    )
                )
            else:
                row.tenant_id = tenant_id
                row.p256dh = keys["p256dh"]
                row.auth = keys["auth"]
                row.user_agent = user_agent
            await session.commit()

    async def delete_subscription(self, endpoint: str) -> None:
        tenant_id = get_current_tenant_id()
        async with self._session_factory() as session:
            await session.execute(
                delete(PushSubscription).where(
                    PushSubscription.endpoint == endpoint,
                    PushSubscription.tenant_id == tenant_id,
                )
            )
            await session.commit()

    async def send_to_tenant(self, tenant_id: str, title: str, body: str, url: str = "/m") -> int:
        if not settings.vapid_private_key:
            logger.warning("VAPID private key unset; skipping push")
            return 0
        payload = json.dumps({"title": title, "body": body[:_MAX_BODY], "url": url})
        async with self._session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(PushSubscription).where(PushSubscription.tenant_id == tenant_id)
                    )
                )
                .scalars()
                .all()
            )
            delivered = 0
            dead: list[str] = []
            for row in rows:
                sub_info = {
                    "endpoint": row.endpoint,
                    "keys": {"p256dh": row.p256dh, "auth": row.auth},
                }
                try:
                    await asyncio.to_thread(
                        webpush,
                        sub_info,
                        payload,
                        vapid_private_key=settings.vapid_private_key,
                        vapid_claims={"sub": settings.vapid_subject},
                    )
                    delivered += 1
                except WebPushException as exc:
                    status = getattr(getattr(exc, "response", None), "status_code", None)
                    if status in (404, 410):
                        dead.append(row.endpoint)
                    else:
                        logger.warning("Web push failed for %s: %s", row.endpoint[:40], exc)
                except Exception as exc:
                    # Transport-level failure (ConnectionError, Timeout, DNS, ...) isn't a
                    # WebPushException — never let one flaky endpoint abort the whole batch.
                    logger.warning("Web push transport error for %s: %s", row.endpoint[:40], exc)
                    continue
            if dead:
                await session.execute(
                    delete(PushSubscription).where(PushSubscription.endpoint.in_(dead))
                )
                await session.commit()
            return delivered
