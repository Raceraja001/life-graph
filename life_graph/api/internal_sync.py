"""Internal sync endpoints — Era 7.

Authenticated via X-Internal-API-Key header.
These are NOT exposed to external clients.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException

from life_graph.api.dependencies import get_sync_service
from life_graph.config import settings
from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.schemas import CrossSystemSyncResponse
from life_graph.services.cross_system_sync import CrossSystemSyncService

router = APIRouter(prefix="/internal/sync", tags=["Internal Sync"])


def _verify_internal_key(x_internal_api_key: str = Header(...)):
    """Verify X-Internal-API-Key header."""
    if x_internal_api_key != settings.internal_api_key:
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
    data: dict,
    tenant_id: str = Depends(get_current_tenant_id),
    svc: CrossSystemSyncService = Depends(get_sync_service),
):
    """Receive analytics data from external system."""
    return await svc.receive_analytics(tenant_id, data)
