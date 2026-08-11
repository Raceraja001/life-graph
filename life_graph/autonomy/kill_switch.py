"""Autonomy kill-switch — a per-tenant emergency stop for autonomous action
execution, checked by AutoFixService._run_action() before anything runs.

Deliberately FAIL-CLOSED: unlike the tenant-status cache
(life_graph/api/middleware.py) and the Governor (life_graph/services/governor.py),
both of which fail OPEN on a DB error so a storage hiccup doesn't block normal
work, a kill-switch that fails open when it can't reach the DB isn't a
kill-switch. If we can't confirm autonomy is NOT paused, we treat it as paused.
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 15.0
_pause_cache: dict[str, tuple[float, bool]] = {}


def invalidate_autonomy_pause_cache(tenant_id: str) -> None:
    """Drop the cached pause state for *tenant_id* (call after every write)."""
    _pause_cache.pop(tenant_id, None)


async def is_autonomy_paused(tenant_id: str) -> bool:
    """Return True if autonomous action execution is paused for *tenant_id*.

    Fails closed: any error reading the flag is treated as paused.
    """
    cached = _pause_cache.get(tenant_id)
    now = time.monotonic()
    if cached is not None and cached[0] > now:
        return cached[1]

    try:
        from life_graph.models.db import TenantConfig
        from life_graph.storage.database import async_session

        async with async_session() as session:
            config = await session.get(TenantConfig, tenant_id)
            paused = bool(config.autonomy_paused) if config else True
        _pause_cache[tenant_id] = (now + _CACHE_TTL_SECONDS, paused)
        return paused
    except Exception:
        logger.warning(
            "Autonomy kill-switch check failed for tenant %s — failing closed (paused)",
            tenant_id,
            exc_info=True,
        )
        return True
