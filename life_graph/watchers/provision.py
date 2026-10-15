"""Create a tenant's watcher config row on first use.

The hourly watcher cron runs only watchers that have a ``watch_configs`` row
for the tenant, and nothing creates rows for watchers a user switches on
through a feature (a page monitor, a project's health URL). This does,
idempotently.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.dialects.postgresql import insert

from life_graph.watchers.models import WatchConfig

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def ensure_config(
    session: AsyncSession,
    tenant_id: str,
    watcher_name: str,
    display_name: str,
    description: str,
    schedule: str = "0 * * * *",
) -> None:
    await session.execute(
        insert(WatchConfig)
        .values(
            tenant_id=tenant_id,
            watcher_name=watcher_name,
            display_name=display_name,
            description=description,
            schedule=schedule,
            enabled=True,
            config={},
            consecutive_failures=0,
        )
        .on_conflict_do_nothing(index_elements=["tenant_id", "watcher_name"])
    )
