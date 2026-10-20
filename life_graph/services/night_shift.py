"""Job 2 — the night shift report (docs/specs/night-shift-report.md).

What the coding engines did since the last report: merged (with the PR),
waiting for the owner and **why**, failed and **why**, and how much is still
queued. Plain code over dev tasks and approvals — the same stages the
dashboard shows, the reasons the quality gate actually gave
(``change_policy.auto_gate``) and the failure cause the insights page uses
(``agent_insights.cause_of``). No model call.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

WAITING = ("awaiting_pr", "awaiting_merge", "needs_review", "landed")
_MAX_LINES = 8
_TEST_TITLE = re.compile(r"for `([\w.]+)` in ([\w/.]+)")


def short_title(title: str | None) -> str:
    """A readable line for a task: 'tests for merchant_from (services/money.py)'
    rather than the whole nightly instruction."""
    text = (title or "").strip()
    m = _TEST_TITLE.search(text)
    if text.lower().startswith("write unit tests") and m:
        return f"tests for {m.group(1)} ({m.group(2).removeprefix('life_graph/')})"
    return text if len(text) <= 80 else text[:77] + "…"


def _settled_at(task: dict) -> datetime | None:
    stamps = [task.get("completed_at")] + [a.get("resolved_at") for a in task.get("approvals", [])]
    parsed = [datetime.fromisoformat(s) for s in stamps if s]
    return max(parsed) if parsed else None


async def _waiting_reason(session: AsyncSession, tenant_id: str, task: dict) -> str:
    """Why this task is waiting for the owner, in the gate's own words."""
    from life_graph.models.db import Approval
    from life_graph.services.change_policy import auto_gate

    if task["stage"] == "needs_review":
        return "its checks failed twice — needs your review"
    pending = [a for a in task.get("approvals", []) if a["status"] == "pending"]
    if not pending:
        return "landed without a PR approval"
    appr = await session.get(Approval, uuid.UUID(pending[-1]["id"]))
    payload = (appr.payload or {}) if appr else {}
    if payload.get("verified") is False:
        return "unverified: some checks could not run"
    if not payload.get("auto_merge") and pending[-1]["kind"] == "driver_merge":
        return "auto-merge is off for this project"
    allowed, why, _ = await auto_gate(session, tenant_id, payload)
    if allowed:
        return "waiting for CI or a mergeable PR"
    return why


async def report(
    session: AsyncSession, tenant_id: str, since: datetime | None = None
) -> dict[str, Any]:
    """The night shift since *since* (default: the last 24 hours)."""
    from life_graph.models.db import AgentTask
    from life_graph.services.agent_insights import cause_of
    from life_graph.services.dev_tasks import list_dev_tasks

    since = since or datetime.now(UTC) - timedelta(hours=24)
    tasks = await list_dev_tasks(session, tenant_id, limit=300)
    merged, waiting, failed = [], [], []
    queued = 0
    for t in tasks:
        settled = _settled_at(t)
        item = {
            "id": t["id"],
            "title": short_title(t.get("title")),
            "stage": t["stage"],
            "pr_url": t.get("pr_url"),
        }
        if t["status"] == "queued":
            queued += 1
        elif t["stage"] == "merged" and settled and settled >= since:
            merged.append(item)
        elif t["stage"] in WAITING:
            waiting.append({**item, "reason": await _waiting_reason(session, tenant_id, t)})
        elif t["status"] == "failed" and settled and settled >= since:
            row = await session.get(AgentTask, uuid.UUID(t["id"]))
            cause = await cause_of(session, tenant_id, row) if row else {}
            reason = cause.get("label") or t.get("error") or "failed"
            if (row.properties or {}).get("escalated_to") if row else False:
                reason += "; handed to OpenCode"
            failed.append({**item, "reason": reason})
    return {
        "since": since.isoformat(),
        "merged": merged,
        "waiting": waiting,
        "failed": failed,
        "queued": queued,
    }


def lines(rep: dict[str, Any]) -> list[str]:
    """The brief section's lines; [] when nothing settled and nothing waits."""
    merged, waiting, failed, queued = rep["merged"], rep["waiting"], rep["failed"], rep["queued"]
    if not (merged or waiting or failed or queued):
        return []
    head = (
        f"{len(merged)} merged, {len(waiting)} waiting for you, {len(failed)} failed, "
        f"{queued} queued"
    )
    out = [head]
    for t in merged[:_MAX_LINES]:
        out.append(f"merged: {t['title']}" + (f" — {t['pr_url']}" if t["pr_url"] else ""))
    for t in waiting[:_MAX_LINES]:
        out.append(
            f"waiting: {t['title']} — {t['reason']}" + (f" ({t['pr_url']})" if t["pr_url"] else "")
        )
    for t in failed[:_MAX_LINES]:
        out.append(f"failed: {t['title']} — {t['reason']}")
    hidden = sum(max(len(x) - _MAX_LINES, 0) for x in (merged, waiting, failed))
    if hidden:
        out.append(f"(and {hidden} more on the Dev tasks page)")
    return out
