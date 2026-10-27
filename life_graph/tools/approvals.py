"""approvals_waiting: what is waiting on the owner's decision, for Jarvis to show.

Read-only (web-chat-wave1 F4). Jarvis lists the pending items of the approvals
queue (pull requests its agents made, models to adopt, contradictions it
resolved); the chat shows each as a card whose buttons the owner presses
(services/jarvis_cards.py). Jarvis itself can never approve or reject: no
tool does that, and the buttons call the same endpoints as the inbox.
"""

from __future__ import annotations

import json
import logging

from life_graph.tools.registry import tool

logger = logging.getLogger(__name__)

MAX_ITEMS = 10


@tool(
    name="approvals_waiting",
    description=(
        "What is waiting on the user's decision in Life Graph (read-only): pull requests"
        " its agents made, models to adopt, contradictions it resolved. Use it when they"
        " ask what needs them, what to approve, or about a PR an agent opened. They decide"
        " with the buttons shown under your reply; you cannot approve anything yourself."
    ),
    parameters_schema={"type": "object", "properties": {}},
)
async def approvals_waiting() -> str:
    """The tenant's pending approvals, newest first, at most MAX_ITEMS. Never raises."""
    from sqlalchemy import func, select

    from life_graph.core.task_context import get_current_task_context
    from life_graph.core.tenant import get_current_tenant_id, has_tenant_context
    from life_graph.models.db import Approval
    from life_graph.storage.database import async_session

    ctx = get_current_task_context()
    tenant_id = (
        get_current_tenant_id() if has_tenant_context() else (ctx.tenant_id if ctx else None)
    )
    if not tenant_id:
        return json.dumps({"error": "approvals_waiting has no tenant context."})
    try:
        async with async_session() as session:
            where = (Approval.tenant_id == tenant_id, Approval.status == "pending")
            total = await session.scalar(select(func.count()).select_from(Approval).where(*where))
            rows = (
                (
                    await session.execute(
                        select(Approval)
                        .where(*where)
                        .order_by(Approval.priority.desc(), Approval.created_at.desc())
                        .limit(MAX_ITEMS)
                    )
                )
                .scalars()
                .all()
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("approvals_waiting failed: %s", exc)
        return json.dumps({"error": f"Could not read the approvals: {exc}"})
    items = []
    for a in rows:
        p = a.payload or {}
        change = p.get("change") or {}
        files = change.get("files")
        items.append(
            {
                "id": str(a.id),
                "kind": a.kind,
                "title": a.title,
                "summary": (a.detail or p.get("summary") or "")[:300],
                "verified": p.get("verified"),
                "files": len(files) if isinstance(files, list) else files,
                "pr_url": p.get("pr_url"),
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
        )
    return json.dumps({"total": int(total or 0), "items": items}, ensure_ascii=False)
