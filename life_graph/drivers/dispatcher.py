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
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from life_graph.autonomy.safety.classifier import RiskLevel
from life_graph.config import settings
from life_graph.core.budget import BudgetCategory
from life_graph.core.events import EventBus, EventType
from life_graph.drivers.base import ContextPacket, DriverResult
from life_graph.drivers.context import ContextPacketBuilder
from life_graph.drivers.registry import driver_registry
from life_graph.drivers.workdir import (
    diff_against_head,
    preserve_verified_work,
    remove_worktree,
    resolve_workdir,
    worktree_intact,
)
from life_graph.services.governor import governor
from life_graph.services.verifiers import VerifierResult, mechanical_autofix, verifier_chain

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────

MAX_WIP_PER_PROJECT = 2
MAX_WIP_PER_TENANT = 5
DEFAULT_COST_CAP_USD = 2.0
MIN_TRUST_THRESHOLD = 0.6
# A persona whose driver is "auto" lets the dispatcher choose per project.
AUTO_DRIVER = "auto"
# Below this merge rate (once established) a driver is skipped for a project.
POOR_MERGE_RATE = 0.5
# At or above this merge rate (once established) a project that opted into
# auto_open_pr gets its PRs opened without the "Open PR" approval.
AUTO_PR_MERGE_RATE = 0.8
# Diff-scoped on purpose: the whole-repo variants lint every file in the
# project, so on any codebase with pre-existing debt they fail on files the
# agent never touched. That is not a verdict on the change — it bounced the
# task once (a wasted frontier call) and then escalated to needs_human, every
# time, forever. A verifier chain judges the diff; a persona may ask for
# something stricter via its own verifier_chain.
#
# no_secrets_in_diff and no_vulnerable_deps_in_diff are in the default
# chain, not opt-in like most other checks — see _ALWAYS_ON_CHECKS below,
# which is what actually guarantees they run even for a persona that picks
# its own chain; listed here too so the default chain reads as complete on
# its own.
DEFAULT_VERIFY_CHAIN = [
    "build_ok_diff",
    "lint_clean_diff",
    "no_secrets_in_diff",
    "no_vulnerable_deps_in_diff",
]


# spec_first: ask the driver to write its plan before touching anything,
# spec-driven-development style (requirements → design → tasks), in the
# same call rather than a separate pre-pass — no extra driver cost, no new
# pause-for-approval architecture, most of the benefit (a reviewable plan,
# a forcing function against misreading the instruction) for one-file's
# worth of code.
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
)


_SPEC_HEADINGS = (
    "## Spec\n"
    "**Requirements:** the acceptance criteria this change must satisfy, one "
    "per line, each with an id and the pytest test that will prove it, "
    "exactly like:\n"
    "AC-1: <what must be true> — test: tests/unit/test_example.py::test_name\n"
    "**Design:** the approach, in a sentence or two.\n"
    "**Tasks:** a numbered list of the concrete steps you will take. End each "
    'task with the criteria it satisfies, e.g. "1. Add the parser (AC-1)". A '
    "task that cites a criterion also writes or updates that criterion's test.\n\n"
)
_SPEC_FIRST_PREFIX = (
    "Before changing anything, write a short spec as the FIRST part of "
    "your response, using exactly these headings:\n"
    + _SPEC_HEADINGS
    + "Then implement it. Keep the spec to a few lines total — it's a plan, "
    "not documentation.\n\n---\n\n"
)
# A plan task's spec is the whole job. Reusing _SPEC_FIRST_PREFIX ("...Then
# implement it.") had a claude_code plan run write the full feature, which
# no_diff_in_plan then rightly rejected.
_PLAN_ONLY_PREFIX = (
    "This is a PLAN-ONLY task for human review: do NOT create, edit or delete "
    "any file. Read the code as much as you need to plan well, then reply with "
    "a spec using exactly these headings, and nothing else:\n"
    + _SPEC_HEADINGS
    + "Rules for the Tasks list:\n"
    "- Every task changes something (code, tests or docs). No task that only "
    "runs checks: lint and tests run automatically after every task, and a "
    "check-only task is dropped.\n"
    "- When a change makes a generated file stale (an inventory or state doc, "
    "a lockfile, generated types), regenerate it inside that same task.\n"
    "- Keep tasks few: each one is a separate run, review and merge.\n\n"
    "Stop after the spec. The tasks run later, one at a time, after this plan "
    "is approved.\n\n---\n\n"
)
# Plan tasks keep only the tools that read. Anything mapping to a write or a
# shell (file_write, code_edit, run_command, and the git_* tools, which the
# claude_code driver maps to a full Bash) is dropped for the plan stage.
_PLAN_READ_TOOLS = frozenset(
    {
        "file_read",
        "code_read",
        "code_search",
        "code_list",
        "web_search",
        "browse_web",
        "memory_search",
    }
)
_SPEC_SECTION_RE = re.compile(r"##\s*Spec\b(.*?)(?:\n##\s|\Z)", re.DOTALL | re.IGNORECASE)


def _extract_spec(output: str | None) -> str | None:
    """Pull the ``## Spec`` section out of a driver's narrative output, if any."""
    if not output:
        return None
    match = _SPEC_SECTION_RE.search(output)
    return match.group(1).strip() or None if match else None


_TASKS_SECTION_RE = re.compile(r"\*\*Tasks:?\*\*\s*(.*)", re.DOTALL | re.IGNORECASE)
# A candidate list marker: "3." or "3)" at the start or after whitespace, then
# whitespace. Only the next expected number counts (see _parse_tasks), so a
# "(default 5, max 20)" inside task 1 is text, not task 20.
_TASK_MARKER_RE = re.compile(r"(?:^|(?<=\s))(\d+)[.)](?=\s)")
_PLAN_SPEC_MAX_CHARS = 50_000
_BOLD_HEADING_RE = re.compile(r"\*\*[A-Za-z][\w -]*:?\*\*")


def _parse_tasks(spec_text: str | None) -> list[str]:
    """Pull the numbered task list out of a spec's ``**Tasks:**`` section.

    Tolerates both inline ("1. x 2. y") and multi-line numbering — the
    model's own formatting varies and neither is wrong. Returns ``[]`` when
    no numbered list is found, so callers fall back to a single combined
    dispatch rather than fanning out on a guess.
    """
    if not spec_text:
        return []
    section = _TASKS_SECTION_RE.search(spec_text)
    if not section:
        return []
    block = section.group(1)
    # Stop at the next bold heading, if the model added one after Tasks.
    block = _BOLD_HEADING_RE.split(block)[0]
    starts = []
    for marker in _TASK_MARKER_RE.finditer(block):
        if int(marker.group(1)) == len(starts) + 1:
            starts.append(marker)
    items = []
    for i, marker in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(block)
        text = block[marker.end() : end].strip()
        if text:
            items.append(text)
    return items


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


class DispatchError(Exception):
    """Raised when a dispatch cannot proceed."""


def _coerce_project_uuid(project_id: str | uuid.UUID | None) -> uuid.UUID | None:
    """Best-effort ``project_id`` → ``uuid.UUID``; ``None`` when not a real UUID.

    Not every caller has a real ``projects`` row: the ambient action pipeline
    stamps its proposals with the pseudo-project ``"ambient"``
    (``life_graph/services/action_proposal_bridge.py::AMBIENT_PROJECT_ID``),
    which is a plain string. Parsing that with ``uuid.UUID()`` raises
    ``ValueError`` and would abort the whole dispatch, so a non-UUID project id
    degrades to "no project context" instead of crashing.
    """
    if project_id is None:
        return None
    if isinstance(project_id, uuid.UUID):
        return project_id
    try:
        return uuid.UUID(str(project_id))
    except (ValueError, AttributeError, TypeError):
        logger.warning(
            "dispatch: project_id %r is not a UUID — treating as no project",
            project_id,
        )
        return None


# Appended unconditionally in _with_required_checks, after persona/caller
# resolution — a persona picking its own verifier_chain (personas.py has
# several) opts out of the default chain, but must not thereby opt out of
# these. Unlike required_checks these are not project-configurable: there
# is no legitimate reason for any project to dispatch without them.
#
# no_vulnerable_deps_in_diff self-gates (a real pass, not a no-op) unless
# the diff touches a dependency manifest, so it costs nothing on the
# overwhelming majority of dispatches that never touch one.
_ALWAYS_ON_CHECKS = ("no_secrets_in_diff", "no_vulnerable_deps_in_diff")


def _with_required_checks(chain: list[str], project_context: dict) -> list[str]:
    """Append the project's required checks (e.g. tests_pass), plus the
    always-on checks, that *chain* lacks.

    A project can require checks for all of its tasks on top of whatever the
    caller or persona asked for. Read from the registry via the packet's
    project context, never from the worktree the agent controls.
    """
    required = [*(project_context.get("required_checks") or []), *_ALWAYS_ON_CHECKS]
    return [*chain, *(c for c in dict.fromkeys(required) if c not in chain)]


def _resolve_verify_chain(caller_chain: list[str] | None, persona) -> list[str]:
    """Precedence: explicit caller argument > persona's own chain > default."""
    if caller_chain is not None:
        return list(caller_chain)
    persona_chain = getattr(persona, "verifier_chain", None) if persona is not None else None
    if persona_chain:
        return list(persona_chain)
    return list(DEFAULT_VERIFY_CHAIN)


class TaskDispatcher:
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
            decision = await governor.authorize(
                tenant_id,
                BudgetCategory.DRIVER,
                estimated_usd=driver.cost_per_task(),
                interactive=interactive,
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
            scratch = Path(tempfile.mkdtemp(prefix=f"lg_dispatch_{task_id[:8]}_"))
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

            # Step 5: Run verifier chain
            unverifiable: list[VerifierResult] = []
            if verify_chain and result.success:
                task_context = {
                    "output": result.output,
                    "task_type": task_type,
                    "instruction": instruction,
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

    async def _load_persona(
        self,
        tenant_id: str,
        persona_name: str | None,
        session: AsyncSession,
    ):
        """Load the active ``AgentPersona`` row for ``persona_name``, or None.

        Never raises: a personaless (or unresolvable) dispatch must still
        proceed — it simply carries no persona prompt/tool scoping, which is
        exactly the pre-existing behavior for every non-persona caller.
        """
        if not persona_name:
            return None
        try:
            from life_graph.models.db import AgentPersona

            result = await session.execute(
                select(AgentPersona).where(
                    AgentPersona.tenant_id == tenant_id,
                    AgentPersona.name == persona_name,
                    AgentPersona.is_active.is_(True),
                )
            )
            persona = result.scalar_one_or_none()
            if persona is None:
                logger.warning(
                    "Persona %r not found for tenant %s — dispatching without "
                    "persona prompt/tool scoping",
                    persona_name,
                    tenant_id,
                )
            return persona
        except Exception:
            logger.warning(
                "Failed to load persona %r — dispatching without persona prompt/tool scoping",
                persona_name,
                exc_info=True,
            )
            return None

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

    async def _check_wip_limits(
        self,
        tenant_id: str,
        project_id: str | uuid.UUID | None,
        session: AsyncSession,
        exclude_task_id: str | uuid.UUID | None = None,
    ) -> None:
        """Enforce WIP concurrency limits.

        ``project_id`` is normally already normalized by ``dispatch_task``; it
        is re-coerced here (idempotent) so the project-level check still works
        for any other caller passing a raw string.

        Raises:
            DispatchError: If WIP limits are exceeded.
        """
        project_uuid = _coerce_project_uuid(project_id)
        try:
            from life_graph.models.db import AgentTask

            # A caller that records its own run as a running AgentTask (the
            # dashboard dev-task runner) must not count against itself.
            own = _coerce_project_uuid(exclude_task_id)
            not_self = [AgentTask.id != own] if own is not None else []

            # Tenant-level WIP
            result = await session.execute(
                select(func.count(AgentTask.id)).where(
                    AgentTask.tenant_id == tenant_id,
                    AgentTask.status == "running",
                    *not_self,
                )
            )
            tenant_wip = result.scalar() or 0

            if tenant_wip >= MAX_WIP_PER_TENANT:
                raise DispatchError(f"Tenant WIP limit reached ({tenant_wip}/{MAX_WIP_PER_TENANT})")

            # Project-level WIP
            if project_uuid is not None:
                result = await session.execute(
                    select(func.count(AgentTask.id)).where(
                        AgentTask.tenant_id == tenant_id,
                        AgentTask.project_id == project_uuid,
                        AgentTask.status == "running",
                        *not_self,
                    )
                )
                project_wip = result.scalar() or 0

                if project_wip >= MAX_WIP_PER_PROJECT:
                    raise DispatchError(
                        f"Project WIP limit reached ({project_wip}/{MAX_WIP_PER_PROJECT})"
                    )
        except DispatchError:
            raise
        except Exception:
            logger.warning("Failed to check WIP limits — proceeding", exc_info=True)

    async def _get_driver_stats(
        self,
        tenant_id: str,
        driver_name: str,
        session: AsyncSession,
    ) -> dict:
        """Get aggregated driver stats for trust scoring.

        Sums across all day-bucketed rows for this driver.

        Returns:
            Dict with success_rate, total_tasks, etc.
        """
        try:
            from life_graph.models.db import DriverStat

            result = await session.execute(
                select(
                    func.sum(DriverStat.dispatched),
                    func.sum(DriverStat.verified_landed),
                    func.sum(DriverStat.failed),
                    func.sum(DriverStat.total_cost_usd),
                    func.sum(DriverStat.total_duration_ms),
                ).where(
                    DriverStat.tenant_id == tenant_id,
                    DriverStat.driver == driver_name,
                )
            )
            row = result.one_or_none()
            if row and row[0]:  # dispatched sum exists
                dispatched = row[0] or 0
                landed = row[1] or 0
                total = dispatched
                return {
                    "success_rate": landed / total if total > 0 else 1.0,
                    "total_tasks": total,
                    "avg_cost_usd": (row[3] or 0) / total if total > 0 else 0.0,
                    "avg_duration_ms": (row[4] or 0) / total if total > 0 else 0,
                }
        except Exception:
            logger.debug("No stats for driver %s — using defaults", driver_name)

        return {"success_rate": 1.0, "total_tasks": 0}

    async def _record_stats(
        self,
        tenant_id: str,
        driver_name: str,
        task_type: str,
        result: DriverResult,
        session: AsyncSession,
    ) -> None:
        """Update driver_stats row (day-bucketed) with latest dispatch result."""
        try:
            from life_graph.models.db import DriverStat

            today = datetime.now(UTC).date()

            existing = await session.execute(
                select(DriverStat).where(
                    DriverStat.tenant_id == tenant_id,
                    DriverStat.driver == driver_name,
                    DriverStat.task_type == task_type,
                    DriverStat.window_start == today,
                )
            )
            stat = existing.scalar_one_or_none()

            if stat:
                stat.dispatched += 1
                if result.success:
                    stat.verified_landed += 1
                else:
                    stat.failed += 1
                stat.total_cost_usd += result.cost_usd
                stat.total_duration_ms += result.duration_ms
            else:
                stat = DriverStat(
                    tenant_id=tenant_id,
                    driver=driver_name,
                    task_type=task_type,
                    window_start=today,
                    dispatched=1,
                    verified_landed=1 if result.success else 0,
                    failed=0 if result.success else 1,
                    total_cost_usd=result.cost_usd,
                    total_duration_ms=result.duration_ms,
                )
                session.add(stat)
        except Exception:
            logger.warning("Failed to record driver stats", exc_info=True)

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
        failures = [f"- {r.verifier}: {r.evidence}" for r in failure_report if not r.passed]
        bounce_instruction = (
            f"{packet.instruction}\n\n"
            f"--- PREVIOUS ATTEMPT FAILED VERIFICATION ---\n"
            f"Fix these issues and try again:\n" + "\n".join(failures)
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
            **{k: packet.project_context.get(k) for k in SANDBOX_SETTINGS},
            "acceptance_tests": acceptance_tests or [],
        }
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
                **landing,
            }
            title_prefix = "Open PR" if verified else "Open PR (UNVERIFIED)"
            if verified:
                detail = (
                    f"Branch {branch} passed "
                    f"{', '.join(checks) if checks else 'no checks'} on driver "
                    f"'{driver_name}'. Approve to push it and open a pull request "
                    f"against {landing.get('base_branch') or '(unknown base)'}."
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
        from life_graph.services.dev_outcomes import track_record
        from life_graph.services.github_pr import PullRequestError, open_pull_request

        record = await track_record(session, appr.tenant_id, driver_name, project_id)
        if not (record["established"] and record["merge_rate"] >= AUTO_PR_MERGE_RATE):
            logger.info(
                "Auto-open PR skipped: %s has %d/%d merged on this project",
                driver_name,
                record["merged"],
                record["total"],
            )
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
            f"Opened automatically: {driver_name} has {record['merged']}/{record['total']} "
            f"merged on this project. PR: {outcome['pr_url']}"
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
