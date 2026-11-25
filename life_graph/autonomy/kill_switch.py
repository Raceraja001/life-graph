"""Autonomy kill-switch — a per-tenant emergency stop for autonomous work.

Checked by AutoFixService._run_action() before anything runs
(:func:`is_autonomy_paused`), and, since 2026-11-25 (Stage 0 finding 4), by
everything else that starts work without the owner asking for it in the
moment (:func:`autonomy_stopped`): the scheduler, watcher findings,
delegation to another persona, the dev runner's claims and errand approvals.
Pausing also cancels the tenant's running dev tasks
(autonomy/safety/router.py).

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

from life_graph.autonomy.approvals import capability as _capability

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 15.0
# tenant -> (expires, autonomy_paused); None = the tenant has no config row.
_pause_cache: dict[str, tuple[float, bool | None]] = {}


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

    count = await asyncio.to_thread(
        _capability.capability_store.revoke_all, tenant_id=tenant_id, task_id=task_id
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


async def _pause_state(tenant_id: str) -> bool | None:
    """The tenant's ``autonomy_paused`` flag, or None when it has no config row.

    Cached for 15 s per process. Raises when the database cannot be read.
    """
    cached = _pause_cache.get(tenant_id)
    now = time.monotonic()
    if cached is not None and cached[0] > now:
        return cached[1]

    from life_graph.models.db import TenantConfig
    from life_graph.storage.database import async_session

    async with async_session() as session:
        config = await session.get(TenantConfig, tenant_id)
        state = bool(config.autonomy_paused) if config is not None else None
    _pause_cache[tenant_id] = (now + _CACHE_TTL_SECONDS, state)
    return state


async def is_autonomy_paused(tenant_id: str) -> bool:
    """Return True if autonomous action execution is paused for *tenant_id*.

    Fails closed: any error reading the flag is treated as paused, and so is a
    tenant with no config row (an unprovisioned tenant runs no auto-fixes).
    """
    try:
        state = await _pause_state(tenant_id)
    except Exception:
        logger.warning(
            "Autonomy kill-switch check failed for tenant %s — failing closed (paused)",
            tenant_id,
            exc_info=True,
        )
        return True
    return True if state is None else state


async def autonomy_stopped(tenant_id: str) -> bool:
    """Whether the owner has paused this tenant: start no new autonomous work.

    For the scheduler, watcher findings, delegation, the dev runner's claims
    and errand approvals. A tenant with no config row has not been paused (the
    pause route refuses a tenant it cannot find), so it is not stopped: unlike
    :func:`is_autonomy_paused`, which also gates on provisioning. A database
    error still fails closed.
    """
    try:
        return bool(await _pause_state(tenant_id))
    except Exception:
        logger.warning(
            "Autonomy kill-switch check failed for tenant %s — failing closed (stopped)",
            tenant_id,
            exc_info=True,
        )
        return True


#: What a caller refused by the kill switch is told.
PAUSED_REFUSAL = "Autonomy is paused (kill switch): resume it to start new work."
