"""ARQ jobs for Job 1, free LLM offers (services/llm_offers.py).

Each runs for the tenants in ``offers_tenants`` (off when empty) and never
raises: a failure in one tenant or one step is logged and reported, so the
next run starts clean.
"""

from __future__ import annotations

import logging

from life_graph.config import settings
from life_graph.core.tenant import set_tenant_context
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)


async def run_llm_catalog_diff(ctx: dict) -> dict:
    """Daily: diff the free-model catalogs (plain code, no model call)."""
    from life_graph.services.llm_offers import catalog_diff

    tenants = settings.offers_tenants_list
    if not tenants:
        return {"skipped": "offers_tenants is empty"}
    try:
        return await catalog_diff(async_session, tenants)
    except Exception as exc:
        logger.warning("catalog diff failed", exc_info=True)
        return {"error": str(exc)[:300]}


async def run_llm_offer_news(ctx: dict) -> dict:
    """Every 6 h: read new pages about free LLM offers."""
    from life_graph.services.llm_offers import news_scan

    out = {}
    for tenant_id in settings.offers_tenants_list:
        set_tenant_context(tenant_id, "system")
        try:
            out[tenant_id] = await news_scan(async_session, tenant_id)
        except Exception as exc:
            logger.warning("offer news scan failed for %s", tenant_id, exc_info=True)
            out[tenant_id] = {"error": str(exc)[:300]}
    return out or {"skipped": "offers_tenants is empty"}


async def run_llm_offer_evals(ctx: dict) -> dict:
    """Hourly: evaluate the next waiting free model, within the daily cap."""
    from life_graph.services.llm_offers import evaluate_next

    out = {}
    for tenant_id in settings.offers_tenants_list:
        set_tenant_context(tenant_id, "system")
        try:
            out[tenant_id] = await evaluate_next(async_session, tenant_id)
        except Exception as exc:
            logger.warning("offer evaluation failed for %s", tenant_id, exc_info=True)
            out[tenant_id] = {"error": str(exc)[:300]}
    return out or {"skipped": "offers_tenants is empty"}
