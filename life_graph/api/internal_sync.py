"""Internal sync endpoints — Era 7.

Authenticated via X-Internal-API-Key header.
These are NOT exposed to external clients.
"""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException

from life_graph.api.dependencies import get_sync_service
from life_graph.config import settings
from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.schemas import AnalyticsBatch, CrossSystemSyncResponse
from life_graph.services.cross_system_sync import CrossSystemSyncService

router = APIRouter(prefix="/internal/sync", tags=["Internal Sync"])


def _verify_internal_key(x_internal_api_key: str = Header(...)):
    """Verify X-Internal-API-Key header.

    With no key configured (the default is ""), nothing can authenticate: the
    old ``!=`` check let an empty header match an empty setting. The compare
    is constant-time so the key cannot be guessed byte by byte from timing.
    """
    expected = settings.internal_api_key
    if not expected:
        raise HTTPException(status_code=403, detail="Internal sync is not configured")
    if not hmac.compare_digest(x_internal_api_key.encode(), expected.encode()):
        raise HTTPException(status_code=403, detail="Invalid internal API key")


@router.post(
    "/preferences",
    response_model=CrossSystemSyncResponse,
    dependencies=[Depends(_verify_internal_key)],
)
async def sync_preferences(
    tenant_id: str = Depends(get_current_tenant_id),
    svc: CrossSystemSyncService = Depends(get_sync_service),
):
    """Sync preferences to external system (Uzhavu)."""
    return await svc.sync_preferences(tenant_id)


@router.post(
    "/analytics",
    response_model=CrossSystemSyncResponse,
    dependencies=[Depends(_verify_internal_key)],
)
async def receive_analytics(
    data: AnalyticsBatch,
    tenant_id: str = Depends(get_current_tenant_id),
    svc: CrossSystemSyncService = Depends(get_sync_service),
):
    """Receive analytics data from external system.

    Each item becomes a *pending* memory: it waits in the review queue like
    every other ingested memory instead of going straight to active.
    """
    return await svc.receive_analytics(tenant_id, data)
