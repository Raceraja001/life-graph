"""Health of the memory engine itself (docs/modular_memory_service_plan.md, 2C).

``/health`` (main.py) checks the whole process: Postgres, Redis, the graph,
startup subsystems. This answers the narrower question an agent or a memory
client asks: can memories be stored and found right now, and is anything
coming in? Postgres and pgvector are required (503 without them); the
embedding backend degrades the status, because without it writes still succeed
while semantic search silently returns nothing.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from life_graph.config import settings
from life_graph.core.tenant import get_current_tenant_id
from life_graph.storage.database import async_session

router = APIRouter(prefix="/health", tags=["health"])


def _ms(t0: float) -> float:
    return round((time.monotonic() - t0) * 1000, 1)


@router.get("/memory", summary="Is the memory engine able to store and find memories?")
async def memory_health() -> JSONResponse:
    """Postgres and pgvector, this tenant's memory and capture counts, the
    embedding backend's status and latency, and the last consolidation run."""
    tenant_id = get_current_tenant_id()
    checks: dict[str, Any] = {}

    t0 = time.monotonic()
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
            checks["postgres"] = {"status": "healthy", "latency_ms": _ms(t0)}

            version = (
                await session.execute(
                    text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
                )
            ).scalar_one_or_none()
            checks["pgvector"] = (
                {"status": "healthy", "version": version}
                if version
                else {"status": "missing", "error": "the vector extension is not installed"}
            )

            by_status = dict(
                (
                    await session.execute(
                        text(
                            "SELECT status, count(*) FROM memories "
                            "WHERE tenant_id = :t GROUP BY status"
                        ),
                        {"t": tenant_id},
                    )
                ).all()
            )
            since = datetime.now(UTC) - timedelta(days=1)
            captures = (
                await session.execute(
                    text(
                        "SELECT count(*), count(*) FILTER (WHERE created_at >= :since), "
                        "max(created_at) FROM capture_events WHERE tenant_id = :t"
                    ),
                    {"t": tenant_id, "since": since},
                )
            ).one()
            last_consolidation = (
                await session.execute(
                    text(
                        "SELECT status, started_at, completed_at FROM job_runs "
                        "WHERE tenant_id = :t AND job_name = 'consolidation' "
                        "ORDER BY created_at DESC LIMIT 1"
                    ),
                    {"t": tenant_id},
                )
            ).one_or_none()
    except Exception as e:  # noqa: BLE001 — any failure here is the answer
        checks["postgres"] = {"status": "unhealthy", "error": str(e), "latency_ms": _ms(t0)}
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "profile": settings.profile, "checks": checks},
        )

    checks["memories"] = {
        "active": int(by_status.get("active", 0)),
        "pending": int(by_status.get("pending", 0)),
        "total": int(sum(by_status.values())),
    }
    checks["capture_events"] = {
        "total": int(captures[0] or 0),
        "last_24h": int(captures[1] or 0),
        "last_at": captures[2].isoformat() if captures[2] else None,
    }
    checks["last_consolidation"] = (
        {
            "status": last_consolidation[0],
            "started_at": last_consolidation[1].isoformat() if last_consolidation[1] else None,
            "completed_at": last_consolidation[2].isoformat() if last_consolidation[2] else None,
        }
        if last_consolidation
        else None
    )

    from life_graph.api.dependencies import get_embedding_service

    t0 = time.monotonic()
    embed_status = await get_embedding_service().probe()
    checks["embeddings"] = {
        "status": embed_status,
        "latency_ms": _ms(t0),
        "model": settings.lm_embedding_model
        if settings.use_local_llm
        else settings.embedding_model,
        "dimension": settings.embedding_dimension,
    }

    if checks["pgvector"]["status"] != "healthy":
        overall, code = "unhealthy", 503
    elif embed_status != "healthy":
        overall, code = "degraded", 200
    else:
        overall, code = "healthy", 200
    return JSONResponse(
        status_code=code,
        content={"status": overall, "profile": settings.profile, "checks": checks},
    )
