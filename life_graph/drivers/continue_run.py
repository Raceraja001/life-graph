"""continue_task inside the dispatcher: resume a finished task's own session.

A mixin: ``TaskDispatcher`` inherits :meth:`ContinueRunMixin.continue_dispatch`
and provides every step it reuses (docs/specs/agent-drivers.md, "Phase 3b
part 2"). services/dev/continuation.py decides whether a task may be
continued and queues it; the dev-task runner then calls this.

The continuation runs in the task's kept worktree, on the same driver,
session and account (``driver.resume``), then through the normal chain: the
owner's steering messages (waiting ones ride in the follow-up, later ones get
a steering turn, drivers/steering.py), the tamper and no-change guards, the
verifier chain (with the bounce and the owner's rounds), landing and the PR
approval. Landing commits on top of the task's ``lg/task-*`` branch, so the
approval path stays single: a pending ``driver_pr`` approval is updated in
place; once its PR is open a new one is filed whose approval pushes the same
branch into the same PR (``gh pr view`` finds it), never a second PR.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from life_graph.core.events import EventType
from life_graph.drivers.base import DriverResult
from life_graph.drivers.dispatch_stats import _coerce_project_uuid
from life_graph.drivers.registry import driver_registry
from life_graph.drivers.workdir import remove_worktree, worktree_intact
from life_graph.services.dev import task_events

if TYPE_CHECKING:
    from life_graph.drivers.dispatcher import _DispatchRun

logger = logging.getLogger(__name__)

MAX_FEEDBACK_CHARS = 8000


def continue_text(feedback: str, reason: str | None) -> str:
    """The follow-up sent to the resumed session."""
    why = (reason or "feedback").strip()[:200]
    return (
        f"The owner reviewed your work on this task ({why}) and asks for the following. "
        "Your previous changes are in this working tree; build on them, do not start over. "
        "When the change is complete, stop.\n\n"
        f"{feedback.strip()[:MAX_FEEDBACK_CHARS]}"
    )


def _refusal(status: str, error: str) -> DriverResult:
    return DriverResult(success=False, error=error, metadata={"exit_status": status})


class ContinueRunMixin:
    """:meth:`continue_dispatch` -- the dispatcher half of continue_task."""

    async def continue_dispatch(
        self,
        *,
        tenant_id: str,
        task_id: str,
        instruction: str,
        task_type: str,
        project_id: Any,
        persona_name: str | None,
        session: Any,
        saved: dict[str, Any],
        feedback: str,
        reason: str | None = None,
        acceptance_tests: list[str] | None = None,
        timeout_seconds: int | None = None,
    ) -> DriverResult:
        """Continue *task_id* in its kept worktree and session with *feedback*.

        *saved* is the task's ``properties.continuation`` record. Refuses (a
        failed DriverResult, nothing run) when the worktree or session is gone
        or the driver cannot resume; the worktree is kept for another try.
        """
        # The dispatcher imports this module: its names are read at call time.
        from life_graph.drivers.dispatcher import (
            DEFAULT_COST_CAP_USD,
            _discard_worktree,
            _DispatchRun,
        )

        origin = saved.get("origin")
        worktree = Path(saved["worktree"]) if saved.get("worktree") else None
        session_id = saved.get("session_id")
        if not session_id:
            return _refusal("no_session", "This task has no agent session to continue")
        if worktree is None or not origin or not worktree.is_dir():
            return _refusal("no_workdir", "This task's worktree is gone; start a new task")
        if not worktree_intact(worktree, origin):
            return _refusal("no_workdir", "This task's worktree is no longer intact")
        driver = driver_registry.get(saved.get("driver") or "")
        if driver is None or not getattr(driver, "supports_resume", False):
            return _refusal(
                "resume_unsupported", f"Driver {saved.get('driver')!r} cannot resume a session"
            )

        run: _DispatchRun = _DispatchRun(
            tenant_id=tenant_id,
            task_id=task_id,
            instruction=instruction,
            task_type=task_type,
            persona_name=persona_name,
            session=session,
            cost_cap_usd=DEFAULT_COST_CAP_USD,
            interactive=True,  # the owner (or their PR feedback) asked for it
            spec_first=False,
            acceptance_tests=acceptance_tests,
            timeout_seconds=timeout_seconds,
        )
        run.session_ref = {
            "driver": driver.name,
            "session_id": str(session_id),
            "account_id": saved.get("account_id"),
        }
        run.base_commit = saved.get("base_commit")
        run.landed_branch = saved.get("branch")
        run.continuation_round = int(saved.get("rounds") or 0) + 1
        try:
            run.project_uuid = _coerce_project_uuid(project_id)
            await self._check_wip_limits(
                tenant_id, run.project_uuid, session, exclude_task_id=task_id
            )
            await self._prepare_packet(
                run,
                private=False,
                caller_verify_chain=list(saved.get("verify_chain") or []) or None,
                isolate_workdir=False,
            )
            # The owner's waiting steering messages ride in the follow-up.
            steer_block = await self._take_start_messages(run, into="continue")
            run.driver = driver
            run.worktree, run.worktree_origin, run.workdir = worktree, origin, worktree
            run.packet.project_context["path"] = str(worktree)
            run.packet.project_context["isolation"] = False
            task_events.emit(
                tenant_id, task_id, "round", f"continuing ({(reason or 'feedback')[:80]})",
                data={"kind": "continue", "round": run.continuation_round,
                      "driver": driver.name, "reason": (reason or "feedback")[:200]},
                source="dispatcher",
            )  # fmt: skip
            denied = await self._budget_gate(run)
            if denied is not None:
                run.result = denied
                await self._log_outcome(run)
                return denied
            await self._emit(
                EventType.DRIVER_DISPATCHED,
                {
                    "task_id": task_id,
                    "driver": driver.name,
                    "task_type": task_type,
                    "tenant_id": tenant_id,
                    "continuation": run.continuation_round,
                },
            )
            await self._end_transaction(session)
            await self._run_driver(
                run,
                resume=(
                    str(session_id),
                    continue_text(feedback, reason) + steer_block,
                    saved.get("account_id"),
                ),
            )
            await self._settle_start_messages(run)
            await self._steer(run)
            await self._check_worktree_link(run)
            await self._check_files_changed(run)
            self._decide_park(run)
            if run.verify_chain and run.result.success:
                await self._verify_result(run)
            await self._land_verified_work(run)
            await self._finish_dispatch(run)
            run.result.metadata = {
                **(run.result.metadata or {}),
                "continuation": run.continuation_round,
            }
            return run.result
        finally:
            if not await self._retain_for_continuation(run):
                packet = run.packet
                if packet is not None:
                    await remove_worktree(packet, worktree, repo_path=origin)
                else:
                    await _discard_worktree(worktree, origin)
