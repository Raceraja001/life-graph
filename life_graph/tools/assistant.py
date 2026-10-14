"""Agent tools for the assistant's non-development work.

docs/specs/assistant-capabilities.md. Each tool reads the caller's tenant
from the request context and shapes its output for the audience
(connectors/locality.py): a local model sees everything, a cloud model sees
what the user would put on a postcard (kinds, dates, percentages), never
amounts, numbers or names of counterparties.
"""

from __future__ import annotations

import json
from typing import Any

from life_graph.connectors.locality import LOCAL, current_audience
from life_graph.tools.registry import tool


def _tenant() -> str | None:
    from life_graph.core.tenant import get_current_tenant_id, has_tenant_context

    return get_current_tenant_id() if has_tenant_context() else None


def _today():
    from datetime import datetime

    from life_graph.connectors.tools import user_tz

    return datetime.now(user_tz()).date()


def _out(payload: dict[str, Any]) -> str:
    payload["audience"] = current_audience()
    return json.dumps(payload, default=str)


@tool(
    name="documents_expiring",
    description=(
        "The user's documents (passport, licence, insurance, warranties…) that expire"
        " within the given number of days, soonest first, with days left."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "days": {"type": "integer", "minimum": 1, "maximum": 3650, "default": 90},
        },
    },
)
async def documents_expiring(days: int = 90) -> str:
    from life_graph.services import documents
    from life_graph.storage.database import async_session

    tenant = _tenant()
    if not tenant:
        return json.dumps({"error": "no tenant context"})
    today = _today()
    async with async_session() as session:
        rows = await documents.expiring(
            session, tenant, today, within_days=max(1, min(int(days), 3650))
        )
    local = current_audience() == LOCAL
    items = []
    for doc in rows:
        d = documents.to_dict(doc, today)
        if not local:
            d = {k: d[k] for k in ("kind", "title", "expires_on", "days_left")}
        items.append(d)
    return _out({"today": today.isoformat(), "documents": items})


@tool(
    name="spending_summary",
    description=(
        "The user's spending per category for a month (default this month) against"
        " their budgets. Cloud models see percentages only."
    ),
    parameters_schema={
        "type": "object",
        "properties": {"month": {"type": "string", "description": "YYYY-MM; default this month"}},
    },
)
async def spending_summary(month: str | None = None) -> str:
    from life_graph.services import money
    from life_graph.storage.database import async_session

    tenant = _tenant()
    if not tenant:
        return json.dumps({"error": "no tenant context"})
    try:
        async with async_session() as session:
            data = await money.summary(session, tenant, month, _today())
    except ValueError:
        return json.dumps({"error": "month must be YYYY-MM"})
    return _out(data if current_audience() == LOCAL else money.cloud_view(data))


@tool(
    name="watch_page",
    description=(
        "Set up a monitor on a web page: tell the user when it changes (mode change),"
        " when the price drops under a threshold (mode price_below), or when some text"
        " appears (mode contains, with pattern). Only when the user asks to watch something."
        " selector: optional simple CSS selector (e.g. span.price, [itemprop=price]) or"
        " regex:<pattern>."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "name": {"type": "string", "description": "Short name, e.g. 'Pixel 9 price'"},
            "mode": {"type": "string", "enum": ["change", "price_below", "contains"]},
            "threshold": {"type": "number", "description": "For price_below"},
            "pattern": {"type": "string", "description": "For contains"},
            "selector": {"type": "string"},
            "interval_minutes": {"type": "integer", "minimum": 30, "default": 180},
        },
        "required": ["url", "mode"],
    },
)
async def watch_page(
    url: str,
    mode: str = "change",
    name: str | None = None,
    threshold: float | None = None,
    pattern: str | None = None,
    selector: str | None = None,
    interval_minutes: int = 180,
) -> str:
    from life_graph.services import page_monitors
    from life_graph.services.safe_fetch import FetchBlockedError
    from life_graph.storage.database import async_session

    tenant = _tenant()
    if not tenant:
        return json.dumps({"error": "no tenant context"})
    try:
        async with async_session() as session:
            monitor = await page_monitors.create(
                session,
                tenant,
                url=url,
                name=name,
                mode=mode,
                threshold=threshold,
                pattern=pattern,
                selector=selector,
                interval_minutes=interval_minutes,
            )
            event = await page_monitors.check(monitor, page_monitors.now_utc())
            await session.commit()
            await session.refresh(monitor)
    except (ValueError, FetchBlockedError) as exc:
        return json.dumps({"error": str(exc)})
    return _out(
        {
            "created": page_monitors.to_dict(monitor),
            "first_check": event or "baseline recorded",
        }
    )


@tool(
    name="list_page_monitors",
    description="The pages the user is watching, with the last value seen.",
    parameters_schema={"type": "object", "properties": {}},
)
async def list_page_monitors() -> str:
    from sqlalchemy import select

    from life_graph.models.assistant import PageMonitor
    from life_graph.services import page_monitors
    from life_graph.storage.database import async_session

    tenant = _tenant()
    if not tenant:
        return json.dumps({"error": "no tenant context"})
    async with async_session() as session:
        rows = (
            (await session.execute(select(PageMonitor).where(PageMonitor.tenant_id == tenant)))
            .scalars()
            .all()
        )
    return _out({"monitors": [page_monitors.to_dict(m) for m in rows]})
