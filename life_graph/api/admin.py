"""Admin routes — health, stats, gaps, raw ingestion, webhooks, tenants, and bulk ops.

Provides operational endpoints: system statistics (simple COUNT
queries), knowledge gap listing, raw text ingestion shortcut,
webhook CRUD, tenant lifecycle management, and bulk memory operations.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select

from life_graph.api.dependencies import get_memory_manager, get_metamemory, get_store
from life_graph.api.openapi_examples import (
    BULK_DELETE,
    BULK_IMPORT,
    TENANT_PROVISIONED,
    TENANT_SUMMARY,
    WEBHOOK_CREATED,
    WEBHOOK_LIST,
)
from life_graph.api.responses import encode_cursor, paginated_response, success_response
from life_graph.core.memory_manager import MemoryManager
from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.db import (
    Intention,
    JobRun,
    KnowledgeGap,
    Memory,
    MemorySession,
    Session,
    TenantConfig,
    TenantUsage,
    TenantWebhook,
)
from life_graph.models.schemas import MemoryResponse
from life_graph.services.metamemory import MetamemoryTracker
from life_graph.storage.database import async_session
from life_graph.storage.postgres import PostgresMemoryStore

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Request / Response schemas ───────────────────────────────


class SystemStats(BaseModel):
    """Aggregate counts for the system dashboard."""

    memory_count: int
    intention_count: int
    gap_count: int
    session_count: int


class GapResponse(BaseModel):
    """Serialized knowledge gap for the API."""

    model_config = {"from_attributes": True}

    id: Any
    topic: str
    query_count: int
    first_asked: Any
    last_asked: Any
    resolved: bool


class IngestRequest(BaseModel):
    """Body for raw text ingestion."""

    text: str = Field(..., min_length=1, description="Raw text to ingest")
    context: dict[str, Any] | None = Field(
        None, description="Optional context (project, module, etc.)"
    )
    source: str | None = Field(
        None, description="Source identifier (e.g. 'chat', 'git', 'manual')"
    )


class BulkImportItem(BaseModel):
    """Single memory item for bulk import."""

    content: str = Field(..., min_length=1)
    tags: list[str] | None = None
    importance: float | None = Field(None, ge=0, le=1)
    source_type: str | None = None


class BulkImportRequest(BaseModel):
    """Request body for bulk memory import."""

    memories: list[BulkImportItem] = Field(..., max_length=500)
    generate_embeddings: bool = True


class BulkDeleteRequest(BaseModel):
    """Request body for bulk memory deletion."""

    filter: dict
    confirm: bool = False


class WebhookCreate(BaseModel):
    """Request body for registering a webhook."""

    url: str = Field(..., min_length=8, description="Target URL for event delivery")
    secret: str = Field(..., min_length=16, description="HMAC signing secret (min 16 chars)")
    events: str = Field("*", description="Comma-separated event types or '*' for all")


class TenantProvisionRequest(BaseModel):
    """Request body for provisioning a new tenant."""

    tenant_id: str = Field(
        ..., min_length=3, max_length=64,
        pattern=r"^[a-z0-9][a-z0-9_-]{2,63}$",
        description="Unique tenant identifier (lowercase alphanumeric + hyphens)",
    )
    plan: str = Field("free", pattern=r"^(free|pro|enterprise)$", description="Tenant plan")


# ── Routes ───────────────────────────────────────────────────


@router.get(
    "/stats",
    summary="System statistics",
)
async def get_stats():
    """Return aggregate counts for memories, intentions, gaps, and sessions."""
    async with async_session() as session:
        memory_count = await session.scalar(select(func.count(Memory.id)))
        intention_count = await session.scalar(select(func.count(Intention.id)))
        gap_count = await session.scalar(select(func.count(KnowledgeGap.id)))
        session_count = await session.scalar(select(func.count(Session.id)))

    return success_response(data=SystemStats(
        memory_count=memory_count or 0,
        intention_count=intention_count or 0,
        gap_count=gap_count or 0,
        session_count=session_count or 0,
    ))


@router.get(
    "/gaps",
    summary="List knowledge gaps",
)
async def list_gaps(
    metamemory: MetamemoryTracker = Depends(get_metamemory),
):
    """Return unresolved knowledge gaps, ordered by query count."""
    gaps = await metamemory.get_gaps()
    return success_response(data=[GapResponse.model_validate(g) for g in gaps])


@router.post(
    "/ingest",
    status_code=status.HTTP_201_CREATED,
    summary="Ingest raw text",
)
async def ingest_text(
    body: IngestRequest,
    manager: MemoryManager = Depends(get_memory_manager),
):
    """Run raw text through the full ingestion pipeline.

    Extracts facts, scores importance, checks contradictions,
    and stores resulting memories.
    """
    memories = await manager.ingest(
        text=body.text,
        context=body.context,
        source=body.source,
    )
    return success_response(data=[MemoryResponse.model_validate(m) for m in memories])


@router.get(
    "/export",
    summary="Export all memories as NDJSON stream",
)
async def export_memories(
    store: PostgresMemoryStore = Depends(get_store),
):
    """Export all memories as a streaming NDJSON (newline-delimited JSON) response.

    Streams memories in batches of 1000 to avoid loading all data into RAM.
    Each line is a valid JSON object representing one memory.
    """
    import json

    async def _stream_generator():
        cursor = None
        while True:
            batch, has_more = await store.list_memories(limit=1000, cursor=cursor)
            for memory in batch:
                row = MemoryResponse.model_validate(memory).model_dump(mode="json")
                yield json.dumps(row, default=str) + "\n"
            if not has_more or not batch:
                break
            cursor = encode_cursor(
                batch[-1].created_at.isoformat(),
                str(batch[-1].id),
            )

    return StreamingResponse(
        _stream_generator(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=memories_export.ndjson"},
    )


# ── Webhooks ─────────────────────────────────────────────────


@router.post(
    "/webhooks",
    status_code=status.HTTP_201_CREATED,
    summary="Register a webhook",
    responses=WEBHOOK_CREATED,
)
async def create_webhook(body: WebhookCreate):
    """Register a new webhook for the current tenant.

    The webhook will receive event notifications at the specified URL.
    A shared secret is used for HMAC signature verification.
    """
    tenant_id = get_current_tenant_id()
    webhook = TenantWebhook(
        tenant_id=tenant_id,
        url=body.url,
        secret=body.secret,
        events=body.events,
    )
    async with async_session() as session:
        session.add(webhook)
        await session.commit()
        await session.refresh(webhook)

    return success_response(data={
        "id": str(webhook.id),
        "url": webhook.url,
        "events": webhook.events,
        "active": webhook.active,
        "created_at": webhook.created_at.isoformat(),
    })


@router.get(
    "/webhooks",
    summary="List webhooks",
    responses=WEBHOOK_LIST,
)
async def list_webhooks():
    """List all webhooks registered for the current tenant."""
    tenant_id = get_current_tenant_id()
    stmt = select(TenantWebhook).where(TenantWebhook.tenant_id == tenant_id)

    async with async_session() as session:
        result = await session.execute(stmt)
        webhooks = result.scalars().all()

    data = [
        {
            "id": str(w.id),
            "url": w.url,
            "events": w.events,
            "active": w.active,
            "created_at": w.created_at.isoformat(),
            "last_delivered_at": w.last_delivered_at.isoformat() if w.last_delivered_at else None,
            "failure_count": w.failure_count,
        }
        for w in webhooks
    ]
    return paginated_response(
        data=data,
        page_size=len(data),
        has_more=False,
    )


@router.delete(
    "/webhooks/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a webhook",
    response_class=Response,
)
async def delete_webhook(webhook_id: uuid.UUID):
    """Delete a webhook registration by ID."""
    tenant_id = get_current_tenant_id()
    async with async_session() as session:
        webhook = await session.get(TenantWebhook, webhook_id)
        if webhook is None or webhook.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Webhook {webhook_id} not found",
            )
        await session.delete(webhook)
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/webhooks/{webhook_id}/test",
    summary="Test a webhook",
)
async def test_webhook(webhook_id: uuid.UUID):
    """Send a test event payload to a webhook URL.

    Delivers a synthetic 'test.ping' event and reports the
    HTTP status and response time from the target.
    """
    tenant_id = get_current_tenant_id()
    async with async_session() as session:
        webhook = await session.get(TenantWebhook, webhook_id)
        if webhook is None or webhook.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Webhook {webhook_id} not found",
            )

    test_payload = {
        "event": "test.ping",
        "tenant_id": tenant_id,
        "webhook_id": str(webhook_id),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(webhook.url, json=test_payload)
        delivery_status = "delivered" if resp.status_code < 400 else "failed"
        return success_response(data={
            "webhook_id": str(webhook_id),
            "delivery_status": delivery_status,
            "http_status": resp.status_code,
            "url": webhook.url,
        })
    except Exception as e:
        return success_response(data={
            "webhook_id": str(webhook_id),
            "delivery_status": "error",
            "error": str(e),
            "url": webhook.url,
        })


# ── Tenant Lifecycle ─────────────────────────────────────────


@router.post(
    "/tenants/provision",
    status_code=status.HTTP_201_CREATED,
    summary="Provision a new tenant",
    responses=TENANT_PROVISIONED,
)
async def provision_tenant(body: TenantProvisionRequest):
    """Provision a new tenant with a configuration record and usage tracking.

    Validates tenant_id format (lowercase alphanumeric, 3-64 chars),
    creates TenantConfig and initial TenantUsage records.
    """
    tenant_id = body.tenant_id
    plan = body.plan

    async with async_session() as session:
        # Check if already exists
        existing = await session.get(TenantConfig, tenant_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Tenant '{tenant_id}' already exists",
            )

        config = TenantConfig(tenant_id=tenant_id, plan=plan)
        usage = TenantUsage(
            tenant_id=tenant_id,
            period_start=datetime.now(timezone.utc),
        )
        session.add(config)
        session.add(usage)
        await session.commit()
        await session.refresh(config)

    return success_response(data={
        "tenant_id": config.tenant_id,
        "plan": config.plan,
        "status": config.status,
        "provisioned_at": config.provisioned_at.isoformat(),
    })


@router.get(
    "/tenants/{tenant_id}",
    summary="Get tenant summary",
    responses=TENANT_SUMMARY,
)
async def get_tenant_summary(tenant_id: str):
    """Return a comprehensive tenant summary.

    Includes memory count, session count, plan, status,
    and aggregated usage statistics.
    """
    async with async_session() as session:
        config = await session.get(TenantConfig, tenant_id)
        if config is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant '{tenant_id}' not found",
            )

        memory_count = await session.scalar(
            select(func.count(Memory.id)).where(Memory.tenant_id == tenant_id)
        )
        session_count = await session.scalar(
            select(func.count(Session.id)).where(Session.tenant_id == tenant_id)
        )

        # Aggregate usage
        usage_stmt = select(
            func.sum(TenantUsage.api_calls),
            func.sum(TenantUsage.memories_created),
            func.sum(TenantUsage.llm_tokens_used),
        ).where(TenantUsage.tenant_id == tenant_id)
        usage_row = (await session.execute(usage_stmt)).one_or_none()

    return success_response(data={
        "tenant_id": config.tenant_id,
        "plan": config.plan,
        "status": config.status,
        "provisioned_at": config.provisioned_at.isoformat(),
        "deactivated_at": config.deactivated_at.isoformat() if config.deactivated_at else None,
        "memory_count": memory_count or 0,
        "session_count": session_count or 0,
        "usage": {
            "total_api_calls": usage_row[0] or 0 if usage_row else 0,
            "total_memories_created": usage_row[1] or 0 if usage_row else 0,
            "total_llm_tokens_used": usage_row[2] or 0 if usage_row else 0,
        },
    })


@router.post(
    "/tenants/{tenant_id}/deactivate",
    summary="Deactivate a tenant",
)
async def deactivate_tenant(tenant_id: str):
    """Deactivate a tenant, switching to read-only access.

    Sets status to 'deactivated' and records the deactivation timestamp.
    The tenant's data is preserved but write operations are blocked.
    """
    async with async_session() as session:
        config = await session.get(TenantConfig, tenant_id)
        if config is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant '{tenant_id}' not found",
            )

        config.status = "deactivated"
        config.deactivated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(config)

    return success_response(data={
        "tenant_id": config.tenant_id,
        "status": config.status,
        "deactivated_at": config.deactivated_at.isoformat(),
    })


@router.post(
    "/tenants/{tenant_id}/reactivate",
    summary="Reactivate a tenant",
)
async def reactivate_tenant(tenant_id: str):
    """Reactivate a previously deactivated tenant.

    Restores full read-write access by setting status back to 'active'
    and clearing the deactivation timestamp.
    """
    async with async_session() as session:
        config = await session.get(TenantConfig, tenant_id)
        if config is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant '{tenant_id}' not found",
            )

        config.status = "active"
        config.deactivated_at = None
        await session.commit()
        await session.refresh(config)

    return success_response(data={
        "tenant_id": config.tenant_id,
        "status": config.status,
    })


@router.delete(
    "/tenants/{tenant_id}",
    summary="Permanently delete a tenant",
)
async def delete_tenant(tenant_id: str):
    """Permanently delete a tenant and ALL associated data.

    Only works if the tenant is already deactivated (status='deactivated').
    Returns 409 Conflict if the tenant is still active.
    Cascade deletes: MemorySession, Memory, Session, Intention,
    KnowledgeGap, JobRun, TenantUsage, TenantWebhook, TenantConfig.
    """
    async with async_session() as session:
        config = await session.get(TenantConfig, tenant_id)
        if config is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant '{tenant_id}' not found",
            )

        if config.status != "deactivated":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Tenant must be deactivated before deletion",
            )

        counts = {}

        # Delete in dependency order (associations first)
        # MemorySessions (references both memories and sessions)
        ms_del = await session.execute(
            delete(MemorySession).where(
                MemorySession.memory_id.in_(
                    select(Memory.id).where(Memory.tenant_id == tenant_id)
                )
            )
        )
        counts["memory_sessions"] = ms_del.rowcount

        mem_del = await session.execute(
            delete(Memory).where(Memory.tenant_id == tenant_id)
        )
        counts["memories"] = mem_del.rowcount

        sess_del = await session.execute(
            delete(Session).where(Session.tenant_id == tenant_id)
        )
        counts["sessions"] = sess_del.rowcount

        int_del = await session.execute(
            delete(Intention).where(Intention.tenant_id == tenant_id)
        )
        counts["intentions"] = int_del.rowcount

        gap_del = await session.execute(
            delete(KnowledgeGap).where(KnowledgeGap.tenant_id == tenant_id)
        )
        counts["knowledge_gaps"] = gap_del.rowcount

        job_del = await session.execute(
            delete(JobRun).where(JobRun.tenant_id == tenant_id)
        )
        counts["job_runs"] = job_del.rowcount

        usage_del = await session.execute(
            delete(TenantUsage).where(TenantUsage.tenant_id == tenant_id)
        )
        counts["tenant_usage"] = usage_del.rowcount

        wh_del = await session.execute(
            delete(TenantWebhook).where(TenantWebhook.tenant_id == tenant_id)
        )
        counts["webhooks"] = wh_del.rowcount

        await session.delete(config)
        counts["tenant_config"] = 1

        await session.commit()

    return success_response(data={
        "tenant_id": tenant_id,
        "deleted": True,
        "counts": counts,
    })


# ── Bulk Operations ──────────────────────────────────────────


@router.post(
    "/bulk/delete",
    summary="Bulk delete memories",
    responses=BULK_DELETE,
)
async def bulk_delete(body: BulkDeleteRequest):
    """Bulk delete memories matching filter criteria.

    Requires at least one filter (tags, created_before, status, source_type).
    If confirm=false, returns a dry-run count without deleting.
    If confirm=true, executes the deletion. All operations are tenant-scoped.
    """
    tenant_id = get_current_tenant_id()
    filters = body.filter

    if not filters:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one filter is required (tags, created_before, status, source_type)",
        )

    # Build query
    stmt = select(Memory.id).where(Memory.tenant_id == tenant_id)

    if "tags" in filters:
        stmt = stmt.where(Memory.tags.overlap(filters["tags"]))
    if "created_before" in filters:
        stmt = stmt.where(Memory.created_at < filters["created_before"])
    if "status" in filters:
        stmt = stmt.where(Memory.status == filters["status"])
    if "source_type" in filters:
        stmt = stmt.where(Memory.source_type == filters["source_type"])

    async with async_session() as session:
        result = await session.execute(stmt)
        matching_ids = [row[0] for row in result.all()]
        count = len(matching_ids)

        if not body.confirm:
            return success_response(data={
                "dry_run": True,
                "match_count": count,
                "filters": filters,
            })

        # Execute delete
        if matching_ids:
            # Delete associations first
            await session.execute(
                delete(MemorySession).where(
                    MemorySession.memory_id.in_(matching_ids)
                )
            )
            del_result = await session.execute(
                delete(Memory).where(Memory.id.in_(matching_ids))
            )
            await session.commit()
            deleted = del_result.rowcount
        else:
            deleted = 0

    return success_response(data={
        "dry_run": False,
        "deleted": deleted,
        "filters": filters,
    })


@router.post(
    "/bulk/import",
    status_code=status.HTTP_201_CREATED,
    summary="Bulk import memories",
    responses=BULK_IMPORT,
)
async def bulk_import(body: BulkImportRequest):
    """Bulk import up to 500 memories directly into the store.

    Inserts memory records without running the full ingestion pipeline.
    If generate_embeddings=true, enqueues an ARQ job to compute
    embeddings asynchronously.
    """
    tenant_id = get_current_tenant_id()
    imported = 0
    embedding_job_id = None

    async with async_session() as session:
        memory_ids = []
        for item in body.memories:
            memory = Memory(
                tenant_id=tenant_id,
                content=item.content,
                tags=item.tags,
                importance=item.importance or 0.5,
                source_type=item.source_type or "bulk_import",
                status="active",
            )
            session.add(memory)
            memory_ids.append(memory.id)
            imported += 1

        await session.commit()

    # Optionally enqueue embedding generation
    searchable = not body.generate_embeddings
    if body.generate_embeddings:
        try:
            from arq import create_pool
            from life_graph.workers.settings import parse_redis_settings

            pool = await create_pool(parse_redis_settings())
            job = await pool.enqueue_job(
                "generate_bulk_embeddings",
                tenant_id,
                [str(mid) for mid in memory_ids],
            )
            embedding_job_id = job.job_id
            await pool.close()
        except Exception:
            # Embeddings will need to be generated later
            pass

    return success_response(data={
        "imported": imported,
        "embedding_job_id": embedding_job_id,
        "searchable": searchable,
    })


# ── Consolidation ────────────────────────────────────────────


class ConsolidationResponse(BaseModel):
    """Result from a consolidation run."""

    gathered: int = 0
    clusters_found: int = 0
    duplicates_removed: int = 0
    principles_created: int = 0
    memories_archived: int = 0
    contradictions_found: int = 0
    duration_seconds: float = 0.0


@router.post(
    "/consolidate",
    summary="Run consolidation now",
)
async def run_consolidation():
    """Manually trigger the nightly consolidation pipeline.

    Runs the full 7-step sleep-cycle analog: gather, cluster,
    dedup, score, distill, decay, and audit.
    """
    from life_graph.api.dependencies import get_job_scheduler
    scheduler = get_job_scheduler()
    report = await scheduler.run_consolidation()
    return success_response(data=ConsolidationResponse(
        gathered=report.gathered,
        clusters_found=report.clusters_found,
        duplicates_removed=report.duplicates_removed,
        principles_created=report.principles_created,
        memories_archived=report.memories_archived,
        contradictions_found=report.contradictions_found,
        duration_seconds=report.duration_seconds,
    ))


@router.post(
    "/micro-consolidate/{session_id}",
    summary="Run micro-consolidation for a session",
)
async def run_micro_consolidation(session_id: uuid.UUID):
    """Manually trigger micro-consolidation for a specific session.

    Runs the lightweight 4-step pipeline: gather session memories,
    dedup against existing, re-score importance, update graph.
    No LLM calls — completes in under 2 seconds.
    """
    from life_graph.api.dependencies import get_micro_consolidator
    from life_graph.models.schemas import MicroConsolidationResponse

    consolidator = get_micro_consolidator()
    report = await consolidator.run(session_id)
    return success_response(data=MicroConsolidationResponse(
        session_id=str(session_id),
        memories_processed=report.memories_processed,
        duplicates_removed=report.duplicates_removed,
        importance_updated=report.importance_updated,
        entities_discovered=report.entities_discovered,
        edges_created=report.edges_created,
        duration_seconds=report.duration_seconds,
    ))


# ── Background Jobs ──────────────────────────────────────────


class JobRunResponse(BaseModel):
    """Serialized job run for the API."""

    model_config = {"from_attributes": True}

    id: Any
    tenant_id: str
    job_name: str
    status: str
    started_at: Any
    completed_at: Any | None = None
    error: str | None = None
    result: dict | None = None


@router.get(
    "/jobs",
    summary="List recent job runs",
)
async def list_job_runs(
    limit: int = 20,
    tenant_id: str | None = None,
):
    """List recent background job runs, optionally filtered by tenant."""
    stmt = select(JobRun).order_by(JobRun.started_at.desc()).limit(limit)
    if tenant_id:
        stmt = stmt.where(JobRun.tenant_id == tenant_id)

    async with async_session() as session:
        result = await session.execute(stmt)
        jobs = result.scalars().all()

    return success_response(data=[JobRunResponse.model_validate(j) for j in jobs])


@router.post(
    "/jobs/consolidate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue consolidation job",
)
async def enqueue_consolidation(tenant_id: str | None = None):
    """Enqueue a consolidation job via ARQ (async, non-blocking).

    If ARQ is unavailable, falls back to the legacy synchronous run.
    """
    try:
        from arq import create_pool
        from life_graph.workers.settings import parse_redis_settings

        pool = await create_pool(parse_redis_settings())
        if tenant_id:
            job = await pool.enqueue_job("run_tenant_consolidation", tenant_id)
        else:
            job = await pool.enqueue_job("run_all_consolidations")
        await pool.close()
        return success_response(data={"job_id": job.job_id, "status": "enqueued"})
    except Exception:
        # Fallback: run the legacy consolidation
        from life_graph.api.dependencies import get_job_scheduler
        scheduler = get_job_scheduler()
        report = await scheduler.run_consolidation()
        return success_response(data={"status": "completed_sync", "gathered": report.gathered})
