"""Workflow Engine — DAG-based multi-step agent orchestration (Era 7).

Manages workflow definitions (DAGs of agent steps), validates acyclicity
via Kahn's algorithm, starts workflow runs, and advances execution as
individual steps complete. Each step maps to an AgentTask created via
the DelegationEngine.

Usage::

    engine = WorkflowEngine(session_factory, delegation_engine)
    wf = await engine.create_workflow(tenant_id, data)
    run = await engine.start_run(wf.id, tenant_id, "api", user_id, {})
"""

from __future__ import annotations

import logging
import re
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from life_graph.core.events import EventType, event_bus

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Return the current UTC timestamp (timezone-aware)."""
    return datetime.now(timezone.utc)


# ── Condition Evaluator ──────────────────────────────────────────


class ConditionEvaluator:
    """Evaluate step transition conditions against step outputs.

    Supports expressions like::

        steps.run_tests.output.passed == true
        steps.build.output.exit_code != 0
        steps.lint.output.errors <= 5

    Operators: ==, !=, >=, <=, >, <
    """

    _OPERATORS = {
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
        ">=": lambda a, b: float(a) >= float(b),
        "<=": lambda a, b: float(a) <= float(b),
        ">": lambda a, b: float(a) > float(b),
        "<": lambda a, b: float(a) < float(b),
    }

    # Match: <lhs> <operator> <rhs>
    # Operator order matters — check >= before > to avoid partial match
    _PATTERN = re.compile(
        r"^(.+?)\s*(!=|>=|<=|==|>|<)\s*(.+)$"
    )

    def evaluate(self, condition: str, step_outputs: dict[str, Any]) -> bool:
        """Evaluate a condition string against collected step outputs.

        Args:
            condition: Expression like ``steps.run_tests.output.passed == true``.
            step_outputs: Mapping of ``step_key → output_dict``.

        Returns:
            True if condition is satisfied, False on any error (safe default).
        """
        try:
            match = self._PATTERN.match(condition.strip())
            if not match:
                logger.warning("Condition does not match pattern: %s", condition)
                return False

            lhs_path, operator, rhs_raw = match.groups()
            lhs_value = self._resolve_path(lhs_path.strip(), step_outputs)
            rhs_value = self._parse_literal(rhs_raw.strip())

            op_fn = self._OPERATORS.get(operator)
            if op_fn is None:
                logger.warning("Unknown operator: %s", operator)
                return False

            return op_fn(lhs_value, rhs_value)

        except Exception:
            logger.debug("Condition evaluation failed: %s", condition, exc_info=True)
            return False

    @staticmethod
    def _resolve_path(path: str, step_outputs: dict[str, Any]) -> Any:
        """Resolve a dot-path like ``steps.build.output.exit_code``."""
        parts = path.split(".")
        if len(parts) < 3 or parts[0] != "steps":
            raise ValueError(f"Invalid LHS path: {path}")

        step_key = parts[1]
        output = step_outputs.get(step_key, {})

        # Navigate remaining path (skip 'steps' and step_key)
        cursor: Any = output
        for part in parts[2:]:
            if part == "output" and isinstance(cursor, dict):
                continue  # 'output' is the dict itself
            if isinstance(cursor, dict):
                cursor = cursor[part]
            elif isinstance(cursor, list) and part.isdigit():
                cursor = cursor[int(part)]
            else:
                raise KeyError(f"Cannot resolve {part} in path {path}")
        return cursor

    @staticmethod
    def _parse_literal(raw: str) -> Any:
        """Parse a literal RHS value."""
        lower = raw.lower()
        if lower == "true":
            return True
        if lower == "false":
            return False
        if lower == "null" or lower == "none":
            return None
        try:
            return int(raw)
        except ValueError:
            pass
        try:
            return float(raw)
        except ValueError:
            pass
        # Strip quotes if present
        if (raw.startswith('"') and raw.endswith('"')) or \
           (raw.startswith("'") and raw.endswith("'")):
            return raw[1:-1]
        return raw


# ── Workflow Engine ──────────────────────────────────────────────


class WorkflowEngine:
    """Orchestrate DAG-based agent workflows.

    Each workflow is a directed acyclic graph of steps. When a run starts,
    root steps (no dependencies) begin immediately. As steps complete,
    the DAG is advanced — downstream steps with all dependencies satisfied
    are started next. Conditions on edges allow conditional branching.
    """

    def __init__(self, session_factory, delegation_engine) -> None:
        self._session_factory = session_factory
        self._delegation_engine = delegation_engine
        self._evaluator = ConditionEvaluator()

    # ── Public API ───────────────────────────────────────────

    async def create_workflow(
        self,
        tenant_id: str,
        data: dict[str, Any],
    ):
        """Create a workflow definition with validated DAG.

        Args:
            tenant_id: Tenant isolation key.
            data: Dict with ``name``, ``description``, ``project_id``,
                  and ``steps`` (list of step dicts).

        Returns:
            The created AgentWorkflow ORM instance.

        Raises:
            ValueError: If the step graph contains cycles.
        """
        from life_graph.models.db import Workflow as AgentWorkflow, WorkflowStep

        steps_data = data.get("steps", [])
        error = self._validate_dag(steps_data)
        if error:
            raise ValueError(error)

        async with self._session_factory() as session:
            workflow = AgentWorkflow(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                name=data["name"],
                description=data.get("description"),
                project_id=data.get("project_id"),
                trigger_type=data.get("trigger_type", "manual"),
                config=data.get("config", {}),
            )
            session.add(workflow)

            for idx, step_data in enumerate(steps_data):
                step = WorkflowStep(
                    id=uuid.uuid4(),
                    workflow_id=workflow.id,
                    step_key=step_data["step_key"],
                    agent_name=step_data["agent_name"],
                    step_order=idx,
                    config=step_data.get("config", {}),
                    depends_on=step_data.get("depends_on", []),
                    condition=step_data.get("condition"),
                    timeout_seconds=step_data.get("timeout_seconds", 300),
                )
                session.add(step)

            await session.commit()
            await session.refresh(workflow)

            logger.info(
                "Created workflow %s with %d steps for tenant %s",
                workflow.id, len(steps_data), tenant_id,
            )
            return workflow

    async def start_run(
        self,
        workflow_id: uuid.UUID,
        tenant_id: str,
        trigger: str = "manual",
        triggered_by: str | None = None,
        input_params: dict[str, Any] | None = None,
    ):
        """Start a new workflow run.

        Creates a WorkflowRun and WorkflowStepRun for every step,
        then kicks off root steps (those with no dependencies).

        Args:
            workflow_id: The workflow definition to run.
            tenant_id: Tenant isolation key.
            trigger: How the run was triggered (manual, schedule, event).
            triggered_by: User or system that triggered the run.
            input_params: Input parameters for the run.

        Returns:
            The created WorkflowRun ORM instance.
        """
        from life_graph.models.db import (
            Workflow as AgentWorkflow, WorkflowStep, WorkflowRun, WorkflowStepRun,
        )

        async with self._session_factory() as session:
            # Load workflow with steps
            result = await session.execute(
                select(AgentWorkflow)
                .options(selectinload(AgentWorkflow.steps))
                .where(
                    AgentWorkflow.id == workflow_id,
                    AgentWorkflow.tenant_id == tenant_id,
                )
            )
            workflow = result.scalar_one_or_none()
            if not workflow:
                raise ValueError(f"Workflow {workflow_id} not found")

            # Create run
            run = WorkflowRun(
                id=uuid.uuid4(),
                workflow_id=workflow.id,
                tenant_id=tenant_id,
                status="running",
                trigger=trigger,
                triggered_by=triggered_by,
                input_params=input_params or {},
                started_at=_utcnow(),
            )
            session.add(run)

            # Create step runs for all steps
            step_runs = []
            for step in workflow.steps:
                sr = WorkflowStepRun(
                    id=uuid.uuid4(),
                    run_id=run.id,
                    step_id=step.id,
                    step_key=step.step_key,
                    status="pending",
                )
                session.add(sr)
                step_runs.append((sr, step))

            await session.commit()

            # Kick off root steps (no dependencies)
            for sr, step in step_runs:
                if not step.depends_on:
                    await self._start_step(sr, step, run, tenant_id)

            await session.commit()
            await session.refresh(run)

            await event_bus.emit(
                EventType.TASK_SPAWNED,
                {
                    "workflow_run_id": str(run.id),
                    "workflow_id": str(workflow_id),
                    "trigger": trigger,
                },
                source="workflow_engine",
            )

            logger.info(
                "Started workflow run %s for workflow %s",
                run.id, workflow_id,
            )
            return run

    async def on_step_completed(
        self,
        run_id: uuid.UUID,
        step_key: str,
        tenant_id: str,
        status: str = "completed",
        output: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Handle a step completion and advance the DAG.

        Args:
            run_id: The workflow run ID.
            step_key: The step that completed.
            tenant_id: Tenant isolation key.
            status: Step status (completed, failed).
            output: Step output data.
            error: Error message if failed.
        """
        from life_graph.models.db import WorkflowStepRun

        async with self._session_factory() as session:
            result = await session.execute(
                select(WorkflowStepRun).where(
                    WorkflowStepRun.run_id == run_id,
                    WorkflowStepRun.step_key == step_key,
                )
            )
            step_run = result.scalar_one_or_none()
            if not step_run:
                logger.warning("Step run not found: run=%s step=%s", run_id, step_key)
                return

            step_run.status = status
            step_run.output = output or {}
            step_run.error = error
            step_run.completed_at = _utcnow()

            await session.commit()

        if status == "failed":
            await self._abort_run(run_id, tenant_id, f"Step {step_key} failed: {error}")
        else:
            await self._advance_dag(run_id, tenant_id)

    async def cancel_run(
        self,
        run_id: uuid.UUID,
        tenant_id: str,
        reason: str = "Cancelled by user",
    ) -> None:
        """Cancel a workflow run and all pending/running steps.

        Args:
            run_id: The workflow run to cancel.
            tenant_id: Tenant isolation key.
            reason: Cancellation reason.
        """
        await self._abort_run(run_id, tenant_id, reason, final_status="cancelled")

    # ── Internal Methods ─────────────────────────────────────

    async def _advance_dag(self, run_id: uuid.UUID, tenant_id: str) -> None:
        """Find steps with all dependencies satisfied and start them.

        If all steps are completed/skipped, complete the run.
        """
        from life_graph.models.db import (
            WorkflowRun, WorkflowStep, WorkflowStepRun,
        )

        async with self._session_factory() as session:
            # Load all step runs for this run
            result = await session.execute(
                select(WorkflowStepRun).where(WorkflowStepRun.run_id == run_id)
            )
            all_step_runs = {sr.step_key: sr for sr in result.scalars().all()}

            # Check if all steps are in a terminal state
            terminal = {"completed", "failed", "skipped", "cancelled"}
            if all(sr.status in terminal for sr in all_step_runs.values()):
                await self._complete_run(run_id, tenant_id)
                return

            # Load workflow run to get workflow_id
            run_result = await session.execute(
                select(WorkflowRun).where(WorkflowRun.id == run_id)
            )
            run = run_result.scalar_one_or_none()
            if not run or run.status != "running":
                return

            # Load workflow steps
            step_result = await session.execute(
                select(WorkflowStep).where(WorkflowStep.workflow_id == run.workflow_id)
            )
            steps_by_key = {s.step_key: s for s in step_result.scalars().all()}

            # Collect completed step outputs for condition evaluation
            step_outputs: dict[str, Any] = {}
            for key, sr in all_step_runs.items():
                if sr.status == "completed":
                    step_outputs[key] = sr.output or {}

            # Find pending steps with all deps satisfied
            for step_key, sr in all_step_runs.items():
                if sr.status != "pending":
                    continue

                step = steps_by_key.get(step_key)
                if not step:
                    continue

                deps = step.depends_on or []
                all_deps_done = all(
                    all_step_runs.get(d, None) is not None
                    and all_step_runs[d].status in ("completed", "skipped")
                    for d in deps
                )

                if not all_deps_done:
                    continue

                # Evaluate condition if present
                if step.condition:
                    if not self._evaluator.evaluate(step.condition, step_outputs):
                        sr.status = "skipped"
                        sr.completed_at = _utcnow()
                        logger.info(
                            "Skipped step %s (condition not met): %s",
                            step_key, step.condition,
                        )
                        continue

                await self._start_step(sr, step, run, tenant_id)

            await session.commit()

        # Re-check for completion after starting new steps
        # (in case all remaining steps were skipped)
        async with self._session_factory() as session:
            result = await session.execute(
                select(WorkflowStepRun).where(WorkflowStepRun.run_id == run_id)
            )
            all_step_runs_refreshed = result.scalars().all()
            terminal = {"completed", "failed", "skipped", "cancelled"}
            if all(sr.status in terminal for sr in all_step_runs_refreshed):
                await self._complete_run(run_id, tenant_id)

    async def _start_step(self, step_run, step, run, tenant_id: str) -> None:
        """Start a single step by delegating to the DelegationEngine.

        Creates an AgentTask and links it back to the workflow run/step.
        """
        step_run.status = "running"
        step_run.started_at = _utcnow()

        try:
            task = await self._delegation_engine.create_task(
                tenant_id=tenant_id,
                task_name=f"workflow:{run.workflow_id}:{step.step_key}",
                agent_name=step.agent_name,
                input_data=step.config.get("input", {}),
                priority=step.config.get("priority", "normal"),
                timeout_seconds=step.timeout_seconds,
                metadata={
                    "workflow_run_id": str(run.id),
                    "workflow_step_id": str(step.id),
                    "step_key": step.step_key,
                },
            )
            step_run.task_id = task.id

            logger.info(
                "Started step %s (task %s) in run %s",
                step.step_key, task.id, run.id,
            )
        except Exception:
            step_run.status = "failed"
            step_run.error = "Failed to create agent task"
            step_run.completed_at = _utcnow()
            logger.exception(
                "Failed to start step %s in run %s",
                step.step_key, run.id,
            )

    async def _complete_run(self, run_id: uuid.UUID, tenant_id: str) -> None:
        """Mark a workflow run as completed and emit event."""
        from life_graph.models.db import WorkflowRun, WorkflowStepRun

        async with self._session_factory() as session:
            run_result = await session.execute(
                select(WorkflowRun).where(WorkflowRun.id == run_id)
            )
            run = run_result.scalar_one_or_none()
            if not run or run.status != "running":
                return

            # Aggregate outputs
            step_result = await session.execute(
                select(WorkflowStepRun).where(WorkflowStepRun.run_id == run_id)
            )
            step_runs = step_result.scalars().all()

            output_summary = {}
            has_failures = False
            for sr in step_runs:
                output_summary[sr.step_key] = {
                    "status": sr.status,
                    "output": sr.output or {},
                }
                if sr.status == "failed":
                    has_failures = True

            run.status = "failed" if has_failures else "completed"
            run.output_summary = output_summary
            run.completed_at = _utcnow()

            await session.commit()

        event_type = EventType.TASK_FAILED if has_failures else EventType.TASK_COMPLETED
        await event_bus.emit(
            event_type,
            {
                "workflow_run_id": str(run_id),
                "status": run.status,
                "output_summary": output_summary,
            },
            source="workflow_engine",
        )

        logger.info("Workflow run %s %s", run_id, run.status)

    async def _abort_run(
        self,
        run_id: uuid.UUID,
        tenant_id: str,
        reason: str,
        final_status: str = "failed",
    ) -> None:
        """Cancel all pending/running steps and mark run as failed/cancelled."""
        from life_graph.models.db import WorkflowRun, WorkflowStepRun

        async with self._session_factory() as session:
            # Update all non-terminal step runs
            await session.execute(
                update(WorkflowStepRun)
                .where(
                    WorkflowStepRun.run_id == run_id,
                    WorkflowStepRun.status.in_(["pending", "running"]),
                )
                .values(
                    status="cancelled",
                    error=reason,
                    completed_at=_utcnow(),
                )
            )

            # Update run
            run_result = await session.execute(
                select(WorkflowRun).where(WorkflowRun.id == run_id)
            )
            run = run_result.scalar_one_or_none()
            if run:
                run.status = final_status
                run.error = reason
                run.completed_at = _utcnow()

            await session.commit()

        await event_bus.emit(
            EventType.TASK_FAILED,
            {
                "workflow_run_id": str(run_id),
                "status": final_status,
                "reason": reason,
            },
            source="workflow_engine",
        )

        logger.info("Workflow run %s aborted: %s", run_id, reason)

    # ── DAG Validation ───────────────────────────────────────

    @staticmethod
    def _validate_dag(steps: list[dict[str, Any]]) -> str | None:
        """Validate step graph is a DAG using Kahn's algorithm.

        Args:
            steps: List of step dicts, each with ``step_key`` and
                   optional ``depends_on`` list.

        Returns:
            Error message if cycle detected or invalid, None if valid.
        """
        if not steps:
            return "Workflow must have at least one step"

        # Build adjacency and in-degree maps
        step_keys = {s["step_key"] for s in steps}
        in_degree: dict[str, int] = {key: 0 for key in step_keys}
        adjacency: dict[str, list[str]] = defaultdict(list)

        for step in steps:
            key = step["step_key"]
            deps = step.get("depends_on", [])
            for dep in deps:
                if dep not in step_keys:
                    return f"Step '{key}' depends on unknown step '{dep}'"
                adjacency[dep].append(key)
                in_degree[key] += 1

        # Kahn's algorithm — topological sort
        queue: deque[str] = deque()
        for key, degree in in_degree.items():
            if degree == 0:
                queue.append(key)

        sorted_count = 0
        while queue:
            node = queue.popleft()
            sorted_count += 1
            for neighbor in adjacency[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if sorted_count != len(step_keys):
            # Find cycle members for helpful error
            cycle_members = [k for k, d in in_degree.items() if d > 0]
            return (
                f"Cycle detected in workflow DAG involving steps: "
                f"{', '.join(sorted(cycle_members))}"
            )

        return None
