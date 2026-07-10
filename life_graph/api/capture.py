"""Capture Spine API routes.

Universal input layer — all data enters Life Graph through these endpoints.
Supports capture event ingestion with SHA-256 dedup and user corrections.

Prefix: /capture
Tags: [capture-spine]
"""

from __future__ import annotations

from datetime import datetime
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Query, status

from life_graph.api.responses import success_response
from life_graph.core.events import event_bus
from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.schemas import (
    CaptureEventCreate,
    CaptureEventResponse,
    CorrectionCreate,
    CorrectionResponse,
)
from life_graph.services.capture import CaptureService
from life_graph.storage.database import async_session

router = APIRouter(prefix="/capture", tags=["capture-spine"])


# ── Dependencies ──────────────────────────────────────────────


async def _get_capture_service() -> AsyncGenerator[CaptureService, None]:
    """Yield a CaptureService bound to a request-scoped session.

    Commits on successful completion; rolls back automatically on error
    via the ``async_session`` context manager.
    """
    async with async_session() as session:
        svc = CaptureService(session, event_bus)
        yield svc
        await session.commit()


# ── Routes ───────────────────────────────────────────────────


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a capture event",
)
async def ingest_capture_event(
    body: CaptureEventCreate,
    svc: CaptureService = Depends(_get_capture_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Ingest raw content from any surface.

    Performs SHA-256 dedup within a 10-minute window per surface.
    Returns the new event or the existing duplicate.
    """
    event = await svc.ingest(
        tenant_id=tenant_id,
        surface=body.surface,
        content=body.content,
        modality=body.modality,
        occurred_at=body.occurred_at,
        properties=body.properties,
    )
    return success_response(data=CaptureEventResponse.model_validate(event))


@router.get(
    "/",
    summary="List capture events",
)
async def list_capture_events(
    svc: CaptureService = Depends(_get_capture_service),
    tenant_id: str = Depends(get_current_tenant_id),
    surface: str | None = Query(None, description="Filter by source surface"),
    since: datetime | None = Query(None, description="Only events after this timestamp"),
    limit: int = Query(50, ge=1, le=200, description="Max results to return"),
):
    """List capture events for the current tenant.

    Supports filtering by surface and timestamp. Returns newest first.
    """
    events = await svc.list_events(
        tenant_id=tenant_id,
        surface=surface,
        since=since,
        limit=limit,
    )
    return success_response(
        data=[CaptureEventResponse.model_validate(e) for e in events],
    )


@router.post(
    "/correction",
    status_code=status.HTTP_201_CREATED,
    summary="Record a correction",
)
async def record_correction(
    body: CorrectionCreate,
    svc: CaptureService = Depends(_get_capture_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Record a user correction (edit, override, reject, approve).

    Corrections feed the self-improving loop — they teach the system
    what the user actually meant.
    """
    correction = await svc.record_correction(
        tenant_id=tenant_id,
        kind=body.kind,
        original=body.original,
        corrected=body.corrected,
        capture_event_id=body.capture_event_id,
        diff_summary=body.diff_summary,
        context=body.context,
        domain_tags=body.domain_tags,
    )
    return success_response(data=CorrectionResponse.model_validate(correction))


@router.get(
    "/corrections",
    summary="List corrections",
)
async def list_corrections(
    svc: CaptureService = Depends(_get_capture_service),
    tenant_id: str = Depends(get_current_tenant_id),
    kind: str | None = Query(None, description="Filter by correction kind"),
    limit: int = Query(50, ge=1, le=200, description="Max results to return"),
):
    """List corrections for the current tenant.

    Supports filtering by kind (edit, override, reject, approve).
    """
    corrections = await svc.list_corrections(
        tenant_id=tenant_id,
        kind=kind,
        limit=limit,
    )
    return success_response(
        data=[CorrectionResponse.model_validate(c) for c in corrections],
    )
