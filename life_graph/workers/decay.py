"""Background job for memory decay sweeps.

Implements exponential decay for memory importance::

    effective_importance = importance * exp(-decay_rate * days_since_activity)

where ``days_since_activity = NOW() - COALESCE(last_accessed, created_at)``.

Memories whose effective importance falls below the configured threshold
(``settings.decay_archive_threshold``) are archived in bulk via a single
SQL UPDATE.

Entry points:
    - ``run_decay_sweep``: Sweep a single tenant (enqueued per-tenant).
    - ``run_all_decay_sweeps``: Nightly cron that sweeps every tenant.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, text, update

from life_graph.config import settings
from life_graph.models.db import JobRun, Memory
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)


async def run_decay_sweep(ctx: dict, tenant_id: str) -> dict:
    """Run a decay sweep for a single tenant.

    Archives memories whose effective importance has decayed below the
    configured threshold.  Uses ``COALESCE(last_accessed, created_at)``
    so that recently-created memories that have never been accessed
    still get a grace period proportional to their initial importance.

    Job execution is tracked via a :class:`JobRun` record.

    Args:
        ctx: ARQ context (contains ``redis`` connection).
        tenant_id: The tenant whose memories should be evaluated.

    Returns:
        Dict with ``archived_count`` and ``evaluated_count``.

    Raises:
        Exception: Re-raised after marking the job as failed.
    """
    threshold = settings.decay_archive_threshold

    # Create job record
    job_id = uuid.uuid4()
    async with async_session() as session:
        job = JobRun(
            id=job_id,
            tenant_id=tenant_id,
            job_name="decay_sweep",
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        session.add(job)
        await session.commit()

    try:
        async with async_session() as session:
            # Count active memories before archiving (for reporting)
            count_result = await session.execute(
                text(
                    "SELECT COUNT(*) FROM memories "
                    "WHERE tenant_id = :tenant_id AND status = 'active'"
                ),
                {"tenant_id": tenant_id},
            )
            total_active = count_result.scalar() or 0

            # Bulk archive: compute effective importance in SQL and
            # archive memories that fall below threshold.
            #
            # Formula: importance * exp(-decay_rate * days_since_activity)
            # days_since_activity = EXTRACT(EPOCH FROM (NOW() - ref_time)) / 86400
            # ref_time = COALESCE(last_accessed, created_at)
            result = await session.execute(
                text("""
                    WITH decay_calc AS (
                        SELECT id,
                               importance * exp(
                                   -decay_rate *
                                   EXTRACT(EPOCH FROM (NOW() - COALESCE(last_accessed, created_at)))
                                   / 86400.0
                               ) AS effective_importance
                        FROM memories
                        WHERE tenant_id = :tenant_id
                          AND status = 'active'
                    )
                    UPDATE memories m
                    SET status = 'archived', updated_at = NOW()
                    FROM decay_calc d
                    WHERE m.id = d.id
                      AND d.effective_importance < :threshold
                    RETURNING m.id
                """),
                {"tenant_id": tenant_id, "threshold": threshold},
            )

            archived_ids = result.fetchall()
            archived_count = len(archived_ids)
            await session.commit()

        result_data = {
            "archived_count": archived_count,
            "evaluated_count": total_active,
        }

        # Update job as success
        async with async_session() as session:
            await session.execute(
                update(JobRun)
                .where(JobRun.id == job_id)
                .values(
                    status="success",
                    completed_at=datetime.now(timezone.utc),
                    result=result_data,
                )
            )
            await session.commit()

        logger.info(
            "Decay sweep for %s: archived=%d, evaluated=%d",
            tenant_id,
            archived_count,
            total_active,
        )
        return result_data

    except Exception as exc:
        # Mark job as failed
        async with async_session() as session:
            await session.execute(
                update(JobRun)
                .where(JobRun.id == job_id)
                .values(
                    status="failed",
                    completed_at=datetime.now(timezone.utc),
                    error=str(exc),
                )
            )
            await session.commit()

        logger.exception("Decay sweep failed for tenant %s", tenant_id)
        raise


async def run_all_decay_sweeps(ctx: dict) -> dict:
    """Nightly cron: run decay sweeps for every tenant.

    Discovers all distinct tenant IDs from the ``memories`` table
    and runs a sweep for each.  Failures for individual tenants
    are caught and logged so that one failing tenant does not block
    the rest.

    Args:
        ctx: ARQ context.

    Returns:
        Dict with ``tenants_processed`` count and per-tenant ``results``.
    """
    logger.info("Starting nightly decay sweep for all tenants")

    # Discover all active tenants
    async with async_session() as session:
        result = await session.execute(select(Memory.tenant_id).distinct())
        tenant_ids = [row[0] for row in result.fetchall()]

    if not tenant_ids:
        logger.info("No tenants found, skipping decay sweep")
        return {"tenants_processed": 0, "results": {}}

    logger.info("Running decay sweep for %d tenants", len(tenant_ids))

    results: dict[str, dict] = {}
    for tid in tenant_ids:
        try:
            results[tid] = await run_decay_sweep(ctx, tid)
        except Exception as exc:
            logger.error("Decay sweep failed for tenant %s: %s", tid, exc)
            results[tid] = {"error": str(exc)}

    return {"tenants_processed": len(tenant_ids), "results": results}
