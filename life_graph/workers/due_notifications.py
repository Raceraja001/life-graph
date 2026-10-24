"""Every 15 minutes: write the owner's due items as phone notifications
(services/due_notifications.py).

Often rather than a few fixed times so a timed reminder reaches the phone
within a quarter of an hour of its time. Bills, to-dos and documents are only
posted in the owner's day (08:00-22:00 user_timezone, "tomorrow" from 18:00),
and writing is idempotent per item and lead time, so the extra runs cost a
few queries each.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from life_graph.models.db import TenantConfig
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)


async def write_due_notifications(ctx: dict | None = None) -> dict:
    from life_graph.config import settings
    from life_graph.services import due_notifications

    if not settings.phone_due_notifications:
        return {"status": "skipped", "reason": "phone_due_notifications off"}
    async with async_session() as session:
        tenants = [
            row[0]
            for row in (
                await session.execute(
                    select(TenantConfig.tenant_id).where(TenantConfig.status == "active")
                )
            ).all()
        ]
    written: dict[str, list[str]] = {}
    for tenant_id in tenants:
        try:
            keys = await due_notifications.run_for_tenant(tenant_id)
        except Exception:
            logger.exception("Due notifications for %s failed", tenant_id)
            continue
        if keys:
            written[tenant_id] = keys
    if written:
        logger.info("Due notifications written: %s", written)
    return {"written": written}
