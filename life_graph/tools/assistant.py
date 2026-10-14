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
