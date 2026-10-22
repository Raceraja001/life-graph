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

from life_graph.core.events import EventType, event_bus
from life_graph.models.db import Approval, Memory, Project
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
        elif appr.kind == "driver_deploy":
            await self._apply_driver_deploy(appr, approve)
        elif appr.kind == "driver_plan":
            await self._apply_driver_plan(tenant_id, appr, approve)
        elif appr.kind == "model_adoption":
            # A free model that passed evaluation (services/llm_offers.py):
            # approving adds it to the cloud model list at once.
            from life_graph.services.llm_offers import apply_adoption

            await apply_adoption(self.session, appr, approve)

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
        from life_graph.services.local_merge import merge_locally, pr_mode

        if await pr_mode(self.session, (appr.payload or {}).get("project_id")) == "local":
            # No remote to open a PR on: this approval is the merge, into the
            # local base branch (services/local_merge.py). One decision, made
            # by the user — local mode never merges on its own.
            try:
                merged = await merge_locally(appr.payload or {})
            except PullRequestError as exc:
                raise ApprovalActionError(str(exc)) from exc
            appr.payload = {
                **(appr.payload or {}),
                "merge_commit": merged["merge_commit"],
                "merged_locally": True,
            }
            note = f"Merged locally into {merged['base_branch']} as {merged['merge_commit'][:8]}"
            if merged.get("existing"):
                note += " (was already merged)"
            appr.resolution_note = (
                f"{appr.resolution_note}\n{note}" if appr.resolution_note else note
            )
            return

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
        # Only notify if it's actually still waiting on someone -- earned
        # auto_merge just resolved this above, and "approval needed" for
        # something already approved is a false alarm.
        if merge_appr.status == "pending":
            await event_bus.emit(
                EventType.APPROVAL_FILED,
                {
                    "tenant_id": merge_appr.tenant_id,
                    "kind": "driver_merge",
                    "title": merge_appr.title,
                    "detail": merge_appr.detail,
                },
                source="approvals",
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
        if (merge_appr.payload or {}).get("verified") is False:
            logger.info("Auto-merge skipped: branch was landed off an unverified diff")
            return
        from life_graph.services.change_policy import auto_gate

        # Trust per kind of change, protected paths and size: change_policy.
        gate_payload = {
            "driver": driver_name,
            "project_id": project_id,
            **(merge_appr.payload or {}),
        }
        allowed, why, _record = await auto_gate(self.session, merge_appr.tenant_id, gate_payload)
        if not allowed:
            logger.info("Auto-merge skipped for %s: %s", driver_name, why)
            return
        try:
            await self._apply_driver_merge(merge_appr, True)
        except ApprovalActionError as exc:
            logger.warning("Auto-merge failed, left for approval: %s", exc)
            return
        merge_appr.status = "approved"
        merge_appr.resolved_at = datetime.now(UTC)
        merge_appr.resolved_by = "auto: trusted driver"
        note = f"Merged automatically: {why} on this project."
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
        await self._maybe_file_deploy_approval(appr)

    async def _maybe_file_deploy_approval(self, merge_appr: Approval) -> None:
        """File a ``driver_deploy`` approval when the project opted in.

        Deliberately a THIRD, separate opt-in from ``auto_open_pr``/
        ``auto_merge``, and unlike those two this one is never trust-gated —
        there is no ``auto_deploy``. A driver's trust record is calibrated
        against merge outcomes (did the PR turn out to be good code?), not
        against production incidents, and a bad deploy is live in a way a
        bad merge isn't. Approving ``driver_deploy`` always requires an
        explicit human click, regardless of how proven the driver is.
        """
        payload = merge_appr.payload or {}
        project_id = payload.get("project_id")
        if not project_id:
            return
        try:
            project = await self.session.get(Project, uuid.UUID(str(project_id)))
        except (ValueError, TypeError):
            project = None
        if project is None:
            return
        meta = project.scan_metadata or {}
        command = meta.get("deploy_command")
        if not (meta.get("deploy_on_merge") and command):
            return
        deploy_payload = {
            "task_id": payload.get("task_id"),
            "driver": payload.get("driver"),
            "project_id": str(project_id),
            "repo_path": payload.get("repo_path"),
            "branch": payload.get("base_branch"),
            "merge_commit": payload.get("merge_commit"),
            "deploy_command": command,
            # Run after a successful deploy (services/approvals.py
            # _post_deploy_checks); operator-set, like deploy_command.
            "smoke_command": meta.get("smoke_command"),
            "rollback_command": meta.get("rollback_command"),
        }
        deploy_appr = Approval(
            tenant_id=merge_appr.tenant_id,
            kind="driver_deploy",
            title=f"Deploy {project.name} @ {str(payload.get('merge_commit') or '?')[:8]}",
            # The actual command, not just that one exists -- every approvals
            # surface (dashboard, mobile) renders `detail` alone, never
            # `payload`, so a human approving a deploy from there needs to see
            # exactly what will run, not take it on faith.
            detail=(
                f"After merge {str(payload.get('merge_commit') or '?')[:8]}, run in "
                f"{project.name}'s repo:\n\n{command}\n\n"
                f"{_post_deploy_plan(meta)}"
                "Never auto-approved, regardless of driver trust."
            ),
            source="driver_deploy",
            source_ref=payload.get("task_id"),
            payload=deploy_payload,
        )
        self.session.add(deploy_appr)
        await event_bus.emit(
            EventType.APPROVAL_FILED,
            {
                "tenant_id": deploy_appr.tenant_id,
                "kind": "driver_deploy",
                "title": deploy_appr.title,
                "detail": deploy_appr.detail,
            },
            source="approvals",
        )

    async def _apply_driver_deploy(self, appr: Approval, approve: bool) -> None:
        """Run the project's own deploy command (approve). Reject: no-op.

        The command is whatever the project operator configured in
        ``scan_metadata.deploy_command`` — never agent-authored, the same
        trust level as ``sandbox_setup``/``sandbox_test_command`` (an
        operator-supplied string, not something the worktree or the diff
        controls). Raises on failure so the approval stays pending for a
        retry, exactly like :meth:`_apply_driver_pr`.
        """
        if not approve:
            return
        import asyncio

        from life_graph.tools._guards import ToolDeniedError, resolve_in_roots

        payload = appr.payload or {}
        command = payload.get("deploy_command")
        if not command:
            raise ApprovalActionError("no deploy_command on this approval")
        try:
            repo = resolve_in_roots(payload.get("repo_path") or "", tool_name="deploy")
        except ToolDeniedError as exc:
            raise ApprovalActionError(str(exc)) from exc

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=repo,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, err = await asyncio.wait_for(proc.communicate(), timeout=600)
        except TimeoutError as exc:
            raise ApprovalActionError("deploy command timed out after 600s") from exc
        except OSError as exc:
            raise ApprovalActionError(f"deploy command could not run: {exc}") from exc

        stdout = out.decode(errors="replace")[-2000:]
        stderr = err.decode(errors="replace")[-2000:]
        if proc.returncode != 0:
            raise ApprovalActionError(
                f"deploy command exited {proc.returncode}: {(stderr or stdout)[-500:]}"
            )
        appr.payload = {
            **payload,
            "deploy_output": stdout,
            "deployed_at": datetime.now(UTC).isoformat(),
        }
        done = f"Deployed (exit 0): {stdout[-300:] or '(no output)'}"
        checks = await self._post_deploy_checks(appr, repo)
        if checks:
            done = f"{done} | {checks}"
        appr.resolution_note = f"{appr.resolution_note} | {done}" if appr.resolution_note else done

    async def _post_deploy_checks(self, appr: Approval, repo: str) -> str | None:
        """After a successful deploy: smoke check, rollback on failure, file a fix.

        Returns a one-line outcome for the approval note, or None when the
        project has no smoke_command. Never raises: the deploy already
        happened, and the approval must record that whatever the checks find.
        """
        from life_graph.config import settings

        payload = appr.payload or {}
        smoke = payload.get("smoke_command")
        if not smoke:
            return None
        code, output = await _run_shell(smoke, repo, settings.post_deploy_smoke_timeout)
        appr.payload = {**payload, "smoke": {"exit": code, "output": output[-2000:]}}
        if code == 0:
            return "smoke check passed"

        outcome = f"smoke check FAILED (exit {code})"
        rollback = payload.get("rollback_command")
        if rollback:
            rcode, rout = await _run_shell(rollback, repo, 600)
            appr.payload = {**appr.payload, "rollback": {"exit": rcode, "output": rout[-2000:]}}
            outcome += "; rolled back" if rcode == 0 else f"; ROLLBACK FAILED (exit {rcode})"
        try:
            from life_graph.services.production_findings import file_fix_task
            from life_graph.storage.database import async_session

            project = await self._project_dict(appr.tenant_id, payload.get("project_id"))
            if project is not None:
                commit = str(payload.get("merge_commit") or "?")[:8]
                filed = await file_fix_task(
                    async_session,
                    appr.tenant_id,
                    project,
                    kind="post_deploy_smoke",
                    title=f"smoke check failed after deploying {commit}",
                    detail=f"Command: {smoke}\nExit {code}\n\n{output[-3000:]}",
                    signature=smoke,
                )
                outcome += (
                    f"; fix task {filed['queued']} queued"
                    if "queued" in filed
                    else f"; fix task {filed['deduplicated']} already open"
                )
        except Exception:
            logger.warning("Could not file a fix task after a failed smoke check", exc_info=True)
        # Reuses the "needs your attention" channel (push + Telegram).
        await event_bus.emit(
            EventType.APPROVAL_FILED,
            {
                "tenant_id": appr.tenant_id,
                "kind": "deploy_smoke_failed",
                "title": f"Deploy smoke check failed: {appr.title}",
                "detail": outcome,
            },
            source="approvals",
        )
        return outcome

    async def _project_dict(self, tenant_id: str, project_id: str | None) -> dict | None:
        """A registry project as the dict dev-task creation takes, or None."""
        if not project_id:
            return None
        try:
            project = await self.session.get(Project, uuid.UUID(str(project_id)))
        except (ValueError, TypeError):
            return None
        if project is None or project.tenant_id != tenant_id:
            return None
        return {
            "id": str(project.id),
            "name": project.name,
            "path": project.path,
            "scan_metadata": project.scan_metadata or {},
        }

    async def _apply_driver_plan(self, tenant_id: str, appr: Approval, approve: bool) -> None:
        """Dispatch the approved plan as one task, or fan out its Tasks list.

        A spec whose ``**Tasks:**`` section parses into 2+ numbered items
        becomes that many child dev tasks, QUEUED (not started immediately)
        so :func:`dev_tasks.run_queue` — already running as an API lifespan
        task — runs them one at a time, oldest first: task 2 only starts
        once task 1 has actually finished, since it may depend on task 1's
        code. A spec with 0 or 1 parsed tasks falls back to today's single
        combined dispatch rather than fanning out on a guess.

        Reject: a plain no-op — the plan is simply abandoned, nothing was
        ever landed to clean up. Raises on a missing/stale project so the
        approval stays pending for a retry, same shape as the other
        producers in this module.
        """
        if not approve:
            return
        payload = appr.payload or {}
        project_id = payload.get("project_id")
        instruction = payload.get("instruction") or ""
        spec = payload.get("spec") or ""
        persona_name = payload.get("persona_name")
        if not (project_id and instruction and persona_name):
            raise ApprovalActionError(
                "plan approval payload is missing project_id/instruction/persona_name"
            )

        try:
            project = await self.session.get(Project, uuid.UUID(str(project_id)))
        except (ValueError, TypeError):
            project = None
        if project is None:
            raise ApprovalActionError(f"project {project_id} no longer exists")

        from life_graph.drivers.dispatcher import _parse_tasks
        from life_graph.services import acceptance, dev_tasks
        from life_graph.storage.database import async_session as session_factory

        project_dict = {"id": str(project.id), "name": project.name}
        parsed = _parse_tasks(spec)
        # Check-only tasks ("run ruff and pytest") are dropped: verification
        # already runs after every task, so they would cost a run and land nothing.
        tasks = [t for t in parsed if not acceptance.is_check_only_task(t)]
        skipped = len(parsed) - len(tasks)
        criteria = acceptance.parse_criteria(spec)
        defined = [c.id for c in criteria]

        def _criteria_block(ac_ids: list[str]) -> str:
            text = acceptance.describe(criteria, ac_ids)
            if not text:
                return ""
            return (
                "\n\n--- ACCEPTANCE CRITERIA THIS TASK MUST SATISFY ---\n"
                f"{text}\n"
                "Write or update each criterion's test, and make it pass. These "
                "tests are run to verify this task."
            )

        if len(tasks) < 2:
            combined_instruction = (
                f"{instruction}\n\n"
                "--- APPROVED PLAN ---\n"
                "The following plan was reviewed and approved. Implement it.\n\n"
                f"{spec}"
                f"{_criteria_block(defined)}"
            )
            task = await dev_tasks.create_dev_task(
                session_factory,
                tenant_id,
                instruction=combined_instruction,
                project=project_dict,
                persona_name=persona_name,
                task_type="code_change",
                properties={
                    "origin": "plan_approval",
                    "plan_task_id": payload.get("task_id"),
                    "acceptance_criteria": defined,
                    "acceptance_tests": acceptance.bound_tests(criteria, defined),
                },
            )
            appr.payload = {**payload, "dispatched_task_id": task.get("id")}
            done = f"Dispatched as task {task.get('id')}"
            appr.resolution_note = (
                f"{appr.resolution_note} | {done}" if appr.resolution_note else done
            )
            return

        plan_group_id = str(uuid.uuid4())
        dispatched_ids = []
        for i, item in enumerate(tasks, start=1):
            # Only the criteria this task cites (and that the spec defines)
            # are checked on it -- task 1 isn't failed for AC-3's test that
            # task 3 is meant to write.
            cites = [ac for ac in acceptance.cited_criteria(item) if ac in defined]
            task_instruction = (
                f"{instruction}\n\n"
                "--- APPROVED PLAN (full spec, for context) ---\n"
                f"{spec}\n\n"
                f"--- YOUR TASK ({i} of {len(tasks)}) ---\n"
                f"{item}"
                f"{_criteria_block(cites)}"
            )
            task = await dev_tasks.create_dev_task(
                session_factory,
                tenant_id,
                instruction=task_instruction,
                project=project_dict,
                persona_name=persona_name,
                task_type="code_change",
                start=False,  # queued -- run_queue() runs the group in order
                properties={
                    "origin": "plan_approval",
                    "plan_task_id": payload.get("task_id"),
                    "plan_group_id": plan_group_id,
                    "plan_task_index": i,
                    "plan_task_count": len(tasks),
                    "acceptance_criteria": cites,
                    "acceptance_tests": acceptance.bound_tests(criteria, cites),
                },
            )
            dispatched_ids.append(task.get("id"))

        appr.payload = {
            **payload,
            "dispatched_task_ids": dispatched_ids,
            "plan_group_id": plan_group_id,
        }
        queued = f"Queued {len(dispatched_ids)} tasks (group {plan_group_id[:8]})"
        if skipped:
            queued += f"; skipped {skipped} check-only task{'s' if skipped > 1 else ''}"
        # Appended, not assigned: the reviewer's own note (why it was approved)
        # used to be overwritten here.
        appr.resolution_note = (
            f"{appr.resolution_note} | {queued}" if appr.resolution_note else queued
        )

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
        """Apply or confirm a supersede (approve), or UNDO / decline it (reject).

        Since 2026-10-22 a contradiction found against a still-pending new
        memory is only recorded (``payload.applied`` False): the old memory
        stays active until the owner agrees. Approving such an item applies
        the supersede and activates the new memory, since agreeing that it
        replaces the old one is agreeing to it. Items whose supersede already
        happened (an owner's explicit "remember this", or an older row with
        no ``applied`` key) are confirmed by approving — a no-op.

        Reject restores the superseded memory to active and clears the chain —
        but only if it's still in the exact state we recorded (defensive
        against later edits). For a supersede that never happened, the old
        memory is still active and reject changes nothing.
        """
        if approve:
            if (appr.payload or {}).get("applied") is False:
                await self._apply_deferred_supersede(tenant_id, appr, activate_new=True)
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

    async def _apply_deferred_supersede(
        self, tenant_id: str, appr: Approval, *, activate_new: bool
    ) -> bool:
        """Supersede the old memory by the new one recorded on *appr*, now.

        Only while the old memory is still active and the new one is pending
        or active (the owner may have rejected or changed either since).
        Marks the payload ``applied`` so a later reject of *appr* undoes it.
        Returns whether the supersede happened.
        """
        payload = appr.payload or {}
        try:
            old = await self.session.get(Memory, uuid.UUID(str(payload.get("memory_id_old"))))
            new = await self.session.get(Memory, uuid.UUID(str(payload.get("memory_id_new"))))
        except (ValueError, TypeError):
            return False
        if old is None or new is None:
            return False
        if old.tenant_id != tenant_id or new.tenant_id != tenant_id:
            return False
        if old.status != "active" or new.status not in ("pending", "active"):
            return False
        if activate_new:
            new.status = "active"
        old.status = "superseded"
        old.superseded_by = new.id
        new.supersedes = old.id
        # Reassign: in-place mutation of a JSONB dict is not change-tracked.
        appr.payload = {**payload, "applied": True}
        return True

    async def _pending_contradictions_for(self, tenant_id: str, memory_id: str) -> list[Approval]:
        """Pending contradiction approvals whose NEW side is *memory_id*."""
        rows = await self.session.execute(
            select(Approval).where(
                Approval.tenant_id == tenant_id,
                Approval.kind == "contradiction",
                Approval.status == "pending",
                Approval.source_ref.like(f"%|{memory_id}"),
            )
        )
        return list(rows.scalars().all())

    async def on_memory_approved(self, tenant_id: str, memory_id: str) -> int:
        """The owner approved a pending memory: apply its deferred supersedes.

        The contradiction approval stays pending, so the owner can still undo
        the supersede by rejecting it (2026-10-22). Returns how many old
        memories were superseded.
        """
        applied = 0
        for appr in await self._pending_contradictions_for(tenant_id, memory_id):
            if (appr.payload or {}).get("applied") is not False:
                continue  # already applied at ingest; nothing deferred
            if await self._apply_deferred_supersede(tenant_id, appr, activate_new=False):
                applied += 1
        await self.session.flush()
        return applied

    async def on_memory_rejected(self, tenant_id: str, memory_id: str) -> int:
        """The owner rejected a pending memory: close its contradiction items.

        Its supersedes were never applied (a pending memory supersedes
        nothing), so the old memories are already active; this only stops a
        moot review item lingering, and keeps a later approve of it from
        applying a supersede for a rejected memory. Returns how many closed.
        """
        rows = await self._pending_contradictions_for(tenant_id, memory_id)
        for appr in rows:
            appr.status = "rejected"
            appr.resolved_at = datetime.now(UTC)
            appr.resolution_note = "The new memory was rejected; the old one stays."
        await self.session.flush()
        return len(rows)

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


def _post_deploy_plan(meta: dict) -> str:
    """What runs after the deploy, for the approval's detail (shown to the approver)."""
    smoke = meta.get("smoke_command")
    if not smoke:
        return ""
    rollback = meta.get("rollback_command")
    tail = (
        f"and, if it fails, the rollback:\n\n{rollback}\n\n"
        if rollback
        else "No rollback_command is set: a failing smoke check only files a fix task.\n\n"
    )
    return f"Then the smoke check:\n\n{smoke}\n\n{tail}"


async def _run_shell(command: str, cwd: str, timeout: int) -> tuple[int, str]:
    """Run an operator-set shell command in *cwd*: (exit code, combined output)."""
    import asyncio

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        return 124, f"timed out after {timeout}s"
    except OSError as exc:
        return 127, f"could not run: {exc}"
    return proc.returncode or 0, out.decode(errors="replace")


async def retry_auto_merges(session_factory, max_age_days: int = 7) -> dict[str, int]:
    """Try auto-merge again on pending ``driver_merge`` approvals.

    :meth:`ApprovalService.maybe_auto_merge` runs once, right after the PR is
    opened, when its CI is usually still running; a "checks not green" there
    left the approval pending for good. On 2026-10-19 five agent PRs (#79,
    #81-#84) sat green and unmerged until someone approved them by hand. This
    re-runs the same check (same trust bar, CI still enforced by the merge
    itself) on approvals whose PR asked for auto-merge. Called by the
    15-minute ``sync_dev_task_prs`` job.
    """
    from datetime import timedelta

    since = datetime.now(UTC) - timedelta(days=max_age_days)
    merged = tried = 0
    async with session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(Approval).where(
                        Approval.kind == "driver_merge",
                        Approval.status == "pending",
                        Approval.created_at >= since,
                    )
                )
            )
            .scalars()
            .all()
        )
        for appr in rows:
            payload = appr.payload or {}
            if not payload.get("auto_merge"):
                continue
            tried += 1
            svc = ApprovalService(session)
            await svc.maybe_auto_merge(
                appr, payload.get("driver") or "", payload.get("project_id"), True
            )
            if appr.status == "approved":
                merged += 1
        await session.commit()
    if tried:
        logger.info("Auto-merge retry: %d of %d pending merges went through", merged, tried)
    return {"tried": tried, "merged": merged}
