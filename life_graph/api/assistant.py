"""API for the assistant's non-development work (docs/specs/assistant-capabilities.md).

Documents, money, page monitors, study cards and invoices. Every route is
tenant-scoped through the request's tenant context; nothing here reaches
another tenant's rows.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from life_graph.api.responses import success_response
from life_graph.core.tenant import get_current_tenant_id
from life_graph.services import documents as documents_svc
from life_graph.storage.database import async_session

router = APIRouter(tags=["assistant"])


def _today() -> date:
    from zoneinfo import ZoneInfo

    from life_graph.config import settings

    try:
        return datetime.now(ZoneInfo(settings.user_timezone)).date()
    except Exception:  # noqa: BLE001
        return datetime.now(UTC).date()


def _uuid(raw: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc


# ── Documents ───────────────────────────────────────────────────────────────


class DocumentIn(BaseModel):
    """Either ``text`` to extract from, or the fields themselves (or both:
    given fields override what extraction found)."""

    text: str | None = Field(default=None, max_length=20_000)
    kind: str | None = None
    title: str | None = Field(default=None, max_length=200)
    issuer: str | None = Field(default=None, max_length=200)
    holder: str | None = Field(default=None, max_length=120)
    number: str | None = Field(default=None, max_length=64)
    issued_on: date | None = None
    expires_on: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


class DocumentPatch(BaseModel):
    kind: str | None = None
    title: str | None = Field(default=None, max_length=200)
    issuer: str | None = Field(default=None, max_length=200)
    holder: str | None = Field(default=None, max_length=120)
    number: str | None = Field(default=None, max_length=64)
    issued_on: date | None = None
    expires_on: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


@router.get("/documents")
async def list_documents() -> dict[str, Any]:
    tenant_id = get_current_tenant_id()
    today = _today()
    async with async_session() as session:
        docs = await documents_svc.list_all(session, tenant_id)
    return success_response([documents_svc.to_dict(d, today) for d in docs])


@router.get("/documents/expiring")
async def expiring_documents(days: int = 60) -> dict[str, Any]:
    tenant_id = get_current_tenant_id()
    today = _today()
    async with async_session() as session:
        docs = await documents_svc.expiring(
            session, tenant_id, today, within_days=max(1, min(days, 3650))
        )
    return success_response([documents_svc.to_dict(d, today) for d in docs])


@router.post("/documents", status_code=201)
async def add_document(body: DocumentIn) -> dict[str, Any]:
    tenant_id = get_current_tenant_id()
    given = body.model_dump(exclude={"text", "number"}, exclude_none=True)
    if body.number:
        given["number_last4"] = documents_svc.last4(body.number)
    if not body.text and not body.title:
        raise HTTPException(status_code=422, detail="Give the document's text, or at least a title")
    async with async_session() as session:
        if body.text:
            doc = await documents_svc.file_text(session, tenant_id, body.text, overrides=given)
        else:
            doc = await documents_svc.create(session, tenant_id, given)
        await session.commit()
        await session.refresh(doc)
    return success_response(documents_svc.to_dict(doc, _today()))


@router.patch("/documents/{doc_id}")
async def edit_document(doc_id: str, body: DocumentPatch) -> dict[str, Any]:
    tenant_id = get_current_tenant_id()
    async with async_session() as session:
        doc = await documents_svc.get(session, tenant_id, _uuid(doc_id))
        if doc is None:
            raise HTTPException(status_code=404, detail="Document not found")
        await documents_svc.update(session, doc, body.model_dump(exclude_unset=True))
        await session.commit()
        await session.refresh(doc)
    return success_response(documents_svc.to_dict(doc, _today()))


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str) -> dict[str, Any]:
    tenant_id = get_current_tenant_id()
    async with async_session() as session:
        doc = await documents_svc.get(session, tenant_id, _uuid(doc_id))
        if doc is None:
            raise HTTPException(status_code=404, detail="Document not found")
        await session.delete(doc)
        await session.commit()
    return success_response({"deleted": doc_id})
