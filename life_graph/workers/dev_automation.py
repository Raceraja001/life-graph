"""Every minute: dev automation's schedules, intake polls and the morning digest.

services/dev/automation (docs/specs/dev-automation.md). One tick at a time
across worker processes (a session-level advisory lock): a tick that runs
long makes the next one skip rather than overlap. Each tenant with anything
switched on gets its due schedule slots and chains, its due intake sources
(poll → sync → reconcile → start) and, at its time, the digest push.
"""

from __future__ import annotations

import logging

from sqlalchemy import text

from life_graph.services.dev.automation.service import get_service
from life_graph.storage.database import engine

logger = logging.getLogger(__name__)

#: pg_try_advisory_lock key for the tick (hashtext('dev_automation_tick')).
LOCK_SQL = "SELECT pg_try_advisory_lock(hashtext('dev_automation_tick'))"
UNLOCK_SQL = "SELECT pg_advisory_unlock(hashtext('dev_automation_tick'))"


async def tick_dev_automation(ctx: dict | None = None) -> dict:
    """The ARQ cron entry point."""
    async with engine.connect() as conn:
        got = (await conn.execute(text(LOCK_SQL))).scalar()
        if not got:
            logger.info("Dev automation tick skipped: the previous tick is still running")
            return {"skipped": "locked"}
        try:
            return await get_service().tick_all()
        finally:
            await conn.execute(text(UNLOCK_SQL))
            await conn.commit()
