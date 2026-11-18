"""Task Dispatcher — selects driver, enforces limits, manages one-bounce.

Selection logic:
1. Persona pin (if persona specifies a driver)
2. Cheapest capable trusted driver (success rate >= 0.6)
3. Fallback to 'local'

Limits:
- WIP: 2 per project, 5 per tenant
- Cost cap: $2 per task default

One-bounce rule:
- Failed verification → re-dispatch once with failure report
- Second failure → needs_human in approval queue
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from life_graph.config import settings
from life_graph.core.budget import BudgetCategory
from life_graph.core.events import EventBus, EventType
from life_graph.drivers.base import ContextPacket, DriverResult
from life_graph.drivers.context import ContextPacketBuilder
from life_graph.drivers.dispatch_approvals import (  # noqa: F401  (re-exported)
    AUTO_PR_MERGE_RATE,
    ApprovalFilingMixin,
)
from life_graph.drivers.dispatch_stats import (  # noqa: F401  (re-exported)
    MAX_WIP_PER_PROJECT,
    MAX_WIP_PER_TENANT,
    DriverStatsMixin,
    _coerce_project_uuid,
)
from life_graph.drivers.errors import DispatchError  # noqa: F401  (re-exported)
from life_graph.drivers.execution_guard import (
    ExecutionCheckpointTracker,
    verify_independent_completion,
)
from life_graph.drivers.plan_spec import (  # noqa: F401  (re-exported)
    _PLAN_ONLY_PREFIX,
    _PLAN_READ_TOOLS,
    _SPEC_FIRST_PREFIX,
    _extract_spec,
    _parse_tasks,
)
from life_graph.drivers.registry import driver_registry
from life_graph.drivers.verify_chain import (  # noqa: F401  (re-exported)
    DEFAULT_VERIFY_CHAIN,
    _resolve_verify_chain,
    _with_required_checks,
    runs_on_local_model,
)
from life_graph.drivers.workdir import (
    diff_against_head,
    escaping_symlinks,
    preserve_verified_work,
    remove_worktree,
    resolve_workdir,
    worktree_intact,
)
from life_graph.services.dev import task_events
from life_graph.services.dev.change_policy import policy_from_project
from life_graph.services.dev.verifiers import (  # noqa: F401  (failure_text: re-exported)
    BOUNCE_TASK_MARKER,
    VerifierResult,
    failure_text,
    mechanical_autofix,
    verifier_chain,
)
from life_graph.services.governor import governor

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# A coding task that left no file changed did not do the task (Step 4c) -- the
# two types the dispatcher has always enforced that on.
_CHANGE_REQUIRED_TASK_TYPES = ("code", "code_change")
# The wider set execution_guard.verify_independent_completion treats as code.
# The diff's file list is read for all of them so the independent-completion
# gate has evidence to weigh; "plan" and "general" are deliberately absent, so
# no task type that legitimately changes nothing gets a `git add -A` pass.
_CODE_TASK_TYPES = ("code", "code_change", "bugfix", "refactor", "feature")

# `diff --git a/<pre> b/<post>`, with git's optional quoting of paths that
# contain whitespace. Non-greedy so the ` b/` separator wins over a path that
# happens to contain " b/" itself.
_DIFF_GIT_HEADER = re.compile(r'^diff --git "?a/(?P<pre>.+?)"? "?b/(?P<post>.+?)"?$')

# ── Constants ────────────────────────────────────────────────

DEFAULT_COST_CAP_USD = 2.0
MIN_TRUST_THRESHOLD = 0.6


async def _head_sha(workdir: Any) -> str | None:
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", "rev-parse", "HEAD", cwd=str(workdir),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        )  # fmt: skip
        out, _ = await proc.communicate()
        return out.decode().strip() or None if proc.returncode == 0 else None
    except Exception:
        return None


async def _discard_worktree(worktree: Path | None, origin: str) -> None:
    """Remove a kept worktree that will not be landed (best-effort)."""
    if worktree is None or not Path(worktree).exists():
        return
    packet = ContextPacket(
        task_id=uuid.uuid4(), tenant_id="-", task_type="code", instruction="-",
        project_context={"path": origin},
    )  # fmt: skip
    await remove_worktree(packet, Path(worktree), repo_path=origin)


def _driver_timeout(driver: Any, run: Any) -> int:
    """The driver's own per-call limit, or the task's (bounded) override."""
    own = int(getattr(driver, "dispatch_timeout", 300))
    override = getattr(run, "timeout_seconds", None) if run is not None else None
    if not override:
        return own
    return max(30, min(int(override), int(settings.dev_task_max_timeout_seconds)))


@dataclass(frozen=True)
class _NamedDriver:
    """Stands in for a driver no longer registered, on a resume (name only)."""

    name: str


# A persona whose driver is "auto" lets the dispatcher choose per project.
AUTO_DRIVER = "auto"
# Below this merge rate (once established) a driver is skipped for a project.
POOR_MERGE_RATE = 0.5


def tenant_scratch_root(tenant_id: str) -> str:
    """A private (0700) parent for one tenant's dispatch scratch dirs and worktrees.

    One customer's agent work never shares a directory with another's, and
    a scratch dir's path says whose it is. The tenant id is reduced to safe
    characters; it is already validated, this only keeps it a single name.
    """
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", tenant_id or "unknown")[:64]
    root = Path(tempfile.gettempdir()) / "lg-tenants" / safe
    root.mkdir(parents=True, exist_ok=True)
    root.chmod(0o700)
    return str(root)


# Registry settings the verifier chain reads (never from the worktree, which
# the agent controls). One list, so the first attempt and the bounce agree.
SANDBOX_SETTINGS: tuple[str, ...] = (
    "sandbox_setup",
    "sandbox_test_command",
    "sandbox_test_timeout",
    "sandbox_toolchain",
    "sandbox_js_test_runner",
    "sandbox_start_command",
    "sandbox_app_port",
    "sandbox_e2e_command",
    "sandbox_e2e_timeout",
    # Thresholds for the proof checks (services/dev/proof_checks.py).
    "diff_coverage_min",
    "mutation_min_kill",
)


_CODE_CONTEXT_TIMEOUT_SECONDS = 30


async def _code_context(workdir: Path, instruction: str) -> str:
    """Callers/callees of the symbols *instruction* names. "" on any failure.

    Built from the task's own worktree (fresh, never stale), off the event
    loop since parsing a few hundred files is CPU and disk work. Best-effort:
    a context that can't be built must never fail a dispatch.
    """
    if not settings.driver_code_context_enabled:
        return ""
    try:
        from life_graph.services.dev.code_graph import build_graph, context_for

        graph = await asyncio.wait_for(
            asyncio.to_thread(build_graph, workdir), timeout=_CODE_CONTEXT_TIMEOUT_SECONDS
        )
        return context_for(graph, instruction)
    except Exception:
        logger.warning("Could not build code context for %s", workdir, exc_info=True)
        return ""


def _changed_paths(diff_text: str) -> list[str]:
    """The repository-relative paths named by a unified diff's ``diff --git`` headers.

    The post-image path (``b/...``) is the one that exists after the change,
    so a rename reads as its new name. git writes both sides even for a pure
    deletion, so the pre-image is only a fallback for a header shaped
    unexpectedly.
    """
    paths: list[str] = []
    for line in (diff_text or "").splitlines():
        if not line.startswith("diff --git "):
            continue
        m = _DIFF_GIT_HEADER.match(line)
        if m is None:
            continue
        path = m.group("post") or m.group("pre")
        if path and path not in paths:
            paths.append(path)
    return paths


@dataclass
class _DispatchRun:
    """What one dispatch_task call carries from step to step.

    The inputs are fixed at the start; each step fills in or replaces the
    rest. A step that turns the outcome into a failure replaces ``result``
    with a fresh DriverResult, and every later step reads that one.
    """

    tenant_id: str
    task_id: str
    instruction: str
    task_type: str
    persona_name: str | None
    session: Any
    cost_cap_usd: float
    interactive: bool
    spec_first: bool
    acceptance_tests: list[str] | None
    # A per-task ceiling for each driver call (Stage 4); None = the driver's own.
    timeout_seconds: int | None = None
    project_uuid: Any = None
    packet: ContextPacket | None = None
    persona: Any = None
    driver: Any = None
    verify_chain: list[str] | None = None
    workdir: Path | None = None
    worktree: Any = None
    worktree_origin: str | None = None
    result: DriverResult | None = None
    unverifiable: list[VerifierResult] = field(default_factory=list)
    spec_text: str | None = None
    tracker: ExecutionCheckpointTracker | None = None
    # The paths this run actually changed, as read from the worktree's own
    # diff -- None while nothing has been observed yet, which is NOT the
    # same fact as "it changed nothing" (see _observe_files_changed).
    files_changed: list[str] | None = None
    # The verifier verdicts that judged the result currently in `result` --
    # replaced by the bounce's own re-verification, so the independent
    # completion gate never weighs a superseded attempt's checks.
    verifier_results: list[VerifierResult] = field(default_factory=list)


class TaskDispatcher(DriverStatsMixin, ApprovalFilingMixin):
    """Selects driver, enforces limits, runs verification, manages one-bounce.

    The dispatcher is the central orchestrator for sending tasks to
    agent drivers. It builds context packets, selects the best driver,
    dispatches with timeout, verifies results, and records stats.
    """

    def __init__(
        self,
        session_factory: callable,
        event_bus: EventBus | None = None,
        reviewer=None,
    ) -> None:
        self._session_factory = session_factory
        self._event_bus = event_bus
        self._context_builder = ContextPacketBuilder()
        self._reviewer = reviewer or self._build_default_reviewer()

    @staticmethod
    def _build_default_reviewer():
        """Build the second-opinion reviewer from settings (off by default).

        Backed by PR-Agent (services/dev/pr_agent_review.py), which reads the
        actual diff rather than the driver's narrative account of it —
        same settings surface (driver_second_opinion_enabled/_model) the
        older thin LLM-skim reviewer used, same gate position.
        """
        from life_graph.config import settings
        from life_graph.services.dev.pr_agent_review import PRAgentReviewer

        return PRAgentReviewer(
            model=settings.driver_second_opinion_model or settings.agent_llm_model,
            enabled=settings.driver_second_opinion_enabled,
            bin_path=settings.driver_pr_agent_bin,
        )

    async def dispatch_task(
        self,
        tenant_id: str,
        task_id: str,
        instruction: str,
        task_type: str = "general",
        project_id: str | None = None,
        session: AsyncSession | None = None,
        persona_name: str | None = None,
        private: bool = False,
        cost_cap_usd: float = DEFAULT_COST_CAP_USD,
        verify_chain: list[str] | None = None,
        interactive: bool = False,
        isolate_workdir: bool = False,
        spec_first: bool = False,
        acceptance_tests: list[str] | None = None,
        timeout_seconds: int | None = None,
    ) -> DriverResult:
        """Dispatch a task through the full driver pipeline.

        Steps (each a method below, in this order):
        1. Check WIP limits
        2. Build the context packet, scoped to the persona   (_prepare_packet)
        3. Select driver, then the Governor budget gate       (_budget_gate)
        4. Dispatch in the resolved workdir                   (_run_driver)
           4b. worktree .git link intact                      (_check_worktree_link)
           4c. a code task changed some file                  (_check_files_changed)
        5. Run verifier chain, auto-fix once                  (_verify_result)
        6. Unverifiable, bounce once, plan spec, or second opinion
           6b. Land the verified work on a branch             (_land_verified_work)
        7. Record stats + emit events                         (_finish_dispatch)

        Each step reads and updates one _DispatchRun; a step that turns the
        outcome into a failure replaces ``run.result`` and later steps see it.

        Args:
            tenant_id: Tenant scope.
            task_id: The task being dispatched.
            instruction: Natural language task description.
            task_type: Category of work (code, research, etc.).
            project_id: Optional project context.
            session: Optional session (creates one if None).
            persona_name: Optional persona pin for driver selection.
            private: If True, strip memories/preferences.
            cost_cap_usd: Maximum cost allowed for this dispatch.
            verify_chain: List of verifier names to run.

        Returns:
            DriverResult with the outcome.

        Raises:
            DispatchError: If WIP limits are exceeded or no driver available.
        """
        owns_session = session is None
        if owns_session:
            session = self._session_factory()

        run = _DispatchRun(
            tenant_id=tenant_id,
            task_id=task_id,
            instruction=instruction,
            task_type=task_type,
            persona_name=persona_name,
            session=session,
            cost_cap_usd=cost_cap_usd,
            interactive=interactive,
            spec_first=spec_first,
            acceptance_tests=acceptance_tests,
            timeout_seconds=timeout_seconds,
        )

        try:
            # Normalize the project id ONCE, before both consumers (WIP check
            # and packet build) — callers may pass a non-UUID pseudo-project.
            run.project_uuid = _coerce_project_uuid(project_id)

            # Step 1: Check WIP limits
            await self._check_wip_limits(
                tenant_id, run.project_uuid, session, exclude_task_id=task_id
            )

            # Step 2: Build context packet (+ persona scope, verifier chain)
            await self._prepare_packet(
                run,
                private=private,
                caller_verify_chain=verify_chain,
                isolate_workdir=isolate_workdir,
            )

            # Step 3: Select driver
            run.driver = await self._select_driver(
                task_type,
                persona_name,
                tenant_id,
                session,
                persona=run.persona,
                project_id=run.project_uuid,
            )
            task_events.emit(
                tenant_id, task_id, "driver", f"driver {run.driver.name}",
                data={"driver": run.driver.name, "persona": persona_name}, source="dispatcher",
            )  # fmt: skip

            # Step 3b: Governor budget gate — refuse before spending, not after.
            denied = await self._budget_gate(run)
            if denied is not None:
                return denied

            # Emit dispatch event
            await self._emit(
                EventType.DRIVER_DISPATCHED,
                {
                    "task_id": task_id,
                    "driver": run.driver.name,
                    "task_type": task_type,
                    "tenant_id": tenant_id,
                },
            )

            # Step 4: Dispatch with workdir, then the two post-run guards
            await self._run_driver(run)
            await self._check_worktree_link(run)
            await self._check_files_changed(run)

            # Steps 5-6: Run verifier chain and act on its verdict
            if run.verify_chain and run.result.success:
                await self._verify_result(run)

            # Step 6b: Land the verified work before cleanup can discard it.
            await self._land_verified_work(run)

            # Step 7: Record stats + emit result
            await self._finish_dispatch(run)

            if owns_session:
                await session.commit()

            return run.result

        except Exception as e:
            if owns_session:
                await session.rollback()
            logger.error("Dispatch failed for task %s: %s", task_id, e, exc_info=True)
            raise
        finally:
            if run.worktree is not None:
                # Run the removal from the ORIGIN repo: packet.project_context
                # ["path"] now points at the worktree itself (see Step 4), and
                # git refuses to delete a worktree from inside it.
                await remove_worktree(run.packet, run.worktree, repo_path=run.worktree_origin)
            if owns_session:
                await session.close()

    async def resume_landing(
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
    ) -> DriverResult | None:
        """Finish a dispatch that had passed verification before a crash.

        No agent runs. Two cases, from the persisted resume point
        (``verifier_completed`` metadata, and ``landed`` if it got that far):

        - **already landed** on ``lg/task-*``: file the PR approval if the crash
          came before it (one approval per task: an existing one is kept);
        - **verified, not landed**: land the kept worktree, but only when it is
          still intact and its diff is byte-for-byte what was verified (the
          SHA-256 recorded then), then file the approval as usual.

        Returns None when neither is possible (worktree gone or changed, no
        resume data); the caller then re-runs the task from the start, or, for
        already-landed work, just closes it out.
        """
        branch = saved.get("landed_branch")
        origin = saved.get("worktree_origin")
        worktree = Path(saved["worktree"]) if saved.get("worktree") else None
        if not origin or not (branch or worktree):
            return None
        if branch and await self._has_pr_approval(tenant_id, task_id, session):
            return DriverResult(
                success=True,
                output=str(saved.get("output") or ""),
                metadata={"landed_branch": branch, "resumed": "already_landed"},
            )
        if not branch:
            if worktree is None or not worktree.is_dir() or not worktree_intact(worktree, origin):
                logger.info("Task %s: kept worktree gone or not intact; re-running", task_id)
                await _discard_worktree(worktree, origin)
                return None
            diff = await diff_against_head(worktree)
            same_diff = hashlib.sha256(diff.encode()).hexdigest() == saved.get("diff_sha256")
            # HEAD pinned too: a moved HEAD could carry extra commits under a
            # matching diff.
            same_head = not saved.get("head") or await _head_sha(worktree) == saved["head"]
            if not (same_diff and same_head):
                logger.warning(
                    "Task %s: worktree changed since it was verified; re-running", task_id
                )
                await _discard_worktree(worktree, origin)
                return None

        run = _DispatchRun(
            tenant_id=tenant_id,
            task_id=task_id,
            instruction=instruction,
            task_type=task_type,
            persona_name=persona_name,
            session=session,
            cost_cap_usd=DEFAULT_COST_CAP_USD,
            interactive=True,
            spec_first=False,
            acceptance_tests=None,
        )
        try:
            run.project_uuid = _coerce_project_uuid(project_id)
            # The project's CURRENT policy (auto_open_pr, auto_merge, protected
            # paths) decides the approval, not a copy from before the crash.
            await self._prepare_packet(
                run,
                private=False,
                caller_verify_chain=saved.get("verify_chain") or None,
                isolate_workdir=False,
            )
            run.driver = driver_registry.get(saved.get("driver") or "") or _NamedDriver(
                saved.get("driver") or "unknown"
            )
            run.verify_chain = list(saved.get("verify_chain") or run.verify_chain or [])
            run.files_changed = list(saved.get("files_changed") or []) or None
            run.result = DriverResult(
                success=True,
                output=str(saved.get("output") or ""),
                metadata={"resumed": "land_only"},
            )
            run.tracker = ExecutionCheckpointTracker(task_id=task_id, tenant_id=tenant_id)
            run.tracker.record_stage(
                "verifier_completed", metadata={"verdict": "passed", "resumed": True}
            )
            if branch:
                run.tracker.record_stage("landed", metadata={"branch": branch, "resumed": True})
                run.result.metadata["landed_branch"] = branch
                ctx = run.packet.project_context
                await self._create_pr_approval(
                    tenant_id=tenant_id,
                    task_id=task_id,
                    driver_name=run.driver.name,
                    instruction=instruction,
                    result=run.result,
                    branch=branch,
                    repo_path=origin,
                    checks=run.verify_chain,
                    project_id=run.project_uuid,
                    session=session,
                    verified=True,
                    unverifiable_checks=[],
                    auto_open_pr=bool(ctx.get("auto_open_pr")),
                    auto_merge=bool(ctx.get("auto_merge")),
                    base_branch=ctx.get("base_branch") or None,
                    change_policy=policy_from_project(ctx),
                )
            else:
                run.worktree, run.worktree_origin, run.workdir = worktree, origin, worktree
                await self._land_verified_work(run)
                if "landed_branch" not in (run.result.metadata or {}):
                    return None
            await self._finish_dispatch(run)
            logger.info("Task %s resumed after restart without re-running the agent", task_id)
            return run.result
        finally:
            if worktree is not None and worktree.is_dir() and run.packet is not None:
                await remove_worktree(run.packet, worktree, repo_path=origin)

    async def _has_pr_approval(self, tenant_id: str, task_id: str, session: Any) -> bool:
        """Whether a driver_pr approval was already filed for this task."""
        from sqlalchemy import select

        from life_graph.models.db import Approval

        row = (
            await session.execute(
                select(Approval.id)
                .where(
                    Approval.tenant_id == tenant_id,
                    Approval.source_ref == str(task_id),
                    Approval.kind == "driver_pr",
                )
                .limit(1)
            )
        ).first()
        return row is not None

    # ── dispatch_task steps, in pipeline order ──────────────────────────

    async def _persist_checkpoint(self, run: _DispatchRun) -> None:
        """Flush the run's stage trail into the task row's properties.

        The trail only ever helps a *restarted* process, which can read
        nothing out of this one's memory -- so every stage writes it to
        ``agent_tasks.properties['checkpoints']``, where
        :func:`~life_graph.services.dev.tasks.fail_interrupted` reads it to
        decide whether an abandoned run has to be re-dispatched in a clean
        worktree, only landed, or left alone because it already landed.

        Best-effort, in its own session: a dispatch with no task row behind
        it (the test endpoint's throwaway ids) or a failed write must never
        break the pipeline.
        """
        if run.tracker is None:
            return
        try:
            from sqlalchemy import select

            from life_graph.models.db import AgentTask

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
                props["checkpoints"] = run.tracker.to_dict()
                task.properties = props
                await session.commit()
            last = run.tracker.checkpoints[-1] if run.tracker.checkpoints else None
            if last is not None:
                meta = {k: v for k, v in (last.metadata or {}).items() if k != "resume"}
                task_events.emit(
                    run.tenant_id, run.task_id, "stage", last.stage,
                    data={"ok": last.ok, "attempt": last.attempt, **meta}, source="dispatcher",
                )  # fmt: skip
        except Exception:
            logger.warning(
                "Could not persist dispatch checkpoints for task %s", run.task_id, exc_info=True
            )

    async def _prepare_packet(
        self,
        run: _DispatchRun,
        *,
        private: bool,
        caller_verify_chain: list[str] | None,
        isolate_workdir: bool,
    ) -> None:
        """Step 2: the context packet, scoped to the persona, and the checks."""
        packet = await self._context_builder.build_packet(
            tenant_id=run.tenant_id,
            task_type=run.task_type,
            instruction=run.instruction,
            project_id=run.project_uuid,
            session=run.session,
            private=private,
        )
        # Override the task_id from the caller
        packet.task_id = uuid.UUID(run.task_id) if isinstance(run.task_id, str) else run.task_id
        run.packet = packet

        if run.task_type == "plan":
            packet.instruction = _PLAN_ONLY_PREFIX + packet.instruction
        elif run.spec_first:
            packet.instruction = _SPEC_FIRST_PREFIX + packet.instruction

        # Step 2b: Resolve the pinned persona ONCE (reused for driver
        # selection below) and scope the packet to it. Without this the
        # driver would run with the FULL tool registry — including the
        # host shell (`run_command`) — for an unattended dispatch.
        persona = await self._load_persona(run.tenant_id, run.persona_name, run.session)
        run.persona = persona
        if persona is not None:
            packet.persona_system_prompt = getattr(persona, "system_prompt", None)
            allowed = getattr(persona, "allowed_tools", None)
            packet.allowed_tools = list(allowed) if allowed is not None else None
            packet.persona_model = getattr(persona, "model", None) or None
        if run.task_type == "plan":
            # Prompting alone didn't hold (see _PLAN_ONLY_PREFIX); take
            # the write tools away too. An unscoped or write-only persona
            # still gets file_read, since a plan needs to read the code.
            read = [t for t in (packet.allowed_tools or []) if t in _PLAN_READ_TOOLS]
            packet.allowed_tools = read or ["file_read"]

        # A persona declares the checks its own work must clear —
        # dependency-updater asks for tests_pass because its whole job is
        # "run the project's tests before landing". Nothing read that
        # column, so it landed on the generic default instead and its
        # tests never ran. An explicit caller argument still wins
        # (precedence: caller argument > persona.verifier_chain > default).
        verify_chain = _resolve_verify_chain(caller_verify_chain, persona)
        verify_chain = _with_required_checks(verify_chain, packet.project_context)
        # A task fanned out from a plan carries the tests bound to the
        # acceptance criteria it cites -- check those specifically, on
        # top of whatever chain the persona/project asked for.
        if run.acceptance_tests and "acceptance_tests_pass" not in verify_chain:
            verify_chain = [*verify_chain, "acceptance_tests_pass"]
        run.verify_chain = verify_chain

        # Step 2c: opt-in workdir isolation — only when the caller asked
        # for it AND a real project path resolved. A no-op flag on a
        # personaless/projectless dispatch (today's exact behavior).
        if isolate_workdir and packet.project_context.get("path"):
            packet.project_context["isolation"] = True

        # Step 2d: the durable checkpoint trail. Each later step records the
        # stage it completed, so a worker that dies mid-dispatch can be told
        # (by recover_interrupted_dispatch) whether to re-dispatch in a clean
        # worktree, land only, or skip work that already landed.
        run.tracker = ExecutionCheckpointTracker(task_id=run.task_id, tenant_id=run.tenant_id)
        run.tracker.record_stage(
            "prepared",
            metadata={
                "task_id": run.task_id,
                "driver": getattr(run, "driver_name", run.persona_name),
            },
        )
        await self._persist_checkpoint(run)

    async def _budget_gate(self, run: _DispatchRun) -> DriverResult | None:
        """Step 3b: the Governor's verdict; a DriverResult when it says no.

        Autonomous dispatches are throttled/denied when the monthly budget
        is exhausted; interactive (user-initiated) tasks are never blocked.
        The cap governs paid API spend only: a run whose every model is
        local (Ollama) cannot spend, so it is never denied.
        """
        driver = run.driver
        decision = await governor.authorize(
            run.tenant_id,
            BudgetCategory.DRIVER,
            estimated_usd=driver.cost_per_task(),
            interactive=run.interactive
            or runs_on_local_model(driver.name, run.packet.persona_model),
        )
        if decision.allowed:
            if run.tracker:
                run.tracker.record_stage(
                    "budget_checked", metadata={"cost_cap_usd": run.cost_cap_usd}
                )
                await self._persist_checkpoint(run)
            return None
        logger.warning(
            "Task %s denied by Governor: %s (spent $%.2f / $%.2f)",
            run.task_id,
            decision.reason,
            decision.spent_usd,
            decision.cap_usd,
        )
        await self._emit(
            EventType.DRIVER_DISPATCHED,
            {
                "task_id": run.task_id,
                "driver": driver.name,
                "task_type": run.task_type,
                "tenant_id": run.tenant_id,
                "budget_denied": True,
            },
        )
        return DriverResult(
            success=False,
            error=f"budget: {decision.reason}",
            metadata={"budget_throttled": True, "reason": decision.reason},
        )

    async def _run_driver(self, run: _DispatchRun) -> None:
        """Step 4: resolve the workdir, run the driver, book what it spent."""
        packet, driver, task_id = run.packet, run.driver, run.task_id
        scratch = Path(
            tempfile.mkdtemp(
                prefix=f"lg_dispatch_{task_id[:8]}_", dir=tenant_scratch_root(run.tenant_id)
            )
        )
        run.workdir, run.worktree = await resolve_workdir(packet, scratch)
        if run.worktree is not None:
            run.worktree_origin = packet.project_context.get("path")
            # Describe the packet's project location as the ALREADY-resolved
            # workdir, so a driver that also calls resolve_workdir internally
            # (e.g. ClaudeCodeDriver) is idempotent — it sees isolation=False
            # and a "path" that's already the resolved worktree, so it returns
            # that same directory directly instead of creating a SECOND, nested
            # worktree the verifier chain would never see.
            #
            # Guarded on worktree is not None on purpose: when isolation was
            # never requested (or failed), project_context stays untouched, so
            # a caller that had an empty {} context keeps one — LocalDriver's
            # prompt gates a whole section on `if packet.project_context:`.
            packet.project_context["path"] = str(run.workdir)
            packet.project_context["isolation"] = False
            # Step 4a: where the symbols the instruction names are defined
            # and who calls them, from this worktree's own code.
            code_context = await _code_context(run.workdir, run.instruction)
            if code_context:
                packet.instruction += (
                    "\n\n--- CODE CONTEXT (where the symbols named above are "
                    "defined and used in this project) ---\n"
                    f"{code_context}\n"
                    "Check these callers before changing a signature or return shape."
                )
        result = await driver.dispatch(packet, run.workdir, timeout=_driver_timeout(driver, run))
        run.result = result
        if run.tracker:
            run.tracker.record_stage(
                "driver_executed",
                metadata={
                    "success": getattr(run.result, "success", False) if run.result else False
                },
            )
            await self._persist_checkpoint(run)
        await self._emit_steps(run.tenant_id, task_id, driver.name, 1, result)
        # Captured here, before later steps replace `run.result` with fresh
        # DriverResult instances (verification failure, dissent, ...)
        # that don't carry the original metadata forward — merged back
        # in at Step 7 regardless of how the task ultimately resolved.
        run.spec_text = _extract_spec(result.output) if run.spec_first else None

        # Book the actual spend into the Governor's ledger.
        await governor.record(run.tenant_id, BudgetCategory.DRIVER, result.cost_usd)

        # Secondary per-task guard (the Governor is the primary budget gate).
        if result.cost_usd > run.cost_cap_usd:
            logger.warning(
                "Task %s exceeded per-task cost cap: $%.2f > $%.2f",
                task_id,
                result.cost_usd,
                run.cost_cap_usd,
            )

    async def _check_worktree_link(self, run: _DispatchRun) -> None:
        """Step 4b: the driver must not have swapped the worktree's .git link.

        Verifier and landing git commands run on the host inside this
        directory; a planted .git dir would carry its own config (filters,
        fsmonitor) and make them execute agent-chosen programs.
        """
        result = run.result
        # Links leaving the worktree are tampering too: host-side readers
        # (verifiers, PR description, landing) would follow them to host files.
        intact = (
            run.worktree is None
            or not run.worktree_origin
            or worktree_intact(run.worktree, run.worktree_origin)
        )
        # git_aware: links committed at HEAD and unchanged are the project's,
        # not the agent's. Only asked of an intact worktree, so the git
        # commands it runs read the origin's config, never a planted one.
        # In a thread: a big worktree is a long walk plus two git calls, and on
        # the event loop that stalled lease heartbeats and the API.
        escaping = (
            await asyncio.to_thread(escaping_symlinks, run.worktree, git_aware=True)
            if result.success and run.worktree is not None and intact
            else []
        )
        if not (
            result.success
            and run.worktree is not None
            and run.worktree_origin
            and (not intact or escaping)
        ):
            if run.tracker:
                run.tracker.record_stage(
                    "worktree_verified", metadata={"workdir": str(run.workdir)}
                )
                await self._persist_checkpoint(run)
            return
        what = (
            f"symlinks leaving the worktree: {', '.join(escaping[:5])}"
            if escaping
            else "worktree .git no longer links to the origin repository"
        )
        logger.error("Task %s: worktree tampered with (%s)", run.task_id, what)
        if run.tracker:
            run.tracker.record_stage(
                "worktree_verified",
                ok=False,
                metadata={"workdir": str(run.workdir), "tampered": True, "why": what},
            )
            await self._persist_checkpoint(run)
        tamper = VerifierResult("worktree_intact", False, {"error": what})
        await self._create_approval_entry(
            run.tenant_id, run.task_id, run.driver.name, [tamper], run.session
        )
        run.result = DriverResult(
            success=False,
            output=result.output,
            error=f"Worktree tampered with by the driver ({what}) — not verified or landed",
            cost_usd=result.cost_usd,
            duration_ms=result.duration_ms,
            metadata={"needs_human": True, "worktree_tampered": True},
        )

    async def _observe_files_changed(self, run: _DispatchRun) -> None:
        """Read the paths this run changed from the worktree's own diff.

        The one source of that fact that is not the driver's own account of
        it, so it is what the independent-completion gate weighs. Left at
        ``None`` where there is nothing to read -- a non-code task type, or a
        dispatch with no worktree behind it -- because "not observed" and
        "observed nothing" are different facts and only the second one is
        evidence that the run did nothing.
        """
        if run.result.success and run.worktree is not None and run.task_type in _CODE_TASK_TYPES:
            # One `git add -A`/diff pass, read for both the Step 4c guard
            # below and the Step 6c gate.
            run.files_changed = _changed_paths(await diff_against_head(run.worktree))

    async def _check_files_changed(self, run: _DispatchRun) -> None:
        """Step 4c: a coding task that left no file changed did not do the task.

        Every diff-scoped verifier passes vacuously on an empty diff, so this
        used to finish as "completed": task ade60cc6 (2026-10-18) added one
        import, ruff's autofix removed it as unused, and nothing else was
        ever written.
        """
        result = run.result
        await self._observe_files_changed(run)
        if run.tracker:
            run.tracker.record_stage("files_checked")
            await self._persist_checkpoint(run)
        if not (
            result.success
            and run.task_type in _CHANGE_REQUIRED_TASK_TYPES
            and run.worktree is not None
            and not run.files_changed
        ):
            return
        logger.warning("Task %s: the run changed no files", run.task_id)
        run.result = DriverResult(
            success=False,
            output=result.output,
            error="The run changed no files, so there is nothing to verify or land",
            cost_usd=result.cost_usd,
            duration_ms=result.duration_ms,
            metadata={**(result.metadata or {}), "stop_reason": "no_change"},
        )

    async def _verify_result(self, run: _DispatchRun) -> None:
        """Steps 5-6: run the verifier chain, then act on what it found."""
        task_context = {
            "output": run.result.output,
            "task_type": run.task_type,
            "instruction": run.instruction,
            "scope_instruction": run.instruction,
            **{k: run.packet.project_context.get(k) for k in SANDBOX_SETTINGS},
            "acceptance_tests": run.acceptance_tests or [],
        }
        v_results = await verifier_chain.run_chain(run.verify_chain, run.workdir, task_context)

        # Step 5b: a mechanical auto-fix pass -- ruff --fix/--format,
        # no driver call -- before the one-bounce rule spends a real
        # (frontier) call re-dispatching a failure a formatter would
        # have resolved for free. Skipped when there's nothing to
        # gain: a clean result, or one that's only inconclusive
        # (ruff can't make a missing tool appear).
        if not verifier_chain.all_passed(v_results) and not verifier_chain.inconclusive(v_results):
            autofix = await mechanical_autofix(run.workdir, task_context)
            if autofix.get("fixed") and autofix.get("candidates"):
                logger.info(
                    "Task %s: mechanical auto-fix ran on %s, re-verifying",
                    run.task_id,
                    autofix["candidates"],
                )
                v_results = await verifier_chain.run_chain(
                    run.verify_chain, run.workdir, task_context
                )

        # Recorded once, after any auto-fix retry: the pre-fix
        # failure was transient and mechanical, not a decision worth
        # keeping a row for — attempt 2 stays reserved for the
        # post-BOUNCE (re-dispatched) re-check.
        await self._record_verification(run.tenant_id, run.task_id, 1, v_results, run.session)

        run.verifier_results = list(v_results)
        run.unverifiable = verifier_chain.inconclusive(v_results)
        if run.unverifiable:
            await self._escalate_unverifiable(run, v_results)
        elif not verifier_chain.all_passed(v_results):
            await self._bounce_or_escalate(run, v_results)
        elif run.task_type == "plan":
            await self._file_plan_spec(run)
        else:
            await self._second_opinion_review(run)

        # Step 6c: the driver's own claim of success is not evidence. Re-check
        # it against what someone other than the driver observed -- the file
        # list from the worktree's diff and the verifier chain's verdicts --
        # before Step 6b is allowed to land it as verified work. Runs last so
        # the specific failure the steps above diagnosed (dissent, bounce,
        # unverifiable) is the one the caller sees; this only ever catches a
        # run still claiming success.
        if run.result and run.result.success:
            files_changed = run.files_changed
            if files_changed is None:
                files_changed = getattr(run.result, "files_changed", None)
            verified, reason = verify_independent_completion(
                driver_claimed_success=run.result.success,
                task_type=run.task_type,
                # The verdicts that judged whatever is in run.result now: a
                # bounce replaced both the result and these.
                verifier_results=run.verifier_results,
                files_changed=files_changed,
                # Nothing to read a diff from, so an unknown file list must
                # not be reported as an empty one. The verifier half of the
                # gate still applies.
                require_file_changes_for_code=files_changed is not None,
            )
            if not verified:
                logger.warning("Task %s independent verification failed: %s", run.task_id, reason)
                # Mark unverified so it cannot land as success.
                run.result.success = False
                run.result.error = reason
                run.result.metadata = {
                    **(run.result.metadata or {}),
                    "needs_human": True,
                    "independent_verification_failed": reason,
                }

        if run.tracker:
            # The verdict, not just "the verifier ran", and only after Step 6c
            # had its say: recovery reads the last ok checkpoint, and work that
            # failed, was inconclusive or was vetoed by the independent check
            # must not read as verified after a restart.
            if run.unverifiable:
                verdict = "unverifiable"
            elif run.result is not None and run.result.success:
                verdict = "passed"
            else:
                verdict = "failed"
            metadata: dict[str, Any] = {"verdict": verdict}
            if verdict == "passed" and run.worktree is not None and run.worktree_origin:
                # Enough to land this exact work after a crash without a second
                # agent run (resume_landing): where it is, and a fingerprint
                # proving it is unchanged since it was verified.
                diff = await diff_against_head(run.workdir)
                metadata["resume"] = {
                    "head": await _head_sha(run.workdir),
                    "worktree": str(run.worktree),
                    "worktree_origin": str(run.worktree_origin),
                    "diff_sha256": hashlib.sha256(diff.encode()).hexdigest(),
                    "driver": getattr(run.driver, "name", None),
                    "verify_chain": list(run.verify_chain or []),
                    "output": (run.result.output or "")[:4000],
                    "files_changed": list(run.files_changed or []),
                }
            run.tracker.record_stage(
                "verifier_completed", ok=verdict == "passed", metadata=metadata
            )
            await self._persist_checkpoint(run)

    async def _escalate_unverifiable(
        self, run: _DispatchRun, v_results: list[VerifierResult]
    ) -> None:
        """Step 6, a check could not run: escalate without a bounce.

        An inconclusive check means the gate never ran — the tool it needs
        is not installed for this project. Re-dispatching the agent cannot
        install it, so bouncing would burn a second frontier call to reach
        the same state. Say plainly that the work was not verified rather
        than that it failed.
        """
        result = run.result
        names = ", ".join(r.verifier for r in run.unverifiable)
        logger.warning(
            "Task %s could not be verified (%s) — escalating without bounce",
            run.task_id,
            names,
        )
        await self._create_approval_entry(
            tenant_id=run.tenant_id,
            task_id=run.task_id,
            driver_name=run.driver.name,
            v_results=v_results,
            session=run.session,
        )
        run.result = DriverResult(
            success=False,
            output=result.output,
            error=f"Could not verify — checks did not run: {names}",
            cost_usd=result.cost_usd,
            duration_ms=result.duration_ms,
            metadata={
                "needs_human": True,
                "unverifiable": [asdict(r) for r in run.unverifiable],
            },
        )

    async def _bounce_or_escalate(self, run: _DispatchRun, v_results: list[VerifierResult]) -> None:
        """Step 6, a check failed: the one-bounce rule, then needs_human."""
        driver = run.driver
        await self._emit(
            EventType.VERIFICATION_FAILED,
            {
                "task_id": run.task_id,
                "driver": driver.name,
                "failures": [asdict(r) for r in v_results if not r.passed],
            },
        )

        # Bounce: re-dispatch once with failure context
        bounce_result = await self._bounce_task(
            tenant_id=run.tenant_id,
            task_id=run.task_id,
            driver=driver,
            packet=run.packet,
            workdir=run.workdir,
            failure_report=v_results,
            session=run.session,
            verify_chain=run.verify_chain,
            acceptance_tests=run.acceptance_tests,
            run=run,
        )

        if bounce_result is not None:
            run.result = bounce_result
            # The bounce re-ran the driver in this same worktree, so Step 4c's
            # file list describes the attempt before it (_bounce_task already
            # replaced run.verifier_results with its own re-verification).
            await self._observe_files_changed(run)
            return
        # Second failure → needs_human
        result = run.result
        run.result = DriverResult(
            success=False,
            output=result.output,
            error="Verification failed after bounce — needs human review",
            cost_usd=result.cost_usd,
            duration_ms=result.duration_ms,
            metadata={
                "needs_human": True,
                "verification_failures": [asdict(r) for r in v_results if not r.passed],
            },
        )
        await self._create_approval_entry(
            run.tenant_id, run.task_id, driver.name, v_results, run.session
        )

    async def _file_plan_spec(self, run: _DispatchRun) -> None:
        """Step 6, a plan passed: file its spec for human review.

        A plan dispatch passed no_diff_in_plan (genuinely no file changes),
        so the normal second-opinion-review-then-land path has nothing to
        review or land here.
        """
        await self._emit(
            EventType.VERIFICATION_PASSED,
            {"task_id": run.task_id, "driver": run.driver.name},
        )
        result = run.result
        plan_spec = _extract_spec(result.output)
        if plan_spec:
            await self._create_plan_approval(
                tenant_id=run.tenant_id,
                task_id=run.task_id,
                driver_name=run.driver.name,
                instruction=run.instruction,
                spec_text=plan_spec,
                project_id=run.project_uuid,
                persona_name=run.persona_name,
                session=run.session,
                auto_approve=bool(run.packet.project_context.get("auto_approve_plans")),
            )
            result.metadata = {**(result.metadata or {}), "spec": plan_spec}
        else:
            run.result = DriverResult(
                success=False,
                output=result.output,
                error="Plan dispatch produced no '## Spec' section to review",
                cost_usd=result.cost_usd,
                duration_ms=result.duration_ms,
                metadata={"needs_human": True},
            )

    async def _second_opinion_review(self, run: _DispatchRun) -> None:
        """Step 6, checks passed: a dissenting review before landing.

        Reads the real diff, not the driver's narrative output -- staging
        here is harmless, preserve_verified_work re-stages (a no-op) and
        commits regardless of the verdict.
        """
        driver = run.driver
        await self._emit(
            EventType.VERIFICATION_PASSED,
            {"task_id": run.task_id, "driver": driver.name},
        )
        diff_text = await diff_against_head(run.workdir)
        verdict = await self._reviewer.review(run.task_type, run.instruction, diff_text)
        if not (verdict.ran and not verdict.approved):
            return
        await self._emit(
            EventType.SECOND_OPINION_DISSENT,
            {
                "task_id": run.task_id,
                "driver": driver.name,
                "concern": verdict.concern,
            },
        )
        await self._create_dissent_approval_entry(
            run.tenant_id,
            run.task_id,
            driver.name,
            verdict.concern,
            run.session,
        )
        result = run.result
        run.result = DriverResult(
            success=False,
            output=result.output,
            error=(f"Second-opinion dissent: {verdict.concern or 'unspecified concern'}"),
            cost_usd=result.cost_usd,
            duration_ms=result.duration_ms,
            metadata={
                "needs_human": True,
                "second_opinion_concern": verdict.concern,
            },
        )

    async def _land_verified_work(self, run: _DispatchRun) -> None:
        """Step 6b: commit the verified work to a branch before cleanup.

        The worktree is created with --detach and removed unconditionally
        in dispatch_task's finally, so a verified change was deleted along
        with it: the pipeline fixed the bug, proved it with the verifier
        chain, then reported success having landed nothing. Committing
        onto a branch keeps it reachable after removal, without merging,
        pushing, or touching the default branch -- a reviewable branch is
        what the approval step needs to act on.

        An inconclusive verifier result is not a pass, but it is also not
        evidence of anything wrong -- the change was simply never checked
        (e.g. the project doesn't have the tool yet). Discarding it here
        means the only way to know the diff was ever correct is this run's
        logs; land it like verified work so a human can still review and
        merge it by hand, but never auto-open or auto-merge it -- that
        trust bar is reserved for work that was actually checked.
        """
        if not (
            (run.result.success or run.unverifiable)
            and run.worktree is not None
            and run.worktree_origin
            and settings.driver_land_verified_work
            # Re-checked: a bounce re-ran the driver after Step 4b.
            and worktree_intact(run.worktree, run.worktree_origin)
        ):
            return
        landed_branch = await preserve_verified_work(
            worktree=run.worktree,
            repo_path=run.worktree_origin,
            task_id=run.task_id,
            # The instruction states the intent; the driver's output
            # is a narrative ("Changed x: ...") that read badly as a
            # commit subject and, via squash-merge, in history.
            summary=run.instruction,
        )
        if not landed_branch:
            return
        if run.tracker:
            run.tracker.record_stage("landed", metadata={"branch": landed_branch})
            await self._persist_checkpoint(run)
        ctx = run.packet.project_context
        run.result.metadata = {**(run.result.metadata or {}), "landed_branch": landed_branch}
        await self._create_pr_approval(
            tenant_id=run.tenant_id,
            task_id=run.task_id,
            driver_name=run.driver.name,
            instruction=run.instruction,
            result=run.result,
            branch=landed_branch,
            repo_path=run.worktree_origin,
            checks=run.verify_chain,
            project_id=run.project_uuid,
            session=run.session,
            verified=not run.unverifiable,
            unverifiable_checks=[r.verifier for r in run.unverifiable],
            auto_open_pr=bool(ctx.get("auto_open_pr")),
            auto_merge=bool(ctx.get("auto_merge")),
            base_branch=ctx.get("base_branch") or None,
            change_policy=policy_from_project(ctx),
        )

    async def _finish_dispatch(self, run: _DispatchRun) -> None:
        """Step 7: record stats and emit the result event."""
        if run.tracker:
            # ok mirrors the outcome: a crash between here and the row's final
            # status write must not turn a failed dispatch into "completed".
            succeeded = bool(run.result is not None and run.result.success)
            run.tracker.record_stage("finished", ok=succeeded, metadata={"success": succeeded})
            await self._persist_checkpoint(run)
        result = run.result
        if run.spec_text:
            result.metadata = {**(result.metadata or {}), "spec": run.spec_text}
        await self._record_stats(run.tenant_id, run.driver.name, run.task_type, result, run.session)

        await self._emit(
            EventType.DRIVER_RESULT,
            {
                "task_id": run.task_id,
                "driver": run.driver.name,
                "success": result.success,
                "cost_usd": result.cost_usd,
                "duration_ms": result.duration_ms,
                "landed_branch": (result.metadata or {}).get("landed_branch"),
            },
        )

    async def _select_driver(
        self,
        task_type: str,
        persona_name: str | None,
        tenant_id: str,
        session: AsyncSession,
        persona=None,
        project_id: uuid.UUID | None = None,
    ):
        """Select the best driver for a task.

        Selection logic:
        1. Persona pin (if persona specifies a driver; ``"auto"`` means none)
        2. Cheapest capable trusted driver (success rate >= 0.6), skipping any
           driver whose work on *this project* has an established poor record
           (merged/rejected/closed outcomes — see ``services/dev_outcomes``)
        3. Fallback to 'local'

        Args:
            persona: Optional pre-resolved ``AgentPersona`` row (see
                ``_load_persona``) — passed by ``dispatch_task`` so the persona
                is looked up once per dispatch rather than twice.

        Returns:
            An AgentDriver instance.

        Raises:
            DispatchError: If no driver is available.
        """
        # 1. Check persona pin
        if persona_name:
            try:
                if persona is None:
                    persona = await self._load_persona(tenant_id, persona_name, session)
                if persona is not None:
                    # agent_personas.driver is a real column (migration 021).
                    # This read only looked in `properties`, which the seeder
                    # leaves as {}, so the pin was always None and both
                    # driver-pinned personas -- uzhavu-ops and
                    # dependency-updater, the two that exist specifically to
                    # run on claude_code -- silently fell through to
                    # cheapest-capable selection instead. The properties
                    # lookup stays as a fallback for personas configured that
                    # way by hand.
                    pinned_driver = getattr(persona, "driver", None) or (
                        (persona.properties or {}).get("driver")
                    )
                    if pinned_driver and pinned_driver != AUTO_DRIVER:
                        driver = driver_registry.get(pinned_driver)
                        if driver and await driver.available():
                            logger.info("Persona %s pins driver %s", persona_name, pinned_driver)
                            return driver
                        if driver and getattr(driver, "pin_required", False):
                            # The cloud driver: falling through would run its
                            # persona's model on another driver, outside the
                            # free-only, no-personal-data rules.
                            raise DispatchError(
                                f"Persona {persona_name} pins driver {pinned_driver}, "
                                "which is not available"
                            )
            except DispatchError:
                raise
            except Exception:
                logger.warning("Failed to check persona driver pin", exc_info=True)

        # 2. Cheapest capable trusted driver
        capable = driver_registry.available_for_task(task_type)
        available = []
        for d in capable:
            try:
                if await d.available():
                    available.append(d)
            except Exception:
                continue

        if available:
            # Sort by cost (cheapest first)
            available.sort(key=lambda d: d.cost_per_task())

            # What the user did with a driver's work on this project outranks
            # whether that work passed the checks: a free driver whose PRs keep
            # getting rejected here is not the cheap option.
            if project_id is not None:
                from life_graph.services.dev.outcomes import track_record

                kept = []
                for d in available:
                    record = await track_record(session, tenant_id, d.name, project_id)
                    if record["established"] and record["merge_rate"] < POOR_MERGE_RATE:
                        logger.info(
                            "Skipping driver %s for project %s: %d/%d merged",
                            d.name,
                            project_id,
                            record["merged"],
                            record["total"],
                        )
                        continue
                    kept.append(d)
                available = kept

            # Check trust scores from stats
            for d in available:
                stats = await self._get_driver_stats(tenant_id, d.name, session)
                success_rate = stats.get("success_rate", 1.0)
                if success_rate >= MIN_TRUST_THRESHOLD:
                    return d

        # 3. Fallback to 'local'
        local = driver_registry.get("local")
        if local and await local.available():
            return local

        raise DispatchError(f"No driver available for task type '{task_type}'")

    async def _bounce_task(
        self,
        tenant_id: str,
        task_id: str,
        driver,
        packet: ContextPacket,
        workdir: Path,
        failure_report: list[VerifierResult],
        session: AsyncSession,
        verify_chain: list[str],
        acceptance_tests: list[str] | None = None,
        run: _DispatchRun | None = None,
    ) -> DriverResult | None:
        """Re-dispatch once with failure context appended to instruction.

        Returns:
            DriverResult if bounce succeeded verification, None if it also failed.
        """
        failures = [failure_text(r) for r in failure_report if not r.passed]
        # The failures first, and the work so far stated as done: with the task
        # first, OpenCode re-read it, found its change already in place and
        # stopped without touching the lint error it was sent back for (task
        # 5c760cb6, 2026-10-17).
        bounce_instruction = (
            "Your previous attempt at this task is already in the working tree. It"
            " failed these checks:\n\n" + "\n".join(failures) + "\n\n"
            "Fix exactly these problems in the files as they are now; do not start"
            " over. When the fix is in, stop.\n\n"
            f"{BOUNCE_TASK_MARKER}\n{packet.instruction}"
        )

        # Update packet with bounce instruction
        bounced_packet = ContextPacket(
            task_id=packet.task_id,
            tenant_id=packet.tenant_id,
            task_type=packet.task_type,
            instruction=bounce_instruction,
            project_context=packet.project_context,
            procedures=packet.procedures,
            preferences=packet.preferences,
            memories=packet.memories,
            calibration_profile=packet.calibration_profile,
            max_tokens=packet.max_tokens,
            private=packet.private,
            # Carry the persona scoping across the bounce — dropping
            # allowed_tools here would silently hand the retry the full tool
            # registry (including the host shell).
            persona_system_prompt=packet.persona_system_prompt,
            allowed_tools=packet.allowed_tools,
            persona_model=packet.persona_model,
        )

        await self._emit(
            EventType.TASK_BOUNCED,
            {
                "task_id": task_id,
                "driver": driver.name,
                "failures": [r.verifier for r in failure_report if not r.passed],
            },
        )

        # Re-dispatch
        bounce_result = await driver.dispatch(
            bounced_packet, workdir, timeout=_driver_timeout(driver, run)
        )
        await self._emit_steps(tenant_id, task_id, driver.name, 2, bounce_result)

        if not bounce_result.success:
            return None

        # Re-verify -- against the same acceptance tests as the first attempt,
        # or a bounce would quietly drop the check it was bounced for.
        task_context = {
            "output": bounce_result.output,
            "task_type": packet.task_type,
            "instruction": bounce_instruction,
            # The original task, not the bounce text: its failure output names
            # unrelated paths that would widen diff_within_scope.
            "scope_instruction": packet.instruction,
            **{k: packet.project_context.get(k) for k in SANDBOX_SETTINGS},
            "acceptance_tests": acceptance_tests or [],
        }
        v_results = await verifier_chain.run_chain(verify_chain, workdir, task_context)
        # The same free ruff pass as before the bounce: the retry's own lint
        # (an unsorted import, task 144b5ed2) is no reason to fail it.
        if not verifier_chain.all_passed(v_results) and not verifier_chain.inconclusive(v_results):
            autofix = await mechanical_autofix(workdir, task_context)
            if autofix.get("fixed") and autofix.get("candidates"):
                v_results = await verifier_chain.run_chain(verify_chain, workdir, task_context)
        await self._record_verification(tenant_id, task_id, 2, v_results, session)

        if run is not None:
            # These supersede the pre-bounce verdicts: they are the checks that
            # actually judged bounce_result.
            run.verifier_results = list(v_results)

        if verifier_chain.all_passed(v_results):
            await self._emit(
                EventType.VERIFICATION_PASSED,
                {"task_id": task_id, "driver": driver.name, "bounce": True},
            )
            return bounce_result

        return None

    async def _record_verification(
        self,
        tenant_id: str,
        task_id: str,
        attempt: int,
        v_results: list[VerifierResult],
        session: AsyncSession,
    ) -> None:
        """Persist one verifier-chain run (attempt 2 is the post-bounce re-check).

        ``verification_runs.task_id`` references ``agent_tasks``, so a run is
        recorded only for dispatches that have a task row (dashboard dev tasks);
        the test endpoint's throwaway ids have none. Best-effort, in a
        savepoint: failing to record must never fail the dispatch.
        """
        for r in v_results:
            verdict = (
                "passed" if r.passed is True else "inconclusive" if r.passed is None else "failed"
            )
            task_events.emit(
                tenant_id, task_id, "verify", f"{r.verifier}: {verdict}",
                data={"verifier": r.verifier, "verdict": verdict, "attempt": attempt},
                source="verifier",
            )  # fmt: skip
        try:
            from life_graph.models.db import AgentTask, VerificationRun

            pk = uuid.UUID(str(task_id))
            if await session.get(AgentTask, pk) is None:
                return
            async with session.begin_nested():
                session.add(
                    VerificationRun(
                        tenant_id=tenant_id,
                        task_id=pk,
                        attempt=attempt,
                        passed=verifier_chain.all_passed(v_results),
                        results=[asdict(r) for r in v_results],
                    )
                )
        except Exception:
            logger.warning("Could not record verification run for %s", task_id, exc_info=True)

    async def _emit_steps(
        self, tenant_id: str, task_id: Any, driver_name: str, attempt: int, result: DriverResult
    ) -> None:
        """Hand one attempt's steps to the trajectory recorder.

        Popped off the result, not copied: the metadata is later merged into
        the task row, and a run's steps (hundreds, some large) belong in
        agent_run_steps, not in AgentTask.properties.
        """
        if result.metadata is not None:
            # Which driver produced this: the scorecards group by it.
            result.metadata.setdefault("driver", driver_name)
        steps = (result.metadata or {}).pop("steps", None)
        if not steps:
            return
        await self._emit(
            EventType.DRIVER_STEPS,
            {
                "tenant_id": tenant_id,
                "task_id": str(task_id),
                "driver": driver_name,
                "attempt": attempt,
                "steps": steps,
            },
        )

    async def _emit(self, event_type: EventType, payload: dict) -> None:
        """Emit an event if event_bus is available."""
        if self._event_bus:
            try:
                await self._event_bus.emit(event_type, payload, source="dispatcher")
            except Exception:
                logger.debug("Failed to emit event %s", event_type, exc_info=True)
