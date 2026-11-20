"""Is owner-only approval enforcement on, and could the owner still get in?

``approvals_require_owner`` (config/core.py) makes approve/reject on both
approval systems owner-only (api/approval_identity.py). The owner is an owner
API key (``owner_api_keys``) or a paired phone. Turned on with neither, every
HTTP caller — the dashboard included — gets 403 and only Telegram (when
``telegram_allow_approvals`` is on) can still decide.

This module reports that state as counts and flags only: never a key, never a
fingerprint of one. Used by the startup check (main.py) and the system view
(``GET /kernel/observability/system``).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from life_graph.config import settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

LOCKOUT_WARNING = (
    "approvals_require_owner is on, but no owner key is configured "
    "(LIFE_GRAPH_OWNER_API_KEYS) and no phone is paired: every HTTP caller, the "
    "dashboard included, will get 403 on approve/reject. Only Telegram can still "
    "decide (telegram_allow_approvals=%s)."
)


async def paired_device_count(session: AsyncSession) -> int:
    """Phones that can still sign in (not revoked), across tenants."""
    from life_graph.models.assistant import Device

    return int(
        (
            await session.execute(
                select(func.count()).select_from(Device).where(Device.revoked_at.is_(None))
            )
        ).scalar_one()
        or 0
    )


def status(paired_devices: int | None) -> dict[str, Any]:
    """Counts and flags only. ``paired_devices`` None = could not be counted."""
    owner_keys = len(settings.owner_api_keys_list)
    service_keys = set(settings.service_api_keys_list)
    if settings.api_key:
        service_keys.add(settings.api_key)
    owner_set = set(settings.owner_api_keys_list)
    enforced = bool(settings.approvals_require_owner)
    owner_reachable = owner_keys > 0 or bool(paired_devices)
    return {
        "approvals_require_owner": enforced,
        "owner_keys_configured": owner_keys,
        # Owner keys must also be accepted keys, or they never get past auth.
        "owner_keys_not_accepted": len(owner_set - service_keys) if service_keys else 0,
        "non_owner_service_keys": len(service_keys - owner_set),
        "paired_devices": paired_devices,
        "telegram_allow_approvals": bool(settings.telegram_allow_approvals),
        # True when enforcement is on and nothing but Telegram could decide.
        "lockout_risk": enforced and paired_devices is not None and not owner_reachable,
    }


async def check_at_startup(session_factory) -> dict[str, Any]:  # noqa: ANN001
    """Log a WARNING when enforcement would lock everyone but Telegram out."""
    paired: int | None = None
    if settings.approvals_require_owner and not settings.owner_api_keys_list:
        async with session_factory() as session:
            paired = await paired_device_count(session)
    report = status(paired)
    if report["lockout_risk"]:
        logger.warning(LOCKOUT_WARNING, settings.telegram_allow_approvals)
    elif report["approvals_require_owner"]:
        logger.info(
            "Owner-only approvals on: %d owner key(s) configured",
            report["owner_keys_configured"],
        )
    return report
