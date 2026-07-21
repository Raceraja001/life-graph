"""Background task definitions for Life Graph ARQ worker.

Tasks run in a separate worker process from the API server.
Each task operates on a single tenant and records results
in the job_runs table for monitoring.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update

from life_graph.core.tenant import set_tenant_context
from life_graph.models.db import JobRun, Memory
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)


async def run_tenant_consolidation(ctx: dict, tenant_id: str) -> dict:
    """Run consolidation pipeline for a single tenant.

    Records the job run in the database with status tracking.
    Implements Redis-based locking to prevent concurrent runs.

    Args:
        ctx: ARQ context (contains Redis connection).
        tenant_id: The tenant to run consolidation for.

    Returns:
        Dict with consolidation results summary.
    """
    redis = ctx.get("redis")
    lock_key = f"job:lock:{tenant_id}:consolidate"

    # Acquire lock (prevent concurrent runs for same tenant)
    if redis:
        locked = await redis.set(lock_key, "1", nx=True, ex=3600)
        if not locked:
            logger.info("Consolidation already running for tenant %s, skipping", tenant_id)
            return {"status": "skipped", "reason": "already_running"}

    # Set tenant context for this task
    set_tenant_context(tenant_id, "system")

    # Create job run record
    job_id = uuid.uuid4()
    async with async_session() as session:
        job = JobRun(
            id=job_id,
            tenant_id=tenant_id,
            job_name="consolidation",
            status="running",
            started_at=datetime.now(UTC),
        )
        session.add(job)
        await session.commit()

    try:
        # Run the consolidation pipeline
        from life_graph.api.dependencies import get_consolidation_pipeline
        pipeline = get_consolidation_pipeline()
        report = await pipeline.run()

        # Update job as success
        result_data = {
            "clusters_found": getattr(report, "clusters_found", 0),
            "duplicates_merged": getattr(report, "duplicates_merged", 0),
            "memories_scored": getattr(report, "memories_scored", 0),
            "distilled": getattr(report, "distilled", 0),
            "decayed": getattr(report, "decayed", 0),
        }

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

        logger.info("Consolidation complete for tenant %s: %s", tenant_id, result_data)
        return result_data

    except Exception as e:
        # Update job as failed
        async with async_session() as session:
            await session.execute(
                update(JobRun)
                .where(JobRun.id == job_id)
                .values(
                    status="failed",
                    completed_at=datetime.now(UTC),
                    error=str(e),
                )
            )
            await session.commit()

        logger.exception("Consolidation failed for tenant %s", tenant_id)
        raise  # ARQ will retry based on max_tries

    finally:
        # Release lock
        if redis:
            await redis.delete(lock_key)


async def run_all_consolidations(ctx: dict) -> dict:
    """Run consolidation for all active tenants.

    Queries distinct tenant_ids from the memories table and
    enqueues individual consolidation jobs for each.

    This is the nightly cron entry point.
    """
    logger.info("Starting nightly consolidation for all tenants")

    # Find all active tenants
    async with async_session() as session:
        result = await session.execute(
            select(Memory.tenant_id).distinct()
        )
        tenant_ids = [row[0] for row in result.fetchall()]

    if not tenant_ids:
        logger.info("No tenants found, skipping consolidation")
        return {"tenants": 0}

    logger.info("Enqueuing consolidation for %d tenants: %s", len(tenant_ids), tenant_ids)

    # Enqueue individual jobs via ARQ
    redis = ctx.get("redis")
    if redis:
        from arq import create_pool

        from life_graph.workers.settings import parse_redis_settings

        pool = await create_pool(parse_redis_settings())
        for tid in tenant_ids:
            await pool.enqueue_job("run_tenant_consolidation", tid)
        await pool.close()
    else:
        # Fallback: run sequentially
        for tid in tenant_ids:
            await run_tenant_consolidation(ctx, tid)

    return {"tenants": len(tenant_ids), "tenant_ids": tenant_ids}


async def run_tenant_merge_suggestions(ctx: dict, tenant_id: str) -> dict:
    """Queue merge-suggestion approvals for near-duplicate memories (one tenant)."""
    set_tenant_context(tenant_id, "system")
    from life_graph.services.merge_suggestions import MergeSuggestionService
    from life_graph.storage.postgres import PostgresMemoryStore

    store = PostgresMemoryStore()
    async with async_session() as session:
        queued = await MergeSuggestionService(session, store).scan_and_queue(tenant_id)
        await session.commit()
    logger.info("Merge suggestions for tenant %s: queued %d", tenant_id, queued)
    return {"tenant_id": tenant_id, "queued": queued}


async def run_all_merge_suggestions(ctx: dict) -> dict:
    """Nightly cron: queue merge suggestions across all tenants."""
    async with async_session() as session:
        result = await session.execute(select(Memory.tenant_id).distinct())
        tenant_ids = [row[0] for row in result.fetchall()]

    total = 0
    for tid in tenant_ids:
        try:
            res = await run_tenant_merge_suggestions(ctx, tid)
            total += res.get("queued", 0)
        except Exception:
            logger.exception("Merge suggestions failed for tenant %s", tid)
    return {"tenants": len(tenant_ids), "queued": total}


async def run_all_research(ctx: dict) -> dict:
    """Weekly research: check stale preferences across all tenants.

    Queries all active tenants from preferences table and runs
    the autonomous research engine for each.

    This is the weekly cron entry point (Sunday 02:00 UTC).
    """
    logger.info("Starting weekly research cycle for all tenants")

    from life_graph.models.db import Preference

    # Find all active tenants with preferences
    async with async_session() as session:
        result = await session.execute(
            select(Preference.tenant_id).distinct()
        )
        tenant_ids = [row[0] for row in result.fetchall()]

    if not tenant_ids:
        logger.info("No tenants with preferences found, skipping research")
        return {"tenants": 0}

    logger.info(
        "Running research for %d tenants: %s", len(tenant_ids), tenant_ids
    )

    from life_graph.api.dependencies import get_research_engine
    engine = get_research_engine()

    results = {}
    for tid in tenant_ids:
        try:
            set_tenant_context(tid, "system")
            result = await engine.run_research_cycle(tid)
            results[tid] = result
        except Exception:
            logger.exception("Research failed for tenant %s", tid)
            results[tid] = {"status": "error"}

    return {"tenants": len(tenant_ids), "results": results}


async def run_nightly_self_heal(ctx: dict) -> dict:
    """Nightly self-heal: evaluate + optimize prompts for all tenants.

    Runs at 03:30 UTC daily. Queries distinct tenant_ids from
    eval suites and runs the self-healing pipeline for each.
    """
    logger.info("Starting nightly self-heal for all tenants")

    from life_graph.api.dependencies import (
        get_eval_service,
        get_optimizer_service,
        get_prompt_version_service,
    )
    from life_graph.self_improving.models import EvalSuite
    from life_graph.self_improving.nightly_cron import nightly_self_heal

    # Find all tenants with eval suites
    async with async_session() as session:
        result = await session.execute(
            select(EvalSuite.tenant_id).distinct()
        )
        tenant_ids = [row[0] for row in result.fetchall()]

    if not tenant_ids:
        logger.info("No tenants with eval suites found, skipping self-heal")
        return {"tenants": 0}

    logger.info(
        "Running self-heal for %d tenants: %s", len(tenant_ids), tenant_ids
    )

    eval_service = get_eval_service()
    prompt_service = get_prompt_version_service()
    optimizer = get_optimizer_service()

    results = {}
    for tid in tenant_ids:
        try:
            set_tenant_context(tid, "system")
            result = await nightly_self_heal(
                tenant_id=tid,
                session_factory=async_session,
                eval_service=eval_service,
                prompt_service=prompt_service,
                optimizer=optimizer,
            )
            results[tid] = result
        except Exception:
            logger.exception("Self-heal failed for tenant %s", tid)
            results[tid] = {"status": "error"}

    return {"tenants": len(tenant_ids), "results": results}


# ── Watcher Framework (Era 6) ────────────────────────────────────────────────


async def run_watchers(ctx: dict) -> dict:
    """Hourly cron: run all enabled watchers for all tenants.

    Iterates distinct tenants from watcher configs, runs each
    enabled watcher, stores events, and routes notifications.
    """
    logger.info("Starting hourly watcher run for all tenants")

    try:
        from life_graph.watchers.models import WatchConfig, WatcherRun, WatchEvent
    except ImportError:
        logger.warning("Watcher models not available — skipping watcher run")
        return {"status": "skipped", "reason": "models_unavailable"}

    from life_graph.api.dependencies import get_watcher_notification_engine
    from life_graph.core.events import EventType, event_bus
    from life_graph.watchers.code_quality_watcher import CodeQualityWatcher
    from life_graph.watchers.server_health_watcher import ServerHealthWatcher

    WATCHER_MAP = {
        "server_health": ServerHealthWatcher,
        "code_quality": CodeQualityWatcher,
    }

    notification_engine = get_watcher_notification_engine()

    # Watcher → task origination: actionable findings become kernel tasks.
    # Called directly (not via EventBus) because the cron runs in the ARQ
    # worker and the Redis bridge is publish-only — an API-process subscriber
    # would never receive worker-emitted events.
    try:
        from life_graph.api.dependencies import get_process_manager
        from life_graph.watchers.origination import TaskOriginationService
        origination = TaskOriginationService(get_process_manager())
    except Exception:
        logger.warning("Task origination unavailable — findings won't spawn tasks", exc_info=True)
        origination = None

    # Find all tenants with watcher configs
    async with async_session() as session:
        result = await session.execute(
            select(WatchConfig.tenant_id).distinct()
        )
        tenant_ids = [row[0] for row in result.fetchall()]

    if not tenant_ids:
        logger.info("No tenants with watcher configs found")
        return {"tenants": 0}

    total_events = 0
    results = {}

    for tid in tenant_ids:
        set_tenant_context(tid, "system")

        async with async_session() as session:
            result = await session.execute(
                select(WatchConfig).where(
                    WatchConfig.tenant_id == tid,
                    WatchConfig.enabled == True,  # noqa: E712
                )
            )
            configs = result.scalars().all()

        tenant_events = 0

        for wconfig in configs:
            watcher_cls = WATCHER_MAP.get(wconfig.watcher_name)
            if watcher_cls is None:
                continue

            # Create run record
            import time
            run_id = uuid.uuid4()
            t_start = time.monotonic()

            async with async_session() as session:
                run = WatcherRun(
                    id=run_id,
                    tenant_id=tid,
                    watcher_name=wconfig.watcher_name,
                    status="running",
                    started_at=datetime.now(UTC),
                )
                session.add(run)
                await session.commit()

            try:
                watcher = watcher_cls(
                    config=wconfig.config or {},
                    session_factory=async_session,
                )
                events = await watcher.execute()

                # Store events
                for evt_data in events:
                    async with async_session() as session:
                        event = WatchEvent(
                            id=uuid.uuid4(),
                            tenant_id=tid,
                            watcher_name=wconfig.watcher_name,
                            severity=evt_data.get("severity", "info"),
                            title=evt_data.get("title", ""),
                            details=evt_data.get("details", ""),
                            run_id=run_id,
                        )
                        session.add(event)
                        await session.commit()

                    # Route notification
                    await notification_engine.route_event(tid, evt_data)

                duration_ms = (time.monotonic() - t_start) * 1000

                async with async_session() as session:
                    await session.execute(
                        update(WatcherRun)
                        .where(WatcherRun.id == run_id)
                        .values(
                            status="success",
                            completed_at=datetime.now(UTC),
                            events_created=len(events),
                            duration_ms=duration_ms,
                        )
                    )
                    await session.commit()

                tenant_events += len(events)

                completed_payload = {
                    "watcher_name": wconfig.watcher_name,
                    "tenant_id": tid,
                    "events_created": len(events),
                    "duration_ms": duration_ms,
                    # Findings carried so downstream origination can act on
                    # them (actionable ones become tasks).
                    "findings": list(events),
                }
                await event_bus.emit(
                    EventType.WATCHER_COMPLETED,
                    completed_payload,
                    source="watcher_framework",
                )

                # Spawn kernel tasks from actionable findings.
                if origination is not None:
                    try:
                        await origination.originate(completed_payload)
                    except Exception:
                        logger.warning(
                            "Origination failed for watcher %s / tenant %s",
                            wconfig.watcher_name, tid, exc_info=True,
                        )

            except Exception as e:
                logger.exception(
                    "Watcher %s failed for tenant %s",
                    wconfig.watcher_name,
                    tid,
                )
                async with async_session() as session:
                    await session.execute(
                        update(WatcherRun)
                        .where(WatcherRun.id == run_id)
                        .values(
                            status="failed",
                            completed_at=datetime.now(UTC),
                            error=str(e),
                        )
                    )
                    await session.commit()

                await event_bus.emit(
                    EventType.WATCHER_FAILED,
                    {
                        "watcher_name": wconfig.watcher_name,
                        "tenant_id": tid,
                        "error": str(e),
                    },
                    source="watcher_framework",
                )

        results[tid] = {"events": tenant_events}
        total_events += tenant_events

    logger.info(
        "Watcher run complete: %d tenants, %d total events",
        len(tenant_ids),
        total_events,
    )

    return {
        "tenants": len(tenant_ids),
        "total_events": total_events,
        "results": results,
    }


async def run_daily_digest(ctx: dict) -> dict:
    """Daily cron (08:00 UTC): generate daily digests for all tenants."""
    logger.info("Starting daily digest generation for all tenants")

    try:
        from life_graph.watchers.models import WatchConfig
    except ImportError:
        logger.warning("Watcher models not available — skipping digest")
        return {"status": "skipped"}

    from life_graph.api.dependencies import get_digest_generator
    digest_gen = get_digest_generator()

    async with async_session() as session:
        result = await session.execute(
            select(WatchConfig.tenant_id).distinct()
        )
        tenant_ids = [row[0] for row in result.fetchall()]

    results = {}
    for tid in tenant_ids:
        try:
            set_tenant_context(tid, "system")
            result = await digest_gen.generate_daily(tid)
            results[tid] = result
        except Exception:
            logger.exception("Digest generation failed for tenant %s", tid)
            results[tid] = {"status": "error"}

    return {"tenants": len(tenant_ids), "results": results}


# ── Autonomous AI (Era 8) ────────────────────────────────────────────────


async def decay_trust_scores(ctx: dict) -> dict:
    """Nightly cron (05:00 UTC): decay trust scores for inactive agents.

    Queries all tenants with trust scores and applies time-based decay.
    """
    logger.info("Starting nightly trust score decay")

    try:
        from life_graph.models.db import TrustScore
    except ImportError:
        logger.warning("TrustScore model not available — skipping decay")
        return {"status": "skipped", "reason": "models_unavailable"}

    from life_graph.api.dependencies import get_trust_service

    try:
        trust_service = get_trust_service()
    except Exception:
        logger.warning("Trust service not available — skipping decay")
        return {"status": "skipped", "reason": "service_unavailable"}

    # Find all tenants with trust scores
    async with async_session() as session:
        result = await session.execute(
            select(TrustScore.tenant_id).distinct()
        )
        tenant_ids = [row[0] for row in result.fetchall()]

    if not tenant_ids:
        logger.info("No tenants with trust scores found")
        return {"tenants": 0}

    results = {}
    for tid in tenant_ids:
        try:
            set_tenant_context(tid, "system")
            if hasattr(trust_service, "decay_scores"):
                count = await trust_service.decay_scores(tid)
                results[tid] = {"decayed": count}
            else:
                results[tid] = {"status": "decay_not_implemented"}
        except Exception:
            logger.exception("Trust decay failed for tenant %s", tid)
            results[tid] = {"status": "error"}

    return {"tenants": len(tenant_ids), "results": results}


async def check_approval_timeouts(ctx: dict) -> dict:
    """Every 5 minutes: check and auto-approve expired approval entries."""
    logger.info("Checking approval timeouts")

    from life_graph.api.dependencies import get_approval_service

    try:
        approval_service = get_approval_service()
        expired = await approval_service.check_expirations()
        logger.info("Approval timeout check: %d expired", expired)
        return {"expired_count": expired}
    except Exception:
        logger.exception("Approval timeout check failed")
        return {"status": "error"}


async def send_approval_escalations(ctx: dict) -> dict:
    """Every 30 minutes: send escalation notifications for pending approvals."""
    logger.info("Sending approval escalations")

    from life_graph.api.dependencies import get_approval_service

    try:
        approval_service = get_approval_service()
        escalated = await approval_service.send_escalations()
        logger.info("Escalation check: %d escalated", escalated)
        return {"escalated_count": escalated}
    except Exception:
        logger.exception("Approval escalation check failed")
        return {"status": "error"}




# ── Capture Spine: Daily Brief (Phase G) ─────────────────────────────────


async def run_daily_brief(ctx: dict) -> dict:
    """Daily cron: compose the daily brief for every active tenant.

    Composition runs the interview expire sweep + generation first, then
    bundles held notifications, capture summary, and watcher digest into
    a single notification. Tenants with no content get no brief.
    """
    logger.info("Starting daily brief composition for all tenants")

    from life_graph.core.events import event_bus
    from life_graph.models.db import TenantConfig
    from life_graph.services.brief import BriefComposer

    async with async_session() as session:
        result = await session.execute(
            select(TenantConfig.tenant_id).where(TenantConfig.status == "active")
        )
        tenant_ids = [row[0] for row in result.fetchall()]

    composer = BriefComposer(async_session, event_bus)
    results: dict[str, dict] = {}
    composed = 0
    for tid in tenant_ids:
        try:
            set_tenant_context(tid, "system")
            brief = await composer.compose_daily(tid)
            if brief:
                composed += 1
                results[tid] = {"status": "composed", "id": brief["id"]}
            else:
                results[tid] = {"status": "silent"}
        except Exception:
            logger.exception("Brief composition failed for tenant %s", tid)
            results[tid] = {"status": "error"}

    logger.info("Daily brief run: %d/%d tenants briefed", composed, len(tenant_ids))
    return {"tenants": len(tenant_ids), "composed": composed, "results": results}


# ── Judgment Engine: Monthly Failure-Pattern Mining (Phase H) ────────────


async def failure_pattern_mining(ctx: dict) -> dict:
    """Monthly cron: mine recurring failure patterns from resolved decisions.

    One LLM pass per tenant over failed decisions (incorrect predictions or
    reversed/superseded decisions). Patterns are stored as ``failure_pattern``
    memories only when they cite >=3 decision instances (else dropped).
    """
    logger.info("Starting monthly failure-pattern mining for all tenants")

    from life_graph.models.db import TenantConfig
    from life_graph.services.failure_mining import FailurePatternMiner
    from life_graph.services.llm_client import LMStudioClient

    async with async_session() as session:
        result = await session.execute(
            select(TenantConfig.tenant_id).where(TenantConfig.status == "active")
        )
        tenant_ids = [row[0] for row in result.fetchall()]

    miner = FailurePatternMiner(session_factory=async_session, llm=LMStudioClient())
    results: dict[str, dict] = {}
    total_stored = 0
    for tid in tenant_ids:
        try:
            set_tenant_context(tid, "system")
            summary = await miner.run(tid)
            total_stored += summary.get("patterns_stored", 0)
            results[tid] = summary
        except Exception:
            logger.exception("Failure mining failed for tenant %s", tid)
            results[tid] = {"status": "error"}

    logger.info(
        "Failure-pattern mining: %d tenants, %d patterns stored",
        len(tenant_ids), total_stored,
    )
    return {"tenants": len(tenant_ids), "patterns_stored": total_stored, "results": results}
