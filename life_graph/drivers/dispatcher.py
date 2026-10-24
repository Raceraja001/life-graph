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
import logging
import re
import tempfile
import uuid
from dataclasses import asdict
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
    preserve_verified_work,
    remove_worktree,
    resolve_workdir,
    worktree_intact,
)
from life_graph.services.change_policy import policy_from_project
from life_graph.services.governor import governor
from life_graph.services.verifiers import (  # noqa: F401  (failure_text: re-exported)
    BOUNCE_TASK_MARKER,
    VerifierResult,
    failure_text,
    mechanical_autofix,
    verifier_chain,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────

DEFAULT_COST_CAP_USD = 2.0
MIN_TRUST_THRESHOLD = 0.6
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
    # Thresholds for the proof checks (services/proof_checks.py).
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
        from life_graph.services.code_graph import build_graph, context_for

        graph = await asyncio.wait_for(
            asyncio.to_thread(build_graph, workdir), timeout=_CODE_CONTEXT_TIMEOUT_SECONDS
        )
        return context_for(graph, instruction)
    except Exception:
        logger.warning("Could not build code context for %s", workdir, exc_info=True)
        return ""


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

        Backed by PR-Agent (services/pr_agent_review.py), which reads the
        actual diff rather than the driver's narrative account of it —
        same settings surface (driver_second_opinion_enabled/_model) the
        older thin LLM-skim reviewer used, same gate position.
        """
        from life_graph.config import settings
        from life_graph.services.pr_agent_review import PRAgentReviewer

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
    ) -> DriverResult:
        """Dispatch a task through the full driver pipeline.

        Steps:
        1. Check WIP limits
        2. Build context packet
        3. Select driver
        4. Dispatch with timeout
        5. Run verifier chain
        6. If failed: bounce once, then needs_human
        7. Record stats + emit events

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
        # verify_chain is resolved after the persona loads (Step 2b): the
        # precedence is caller argument > persona.verifier_chain > default.
        caller_verify_chain = verify_chain

        owns_session = session is None
        if owns_session:
            session = self._session_factory()

        worktree = None
        worktree_origin: str | None = None

        try:
            # Normalize the project id ONCE, before both consumers (WIP check
            # and packet build) — callers may pass a non-UUID pseudo-project.
            project_uuid = _coerce_project_uuid(project_id)

            # Step 1: Check WIP limits
            await self._check_wip_limits(tenant_id, project_uuid, session, exclude_task_id=task_id)

            # Step 2: Build context packet
            packet = await self._context_builder.build_packet(
                tenant_id=tenant_id,
                task_type=task_type,
                instruction=instruction,
                project_id=project_uuid,
                session=session,
                private=private,
            )
            # Override the task_id from the caller
            packet.task_id = uuid.UUID(task_id) if isinstance(task_id, str) else task_id

            if task_type == "plan":
                packet.instruction = _PLAN_ONLY_PREFIX + packet.instruction
            elif spec_first:
                packet.instruction = _SPEC_FIRST_PREFIX + packet.instruction

            # Step 2b: Resolve the pinned persona ONCE (reused for driver
            # selection below) and scope the packet to it. Without this the
            # driver would run with the FULL tool registry — including the
            # host shell (`run_command`) — for an unattended dispatch.
            persona = await self._load_persona(tenant_id, persona_name, session)
            if persona is not None:
                packet.persona_system_prompt = getattr(persona, "system_prompt", None)
                allowed = getattr(persona, "allowed_tools", None)
                packet.allowed_tools = list(allowed) if allowed is not None else None
                packet.persona_model = getattr(persona, "model", None) or None
            if task_type == "plan":
                # Prompting alone didn't hold (see _PLAN_ONLY_PREFIX); take
                # the write tools away too. An unscoped or write-only persona
                # still gets file_read, since a plan needs to read the code.
                read = [t for t in (packet.allowed_tools or []) if t in _PLAN_READ_TOOLS]
                packet.allowed_tools = read or ["file_read"]

            # A persona declares the checks its own work must clear —
            # dependency-updater asks for tests_pass because its whole job is
            # "run the project's tests before landing". Nothing read that
            # column, so it landed on the generic default instead and its
            # tests never ran. An explicit caller argument still wins.
            verify_chain = _resolve_verify_chain(caller_verify_chain, persona)
            verify_chain = _with_required_checks(verify_chain, packet.project_context)
            # A task fanned out from a plan carries the tests bound to the
            # acceptance criteria it cites -- check those specifically, on
            # top of whatever chain the persona/project asked for.
            if acceptance_tests and "acceptance_tests_pass" not in verify_chain:
                verify_chain = [*verify_chain, "acceptance_tests_pass"]

            # Step 2c: opt-in workdir isolation — only when the caller asked
            # for it AND a real project path resolved. A no-op flag on a
            # personaless/projectless dispatch (today's exact behavior).
            if isolate_workdir and packet.project_context.get("path"):
                packet.project_context["isolation"] = True

            # Step 3: Select driver
            driver = await self._select_driver(
                task_type,
                persona_name,
                tenant_id,
                session,
                persona=persona,
                project_id=project_uuid,
            )

            # Step 3b: Governor budget gate — refuse before spending, not after.
            # Autonomous dispatches are throttled/denied when the monthly budget
            # is exhausted; interactive (user-initiated) tasks are never blocked.
            # The cap governs paid API spend only: a run whose every model is
            # local (Ollama) cannot spend, so it is never denied.
            decision = await governor.authorize(
                tenant_id,
                BudgetCategory.DRIVER,
                estimated_usd=driver.cost_per_task(),
                interactive=interactive or runs_on_local_model(driver.name, packet.persona_model),
            )
            if not decision.allowed:
                logger.warning(
                    "Task %s denied by Governor: %s (spent $%.2f / $%.2f)",
                    task_id,
                    decision.reason,
                    decision.spent_usd,
                    decision.cap_usd,
                )
                await self._emit(
                    EventType.DRIVER_DISPATCHED,
                    {
                        "task_id": task_id,
                        "driver": driver.name,
                        "task_type": task_type,
                        "tenant_id": tenant_id,
                        "budget_denied": True,
                    },
                )
                return DriverResult(
                    success=False,
                    error=f"budget: {decision.reason}",
                    metadata={"budget_throttled": True, "reason": decision.reason},
                )

            # Emit dispatch event
            await self._emit(
                EventType.DRIVER_DISPATCHED,
                {
                    "task_id": task_id,
                    "driver": driver.name,
                    "task_type": task_type,
                    "tenant_id": tenant_id,
                },
            )

            # Step 4: Dispatch with workdir
            scratch = Path(
                tempfile.mkdtemp(
                    prefix=f"lg_dispatch_{task_id[:8]}_", dir=tenant_scratch_root(tenant_id)
                )
            )
            workdir, worktree = await resolve_workdir(packet, scratch)
            if worktree is not None:
                worktree_origin = packet.project_context.get("path")
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
                packet.project_context["path"] = str(workdir)
                packet.project_context["isolation"] = False
                # Step 4a: where the symbols the instruction names are defined
                # and who calls them, from this worktree's own code.
                code_context = await _code_context(workdir, instruction)
                if code_context:
                    packet.instruction += (
                        "\n\n--- CODE CONTEXT (where the symbols named above are "
                        "defined and used in this project) ---\n"
                        f"{code_context}\n"
                        "Check these callers before changing a signature or return shape."
                    )
            result = await driver.dispatch(
                packet, workdir, timeout=getattr(driver, "dispatch_timeout", 300)
            )
            await self._emit_steps(tenant_id, task_id, driver.name, 1, result)
            # Captured here, before later steps replace `result` with fresh
            # DriverResult instances (verification failure, dissent, ...)
            # that don't carry the original metadata forward — merged back
            # in at Step 7 regardless of how the task ultimately resolved.
            spec_text = _extract_spec(result.output) if spec_first else None

            # Book the actual spend into the Governor's ledger.
            await governor.record(tenant_id, BudgetCategory.DRIVER, result.cost_usd)

            # Secondary per-task guard (the Governor is the primary budget gate).
            if result.cost_usd > cost_cap_usd:
                logger.warning(
                    "Task %s exceeded per-task cost cap: $%.2f > $%.2f",
                    task_id,
                    result.cost_usd,
                    cost_cap_usd,
                )

            # Step 4b: The driver must not have swapped the worktree's .git
            # link. Verifier and landing git commands run on the host inside
            # this directory; a planted .git dir would carry its own config
            # (filters, fsmonitor) and make them execute agent-chosen programs.
            if (
                result.success
                and worktree is not None
                and worktree_origin
                and not worktree_intact(worktree, worktree_origin)
            ):
                logger.error("Task %s: worktree .git link was tampered with", task_id)
                tamper = VerifierResult(
                    "worktree_intact",
                    False,
                    {"error": "worktree .git no longer links to the origin repository"},
                )
                await self._create_approval_entry(
                    tenant_id, task_id, driver.name, [tamper], session
                )
                result = DriverResult(
                    success=False,
                    output=result.output,
                    error="Worktree .git was modified by the driver — not verified or landed",
                    cost_usd=result.cost_usd,
                    duration_ms=result.duration_ms,
                    metadata={"needs_human": True, "worktree_tampered": True},
                )

            # Step 4c: a coding task that left no file changed did not do the
            # task. Every diff-scoped verifier passes vacuously on an empty
            # diff, so this used to finish as "completed": task ade60cc6
            # (2026-10-18) added one import, ruff's autofix removed it as
            # unused, and nothing else was ever written.
            if (
                result.success
                and task_type in ("code", "code_change")
                and worktree is not None
                and not await diff_against_head(worktree)
            ):
                logger.warning("Task %s: the run changed no files", task_id)
                result = DriverResult(
                    success=False,
                    output=result.output,
                    error="The run changed no files, so there is nothing to verify or land",
                    cost_usd=result.cost_usd,
                    duration_ms=result.duration_ms,
                    metadata={**(result.metadata or {}), "stop_reason": "no_change"},
                )

            # Step 5: Run verifier chain
            unverifiable: list[VerifierResult] = []
            if verify_chain and result.success:
                task_context = {
                    "output": result.output,
                    "task_type": task_type,
                    "instruction": instruction,
                    "scope_instruction": instruction,
                    **{k: packet.project_context.get(k) for k in SANDBOX_SETTINGS},
                    "acceptance_tests": acceptance_tests or [],
                }
                v_results = await verifier_chain.run_chain(verify_chain, workdir, task_context)

                # Step 5b: a mechanical auto-fix pass -- ruff --fix/--format,
                # no driver call -- before the one-bounce rule spends a real
                # (frontier) call re-dispatching a failure a formatter would
                # have resolved for free. Skipped when there's nothing to
                # gain: a clean result, or one that's only inconclusive
                # (ruff can't make a missing tool appear).
                if not verifier_chain.all_passed(v_results) and not verifier_chain.inconclusive(
                    v_results
                ):
                    autofix = await mechanical_autofix(workdir, task_context)
                    if autofix.get("fixed") and autofix.get("candidates"):
                        logger.info(
                            "Task %s: mechanical auto-fix ran on %s, re-verifying",
                            task_id,
                            autofix["candidates"],
                        )
                        v_results = await verifier_chain.run_chain(
                            verify_chain, workdir, task_context
                        )

                # Recorded once, after any auto-fix retry: the pre-fix
                # failure was transient and mechanical, not a decision worth
                # keeping a row for — attempt 2 stays reserved for the
                # post-BOUNCE (re-dispatched) re-check.
                await self._record_verification(tenant_id, task_id, 1, v_results, session)

                # An inconclusive check means the gate never ran — the tool it
                # needs is not installed for this project. Re-dispatching the
                # agent cannot install it, so bouncing would burn a second
                # frontier call to reach the same state. Escalate directly,
                # and say plainly that the work was not verified rather than
                # that it failed.
                unverifiable = verifier_chain.inconclusive(v_results)
                if unverifiable:
                    names = ", ".join(r.verifier for r in unverifiable)
                    logger.warning(
                        "Task %s could not be verified (%s) — escalating without bounce",
                        task_id,
                        names,
                    )
                    await self._create_approval_entry(
                        tenant_id=tenant_id,
                        task_id=task_id,
                        driver_name=driver.name,
                        v_results=v_results,
                        session=session,
                    )
                    result = DriverResult(
                        success=False,
                        output=result.output,
                        error=f"Could not verify — checks did not run: {names}",
                        cost_usd=result.cost_usd,
                        duration_ms=result.duration_ms,
                        metadata={
                            "needs_human": True,
                            "unverifiable": [asdict(r) for r in unverifiable],
                        },
                    )
                elif not verifier_chain.all_passed(v_results):
                    # Step 6: One-bounce rule
                    await self._emit(
                        EventType.VERIFICATION_FAILED,
                        {
                            "task_id": task_id,
                            "driver": driver.name,
                            "failures": [asdict(r) for r in v_results if not r.passed],
                        },
                    )

                    # Bounce: re-dispatch once with failure context
                    bounce_result = await self._bounce_task(
                        tenant_id=tenant_id,
                        task_id=task_id,
                        driver=driver,
                        packet=packet,
                        workdir=workdir,
                        failure_report=v_results,
                        session=session,
                        verify_chain=verify_chain,
                        acceptance_tests=acceptance_tests,
                    )

                    if bounce_result is not None:
                        result = bounce_result
                    else:
                        # Second failure → needs_human
                        result = DriverResult(
                            success=False,
                            output=result.output,
                            error="Verification failed after bounce — needs human review",
                            cost_usd=result.cost_usd,
                            duration_ms=result.duration_ms,
                            metadata={
                                "needs_human": True,
                                "verification_failures": [
                                    asdict(r) for r in v_results if not r.passed
                                ],
                            },
                        )
                        await self._create_approval_entry(
                            tenant_id, task_id, driver.name, v_results, session
                        )
                elif task_type == "plan":
                    # A plan dispatch passed no_diff_in_plan (genuinely no file
                    # changes) -- file the spec for human review instead of the
                    # normal second-opinion-review-then-land path, which has
                    # nothing to review or land here.
                    await self._emit(
                        EventType.VERIFICATION_PASSED,
                        {"task_id": task_id, "driver": driver.name},
                    )
                    plan_spec = _extract_spec(result.output)
                    if plan_spec:
                        await self._create_plan_approval(
                            tenant_id=tenant_id,
                            task_id=task_id,
                            driver_name=driver.name,
                            instruction=instruction,
                            spec_text=plan_spec,
                            project_id=project_uuid,
                            persona_name=persona_name,
                            session=session,
                            auto_approve=bool(packet.project_context.get("auto_approve_plans")),
                        )
                        result.metadata = {**(result.metadata or {}), "spec": plan_spec}
                    else:
                        result = DriverResult(
                            success=False,
                            output=result.output,
                            error="Plan dispatch produced no '## Spec' section to review",
                            cost_usd=result.cost_usd,
                            duration_ms=result.duration_ms,
                            metadata={"needs_human": True},
                        )
                else:
                    await self._emit(
                        EventType.VERIFICATION_PASSED,
                        {"task_id": task_id, "driver": driver.name},
                    )

                    # Step 6b: Second-opinion dissenting review before landing.
                    # Reads the real diff, not the driver's narrative output --
                    # staging here is harmless, preserve_verified_work below
                    # re-stages (a no-op) and commits regardless of the verdict.
                    diff_text = await diff_against_head(workdir)
                    verdict = await self._reviewer.review(task_type, instruction, diff_text)
                    if verdict.ran and not verdict.approved:
                        await self._emit(
                            EventType.SECOND_OPINION_DISSENT,
                            {
                                "task_id": task_id,
                                "driver": driver.name,
                                "concern": verdict.concern,
                            },
                        )
                        await self._create_dissent_approval_entry(
                            tenant_id,
                            task_id,
                            driver.name,
                            verdict.concern,
                            session,
                        )
                        result = DriverResult(
                            success=False,
                            output=result.output,
                            error=(
                                "Second-opinion dissent: "
                                f"{verdict.concern or 'unspecified concern'}"
                            ),
                            cost_usd=result.cost_usd,
                            duration_ms=result.duration_ms,
                            metadata={
                                "needs_human": True,
                                "second_opinion_concern": verdict.concern,
                            },
                        )

            # Step 6b: Land the verified work before cleanup can discard it.
            #
            # The worktree is created with --detach and removed unconditionally
            # in the finally below, so a verified change was deleted along with
            # it: the pipeline fixed the bug, proved it with the verifier
            # chain, then reported success having landed nothing. Committing
            # onto a branch keeps it reachable after removal, without merging,
            # pushing, or touching the default branch -- a reviewable branch is
            # what the approval step needs to act on.
            # An inconclusive verifier result is not a pass, but it is also not
            # evidence of anything wrong -- the change was simply never
            # checked (e.g. the project doesn't have the tool yet). Discarding
            # it here means the only way to know the diff was ever correct is
            # this run's logs; land it like verified work so a human can
            # still review and merge it by hand, but never auto-open or
            # auto-merge it -- that trust bar is reserved for work that was
            # actually checked.
            if (
                (result.success or unverifiable)
                and worktree is not None
                and worktree_origin
                and settings.driver_land_verified_work
                # Re-checked: a bounce re-ran the driver after Step 4b.
                and worktree_intact(worktree, worktree_origin)
            ):
                landed_branch = await preserve_verified_work(
                    worktree=worktree,
                    repo_path=worktree_origin,
                    task_id=task_id,
                    # The instruction states the intent; the driver's output
                    # is a narrative ("Changed x: ...") that read badly as a
                    # commit subject and, via squash-merge, in history.
                    summary=instruction,
                )
                if landed_branch:
                    result.metadata = {**(result.metadata or {}), "landed_branch": landed_branch}
                    await self._create_pr_approval(
                        tenant_id=tenant_id,
                        task_id=task_id,
                        driver_name=driver.name,
                        instruction=instruction,
                        result=result,
                        branch=landed_branch,
                        repo_path=worktree_origin,
                        checks=verify_chain,
                        project_id=project_uuid,
                        session=session,
                        verified=not unverifiable,
                        unverifiable_checks=[r.verifier for r in unverifiable],
                        auto_open_pr=bool(packet.project_context.get("auto_open_pr")),
                        auto_merge=bool(packet.project_context.get("auto_merge")),
                        base_branch=packet.project_context.get("base_branch") or None,
                        change_policy=policy_from_project(packet.project_context),
                    )

            # Step 7: Record stats + emit result
            if spec_text:
                result.metadata = {**(result.metadata or {}), "spec": spec_text}
            await self._record_stats(tenant_id, driver.name, task_type, result, session)

            await self._emit(
                EventType.DRIVER_RESULT,
                {
                    "task_id": task_id,
                    "driver": driver.name,
                    "success": result.success,
                    "cost_usd": result.cost_usd,
                    "duration_ms": result.duration_ms,
                    "landed_branch": (result.metadata or {}).get("landed_branch"),
                },
            )

            if owns_session:
                await session.commit()

            return result

        except Exception as e:
            if owns_session:
                await session.rollback()
            logger.error("Dispatch failed for task %s: %s", task_id, e, exc_info=True)
            raise
        finally:
            if worktree is not None:
                # Run the removal from the ORIGIN repo: packet.project_context
                # ["path"] now points at the worktree itself (see Step 4), and
                # git refuses to delete a worktree from inside it.
                await remove_worktree(packet, worktree, repo_path=worktree_origin)
            if owns_session:
                await session.close()

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
                from life_graph.services.dev_outcomes import track_record

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
            bounced_packet, workdir, timeout=getattr(driver, "dispatch_timeout", 300)
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
