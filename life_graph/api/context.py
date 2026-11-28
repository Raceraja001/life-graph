"""Read-only context snapshot (M8 Stage 1, services/memory/snapshot.py).

``GET /api/v1/context/snapshot?q=...&as_of=...`` returns what Life Graph holds
that bears on *q* for the request's tenant: references to memories, decisions
and open intentions with their origin, evidence, freshness and why each was
included, plus conflicts, exclusion counts and an explicit ``insufficient``
flag. For inspection and evaluation; nothing is written and no model is
called (the query embedding is local). Same authentication and tenant
handling as ``/search`` (middleware).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query

from life_graph.api.responses import Envelope, success_response
from life_graph.config import settings
from life_graph.services.memory.snapshot import assemble_context

router = APIRouter(prefix="/context", tags=["context"])


@router.get(
    "/snapshot",
    summary="Read-only context snapshot for a query (references and labels)",
    response_model=Envelope[dict[str, Any]],
)
async def context_snapshot(
    q: str = Query(..., min_length=1, max_length=2000, description="The question or topic"),
    as_of: datetime | None = Query(
        None, description="Ask about an earlier instant (valid time); default now"
    ),
) -> dict[str, Any]:
    """Assemble the snapshot for the current tenant (see services/memory/snapshot.py).

    Under settings.context_precision_mode ("" by default: the normal snapshot)
    it is built with that precision mode's fixed experiment set.
    """
    snap = await assemble_context(q, as_of=as_of, mode=settings.context_precision_mode)
    return success_response(data=snap.to_dict())
