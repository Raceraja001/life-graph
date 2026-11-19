"""Alert the owner when the dev-task runtime is unhealthy.

Runs every 10 minutes in the arq worker -- a different process from the
dev-task worker, so a dead dev-task worker is still noticed. Each issue from
:mod:`life_graph.services.dev.runtime_health` becomes one owner notification
(the phone polls these), at most once per issue per 6-hour window while it
lasts. Counts and issue codes only; no task data.

Who is told: ``runtime_health_alert_tenants`` (comma-separated), else every
tenant that created a dev task in the last 30 days.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

SOURCE_TYPE = "runtime_health"
WINDOW_HOURS = 6


def dedup_key(code: str, now: datetime) -> str:
    return f"{SOURCE_TYPE}:{code}:{now:%Y%m%d}:{now.hour // WINDOW_HOURS}"


async def _alert_tenants(session, now: datetime) -> list[str]:
    from life_graph.config import settings
    from life_graph.models.db import AgentTask
    from life_graph.services.dev.tasks import _kind_filter

    configured = [t.strip() for t in settings.runtime_health_alert_tenants.split(",") if t.strip()]
    if configured:
        return configured
    rows = await session.execute(
        select(AgentTask.tenant_id)
        .where(_kind_filter(), AgentTask.created_at >= now - timedelta(days=30))
        .group_by(AgentTask.tenant_id)
        .order_by(func.count().desc())
    )
    return [r[0] for r in rows.all()]


async def check_runtime_health(ctx: dict | None = None, *, now: datetime | None = None) -> dict:
    """Collect the runtime report and notify the owner about each new issue."""
    from life_graph.models.tenancy import Notification
    from life_graph.services.dev import runtime_health

    now = now or datetime.now(UTC)
    report = await runtime_health.collect(async_session, now=now)
    out = {"status": report.status, "issues": [i.code for i in report.issues], "notified": 0}
    if not report.issues:
        return out
    logger.warning(
        "dev-task runtime %s: %s",
        report.status,
        "; ".join(f"{i.code}: {i.detail}" for i in report.issues),
    )
    key_col = Notification.extra_metadata["dedup_key"].astext
    async with async_session() as session:
        tenants = await _alert_tenants(session, now)
        for tenant in tenants:
            keys = [dedup_key(i.code, now) for i in report.issues]
            seen = set(
                (
                    await session.execute(
                        select(key_col).where(
                            Notification.tenant_id == tenant,
                            Notification.source_type == SOURCE_TYPE,
                            key_col.in_(keys),
                        )
                    )
                )
                .scalars()
                .all()
            )
            for issue in report.issues:
                key = dedup_key(issue.code, now)
                if key in seen:
                    continue
                session.add(
                    Notification(
                        id=uuid.uuid4(),
                        tenant_id=tenant,
                        priority="important" if issue.severity == "critical" else "info",
                        title=f"Dev-task runtime: {issue.code.replace('_', ' ')}"[:500],
                        body=f"{issue.detail}. See GET /api/v1/observe/system (runtime) "
                        "and docs/OPERATIONS.md, 'Runtime health'.",
                        extra_metadata={
                            "kind": SOURCE_TYPE,
                            "code": issue.code,
                            "severity": issue.severity,
                            "dedup_key": key,
                        },
                        is_delivered=True,
                        delivered_at=now,
                        source_type=SOURCE_TYPE,
                    )
                )
                out["notified"] += 1
        await session.commit()
    return out
