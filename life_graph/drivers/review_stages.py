"""The owner's autonomy rounds inside a dispatch: review stages, fix-round
gating, the risk report, and what the PR approval carries for the owner's
conditions. A mixin: ``TaskDispatcher`` inherits these and provides
``_bounce_task``, ``_observe_files_changed``, ``_worktree_diff``, ``_emit``,
the approval filers and ``_session_factory``.

docs/specs/agent-drivers.md, "Autonomy policy" (2026-11-27, owner decision D2):

* a round is **bounded** (services/dev/autonomy_policy.py ``MAX_FIX_ROUNDS``),
  **gated** on the kill switch, the Governor budget and the per-task cost cap
  (:meth:`AutonomyRoundsMixin._round_allowed`), **recorded** as the next
  verification attempt (``_bounce_task`` re-runs the verifier chain), and
  **never approves** anything: the single approval path is untouched;
* a review stage can only object; an objection goes back to the author while
  review-fix rounds last, then to a person, exactly like today's dissent.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from life_graph.autonomy.kill_switch import autonomy_stopped
from life_graph.core.budget import BudgetCategory
from life_graph.core.events import EventType
from life_graph.drivers.base import DriverResult
from life_graph.drivers.verify_chain import runs_on_local_model
from life_graph.models.db import AgentTask
from life_graph.services.dev import task_events
from life_graph.services.dev.autonomy_policy import NEUTRAL, EffectivePolicy, load_effective
from life_graph.services.dev.review_stages import latest_per_stage, reviewer_for, stage_record
from life_graph.services.dev.risk_report import build_report, summary
from life_graph.services.dev.verifiers import VerifierResult
from life_graph.services.governor import governor

if TYPE_CHECKING:
    from life_graph.drivers.dispatcher import _DispatchRun

logger = logging.getLogger(__name__)

# Task properties written by this mixin (cleared when a new dispatch starts).
REVIEW_STAGES_KEY = "review_stages"
RISK_REPORT_KEY = "risk_report"


class AutonomyRoundsMixin:
    """Review stages, fix-round gating and the risk report for a dispatch."""

    async def _load_autonomy_policy(self, run: _DispatchRun) -> EffectivePolicy:
        """The owner's policy for this task, in its own session.

        Any failure reads as the neutral policy: no rounds, no stages -- the
        behaviour from before the policy existed. (Auto-approval does not
        rely on this copy: ``auto_gate`` reads the policy again and refuses
        when it cannot.)
        """
        try:
            async with self._session_factory() as session:
                return await load_effective(session, run.tenant_id, run.project_uuid)
        except Exception:
            logger.debug("No autonomy policy for task %s", run.task_id, exc_info=True)
            return NEUTRAL

    async def _round_allowed(self, run: _DispatchRun) -> tuple[bool, str | None]:
        """Whether one more automatic round may run, and if not, why.

        Fail-closed: the kill switch (paused, or unreadable), the per-task cost
        cap and the Governor all have to say yes.
        """
        if await autonomy_stopped(run.tenant_id):
            return False, "autonomy is paused (kill switch)"
        if run.spent_usd >= run.cost_cap_usd:
            return False, f"per-task cost cap reached (${run.spent_usd:.2f})"
        try:
            decision = await governor.authorize(
                run.tenant_id,
                BudgetCategory.DRIVER,
                estimated_usd=run.driver.cost_per_task(),
                interactive=run.interactive
                or runs_on_local_model(run.driver.name, run.packet.persona_model),
            )
        except Exception as exc:
            return False, f"budget could not be checked ({type(exc).__name__})"
        if not decision.allowed:
            return False, f"budget: {decision.reason}"
        return True, None

    async def _persist_task_props(self, run: _DispatchRun, updates: dict[str, Any]) -> None:
        """Merge *updates* into the task row's properties, in its own session.

        Best-effort like ``_persist_checkpoint``: a throwaway task id (no row)
        or a failed write never breaks the dispatch.
        """
        try:
            pk = uuid.UUID(str(run.task_id))
            async with self._session_factory() as session:
                task = (
                    await session.execute(
                        select(AgentTask).where(
                            AgentTask.id == pk, AgentTask.tenant_id == run.tenant_id
                        )
                    )
                ).scalar_one_or_none()
                if task is None:
                    return
                props = dict(task.properties or {})
                for key, value in updates.items():
                    if value is None:
                        props.pop(key, None)
                    else:
                        props[key] = value
                task.properties = props
                await session.commit()
        except Exception:
            logger.debug(
                "Could not store %s for task %s", list(updates), run.task_id, exc_info=True
            )

    # ── Review stages ─────────────────────────────────────────

    async def _run_review_stages(self, run: _DispatchRun) -> None:
        """Run the owner's review stages in order (Step 6, checks passed).

        Per stage: review the real diff; no objection → next stage; objection
        → a review-fix round if one is left and allowed (the author gets the
        objection as a failed check, the verifier chain re-runs, then *that*
        stage reviews again), else a person decides, as with today's dissent.
        A ``human`` stage stops the chain: the task lands for a person and is
        never auto-approved. A stage that could not run is recorded
        ``unavailable`` and the chain goes on (it refuses auto-approval).
        """
        policy = run.policy
        rounds_left = policy.review_fix_rounds
        rounds_used = 0
        stages = list(policy.review_stages)
        for index, stage in enumerate(stages):
            if stage.reviewer == "human":
                run.review_results.append(stage_record(index, stage, "human"))
                run.review_results.extend(
                    stage_record(i, s, "skipped", note="after a human stage")
                    for i, s in enumerate(stages[index + 1 :], start=index + 1)
                )
                run.autonomy["human_stage"] = True
                break
            reviewer = reviewer_for(stage)
            fix_round = 0
            while True:
                diff_text = await self._worktree_diff(run.workdir)
                verdict = await reviewer.review(
                    run.task_type, run.instruction, diff_text, focus=stage.focus
                )
                if not verdict.ran:
                    run.review_results.append(
                        stage_record(
                            index, stage, "unavailable", note=verdict.concern, fix_round=fix_round
                        )
                    )
                    break
                if verdict.approved:
                    run.review_results.append(
                        stage_record(index, stage, "no_objection", fix_round=fix_round)
                    )
                    break
                run.review_results.append(
                    stage_record(
                        index, stage, "objection", concern=verdict.concern, fix_round=fix_round
                    )
                )
                await self._persist_review_results(run)
                why: str | None = "no review-fix rounds left"
                allowed = False
                if rounds_left > 0:
                    allowed, why = await self._round_allowed(run)
                if not allowed:
                    await self._stage_dissent(run, stage.name, verdict.concern, why)
                    return
                rounds_left -= 1
                rounds_used += 1
                fix_round += 1
                run.autonomy["review_fix"] = {
                    "rounds": rounds_used,
                    "allowed": policy.review_fix_rounds,
                }
                task_events.emit(
                    run.tenant_id, run.task_id, "round",
                    f"review-fix round {rounds_used} of {policy.review_fix_rounds} "
                    f"(stage {stage.name})",
                    data={"kind": "review_fix", "round": rounds_used,
                          "of": policy.review_fix_rounds, "stage": stage.name,
                          "attempt": run.next_attempt}, source="dispatcher",
                )  # fmt: skip
                objection = VerifierResult(
                    f"review:{stage.name}",
                    False,
                    {
                        "concern": verdict.concern or "the reviewer objected",
                        "focus": stage.focus or "general correctness",
                        "hint": "Address this concern in the files as they are now.",
                    },
                )
                attempt = run.next_attempt
                run.next_attempt += 1
                fixed = await self._bounce_task(
                    tenant_id=run.tenant_id,
                    task_id=run.task_id,
                    driver=run.driver,
                    packet=run.packet,
                    workdir=run.workdir,
                    failure_report=[objection],
                    session=run.session,
                    verify_chain=run.verify_chain,
                    acceptance_tests=run.acceptance_tests,
                    run=run,
                    attempt=attempt,
                )
                if fixed is not None and (fixed.metadata or {}).get("worktree_tampered"):
                    run.result = fixed  # vetoed and queued by the tamper check
                    await self._persist_review_results(run)
                    return
                if fixed is None:
                    await self._review_fix_failed(run, stage.name)
                    return
                run.result = fixed
                await self._observe_files_changed(run)
        await self._persist_review_results(run)

    async def _persist_review_results(self, run: _DispatchRun) -> None:
        run.autonomy["review_stages"] = latest_per_stage(run.review_results)
        await self._persist_task_props(run, {REVIEW_STAGES_KEY: list(run.review_results)})

    async def _stage_dissent(
        self, run: _DispatchRun, stage_name: str, concern: str | None, why: str | None
    ) -> None:
        """A stage objected and no fix round is left: a person decides (as today)."""
        driver = run.driver
        text = f"review stage '{stage_name}': {concern or 'unspecified concern'}"
        if why and why != "no review-fix rounds left":
            text += f" (no fix round: {why})"
        await self._emit(
            EventType.SECOND_OPINION_DISSENT,
            {"task_id": run.task_id, "driver": driver.name, "concern": text, "stage": stage_name},
        )
        await self._create_dissent_approval_entry(
            run.tenant_id, run.task_id, driver.name, text, run.session
        )
        result = run.result
        run.result = DriverResult(
            success=False,
            output=result.output,
            error=f"Review stage dissent: {text}",
            cost_usd=result.cost_usd,
            duration_ms=result.duration_ms,
            metadata={
                "needs_human": True,
                "second_opinion_concern": concern,
                "review_stage": stage_name,
            },
        )
        await self._persist_review_results(run)

    async def _review_fix_failed(self, run: _DispatchRun, stage_name: str) -> None:
        """A review-fix round's driver run or re-verification failed: needs a person."""
        from dataclasses import asdict

        failures = [r for r in run.verifier_results if not r.passed]
        reason = (
            "its driver run failed"
            if run.bounce_outcome == "driver_failed"
            else "verification failed afterwards"
        )
        await self._create_approval_entry(
            run.tenant_id,
            run.task_id,
            run.driver.name,
            failures or list(run.verifier_results),
            run.session,
        )
        result = run.result
        run.result = DriverResult(
            success=False,
            output=result.output,
            error=f"Review-fix round for stage '{stage_name}' failed ({reason}) — needs human review",
            cost_usd=result.cost_usd,
            duration_ms=result.duration_ms,
            metadata={
                "needs_human": True,
                "review_stage": stage_name,
                "verification_failures": [asdict(r) for r in failures],
            },
        )
        await self._persist_review_results(run)

    # ── Risk report + what the approval carries ───────────────

    async def _record_risk_report(self, run: _DispatchRun) -> None:
        """Build and store the change's risk report (Step 6b, before landing).

        Informational unless the owner's ``risk_tolerance`` asks for it. A diff
        that came back empty while files changed is recorded as incomplete,
        which such a condition refuses (never "clean").
        """
        try:
            diff_text = await self._worktree_diff(run.workdir)
            ctx = run.packet.project_context or {}
            report = build_report(
                diff_text,
                instruction=run.instruction,
                protected_globs=[str(p) for p in ctx.get("protected_paths") or []],
                complete=bool(diff_text) or not run.files_changed,
            )
        except Exception:
            logger.warning("Risk report failed for task %s", run.task_id, exc_info=True)
            return
        run.autonomy["risk"] = summary(report)
        await self._persist_task_props(run, {RISK_REPORT_KEY: report})

    @staticmethod
    def _autonomy_payload(run: _DispatchRun) -> dict[str, Any] | None:
        """The ``autonomy`` block of the PR approval payload (None when empty)."""
        return dict(run.autonomy) or None
