"""Filing approvals from a dispatch: plan review, PR/merge, second-opinion
dissent and needs-human entries, plus trusted auto-open. A mixin:
``TaskDispatcher`` inherits these methods unchanged and provides ``_emit``
(split out of dispatcher.py, 2026-10-25)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from life_graph.autonomy.safety.classifier import RiskLevel
from life_graph.config import settings
from life_graph.core.events import EventType
from life_graph.drivers.plan_spec import _PLAN_SPEC_MAX_CHARS, _parse_tasks
from life_graph.services.change_policy import describe_change, second_opinion

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from life_graph.drivers.base import DriverResult
    from life_graph.services.verifiers import VerifierResult

logger = logging.getLogger(__name__)

# At or above this merge rate (once established) a project that opted into
# auto_open_pr gets its PRs opened without the "Open PR" approval.
AUTO_PR_MERGE_RATE = 0.8


class ApprovalFilingMixin:
    """The approvals a dispatch files; the host class provides ``_emit``."""

    async def _create_dissent_approval_entry(
        self,
        tenant_id: str,
        task_id: str,
        driver_name: str,
        concern: str | None,
        session: AsyncSession,
    ) -> None:
        """Create an approval entry when the second-opinion reviewer dissents."""
        try:
            from life_graph.autonomy.models import ApprovalQueueEntry

            entry = ApprovalQueueEntry(
                tenant_id=tenant_id,
                agent_id=driver_name,
                action_name="driver_second_opinion_dissent",
                action_command=f"review task {task_id}",
                # approval_queue.ck_aq_risk_level allows only moderate/dangerous.
                # This said "medium", which is not in RiskLevel at all, so every
                # escalation to human review died on a CheckViolationError and
                # the driver's whole safety net silently failed closed.
                risk_level=RiskLevel.MODERATE.value,
                category="driver",
                trigger_type="driver_review",
                trigger_detail=(
                    f"Driver '{driver_name}' output for task {task_id} passed "
                    f"automated checks but the second-opinion reviewer dissented: "
                    f"{concern or 'unspecified concern'}"
                ),
                status="pending",
            )
            session.add(entry)
            logger.info("Created second-opinion approval entry for task %s", task_id)
            await self._emit(
                EventType.APPROVAL_FILED,
                {
                    "tenant_id": tenant_id,
                    "kind": "driver_second_opinion_dissent",
                    "title": f"Second-opinion dissent on task {task_id}",
                    "detail": entry.trigger_detail,
                },
            )
        except Exception:
            logger.warning("Failed to create dissent approval entry", exc_info=True)

    async def _create_plan_approval(
        self,
        *,
        tenant_id: str,
        task_id: str,
        driver_name: str,
        instruction: str,
        spec_text: str,
        project_id: uuid.UUID | None,
        persona_name: str | None,
        session: AsyncSession,
        auto_approve: bool = False,
    ) -> None:
        """File a ``driver_plan`` approval for a spec produced with no code changes.

        Approving it dispatches the ORIGINAL instruction plus this spec as a
        normal code-writing task — the full existing pipeline (driver,
        mechanical autofix, verify, second-opinion review, land, PR/merge
        approvals), unchanged. Rejecting it is a plain no-op: the plan is
        simply abandoned, nothing was ever landed to clean up.

        Best-effort, like the other approval producers: a failure here is
        logged and swallowed rather than failing a plan that already
        verified cleanly (no file changes, a real spec).
        """
        try:
            from life_graph.models.db import Approval
            from life_graph.services.acceptance import parse_criteria, spec_gaps

            title_line = instruction.strip().splitlines()[0] if instruction.strip() else "Plan"
            gaps = spec_gaps(parse_criteria(spec_text), _parse_tasks(spec_text))
            payload = {
                "task_id": task_id,
                "driver": driver_name,
                "instruction": instruction[:4000],
                # Not cut to 4000 like the instruction: approving fans out
                # from THIS copy, so a cut spec silently drops the later tasks
                # and their AC citations (seen: a 5.5k spec became 2 of 5 tasks,
                # no tests bound). The cap only guards against a runaway output.
                "spec": spec_text[:_PLAN_SPEC_MAX_CHARS],
                "spec_gaps": gaps,
                "project_id": str(project_id) if project_id else None,
                "persona_name": persona_name,
            }
            # Gaps are advisory: the reviewer decides whether they matter, but
            # they must see them -- not find out later that a criterion was
            # never checked.
            gap_text = (
                "Gaps to consider before approving:\n" + "\n".join(f"- {g}" for g in gaps) + "\n\n"
                if gaps
                else "Every acceptance criterion has a test and is covered by a task.\n\n"
            )
            appr = Approval(
                tenant_id=tenant_id,
                kind="driver_plan",
                title=f"Review plan: {title_line[:100]}",
                # The actual spec, not just a description of the step -- every
                # approvals surface (dashboard, mobile) renders `detail` alone,
                # never `payload`, so a human approving from there needs the
                # plan's actual content here or they are approving blind.
                detail=(
                    f"Driver '{driver_name}' produced this plan with no file changes:\n\n"
                    f"{spec_text[:2000]}\n\n"
                    f"{gap_text}"
                    "Approve to dispatch the instruction and this spec together as "
                    "a normal code-writing task; reject to abandon it."
                ),
                source="driver_plan",
                source_ref=str(task_id),
                payload=payload,
            )
            async with session.begin_nested():
                session.add(appr)
            logger.info("Task %s: plan approval filed", task_id)
            if await self._maybe_auto_approve_plan(
                appr, driver_name, project_id, session, auto_approve, spec_text, gaps
            ):
                return  # approved and fanned out: nothing is waiting on a person
            await self._emit(
                EventType.APPROVAL_FILED,
                {
                    "tenant_id": tenant_id,
                    "kind": "driver_plan",
                    "title": appr.title,
                    "detail": appr.detail,
                },
            )
        except Exception:
            logger.warning("Failed to file plan approval for task %s", task_id, exc_info=True)

    async def _maybe_auto_approve_plan(
        self,
        appr,
        driver_name: str,
        project_id: uuid.UUID | None,
        session: AsyncSession,
        opted_in: bool,
        spec_text: str,
        gaps: list[str],
    ) -> bool:
        """Approve the plan without asking when services/plan_policy.py allows it.

        Approval goes through ApprovalService.resolve, the same path a
        person's click takes, so fan-out is identical. Whatever the outcome,
        the reasons are written on the approval. Any failure leaves it
        pending, exactly as with auto-approval off.
        """
        from life_graph.services import plan_policy
        from life_graph.services.approvals import ApprovalService
        from life_graph.services.dev_outcomes import track_record

        try:
            record = (
                await track_record(session, appr.tenant_id, driver_name, project_id)
                if opted_in
                else {}
            )
            decision = plan_policy.decide(
                opted_in=opted_in,
                spec=spec_text,
                tasks=_parse_tasks(spec_text),
                gaps=gaps,
                record=record,
                merge_bar=AUTO_PR_MERGE_RATE,
            )
            if not decision.approve:
                if opted_in:
                    appr.detail = f"{appr.detail}\n\nNot auto-approved: {decision.summary}."
                return False
            await ApprovalService(session).resolve(
                appr.tenant_id,
                str(appr.id),
                "approve",
                note=f"Approved automatically: {decision.summary}.",
                resolved_by="auto: small trusted plan",
            )
            logger.info("Plan %s auto-approved (%s)", appr.id, decision.summary)
            return True
        except Exception:
            logger.warning("Plan auto-approval failed for %s; left pending", appr.id, exc_info=True)
            return False

    async def _draft_pr_description(
        self, repo_path: str, landing: dict, instruction: str
    ) -> str | None:
        """Draft the PR description from the landed diff. None on any failure."""
        if not settings.driver_pr_description_enabled:
            return None
        base, head = landing.get("base_commit"), landing.get("head_commit")
        if not (base and head):
            return None
        try:
            from life_graph.services.github_pr import landed_diff
            from life_graph.services.llm_client import get_resilient_llm
            from life_graph.services.pr_description import draft_pr_description

            diff_text = await landed_diff(repo_path, base, head)
            return await draft_pr_description(
                diff_text,
                instruction,
                chat=get_resilient_llm().chat,
                model=settings.driver_pr_description_model or settings.agent_llm_model,
            )
        except Exception:
            logger.warning("Could not draft a PR description", exc_info=True)
            return None

    async def _create_pr_approval(
        self,
        *,
        tenant_id: str,
        task_id: str,
        driver_name: str,
        instruction: str,
        result: DriverResult,
        branch: str,
        repo_path: str,
        checks: list[str],
        project_id: uuid.UUID | None,
        session: AsyncSession,
        verified: bool = True,
        unverifiable_checks: list[str] | None = None,
        auto_open_pr: bool = False,
        auto_merge: bool = False,
        base_branch: str | None = None,
        change_policy: dict | None = None,
    ) -> None:
        """File a ``driver_pr`` approval for a landed branch.

        Approving it pushes the branch and opens a pull request
        (``services/github_pr.py``). The payload pins the exact verified commit
        and the commit the work started from, so approval acts on what was
        checked — not on whatever the branch holds by the time someone taps it.
        Best-effort, like the other approval producers: a failure here leaves
        the branch landed and reviewable by hand.

        ``verified`` is False for a branch landed off an inconclusive verifier
        chain (the checks never ran, not that they failed) — the title and
        detail say so plainly, and the caller is expected to have already
        forced ``auto_open_pr`` off for this case; trust-based auto-approval
        is reserved for work that was actually checked.

        ``auto_merge`` is stored in the payload (not acted on here) so the
        trust check runs at merge-approval time, whichever path files it —
        a human approving ``driver_pr`` normally, or :meth:`_auto_open_pr`.
        """
        try:
            from life_graph.models.db import Approval
            from life_graph.services.github_pr import describe_landing

            landing = await describe_landing(repo_path, branch, base_branch=base_branch)
            title_line = instruction.strip().splitlines()[0] if instruction.strip() else branch
            pr_description = await self._draft_pr_description(repo_path, landing, instruction)
            # What the change is (kind, size, protected paths), fixed now:
            # every unattended open/merge is gated on it (change_policy.auto_gate).
            change = await describe_change(
                repo_path, landing.get("base_commit"), landing.get("head_commit"), change_policy
            )
            if (
                change["kind"] == "code"
                and verified
                and (auto_open_pr or auto_merge)
                and not change["review_reasons"]
            ):
                # Only for code that could otherwise land without a person.
                from life_graph.services.github_pr import landed_diff

                diff = await landed_diff(
                    repo_path, landing.get("base_commit", ""), landing.get("head_commit", "")
                )
                ok, note = await second_opinion(instruction, diff)
                change["second_opinion"] = note
                if not ok:
                    change["review_reasons"].append(note)
            payload = {
                "task_id": task_id,
                "driver": driver_name,
                "instruction": instruction[:4000],
                "summary": (result.output or "")[:4000],
                "branch": branch,
                "repo_path": repo_path,
                "project_id": str(project_id) if project_id else None,
                "checks": list(checks or []),
                "unverifiable_checks": list(unverifiable_checks or []),
                "cost_usd": result.cost_usd,
                "auto_merge": auto_merge,
                "verified": verified,
                "pr_description": pr_description,
                "change": change,
                **landing,
            }
            from life_graph.services.local_merge import pr_mode

            # In local mode approving is the merge (services/approvals.py), so say that.
            local = await pr_mode(session, project_id) == "local"
            action = "Merge" if local else "Open PR"
            title_prefix = action if verified else f"{action} (UNVERIFIED)"
            base = landing.get("base_branch") or "(unknown base)"
            if verified:
                detail = (
                    f"Branch {branch} passed "
                    f"{', '.join(checks) if checks else 'no checks'} on driver "
                    f"'{driver_name}'. "
                    + (
                        f"Approve to merge it into {base} locally."
                        if local
                        else f"Approve to push it and open a pull request against {base}."
                    )
                )
            else:
                names = unverifiable_checks or checks
                rest = [c for c in (checks or []) if c not in (unverifiable_checks or [])]
                detail = (
                    f"Branch {branch} was landed by driver '{driver_name}', but "
                    f"{', '.join(names) if names else 'verification'} could not run "
                    f"for this project — the change is neither known good nor known "
                    f"bad on {'that check' if len(names) == 1 else 'those checks'}."
                    + (f" ({', '.join(rest)} passed.)" if rest else "")
                    + " Review the diff by hand before approving; this will not "
                    "auto-open or auto-merge regardless of trust."
                )
            detail += (
                f"\n\nChange: {change['kind']}, {len(change['files'])} file(s), "
                f"{change['lines']} line(s)."
            )
            if change["review_reasons"]:
                detail += " Needs your review: " + "; ".join(change["review_reasons"]) + "."
            if pr_description:
                # Shown before approving, since `detail` is all an approvals
                # surface renders: the reviewer sees what the PR will say.
                detail += f"\n\nProposed PR description:\n\n{pr_description[:1500]}"
            appr = Approval(
                tenant_id=tenant_id,
                kind="driver_pr",
                title=f"{title_prefix}: {title_line[:100]}",
                detail=detail,
                source="driver",
                source_ref=str(task_id),
                payload=payload,
            )
            async with session.begin_nested():
                session.add(appr)
            logger.info("Task %s: PR approval filed for %s", task_id, branch)
        except Exception:
            logger.warning("Failed to file PR approval for task %s", task_id, exc_info=True)
            return

        if auto_open_pr and verified:
            await self._auto_open_pr(appr, driver_name, project_id, session)

        # Only notify if it's actually still waiting on someone -- a driver
        # proven enough to earn auto_open_pr just resolved this above, and
        # "approval needed" for something already approved is a false alarm.
        if appr.status == "pending":
            await self._emit(
                EventType.APPROVAL_FILED,
                {
                    "tenant_id": tenant_id,
                    "kind": "driver_pr",
                    "title": appr.title,
                    "detail": appr.detail,
                },
            )

    async def _auto_open_pr(
        self,
        appr,
        driver_name: str,
        project_id: uuid.UUID | None,
        session: AsyncSession,
    ) -> None:
        """Open the PR without asking when the project opted in and the driver
        has earned it there (established record, merge rate >= AUTO_PR_MERGE_RATE).

        The merge approval is still filed as usual after opening, so by
        default nothing reaches the base branch without the user — unless the
        project *also* opted into ``auto_merge`` (a second, separate flag: see
        ``ApprovalService._maybe_auto_merge``), in which case that freshly
        filed approval is itself checked against the same trust bar and may
        resolve immediately too. Any failure here leaves the ``driver_pr``
        approval pending, exactly as if auto-open were off.
        """
        from life_graph.services.approvals import ApprovalService
        from life_graph.services.change_policy import auto_gate
        from life_graph.services.github_pr import PullRequestError, open_pull_request
        from life_graph.services.local_merge import pr_mode

        if await pr_mode(session, project_id) == "local":
            # In local mode, approving driver_pr merges: never unattended.
            logger.info(
                "Auto-open PR skipped for %s: local mode merges only on approval", driver_name
            )
            return
        allowed, why, _record = await auto_gate(session, appr.tenant_id, appr.payload or {})
        if not allowed:
            logger.info("Auto-open PR skipped for %s: %s", driver_name, why)
            return
        try:
            outcome = await open_pull_request(appr.payload or {})
        except PullRequestError as exc:
            logger.warning("Auto-open PR failed, left for approval: %s", exc)
            appr.detail = f"{appr.detail} Auto-open failed: {exc}"
            return
        appr.status = "approved"
        appr.resolved_at = datetime.now(UTC)
        appr.resolved_by = "auto: trusted driver"
        appr.resolution_note = (
            f"Opened automatically: {why} on this project. PR: {outcome['pr_url']}"
        )
        appr.payload = {**(appr.payload or {}), "pr_url": outcome["pr_url"], "auto_opened": True}
        approvals = ApprovalService(session)
        merge_appr = approvals.file_merge_approval(appr)
        await approvals.maybe_auto_merge(
            merge_appr, driver_name, project_id, bool((appr.payload or {}).get("auto_merge"))
        )
        logger.info("Auto-opened PR %s (%s)", outcome["pr_url"], driver_name)
        if merge_appr.status == "pending":
            await self._emit(
                EventType.APPROVAL_FILED,
                {
                    "tenant_id": merge_appr.tenant_id,
                    "kind": "driver_merge",
                    "title": merge_appr.title,
                    "detail": merge_appr.detail,
                },
            )

    async def _create_approval_entry(
        self,
        tenant_id: str,
        task_id: str,
        driver_name: str,
        v_results: list[VerifierResult],
        session: AsyncSession,
    ) -> None:
        """Create an approval queue entry for tasks that need human review."""
        try:
            from life_graph.autonomy.models import ApprovalQueueEntry

            unverifiable = [r for r in v_results if r.inconclusive]
            if unverifiable:
                # Distinct from a failure: nothing is wrong with the work, the
                # gate simply never ran. Saying "failed verification" here
                # would send you looking for a bug in a change that was never
                # checked.
                names = ", ".join(r.verifier for r in unverifiable)
                action_name = "driver_verification_unavailable"
                detail = (
                    f"Task {task_id} ran on driver '{driver_name}', but these "
                    f"checks could not be performed: {names}. The change is "
                    f"UNVERIFIED — not known good and not known bad. Install "
                    f"the missing tooling in the project environment, or "
                    f"review the diff by hand."
                )
            else:
                failures = ", ".join(r.verifier for r in v_results if not r.passed)
                action_name = "driver_verification_failed"
                detail = (
                    f"Driver '{driver_name}' failed verification for task {task_id} "
                    f"after one bounce. Failures: {failures}"
                )
            entry = ApprovalQueueEntry(
                tenant_id=tenant_id,
                agent_id=driver_name,
                action_name=action_name,
                action_command=f"review task {task_id}",
                # approval_queue.ck_aq_risk_level allows only moderate/dangerous.
                # This said "medium", which is not in RiskLevel at all, so every
                # escalation to human review died on a CheckViolationError and
                # the driver's whole safety net silently failed closed.
                risk_level=RiskLevel.MODERATE.value,
                category="driver",
                trigger_type="driver_review",
                trigger_detail=detail,
                status="pending",
            )
            session.add(entry)
            logger.info("Created approval entry for task %s — needs human review", task_id)
            await self._emit(
                EventType.APPROVAL_FILED,
                {
                    "tenant_id": tenant_id,
                    "kind": action_name,
                    "title": f"Review needed: task {task_id}",
                    "detail": detail,
                },
            )
        except Exception:
            logger.warning("Failed to create approval entry", exc_info=True)
