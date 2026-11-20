"""Autonomy kill-switch — a per-tenant emergency stop for autonomous action
execution, checked by AutoFixService._run_action() before anything runs.

Deliberately FAIL-CLOSED: unlike the tenant-status cache
(life_graph/api/middleware.py) and the Governor (life_graph/services/governor.py),
both of which fail OPEN on a DB error so a storage hiccup doesn't block normal
work, a kill-switch that fails open when it can't reach the DB isn't a
kill-switch. If we can't confirm autonomy is NOT paused, we treat it as paused.

Pausing also revokes the tenant's live capabilities
(:func:`revoke_live_capabilities`): a capability is the owner's mandate for an
errand step (autonomy/approvals/capability.py), and errands do not go through
``_run_action``, so without this a paused tenant's mandates stayed spendable.
"""

from __future__ import annotations

import asyncio
import logging
import time

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 15.0
_pause_cache: dict[str, tuple[float, bool]] = {}


async def revoke_live_capabilities(tenant_id: str, task_id: str | None = None) -> int:
    """Revoke the tenant's (or one task's) live capabilities. Returns how many.

    Called when autonomy is paused and when a dev task is cancelled: a stop
    must not leave a live mandate behind it. The durable store is
    synchronous, so it runs in a worker thread.

    Raises ``StoreUnavailableError`` when the store cannot be reached — never
    0 for an outage. Callers stop first and revoke second (the stop must not
    wait on, or fail with, the capability store), then report a failure here
    loudly instead of passing it off as "nothing was live".
    """
    from life_graph.autonomy.approvals.capability import capability_store

    count = await asyncio.to_thread(
        capability_store.revoke_all, tenant_id=tenant_id, task_id=task_id
    )
    logger.info(
        "Revoked %d live capabilities for tenant %s%s",
        count,
        tenant_id,
        f" task {task_id}" if task_id else "",
    )
    return count


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
