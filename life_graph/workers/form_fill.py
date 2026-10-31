"""Nightly: give active memories their form slot (services/form_fill.py)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def run_all_form_fills(ctx: dict | None = None) -> dict:
    from sqlalchemy import select

    from life_graph.config import settings
    from life_graph.models.db import Memory
    from life_graph.services import form_fill
    from life_graph.storage.database import async_session

    if not settings.memory_form_fill:
        return {"skipped": "memory_form_fill is off"}
    async with async_session() as session:
        tenants = [
            r[0]
            for r in (
                await session.execute(
                    select(Memory.tenant_id).where(Memory.status == "active").distinct()
                )
            ).all()
        ]
    out: dict[str, dict] = {}
    for tenant in tenants:
        try:
            out[tenant] = await form_fill.fill(tenant)
        except Exception:  # noqa: BLE001 — one tenant's failure never stops the others
            logger.warning("Form fill failed for %s", tenant, exc_info=True)
    return {"tenants": out}
