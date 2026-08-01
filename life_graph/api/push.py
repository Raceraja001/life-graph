"""Web Push subscription + test API.

`POST /push/subscriptions` saves a browser push subscription;
`DELETE /push/subscriptions` removes one; `GET /push/vapid-key` hands the
frontend the public VAPID key; `POST /push/test` sends a test notification
to every subscription on the caller's tenant. See docs/specs/web-push-notifications.md.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from life_graph.api.responses import success_response
from life_graph.config import settings
from life_graph.core.tenant import get_current_tenant_id
from life_graph.services.webpush import PushService
from life_graph.storage.database import async_session

router = APIRouter(prefix="/push", tags=["push"])


def _service() -> PushService:
    # PushService manages its own sessions, so it takes the session factory
    # directly rather than a per-request Depends(get_session) session.
    return PushService(async_session)


class SubKeys(BaseModel):
    p256dh: str
    auth: str


class SubscribeBody(BaseModel):
    endpoint: str
    keys: SubKeys


class UnsubscribeBody(BaseModel):
    endpoint: str


@router.post("/subscriptions", summary="Save a browser push subscription")
async def subscribe(body: SubscribeBody, request: Request):
    await _service().save_subscription(
        body.model_dump(), user_agent=request.headers.get("user-agent")
    )
    return success_response(data={"ok": True})


@router.delete("/subscriptions", summary="Remove a browser push subscription")
async def unsubscribe(body: UnsubscribeBody):
    await _service().delete_subscription(body.endpoint)
    return success_response(data={"ok": True})


@router.get("/vapid-key", summary="Get the public VAPID key")
async def vapid_key():
    return success_response(data={"key": settings.vapid_public_key})


@router.post("/test", summary="Send a test push notification to the caller's tenant")
async def test_push(tenant_id: str = Depends(get_current_tenant_id)):
    delivered = await _service().send_to_tenant(
        tenant_id, "Life Graph", "Test notification \U0001f389", "/m"
    )
    return success_response(data={"delivered": delivered})
