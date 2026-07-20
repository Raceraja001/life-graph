"""Approvals service — the unified human-in-the-loop queue.

Lists pending items and resolves them, running the source subsystem's real
side-effect on approve. Today it reconciles ``self_improving`` optimization
runs awaiting review into the feed; other producers (merges, contradictions,
weekly review) write ``approvals`` rows directly as they are added.

See docs/specs/approvals-feed.md.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from life_graph.models.db import Approval, Memory
from life_graph.self_improving.models import OptimizationRun, PromptVersion


class ApprovalAlreadyResolvedError(Exception):
    """Raised when approve/reject is called on an already-resolved item."""


class ApprovalService:
    """Business logic for the unified approvals feed."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Read ──────────────────────────────────────────────────

    async def list_approvals(
        self, tenant_id: str, status: str = "pending", limit: int = 100
    ) -> list[dict[str, Any]]:
        """Reconcile producers, then return approvals (newest first)."""
        await self.reconcile_promotions(tenant_id)

        query = select(Approval).where(Approval.tenant_id == tenant_id)
        if status != "all":
            query = query.where(Approval.status == status)
        query = query.order_by(Approval.created_at.desc()).limit(limit)

        rows = (await self.session.execute(query)).scalars().all()
        return [self._serialize(r) for r in rows]

    @staticmethod
    def _serialize(a: Approval) -> dict[str, Any]:
        return {
            "id": str(a.id),
            "kind": a.kind,
            "title": a.title,
            "detail": a.detail,
            "status": a.status,
            "source": a.source,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }

    # ── Producer: self_improving promotions ───────────────────

    async def reconcile_promotions(self, tenant_id: str) -> None:
        """Upsert optimization runs in ``needs_review`` into the feed.

        Idempotent on ``(tenant_id, source, source_ref)`` — existing rows are
        skipped, so pre-existing runs surface exactly once.
        """
        existing = set(
            (
                await self.session.execute(
                    select(Approval.source_ref).where(
                        Approval.tenant_id == tenant_id,
                        Approval.source == "self_improving",
                    )
                )
            )
            .scalars()
            .all()
        )

        runs = (
            (
                await self.session.execute(
                    select(OptimizationRun).where(
                        OptimizationRun.tenant_id == tenant_id,
                        OptimizationRun.status == "needs_review",
                    )
                )
            )
            .scalars()
            .all()
        )

        added = False
        for run in runs:
            ref = str(run.id)
            if ref in existing:
                continue
            self.session.add(
                Approval(
                    tenant_id=tenant_id,
                    kind="promotion",
                    source="self_improving",
                    source_ref=ref,
                    title=f"Promote {run.task_type} prompt to active",
                    detail=self._promotion_detail(run),
                    payload={
                        "candidate_version_id": run.candidate_version_id,
                        "previous_version_id": run.previous_version_id,
                        "task_type": run.task_type,
                        "candidate_accuracy_pct": _num(run.candidate_accuracy_pct),
                        "previous_accuracy_pct": _num(run.previous_accuracy_pct),
                    },
                )
            )
            added = True

        if added:
            await self.session.flush()

    @staticmethod
    def _promotion_detail(run: OptimizationRun) -> str:
        cand = run.candidate_accuracy_pct
        prev = run.previous_accuracy_pct
        if cand is not None and prev is not None:
            return f"optimizer · {cand}% candidate vs {prev}% current"
        if cand is not None:
            return f"optimizer · {cand}% candidate"
        return "optimizer · candidate prompt awaiting review"

    # ── Resolve ───────────────────────────────────────────────

    async def resolve(
        self,
        tenant_id: str,
        approval_id: str,
        decision: str,
        note: str | None = None,
        resolved_by: str | None = None,
    ) -> dict[str, Any]:
        """Approve or reject an item; run its side-effect on approve.

        Raises:
            LookupError: no such approval for this tenant.
            ApprovalAlreadyResolved: item is not pending.
        """
        try:
            pk = uuid.UUID(str(approval_id))
        except (ValueError, TypeError):
            raise LookupError(approval_id) from None

        appr = await self.session.get(Approval, pk)
        if appr is None or appr.tenant_id != tenant_id:
            raise LookupError(approval_id)
        if appr.status != "pending":
            raise ApprovalAlreadyResolvedError(appr.status)

        approve = decision == "approve"
        appr.status = "approved" if approve else "rejected"
        appr.resolved_at = datetime.now(UTC)
        appr.resolved_by = resolved_by
        appr.resolution_note = note

        if appr.kind == "promotion":
            await self._apply_promotion(tenant_id, appr, approve, resolved_by)
        elif appr.kind == "merge":
            await self._apply_merge(tenant_id, appr, approve)

        await self.session.flush()
        return self._serialize(appr)

    async def _apply_promotion(
        self, tenant_id: str, appr: Approval, approve: bool, resolved_by: str | None
    ) -> None:
        """Activate the candidate prompt version (approve) and mark the run.

        Defensive: if the run or candidate is missing the approval still
        resolves — we never trap the user on a dangling reference.
        """
        ref = appr.source_ref
        if not ref:
            return
        try:
            run = await self.session.get(OptimizationRun, uuid.UUID(ref))
        except (ValueError, TypeError):
            run = None
        now = datetime.now(UTC)

        if not approve:
            if run is not None:
                run.review_decision = "reject"
                run.review_reason = appr.resolution_note
                run.reviewed_by = resolved_by
                run.reviewed_at = now
                run.status = "rejected"
            return

        candidate_id = (appr.payload or {}).get("candidate_version_id") or (
            run.candidate_version_id if run is not None else None
        )
        task_type = (appr.payload or {}).get("task_type") or (
            run.task_type if run is not None else None
        )

        if candidate_id and task_type:
            # One active version per (tenant, task_type): deactivate first.
            await self.session.execute(
                update(PromptVersion)
                .where(
                    PromptVersion.tenant_id == tenant_id,
                    PromptVersion.task_type == task_type,
                    PromptVersion.is_active.is_(True),
                )
                .values(is_active=False, deactivated_at=now)
            )
            try:
                candidate = await self.session.get(PromptVersion, uuid.UUID(str(candidate_id)))
            except (ValueError, TypeError):
                candidate = None
            if candidate is not None:
                candidate.is_active = True
                candidate.activated_at = now

        if run is not None:
            run.review_decision = "approve"
            run.review_reason = appr.resolution_note
            run.reviewed_by = resolved_by
            run.reviewed_at = now
            run.status = "deployed"

    async def _apply_merge(self, tenant_id: str, appr: Approval, approve: bool) -> None:
        """Merge the two memories (approve) or leave them (reject).

        Winner = higher importance (ties → newer); tags unioned, properties
        merged (winner wins conflicts), loser superseded → winner. Defensive:
        if either memory is missing or no longer active, resolve without acting.
        """
        if not approve:
            return  # reject → keep both; the resolved row prevents re-suggestion
        payload = appr.payload or {}
        a_id, b_id = payload.get("memory_id_a"), payload.get("memory_id_b")
        if not a_id or not b_id:
            return
        try:
            a = await self.session.get(Memory, uuid.UUID(str(a_id)))
            b = await self.session.get(Memory, uuid.UUID(str(b_id)))
        except (ValueError, TypeError):
            return
        if a is None or b is None:
            return
        if a.tenant_id != tenant_id or b.tenant_id != tenant_id:
            return
        if a.status != "active" or b.status != "active":
            return  # already merged/changed since the suggestion was made

        winner, loser = (
            (a, b)
            if (a.importance or 0.5, a.created_at) >= (b.importance or 0.5, b.created_at)
            else (b, a)
        )
        winner.importance = max(a.importance or 0.5, b.importance or 0.5)
        winner.tags = sorted(set((winner.tags or []) + (loser.tags or [])))
        winner.properties = {**(loser.properties or {}), **(winner.properties or {})}
        loser.status = "superseded"
        loser.superseded_by = winner.id
        winner.supersedes = loser.id


def _num(value: Any) -> str | None:
    """JSON-safe rendering of a Numeric/Decimal accuracy value."""
    return None if value is None else str(value)
