"""ARQ job for Job 10, the tech watch (services/web_research.py).

Runs for the tenants in ``tech_watch_tenants`` (off when empty) and never
raises: a failure in one tenant is logged and reported.
"""

from __future__ import annotations

import logging

from life_graph.config import settings
from life_graph.core.tenant import set_tenant_context
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)


async def run_tech_watch(ctx: dict) -> dict:
    """Daily: read new pages on each tech-watch topic."""
    from life_graph.services.web_research import tech_watch

    out = {}
    for tenant_id in settings.tech_watch_tenants_list:
        set_tenant_context(tenant_id, "system")
        try:
            out[tenant_id] = await tech_watch(async_session, tenant_id)
        except Exception as exc:
            logger.warning("tech watch failed for %s", tenant_id, exc_info=True)
            out[tenant_id] = {"error": str(exc)[:300]}
    return out or {"skipped": "tech_watch_tenants is empty"}
