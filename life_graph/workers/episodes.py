"""Hourly: write yesterday's conversation summaries (services/episodes.py).

Hourly rather than once at midnight so a missed run (PC asleep, worker down)
is made up the next hour; writing is idempotent per day and source. Looks back
three days to fill gaps after a longer outage.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from life_graph.models.db import TenantConfig
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

LOOKBACK_DAYS = 3


async def write_daily_episodes(ctx: dict | None = None) -> dict:
    from life_graph.config import settings
    from life_graph.services import episodes

    if not settings.use_local_llm:
        # The summaries read the owner's conversations: local model or nothing.
        return {"status": "skipped", "reason": "local LLM off"}
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
            keys = await episodes.write_recent(tenant_id, days=LOOKBACK_DAYS)
        except Exception:
            logger.exception("Episodes for %s failed", tenant_id)
            continue
        if keys:
            written[tenant_id] = keys
    if written:
        logger.info("Episodes written: %s", written)
    return {"written": written}
