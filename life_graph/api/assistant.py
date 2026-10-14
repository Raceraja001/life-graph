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


# ── Money ───────────────────────────────────────────────────────────────────


class CsvImport(BaseModel):
    csv: str = Field(max_length=5_000_000)
    categorise_with_model: bool = True


class AlertImport(BaseModel):
    """One or more bank alert texts (SMS or app notifications), one per item."""

    texts: list[str] = Field(min_length=1, max_length=200)


class TxnPatch(BaseModel):
    category: str
    remember: bool = True


class BudgetIn(BaseModel):
    monthly_limit: float = Field(gt=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)


@router.post("/money/import")
async def import_statement(body: CsvImport) -> dict[str, Any]:
    from life_graph.services import money

    tenant_id = get_current_tenant_id()
    txns, problems = money.parse_csv(body.csv)
    if not txns and problems:
        raise HTTPException(status_code=422, detail=problems[0])
    async with async_session() as session:
        counts = await money.store(
            session, tenant_id, txns, source="csv", use_model=body.categorise_with_model
        )
        await session.commit()
    return success_response({**counts, "problems": problems[:20]})


@router.post("/money/alerts")
async def import_alerts(body: AlertImport) -> dict[str, Any]:
    from life_graph.services import money

    tenant_id = get_current_tenant_id()
    parsed = [money.parse_alert(t) for t in body.texts]
    txns = [t for t in parsed if t is not None]
    async with async_session() as session:
        counts = await money.store(session, tenant_id, txns, source="alert")
        await session.commit()
    return success_response({**counts, "not_transactions": len(parsed) - len(txns)})


@router.get("/money/transactions")
async def list_transactions(
    month: str | None = None, category: str | None = None
) -> dict[str, Any]:
    from life_graph.services import money

    tenant_id = get_current_tenant_id()
    try:
        start, end, label = money.month_bounds(month, _today())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="month must be YYYY-MM") from exc
    async with async_session() as session:
        rows = await money.list_transactions(session, tenant_id, start, end, category)
    return success_response([money.txn_dict(t) for t in rows], meta={"month": label})


@router.patch("/money/transactions/{txn_id}")
async def recategorise(txn_id: str, body: TxnPatch) -> dict[str, Any]:
    from life_graph.services import money

    tenant_id = get_current_tenant_id()
    async with async_session() as session:
        try:
            txn = await money.recategorise(
                session, tenant_id, _uuid(txn_id), body.category, remember=body.remember
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if txn is None:
            raise HTTPException(status_code=404, detail="Transaction not found")
        await session.commit()
        await session.refresh(txn)
    return success_response(money.txn_dict(txn))


@router.get("/money/summary")
async def money_summary(month: str | None = None) -> dict[str, Any]:
    from life_graph.services import money

    tenant_id = get_current_tenant_id()
    try:
        async with async_session() as session:
            data = await money.summary(session, tenant_id, month, _today())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="month must be YYYY-MM") from exc
    return success_response(data)


@router.get("/money/categories")
async def money_categories() -> dict[str, Any]:
    from life_graph.services import money

    return success_response(list(money.CATEGORIES))


@router.get("/money/budgets")
async def list_budgets() -> dict[str, Any]:
    from sqlalchemy import select

    from life_graph.models.assistant import MoneyBudget

    tenant_id = get_current_tenant_id()
    async with async_session() as session:
        rows = (
            (await session.execute(select(MoneyBudget).where(MoneyBudget.tenant_id == tenant_id)))
            .scalars()
            .all()
        )
    return success_response(
        [
            {
                "category": b.category,
                "monthly_limit": float(b.monthly_limit),
                "currency": b.currency,
            }
            for b in rows
        ]
    )


@router.put("/money/budgets/{category}")
async def put_budget(category: str, body: BudgetIn) -> dict[str, Any]:
    from decimal import Decimal

    from life_graph.services import money

    tenant_id = get_current_tenant_id()
    async with async_session() as session:
        try:
            b = await money.set_budget(
                session,
                tenant_id,
                category,
                Decimal(str(body.monthly_limit)),
                body.currency.upper(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        await session.commit()
    return success_response(
        {"category": b.category, "monthly_limit": float(b.monthly_limit), "currency": b.currency}
    )


@router.delete("/money/budgets/{category}")
async def delete_budget(category: str) -> dict[str, Any]:
    from sqlalchemy import delete

    from life_graph.models.assistant import MoneyBudget

    tenant_id = get_current_tenant_id()
    async with async_session() as session:
        result = await session.execute(
            delete(MoneyBudget).where(
                MoneyBudget.tenant_id == tenant_id, MoneyBudget.category == category
            )
        )
        await session.commit()
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="No budget for that category")
    return success_response({"deleted": category})
