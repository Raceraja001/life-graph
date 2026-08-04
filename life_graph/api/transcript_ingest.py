"""Ingest endpoint for external AI-tool transcript deltas.

Appends raw lines to a per-session MinIO staging object, upserts the
ExternalSession, and enqueues a debounced distill job.

NOTE: named `transcript_ingest.py` (not `ingest_transcript.py`) and mounted at
`/api/v1/ingest/external-transcript` (not `/api/v1/ingest/transcript`) to avoid
colliding with the pre-existing `life_graph/api/ingest_transcript.py`, which
already owns `POST /api/v1/ingest/transcript` for the unrelated Era4 Personal
AI preference-extraction feature. See task-5-report.md for details.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from minio.error import S3Error
from sqlalchemy import select

from life_graph.api.dependencies import async_session
from life_graph.core.tenant import get_current_tenant_id
from life_graph.extraction.transcript_parsers import PARSERS
from life_graph.models.db import ExternalSession, _utcnow
from life_graph.models.schemas import TranscriptSessionIngest
from life_graph.services.transcript_distiller import ARCHIVE_BUCKET
from life_graph.storage.minio_client import MinIOStorage
from life_graph.storage.redis import get_redis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])

DISTILL_JOB = "life_graph.workers.distill_transcript.distill_transcript"


@router.post("/external-transcript", status_code=202)
async def ingest_external_transcript(payload: TranscriptSessionIngest) -> dict:
    if payload.tool not in PARSERS:
        raise HTTPException(status_code=422, detail=f"Unknown tool: {payload.tool}")

    tenant_id = get_current_tenant_id()
    minio = MinIOStorage()

    async with async_session() as session:
        rows = await session.execute(
            select(ExternalSession).where(
                ExternalSession.tenant_id == tenant_id,
                ExternalSession.tool == payload.tool,
                ExternalSession.external_id == payload.session_id,
            )
        )
        es = rows.scalars().first()
        if es is None:
            es = ExternalSession(
                tenant_id=tenant_id,
                tool=payload.tool,
                external_id=payload.session_id,
                source_path=payload.source_path,
                raw_key=f"staging/{tenant_id}/{payload.tool}/{payload.session_id}.ndjson",
            )
            session.add(es)
        else:
            es.source_path = payload.source_path
            es.updated_at = _utcnow()

        # Read-append-write the raw staging object (sequential per session).
        # Only a genuinely-absent staging object (first write for this session)
        # may fall back to an empty base — any other download failure must
        # propagate, or a transient outage would silently overwrite previously
        # staged lines. NoSuchKey = object not written yet; NoSuchBucket = the
        # bucket doesn't exist yet on a fresh deploy (upload()'s ensure_bucket
        # creates it on the write below), so both mean "nothing staged yet".
        existing = b""
        if es.raw_key:
            try:
                existing = minio.download(ARCHIVE_BUCKET, es.raw_key)
            except S3Error as exc:
                if exc.code not in ("NoSuchKey", "NoSuchBucket"):
                    raise
        appended = existing + ("".join(line + "\n" for line in payload.lines)).encode("utf-8")
        # SECURITY: this staging object holds RAW, UNREDACTED transcript lines —
        # redaction only happens later, in the distiller (extracted facts + archive).
        # This bucket MUST remain private. It can't be truncated after a distill
        # pass today, since the distiller re-parses the whole object and indexes by
        # turn count; a future byte/line-offset marker would allow safe truncation.
        minio.upload(ARCHIVE_BUCKET, es.raw_key, appended, content_type="application/x-ndjson")
        es.line_count = (es.line_count or 0) + len(payload.lines)

        await session.commit()

    # Debounced enqueue: one job per session per short window.
    should_enqueue = True
    redis = get_redis()
    if redis is not None:
        try:
            key = f"distill:transcript:{tenant_id}:{payload.session_id}"
            should_enqueue = bool(await redis.set(key, "1", nx=True, ex=60))
        except Exception:  # pragma: no cover - fail open
            should_enqueue = True

    if should_enqueue:
        try:
            from arq import create_pool

            from life_graph.workers.settings import parse_redis_settings

            pool = await create_pool(parse_redis_settings())
            try:
                await pool.enqueue_job(DISTILL_JOB, payload.session_id, tenant_id)
            finally:
                await pool.close()
        except Exception:  # pragma: no cover - enqueue best-effort
            logger.exception("Failed to enqueue distill_transcript for %s", payload.session_id)

    return {"data": {"accepted": len(payload.lines), "session_id": payload.session_id}}
