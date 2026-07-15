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

import logging
import tempfile
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from life_graph.core.budget import BudgetCategory
from life_graph.core.events import EventBus, EventType
from life_graph.drivers.base import ContextPacket, DriverResult
from life_graph.drivers.context import ContextPacketBuilder
from life_graph.drivers.registry import driver_registry
from life_graph.services.governor import governor
from life_graph.services.verifiers import VerifierResult, verifier_chain

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────

MAX_WIP_PER_PROJECT = 2
MAX_WIP_PER_TENANT = 5
DEFAULT_COST_CAP_USD = 2.0
MIN_TRUST_THRESHOLD = 0.6
DEFAULT_VERIFY_CHAIN = ["build_ok", "lint_clean"]


class DispatchError(Exception):
    """Raised when a dispatch cannot proceed."""


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
        """Build the second-opinion reviewer from settings (off by default)."""
        from life_graph.config import settings
        from life_graph.services.second_opinion import SecondOpinionReviewer

        enabled = settings.driver_second_opinion_enabled
        llm = None
        if enabled:
            from life_graph.services.llm_client import LMStudioClient
            llm = LMStudioClient()
        return SecondOpinionReviewer(
            llm=llm,
            model=settings.driver_second_opinion_model,
            enabled=enabled,
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
        if verify_chain is None:
            verify_chain = list(DEFAULT_VERIFY_CHAIN)

        owns_session = session is None
        if owns_session:
            session = self._session_factory()

        try:
            # Step 1: Check WIP limits
            await self._check_wip_limits(tenant_id, project_id, session)

            # Step 2: Build context packet
            project_uuid = uuid.UUID(project_id) if project_id else None
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

            # Step 3: Select driver
            driver = await self._select_driver(
                task_type, persona_name, tenant_id, session
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
                    task_id, decision.reason, decision.spent_usd, decision.cap_usd,
                )
                await self._emit(
                    EventType.DRIVER_DISPATCHED,
                    {
                        "task_id": task_id, "driver": driver.name,
                        "task_type": task_type, "tenant_id": tenant_id,
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
            workdir = Path(tempfile.mkdtemp(prefix=f"lg_dispatch_{task_id[:8]}_"))
            result = await driver.dispatch(packet, workdir, timeout=300)

            # Book the actual spend into the Governor's ledger.
            await governor.record(tenant_id, BudgetCategory.DRIVER, result.cost_usd)

            # Secondary per-task guard (the Governor is the primary budget gate).
            if result.cost_usd > cost_cap_usd:
                logger.warning(
                    "Task %s exceeded per-task cost cap: $%.2f > $%.2f",
                    task_id, result.cost_usd, cost_cap_usd,
                )

            # Step 5: Run verifier chain
            if verify_chain and result.success:
                task_context = {
                    "output": result.output,
                    "task_type": task_type,
                    "instruction": instruction,
                }
                v_results = await verifier_chain.run_chain(
                    verify_chain, workdir, task_context
                )

                if not verifier_chain.all_passed(v_results):
                    # Step 6: One-bounce rule
                    await self._emit(
                        EventType.VERIFICATION_FAILED,
                        {
                            "task_id": task_id,
                            "driver": driver.name,
                            "failures": [
                                asdict(r) for r in v_results if not r.passed
                            ],
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
                else:
                    await self._emit(
                        EventType.VERIFICATION_PASSED,
                        {"task_id": task_id, "driver": driver.name},
                    )

                    # Step 6b: Second-opinion dissenting review before landing.
                    verdict = await self._reviewer.review(
                        task_type, instruction, result.output
                    )
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
                            tenant_id, task_id, driver.name,
                            verdict.concern, session,
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

            # Step 7: Record stats + emit result
            await self._record_stats(
                tenant_id, driver.name, task_type, result, session
            )

            await self._emit(
                EventType.DRIVER_RESULT,
                {
                    "task_id": task_id,
                    "driver": driver.name,
                    "success": result.success,
                    "cost_usd": result.cost_usd,
                    "duration_ms": result.duration_ms,
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
            if owns_session:
                await session.close()

    async def _select_driver(
        self,
        task_type: str,
        persona_name: str | None,
        tenant_id: str,
        session: AsyncSession,
    ):
        """Select the best driver for a task.

        Selection logic:
        1. Persona pin (if persona specifies a driver)
        2. Cheapest capable trusted driver (success rate >= 0.6)
        3. Fallback to 'local'

        Returns:
            An AgentDriver instance.

        Raises:
            DispatchError: If no driver is available.
        """
        # 1. Check persona pin
        if persona_name:
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
                if persona and persona.properties:
                    pinned_driver = persona.properties.get("driver")
                    if pinned_driver:
                        driver = driver_registry.get(pinned_driver)
                        if driver and await driver.available():
                            logger.info(
                                "Persona %s pins driver %s", persona_name, pinned_driver
                            )
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

        raise DispatchError(
            f"No driver available for task type '{task_type}'"
        )

    async def _check_wip_limits(
        self,
        tenant_id: str,
        project_id: str | None,
        session: AsyncSession,
    ) -> None:
        """Enforce WIP concurrency limits.

        Raises:
            DispatchError: If WIP limits are exceeded.
        """
        try:
            from life_graph.models.db import AgentTask

            # Tenant-level WIP
            result = await session.execute(
                select(func.count(AgentTask.id)).where(
                    AgentTask.tenant_id == tenant_id,
                    AgentTask.status == "running",
                )
            )
            tenant_wip = result.scalar() or 0

            if tenant_wip >= MAX_WIP_PER_TENANT:
                raise DispatchError(
                    f"Tenant WIP limit reached ({tenant_wip}/{MAX_WIP_PER_TENANT})"
                )

            # Project-level WIP
            if project_id:
                result = await session.execute(
                    select(func.count(AgentTask.id)).where(
                        AgentTask.tenant_id == tenant_id,
                        AgentTask.project_id == uuid.UUID(project_id),
                        AgentTask.status == "running",
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
                failed = row[2] or 0
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
    ) -> DriverResult | None:
        """Re-dispatch once with failure context appended to instruction.

        Returns:
            DriverResult if bounce succeeded verification, None if it also failed.
        """
        failures = [
            f"- {r.verifier}: {r.evidence}" for r in failure_report if not r.passed
        ]
        bounce_instruction = (
            f"{packet.instruction}\n\n"
            f"--- PREVIOUS ATTEMPT FAILED VERIFICATION ---\n"
            f"Fix these issues and try again:\n"
            + "\n".join(failures)
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
        bounce_result = await driver.dispatch(bounced_packet, workdir, timeout=300)

        if not bounce_result.success:
            return None

        # Re-verify
        task_context = {
            "output": bounce_result.output,
            "task_type": packet.task_type,
            "instruction": bounce_instruction,
        }
        v_results = await verifier_chain.run_chain(verify_chain, workdir, task_context)

        if verifier_chain.all_passed(v_results):
            await self._emit(
                EventType.VERIFICATION_PASSED,
                {"task_id": task_id, "driver": driver.name, "bounce": True},
            )
            return bounce_result

        return None

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
            from life_graph.models.db import ApprovalQueue

            entry = ApprovalQueue(
                tenant_id=tenant_id,
                action_type="driver_second_opinion_dissent",
                action_description=(
                    f"Driver '{driver_name}' output for task {task_id} passed "
                    f"automated checks but the second-opinion reviewer dissented: "
                    f"{concern or 'unspecified concern'}"
                ),
                risk_level="medium",
                agent_id=driver_name,
                context={
                    "task_id": task_id,
                    "driver": driver_name,
                    "concern": concern,
                },
                status="pending",
            )
            session.add(entry)
            logger.info(
                "Created second-opinion approval entry for task %s", task_id
            )
        except Exception:
            logger.warning(
                "Failed to create dissent approval entry", exc_info=True
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
            from life_graph.models.db import ApprovalQueue

            entry = ApprovalQueue(
                tenant_id=tenant_id,
                action_type="driver_verification_failed",
                action_description=(
                    f"Driver '{driver_name}' failed verification for task {task_id} "
                    f"after one bounce. Failures: "
                    + ", ".join(r.verifier for r in v_results if not r.passed)
                ),
                risk_level="medium",
                agent_id=driver_name,
                context={
                    "task_id": task_id,
                    "driver": driver_name,
                    "failures": [
                        {"verifier": r.verifier, "evidence": r.evidence}
                        for r in v_results
                        if not r.passed
                    ],
                },
                status="pending",
            )
            session.add(entry)
            logger.info(
                "Created approval entry for task %s — needs human review", task_id
            )
        except Exception:
            logger.warning("Failed to create approval entry", exc_info=True)

    async def _emit(self, event_type: EventType, payload: dict) -> None:
        """Emit an event if event_bus is available."""
        if self._event_bus:
            try:
                await self._event_bus.emit(event_type, payload, source="dispatcher")
            except Exception:
                logger.debug("Failed to emit event %s", event_type, exc_info=True)
