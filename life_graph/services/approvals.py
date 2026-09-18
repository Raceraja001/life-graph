"""Approvals service — the unified human-in-the-loop queue.

Lists pending items and resolves them, running the source subsystem's real
side-effect on approve. Today it reconciles ``self_improving`` optimization
runs awaiting review into the feed; other producers (merges, contradictions,
weekly review) write ``approvals`` rows directly as they are added.

See docs/specs/approvals-feed.md.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select, update

from life_graph.models.db import Approval, Memory
from life_graph.self_improving.models import OptimizationRun, PromptVersion

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# reconcile_promotions() used to run unconditionally on every list_approvals()
# call — 2 extra DB round trips on every GET /approvals for state that only
# actually changes once a day (the self_improving nightly cron is the only
# thing that sets OptimizationRun.status='needs_review'). A short per-tenant
# TTL skip is enough to eliminate nearly all of that redundant work; a new
# promotion still surfaces within one TTL window of the cron run finishing.
_RECONCILE_TTL_SECONDS = 60.0
_last_reconciled: dict[str, float] = {}


class ApprovalAlreadyResolvedError(Exception):
    """Raised when approve/reject is called on an already-resolved item."""


class ApprovalActionError(Exception):
    """The approve side-effect failed; the item stays pending. Message is user-safe."""


class ApprovalService:
    """Business logic for the unified approvals feed."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Read ──────────────────────────────────────────────────

    async def list_approvals(
        self, tenant_id: str, status: str = "pending", limit: int = 100
    ) -> list[dict[str, Any]]:
        """Reconcile producers (at most once per TTL window), then return
        approvals (newest first)."""
        now = time.monotonic()
        last = _last_reconciled.get(tenant_id)
        if last is None or now - last >= _RECONCILE_TTL_SECONDS:
            await self.reconcile_promotions(tenant_id)
            _last_reconciled[tenant_id] = now

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
            # Producers stash kind-specific extras here (e.g. the
            # AutonomousApprovalProducer's risk_level) — passed through so the
            # mobile feed can render a risk badge without a dedicated endpoint.
            "payload": a.payload or {},
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
        elif appr.kind == "archive":
            await self._apply_archive(tenant_id, appr, approve)
        elif appr.kind == "contradiction":
            await self._apply_contradiction(tenant_id, appr, approve)
        elif appr.kind == "autonomous_action":
            await self._apply_autonomous_action(tenant_id, appr, approve, resolved_by)
        elif appr.kind == "driver_pr":
            await self._apply_driver_pr(appr, approve)
        elif appr.kind == "driver_merge":
            await self._apply_driver_merge(appr, approve)

        await self.session.flush()
        return self._serialize(appr)

    async def _apply_driver_pr(self, appr: Approval, approve: bool) -> None:
        """Push a verified task branch and open its PR (approve). Reject: no-op.

        Unlike the sibling handlers, a failure here raises: the approval stays
        pending (the request's transaction is not committed) so the user can
        fix the cause — ``gh`` not logged in, base branch not pushed — and
        approve again. Push and PR creation are both idempotent, so a retry
        after a partial success finishes the job.
        """
        if not approve:
            return
        from life_graph.services.github_pr import PullRequestError, open_pull_request

        try:
            outcome = await open_pull_request(appr.payload or {})
        except PullRequestError as exc:
            raise ApprovalActionError(str(exc)) from exc
        # Reassign: in-place mutation of a JSONB dict is not change-tracked.
        appr.payload = {**(appr.payload or {}), "pr_url": outcome["pr_url"]}
        note = f"PR: {outcome['pr_url']}"
        appr.resolution_note = f"{appr.resolution_note}\n{note}" if appr.resolution_note else note
        payload = appr.payload or {}
        merge_appr = self.file_merge_approval(appr)
        await self.maybe_auto_merge(
            merge_appr,
            payload.get("driver", ""),
            payload.get("project_id"),
            bool(payload.get("auto_merge")),
        )

    async def maybe_auto_merge(
        self,
        merge_appr: Approval,
        driver_name: str,
        project_id: str | None,
        auto_merge: bool,
    ) -> None:
        """Auto-resolve a freshly filed ``driver_merge`` approval, if earned.

        A second, separate opt-in from ``auto_open_pr``: opening a PR is
        reversible, merging to the base branch is the step that actually
        matters, so a project must choose that explicitly rather than
        inheriting it from the PR-open setting. Called from both places a
        ``driver_merge`` approval gets filed: here (a human approved
        ``driver_pr`` normally) and :meth:`TaskDispatcher._auto_open_pr`
        (the PR itself was opened automatically too).

        Same trust bar as ``auto_open_pr`` (established record, merge rate
        >= ``AUTO_PR_MERGE_RATE``) — CI/required-checks are always enforced
        regardless, by :func:`github_pr.merge_pull_request` itself via
        ``--match-head-commit``, exactly as a manual merge is. Any failure
        (untrusted driver, CI not green, merge conflict, ...) leaves the
        approval pending, exactly as if auto-merge were off.
        """
        if not auto_merge:
            return
        from life_graph.drivers.dispatcher import AUTO_PR_MERGE_RATE
        from life_graph.services.dev_outcomes import track_record

        record = await track_record(self.session, merge_appr.tenant_id, driver_name, project_id)
        if not (record["established"] and record["merge_rate"] >= AUTO_PR_MERGE_RATE):
            logger.info(
                "Auto-merge skipped: %s has %d/%d merged on this project",
                driver_name,
                record["merged"],
                record["total"],
            )
            return
        try:
            await self._apply_driver_merge(merge_appr, True)
        except ApprovalActionError as exc:
            logger.warning("Auto-merge failed, left for approval: %s", exc)
            return
        merge_appr.status = "approved"
        merge_appr.resolved_at = datetime.now(UTC)
        merge_appr.resolved_by = "auto: trusted driver"
        note = (
            f"Merged automatically: {driver_name} has {record['merged']}/{record['total']} "
            f"merged on this project."
        )
        merge_appr.resolution_note = (
            f"{merge_appr.resolution_note}\n{note}" if merge_appr.resolution_note else note
        )
        logger.info("Auto-merged PR for driver %s", driver_name)

    def file_merge_approval(self, pr_approval: Approval) -> Approval:
        """Queue the separate decision to merge a PR that was just opened.

        Opening and merging are distinct approvals on purpose: the PR exists so
        the change can be read on GitHub before anything reaches the base.
        Keyed ``(source="driver_merge", source_ref=task_id)`` so it is filed
        once per task.
        """
        from life_graph.services.github_pr import merge_approval_fields

        fields = merge_approval_fields(pr_approval.payload or {})
        merge = Approval(
            tenant_id=pr_approval.tenant_id,
            kind="driver_merge",
            status="pending",
            source="driver_merge",
            source_ref=pr_approval.source_ref,
            **fields,
        )
        self.session.add(merge)
        return merge

    async def _apply_driver_merge(self, appr: Approval, approve: bool) -> None:
        """Squash-merge the task's PR (approve). Reject: leave the PR open.

        Raises like :meth:`_apply_driver_pr`, keeping the item pending, when the
        PR moved, conflicts, or its CI has not passed — a retry after CI
        finishes is the expected path, not an error to swallow.
        """
        if not approve:
            return
        from life_graph.services.github_pr import PullRequestError, merge_pull_request

        try:
            outcome = await merge_pull_request(appr.payload or {})
        except PullRequestError as exc:
            raise ApprovalActionError(str(exc)) from exc
        appr.payload = {**(appr.payload or {}), "merge_commit": outcome.get("merge_commit")}
        note = f"Merged as {str(outcome.get('merge_commit') or '?')[:8]}"
        if outcome.get("already"):
            note += " (was already merged)"
        elif not outcome.get("checks"):
            note += " — no CI checks ran on this PR; sandbox verification was the gate"
        appr.resolution_note = f"{appr.resolution_note}\n{note}" if appr.resolution_note else note

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

    async def _apply_archive(self, tenant_id: str, appr: Approval, approve: bool) -> None:
        """Archive a decayed memory (approve) or leave it alone (reject).

        Decay no longer archives anything by itself — it proposes, and a
        memory stays active and fully recallable until someone approves the
        proposal here. Rejecting is a genuine no-op: the memory was never
        touched, and the resolved approval keeps the sweep from re-queueing
        it, since proposals are idempotent on source_ref.

        Archiving is still reversible — PostgresMemoryStore.unarchive() sets
        status back to active — so this is a demotion out of recall, not a
        deletion. Nothing in the decay path ever deletes a memory.
        """
        if not approve:
            return

        memory_id = (appr.payload or {}).get("memory_id")
        if not memory_id:
            return
        try:
            memory = await self.session.get(Memory, uuid.UUID(str(memory_id)))
        except (ValueError, TypeError):
            return
        if memory is None or memory.tenant_id != tenant_id:
            return
        # Recalled since the proposal was raised — it has earned its place.
        if memory.status != "active":
            return
        memory.status = "archived"

    async def _apply_contradiction(self, tenant_id: str, appr: Approval, approve: bool) -> None:
        """Confirm an auto-supersede (approve, no-op) or UNDO it (reject).

        Undo restores the superseded memory to active and clears the chain —
        but only if it's still in the exact state we recorded (defensive against
        later edits). Approving is a no-op: the supersede already happened.
        """
        if approve:
            return
        payload = appr.payload or {}
        old_id, new_id = payload.get("memory_id_old"), payload.get("memory_id_new")
        if not old_id:
            return
        try:
            old = await self.session.get(Memory, uuid.UUID(str(old_id)))
            new = await self.session.get(Memory, uuid.UUID(str(new_id))) if new_id else None
        except (ValueError, TypeError):
            return
        if old is None or old.tenant_id != tenant_id:
            return
        if old.status == "superseded" and (new is None or old.superseded_by == new.id):
            old.status = "active"
            old.superseded_by = None
            if new is not None and new.supersedes == old.id:
                new.supersedes = None

    async def _apply_autonomous_action(
        self, tenant_id: str, appr: Approval, approve: bool, resolved_by: str | None
    ) -> None:
        """Resolve the linked autonomy approval-queue entry; execute on approve.

        ``appr.payload`` carries the autonomy-side identifiers written by the
        ``AutonomousApprovalProducer`` (``approval_id`` — the ``approval_queue``
        row; ``auto_action_id`` — the queued ``AutoAction``). Imports are lazy
        to avoid an import cycle between ``life_graph.api.dependencies`` (which
        wires this service) and the autonomy pipeline it depends on here.
        Defensive: a malformed payload (missing autonomy approval id) resolves
        the generic approval without acting, matching the sibling handlers.

        Idempotent retry-tap tolerance: the autonomy-side ``resolve()`` and
        ``execute_pending()`` each commit in their own session, independent of
        this method's caller flushing ``appr.status``. If ``execute_pending``
        raised a genuine infra error on a first attempt, the autonomy side is
        already committed "approved" while the generic feed row never
        resolved. A user retry re-enters this method: the autonomy
        ``resolve()`` then raises "already resolved" (see
        ``life_graph.autonomy.approvals.service.ApprovalService.resolve``,
        which raises ``ValueError(f"Approval already resolved: {status}")``)
        — swallow exactly that case (not any other ``ValueError``, e.g. "not
        found") and continue to ``execute_pending`` so the retry can still
        run the action. Symmetrically, if the action already executed on a
        prior attempt, ``execute_pending`` raises
        ``ValueError(f"Cannot execute action in status: {status}")`` (see
        ``life_graph.autonomy.pipeline.service.AutoFixService.execute_pending``)
        — also swallowed, so the retry resolves the feed row cleanly instead
        of surfacing a stale error.

        Phase B2 Task 4: ``execute_pending`` on a ``kind="agent_task"``
        action can hit a ``dispatch_task`` failure (e.g. a WIP-limit
        ``DispatchError``). That is caught inside ``AutoFixService._run_action``
        and turned into an ordinary ``status="failure"`` ``AutoActionResponse``
        instead of raising — so it never reaches either ``except`` clause
        below. No broadening of the narrow ``ValueError`` swallow was needed
        here: ``appr.status`` is already set to "approved"/"rejected" by the
        caller (``resolve()``, above) before this method runs, so the generic
        feed row resolves on a normal return regardless of whether the
        underlying execution succeeded or failed — a failed-but-completed
        agent_task is still a *resolved* approval.
        """
        from life_graph.api.dependencies import get_approval_service, get_autofix_service

        payload = appr.payload or {}
        autonomy_approval_id = payload.get("approval_id")
        auto_action_id = payload.get("auto_action_id")
        if not autonomy_approval_id:
            return

        try:
            await get_approval_service().resolve(
                tenant_id=tenant_id,
                approval_id=autonomy_approval_id,
                decision="approve" if approve else "reject",
                note=appr.resolution_note,
                resolved_by=resolved_by,
            )
        except ValueError as exc:
            if "already resolved" not in str(exc):
                raise
            logger.info(
                "Autonomous action approval %s: autonomy side already resolved "
                "(%s) — retry-tap, continuing",
                autonomy_approval_id,
                exc,
            )

        if approve and auto_action_id:
            try:
                await get_autofix_service().execute_pending(tenant_id, auto_action_id)
            except ValueError as exc:
                if "Cannot execute action in status" not in str(exc):
                    raise
                logger.info(
                    "Autonomous action %s: already executed — retry-tap, "
                    "resolving feed row without re-running (%s)",
                    auto_action_id,
                    exc,
                )


def _num(value: Any) -> str | None:
    """JSON-safe rendering of a Numeric/Decimal accuracy value."""
    return None if value is None else str(value)
