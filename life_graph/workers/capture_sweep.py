"""Retry captures that were never processed.

A capture is extracted by CaptureProcessors, which listens on the API
process's in-memory event bus. A capture written by the worker (PR review
feedback, services/dev_outcomes.py), or one whose handler died with the
process, stays ``received`` for good: on 2026-10-23 there were 970 of them,
among them 6 of the owner's prompts and 5 voice notes. Nothing retried them.

Every 15 minutes this picks up captures left ``received`` for over 15 minutes
and runs the same processor on them, in this process. Each one is tried at
most ``MAX_ATTEMPTS`` times, then marked ``failed`` so it is not retried for
ever. Surfaces that are never extracted are just marked processed by the
processor itself.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from life_graph.models.db import CaptureEvent
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

STALE_AFTER = timedelta(minutes=15)
BATCH = 50
MAX_ATTEMPTS = 3


async def sweep_stuck_captures(ctx: dict | None = None, tenant_id: str | None = None) -> dict:
    """Process up to BATCH stale ``received`` captures (one tenant, or all);
    mark repeat failures ``failed``."""
    from life_graph.config import settings
    from life_graph.core.events import Event, EventType
    from life_graph.services.capture_processors import capture_processors

    cutoff = datetime.now(UTC) - STALE_AFTER
    query = select(CaptureEvent).where(
        CaptureEvent.status == "received", CaptureEvent.created_at < cutoff
    )
    floor = settings.memory_start()
    if floor is not None:
        # A fresh start: captures from before it are not extracted again.
        query = query.where(CaptureEvent.created_at >= floor)
    if tenant_id is not None:
        query = query.where(CaptureEvent.tenant_id == tenant_id)
    async with async_session() as session:
        rows = (
            (await session.execute(query.order_by(CaptureEvent.created_at).limit(BATCH)))
            .scalars()
            .all()
        )
        picked = [
            (r.id, r.tenant_id, r.modality, r.surface, dict(r.properties or {})) for r in rows
        ]
        for row in rows:
            # Count the attempt before trying, so a handler that kills the
            # process still uses one up.
            props = dict(row.properties or {})
            props["sweep_attempts"] = int(props.get("sweep_attempts") or 0) + 1
            row.properties = props
        await session.commit()

    processed = failed = 0
    for capture_id, owner, modality, surface, props in picked:
        attempts = int(props.get("sweep_attempts") or 0) + 1
        if modality != "text":
            # The processor skips non-text captures without marking them; their
            # content is handled by the upload path (services/multimodal.py).
            await _mark(capture_id, owner, "processed")
            processed += 1
            continue
        try:
            await capture_processors._on_capture_received(
                Event(
                    type=EventType.CAPTURE_RECEIVED,
                    payload={
                        "capture_event_id": str(capture_id),
                        "tenant_id": owner,
                        "modality": modality,
                        "surface": surface,
                    },
                    source="capture_sweep",
                )
            )
        except Exception:
            logger.warning("Capture %s retry failed", capture_id, exc_info=True)
        if await _status(capture_id, owner) == "received":
            if attempts >= MAX_ATTEMPTS:
                await _mark(capture_id, owner, "failed")
                failed += 1
        else:
            processed += 1
    if picked:
        logger.info(
            "Capture sweep: %d picked, %d processed, %d marked failed",
            len(picked),
            processed,
            failed,
        )
    return {"picked": len(picked), "processed": processed, "failed": failed}


async def _status(capture_id, tenant_id: str) -> str | None:
    async with async_session() as session:
        return await session.scalar(
            select(CaptureEvent.status).where(
                CaptureEvent.id == capture_id, CaptureEvent.tenant_id == tenant_id
            )
        )


async def _mark(capture_id, tenant_id: str, status: str) -> None:
    async with async_session() as session:
        await session.execute(
            update(CaptureEvent)
            .where(CaptureEvent.id == capture_id, CaptureEvent.tenant_id == tenant_id)
            .values(status=status)
        )
        await session.commit()
