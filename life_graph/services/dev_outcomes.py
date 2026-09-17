"""Learn from what happens to agent work after verification.

Verification says a change is *acceptable*; the user's decision says whether it
was *wanted*. Until now that second signal was dropped: nothing listened to
``driver_pr`` / ``driver_merge`` approvals, and a PR merged or closed directly
on GitHub was invisible. This module records the outcome once per task and
feeds it back:

* **Trust** — :class:`TrustScoreService` success on merge, failure on a
  rejected or closed PR, keyed ``(agent_id=driver, action_type="dev_task",
  project_id)``.
* **Corrections** — a rejected or closed PR becomes a ``reject`` correction
  carrying the user's note, the raw material for preference learning.
* **Review comments** — the user's own comments on the PR (general, review
  and inline code comments) enter the capture spine as pending memories.
  Only the authenticated GitHub user's comments are taken: the repository
  may be public, and anyone else's text would be an injection path into
  memory.

The outcome is stored on the ``driver_pr`` approval's payload (every PR task
has one, with or without a dev-task row), which makes recording idempotent
across the approval subscriber and the GitHub sync job. Rejecting a *merge*
is deliberately not an outcome — the user may simply prefer to merge by hand —
so the sync job settles it from the PR's real state.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from life_graph.config import settings
from life_graph.core.events import Event, EventBus, EventType, event_bus
from life_graph.models.db import AgentTask, Approval

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

ACTION_TYPE = "dev_task"
REVIEW_SURFACE = "github_pr_review"
FINAL = ("merged", "pr_rejected", "closed")
_PR_URL_RE = re.compile(r"^https://github\.com/([\w.-]+)/([\w.-]+)/pull/(\d+)$")


def _project_label(payload: dict[str, Any]) -> str:
    return os.path.basename(str(payload.get("repo_path") or "").rstrip("/")) or "unknown"


async def record_outcome(
    session: AsyncSession,
    pr_approval: Approval,
    outcome: str,
    *,
    source: str,
    note: str | None = None,
) -> bool:
    """Record a task's final outcome once. Returns False if already recorded."""
    from life_graph.autonomy.trust.service import TrustScoreService
    from life_graph.services.capture import CaptureService

    if outcome not in FINAL:
        raise ValueError(f"not a final outcome: {outcome}")
    payload = dict(pr_approval.payload or {})
    if payload.get("outcome") in FINAL:
        return False

    tenant_id = pr_approval.tenant_id
    driver = payload.get("driver") or "unknown"
    project_id = payload.get("project_id")
    trust = TrustScoreService(session)
    if outcome == "merged":
        await trust.record_success(tenant_id, driver, ACTION_TYPE, project_id)
    else:
        await trust.record_failure(tenant_id, driver, ACTION_TYPE, project_id)
        await CaptureService(session).record_correction(
            tenant_id,
            kind="reject",
            original=payload.get("summary") or payload.get("instruction"),
            diff_summary=note
            or (
                "PR closed on GitHub without merging"
                if outcome == "closed"
                else "User declined to open a PR for this change"
            ),
            context={
                "task_id": payload.get("task_id"),
                "instruction": payload.get("instruction"),
                "branch": payload.get("branch"),
                "pr_url": payload.get("pr_url"),
                "driver": driver,
                "outcome": outcome,
            },
            domain_tags=["code", ACTION_TYPE, f"project:{_project_label(payload)}"],
        )

    now = datetime.now(UTC).isoformat()
    pr_approval.payload = {
        **payload,
        "outcome": outcome,
        "outcome_at": now,
        "outcome_source": source,
    }

    task_id = payload.get("task_id")
    try:
        task = await session.get(AgentTask, uuid.UUID(str(task_id))) if task_id else None
    except ValueError:
        task = None
    if task is not None:
        task.properties = {**(task.properties or {}), "outcome": outcome}

    logger.info("Dev task %s outcome: %s (%s, driver=%s)", task_id, outcome, source, driver)
    return True


async def _pr_approval_for(
    session: AsyncSession, tenant_id: str, task_ref: str | None
) -> Approval | None:
    if not task_ref:
        return None
    return (
        await session.execute(
            select(Approval).where(
                Approval.tenant_id == tenant_id,
                Approval.kind == "driver_pr",
                Approval.source_ref == task_ref,
            )
        )
    ).scalar_one_or_none()


class DevOutcomeRecorder:
    """Records outcomes when the user resolves PR / merge approvals."""

    def __init__(self, bus: EventBus | None = None) -> None:
        self._bus = bus or event_bus
        self._subscribed = False

    def subscribe(self) -> None:
        if self._subscribed:
            return
        self._bus.subscribe(EventType.APPROVAL_RESOLVED, self._on_resolved)
        self._subscribed = True

    def unsubscribe(self) -> None:
        if not self._subscribed:
            return
        self._bus.unsubscribe(EventType.APPROVAL_RESOLVED, self._on_resolved)
        self._subscribed = False

    async def _on_resolved(self, event: Event) -> None:
        data = event.payload or {}
        if data.get("kind") not in ("driver_pr", "driver_merge"):
            return
        from life_graph.storage.database import async_session

        try:
            async with async_session() as session:
                await self.handle(session, str(data["id"]))
                await session.commit()
        except Exception:
            logger.warning(
                "Could not record dev task outcome for %s", data.get("id"), exc_info=True
            )

    @staticmethod
    async def handle(session: AsyncSession, approval_id: str) -> str | None:
        appr = await session.get(Approval, uuid.UUID(approval_id))
        if appr is None:
            return None
        if appr.kind == "driver_pr" and appr.status == "rejected":
            await record_outcome(
                session, appr, "pr_rejected", source="approval", note=appr.resolution_note
            )
            return "pr_rejected"
        if appr.kind == "driver_merge" and appr.status == "approved":
            pr = await _pr_approval_for(session, appr.tenant_id, appr.source_ref)
            if pr is not None:
                await record_outcome(
                    session, pr, "merged", source="approval", note=appr.resolution_note
                )
                return "merged"
        return None


dev_outcome_recorder = DevOutcomeRecorder()


# ── GitHub sync (worker cron) ────────────────────────────────


async def _gh(*args: str) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        settings.driver_gh_bin,
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "GH_PROMPT_DISABLED": "1"},
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=60)
    except TimeoutError:
        proc.kill()
        await proc.communicate()
        return -1, "timeout"
    return proc.returncode or 0, (out or err).decode(errors="replace")


def _user_comments(pr: dict, inline: list, viewer: str) -> list[dict]:
    """The authenticated user's non-empty comments, reviews and inline notes."""
    found: list[dict] = []
    for c in pr.get("comments") or []:
        found.append(
            {
                "id": f"c:{c.get('id')}",
                "author": (c.get("author") or {}).get("login"),
                "body": c.get("body"),
                "where": None,
            }
        )
    for r in pr.get("reviews") or []:
        found.append(
            {
                "id": f"r:{r.get('id')}",
                "author": (r.get("author") or {}).get("login"),
                "body": r.get("body"),
                "where": None,
            }
        )
    for c in inline or []:
        where = f"{c.get('path')}:{c.get('line') or c.get('original_line') or '?'}"
        found.append(
            {
                "id": f"i:{c.get('id')}",
                "author": (c.get("user") or {}).get("login"),
                "body": c.get("body"),
                "where": where,
            }
        )
    return [
        f
        for f in found
        if f["author"] and f["author"].lower() == viewer.lower() and (f["body"] or "").strip()
    ]


async def sync_pr(session: AsyncSession, pr_approval: Approval, viewer: str) -> dict[str, Any]:
    """Reconcile one PR task with GitHub: final state + new review comments."""
    from life_graph.services.capture import CaptureService

    payload = pr_approval.payload or {}
    url = payload.get("pr_url") or ""
    m = _PR_URL_RE.match(url)
    if not m:
        return {"skipped": "no pr url"}
    owner, repo, number = m.groups()

    code, out = await _gh("pr", "view", url, "--json", "state,mergeCommit,comments,reviews,title")
    if code != 0:
        return {"error": out[-300:]}
    pr = json.loads(out)
    code, out = await _gh("api", f"repos/{owner}/{repo}/pulls/{number}/comments", "--paginate")
    inline = json.loads(out) if code == 0 and out.strip().startswith("[") else []

    report: dict[str, Any] = {"pr": url, "state": pr.get("state")}

    seen = set(payload.get("seen_review_ids") or [])
    new = [c for c in _user_comments(pr, inline, viewer) if c["id"] not in seen]
    capture = CaptureService(session)
    for c in new:
        where = f" on {c['where']}" if c["where"] else ""
        await capture.ingest(
            pr_approval.tenant_id,
            surface=REVIEW_SURFACE,
            content=(
                f"My code review feedback{where} on an agent-written change in "
                f"{_project_label(payload)} (PR {url}, task: "
                f"{(payload.get('instruction') or '').strip().splitlines()[0][:120] if payload.get('instruction') else '?'}):\n"
                f"{c['body'].strip()}"
            ),
            properties={"pr_url": url, "task_id": payload.get("task_id"), "comment_id": c["id"]},
        )
    if new:
        pr_approval.payload = {**payload, "seen_review_ids": sorted(seen | {c["id"] for c in new})}
        payload = pr_approval.payload
    report["new_comments"] = len(new)

    state = pr.get("state")
    if state in ("MERGED", "CLOSED") and payload.get("outcome") not in FINAL:
        outcome = "merged" if state == "MERGED" else "closed"
        await record_outcome(session, pr_approval, outcome, source="github")
        merge = (
            await session.execute(
                select(Approval).where(
                    Approval.tenant_id == pr_approval.tenant_id,
                    Approval.kind == "driver_merge",
                    Approval.source_ref == pr_approval.source_ref,
                    Approval.status == "pending",
                )
            )
        ).scalar_one_or_none()
        if merge is not None:
            # The decision was made on GitHub; a pending "Merge PR?" is moot.
            merge.status = "approved" if outcome == "merged" else "rejected"
            merge.resolved_at = datetime.now(UTC)
            merge.resolved_by = "github"
            merge.resolution_note = (
                "Merged directly on GitHub"
                if outcome == "merged"
                else "PR closed on GitHub without merging"
            )
            if outcome == "merged":
                merge.payload = {
                    **(merge.payload or {}),
                    "merge_commit": (pr.get("mergeCommit") or {}).get("oid"),
                }
        report["outcome"] = outcome
    return report


async def sync_all(session_factory) -> dict[str, Any]:
    """Sync every opened, not-yet-settled task PR across tenants."""
    code, viewer = await _gh("api", "user", "-q", ".login")
    viewer = viewer.strip()
    if code != 0 or not viewer:
        logger.info("dev PR sync skipped: gh is not logged in")
        return {"skipped": "gh not logged in"}

    async with session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(Approval.id).where(
                        Approval.kind == "driver_pr",
                        Approval.status == "approved",
                        Approval.payload["pr_url"].astext.isnot(None),
                    )
                )
            )
            .scalars()
            .all()
        )

    reports = []
    for approval_id in rows:
        async with session_factory() as session:
            appr = await session.get(Approval, approval_id)
            # Keep syncing merged/closed PRs for late review comments, but
            # stop once a settled PR is a week old.
            settled_at = (appr.payload or {}).get("outcome_at")
            if settled_at and (datetime.now(UTC) - datetime.fromisoformat(settled_at)).days >= 7:
                continue
            try:
                reports.append(await sync_pr(session, appr, viewer))
                await session.commit()
            except Exception as exc:
                await session.rollback()
                logger.warning("dev PR sync failed for approval %s", approval_id, exc_info=True)
                reports.append({"approval": str(approval_id), "error": str(exc)[:200]})
    return {"synced": len(reports), "reports": reports}
