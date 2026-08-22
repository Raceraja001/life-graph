"""Background job for memory decay sweeps.

Implements exponential decay for memory importance::

    effective_importance = importance * exp(-decay_rate * days_since_activity)

where ``days_since_activity = NOW() - COALESCE(last_accessed, created_at)``.

Memories whose effective importance falls below the configured threshold
(``settings.decay_archive_threshold``) are proposed for archival via a single
SQL UPDATE.

Entry points:
    - ``run_decay_sweep``: Sweep a single tenant (enqueued per-tenant).
    - ``run_all_decay_sweeps``: Nightly cron that sweeps every tenant.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, text, update

from life_graph.config import settings
from life_graph.models.db import Approval, JobRun, Memory
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)


async def _queue_archive_proposals(session, tenant_id: str, candidates) -> int:
    """Queue an ``archive`` approval per decayed memory. Returns how many.

    Idempotent on ``source_ref`` (the memory id) so a nightly sweep does not
    re-queue what is already pending, and does not resurrect a proposal a
    human already rejected.
    """
    if not candidates:
        return 0

    ids = [str(row.id) for row in candidates]
    existing = await session.execute(
        select(Approval.source_ref).where(
            Approval.tenant_id == tenant_id,
            Approval.kind == "archive",
            Approval.source_ref.in_(ids),
        )
    )
    seen = {ref for (ref,) in existing}

    queued = 0
    for row in candidates:
        ref = str(row.id)
        if ref in seen:
            continue
        session.add(
            Approval(
                tenant_id=tenant_id,
                kind="archive",
                source="decay",
                source_ref=ref,
                title="Archive a decayed memory",
                detail=(
                    f"decay · effective importance "
                    f"{float(row.effective_importance):.4f} · "
                    f"tier {row.importance_tier} · "
                    f"\u201c{(row.content or '')[:80]}\u201d"
                ),
                payload={
                    "memory_id": ref,
                    "effective_importance": round(float(row.effective_importance), 6),
                    "importance": round(float(row.importance), 4),
                    "importance_tier": row.importance_tier,
                },
            )
        )
        queued += 1

    if queued:
        await session.flush()
    return queued


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
        Dict with ``proposed_count``, ``candidate_count`` and ``evaluated_count``.

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
            started_at=datetime.now(UTC),
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

            # Decay lowers a memory's standing; it does not remove it.
            #
            # This used to be a bulk UPDATE ... SET status = 'archived', which
            # every query filters out — so a decayed memory disappeared from
            # recall with no record and no way back short of a manual
            # unarchive(). Ranking already demotes stale memories on its own:
            # the recency and frequency signals are computed from exactly the
            # inputs decay uses, so a memory nobody touches sinks down the
            # order without anything hiding it.
            #
            # Removal is a separate decision, taken deliberately. Candidates
            # are queued as approvals, mirroring workers/cleanup.py, and
            # nothing changes status until someone says so.
            #
            # Formula: importance * exp(-decay_rate * days_since_activity)
            # ref_time = COALESCE(last_accessed, created_at)
            result = await session.execute(
                text("""
                    SELECT id, content, importance, importance_tier,
                           importance * exp(
                               -decay_rate *
                               EXTRACT(EPOCH FROM (NOW() - COALESCE(last_accessed, created_at)))
                               / 86400.0
                           ) AS effective_importance
                    FROM memories
                    WHERE tenant_id = :tenant_id
                      AND status = 'active'
                      AND importance_tier <> 'critical'
                      AND importance * exp(
                              -decay_rate *
                              EXTRACT(EPOCH FROM (NOW() - COALESCE(last_accessed, created_at)))
                              / 86400.0
                          ) < :threshold
                    ORDER BY effective_importance ASC
                    LIMIT :cap
                """),
                {
                    "tenant_id": tenant_id,
                    "threshold": threshold,
                    "cap": settings.decay_proposal_limit,
                },
            )
            candidates = result.fetchall()
            proposed = await _queue_archive_proposals(session, tenant_id, candidates)
            await session.commit()

        result_data = {
            "proposed_count": proposed,
            "candidate_count": len(candidates),
            "evaluated_count": total_active,
        }

        # Update job as success
        async with async_session() as session:
            await session.execute(
                update(JobRun)
                .where(JobRun.id == job_id)
                .values(
                    status="success",
                    completed_at=datetime.now(UTC),
                    result=result_data,
                )
            )
            await session.commit()

        logger.info(
            "Decay sweep for %s: proposed=%d of %d candidates, evaluated=%d",
            tenant_id,
            proposed,
            len(candidates),
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
                    completed_at=datetime.now(UTC),
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
