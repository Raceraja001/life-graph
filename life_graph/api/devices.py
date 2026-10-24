"""Phones paired with Jarvis (services/devices.py, docs/design/12_android_app_plan.md).

``POST /devices/codes`` (service key) shows the owner a one-time code;
``POST /devices/pair`` (no credential: the code is it) trades it for a device
token; ``GET /devices`` lists them and ``DELETE /devices/{id}`` revokes one.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from life_graph.api.responses import success_response
from life_graph.core.tenant import get_current_tenant_id
from life_graph.storage.database import async_session

router = APIRouter(prefix="/devices", tags=["devices"])


class PairRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=16)
    name: str = Field("Phone", max_length=120)


@router.post(
    "/codes", status_code=status.HTTP_201_CREATED, summary="A one-time code to pair a phone"
)
async def create_code():
    from life_graph.services import devices

    async with async_session() as session:
        row = await devices.issue_code(session, get_current_tenant_id())
        await session.commit()
        return success_response(data={"code": row.code, "expires_at": row.expires_at.isoformat()})


@router.post("/pair", summary="Pair a phone with a one-time code (no API key)")
async def pair(body: PairRequest, request: Request):
    from life_graph.services import devices

    client = request.client.host if request.client else "unknown"
    # Counted as a failure before the lookup, given back only on success: a
    # burst of concurrent guesses cannot all slip past the cap (review M1).
    if not devices.pairing_limiter.allowed(client):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Wait ten minutes and try again."
        )
    async with async_session() as session:
        try:
            device, token = await devices.redeem(session, body.code, body.name)
        except devices.PairingError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None
        await session.commit()
        devices.pairing_limiter.succeeded(client)
        return success_response(data={"device_id": str(device.id), "token": token})


@router.get("", summary="Paired phones")
async def list_devices():
    from life_graph.services import devices

    async with async_session() as session:
        rows = await devices.list_devices(session, get_current_tenant_id())
        return success_response(data=[devices.to_dict(d) for d in rows])


@router.delete("/{device_id}", summary="Revoke a phone: its token stops working at once")
async def revoke_device(device_id: str):
    from life_graph.services import devices

    try:
        pk = uuid.UUID(device_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "device not found") from None
    async with async_session() as session:
        if not await devices.revoke(session, get_current_tenant_id(), pk):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "device not found")
        await session.commit()
        return success_response(data={"revoked": True})
