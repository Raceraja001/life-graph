"""The daily study nudge: "12 cards due" (docs/research/study-helper-spec-2026-10.html).

Hourly, per active tenant: once the owner's local hour reaches
``settings.study_nudge_hour`` (default 18; -1 turns it off), outside quiet
hours (services/nudge_pick.in_quiet_hours, 22:00-06:59), at most once per
owner-day, and only when cards are due, write one ``Notification`` the phone
polls for — as the promise nudges do (services/nudges.py), with their own cap
untouched. It says how many, never what the cards ask: a phone notification
leaves the machine.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select

logger = logging.getLogger(__name__)

SOURCE_TYPE = "study_due"
TITLE = "Study"
#: One a day: the morning brief already has a study line.
MAX_PER_DAY = 1


def should_send(local_now: datetime, *, hour: int, sent_today: int, due: int) -> bool:
    """Pure: whether the nudge goes out now (``local_now`` in the owner's zone)."""
    from life_graph.services.nudge_pick import in_quiet_hours

    if hour < 0 or due <= 0 or sent_today >= MAX_PER_DAY:
        return False
    if local_now.hour < hour:
        return False
    return not in_quiet_hours(local_now, (22, 7))


def body_for(due: int) -> str:
    cards = "card" if due == 1 else "cards"
    return f"{due} {cards} due today — /review on Telegram, or open Study in the app."


async def run_tenant(session, tenant_id: str, now: datetime, tz: Any, *, hour: int) -> int:
    """1 when a nudge was written for this tenant, else 0."""
    from life_graph.models.db import Notification
    from life_graph.services import study
    from life_graph.services.nudges import _local_midnight

    local_now = now.astimezone(tz)
    today = local_now.date()
    sent_today = int(
        await session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.tenant_id == tenant_id,
                Notification.source_type == SOURCE_TYPE,
                Notification.created_at >= _local_midnight(now, tz),
            )
        )
        or 0
    )
    if sent_today >= MAX_PER_DAY or hour < 0 or local_now.hour < hour:
        return 0
    due = int(await study.count_due(session, tenant_id, today))
    if not should_send(local_now, hour=hour, sent_today=sent_today, due=due):
        return 0
    session.add(
        Notification(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            priority="info",
            title=TITLE,
            body=body_for(due),
            extra_metadata={
                "kind": SOURCE_TYPE,
                "due": due,
                "dedup_key": f"{SOURCE_TYPE}:{today.isoformat()}",
            },
            source_type=SOURCE_TYPE,
            # The phone polls for these, as for due notifications.
            is_delivered=True,
            delivered_at=now,
            created_at=now,
        )
    )
    await session.commit()
    return 1


async def run(session_factory, now: datetime | None = None) -> dict[str, int]:
    """Every active tenant's study nudge, if one is due now."""
    from life_graph.config import settings
    from life_graph.connectors.tools import user_tz
    from life_graph.models.db import TenantConfig

    now = now or datetime.now(UTC)
    hour = int(settings.study_nudge_hour)
    if hour < 0:
        return {}
    async with session_factory() as session:
        tenants = [
            r[0]
            for r in (
                await session.execute(
                    select(TenantConfig.tenant_id).where(TenantConfig.status == "active")
                )
            ).all()
        ]
    out: dict[str, int] = {}
    for tenant_id in tenants:
        try:
            async with session_factory() as session:
                sent = await run_tenant(session, tenant_id, now, user_tz(), hour=hour)
        except Exception:  # one tenant never stops the rest
            logger.exception("Study nudge for %s failed", tenant_id)
            continue
        if sent:
            out[tenant_id] = sent
    return out
