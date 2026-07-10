"""DSPy Optimizer Service — Phase 4.

Automated prompt optimization using DSPy BootstrapFewShot.
Collects pass/fail training data from eval runs, optimizes prompts,
tests candidates, checks for cross-task regressions, and deploys
improvements automatically.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ── Graceful DSPy import ──────────────────────────────────────
try:
    import dspy
    from dspy.teleprompt import BootstrapFewShot

    DSPY_AVAILABLE = True
except ImportError:
    dspy = None  # type: ignore[assignment]
    BootstrapFewShot = None  # type: ignore[assignment,misc]
    DSPY_AVAILABLE = False
    logger.warning(
        "dspy not installed — DSPyOptimizerService will operate in "
        "degraded mode (no actual optimization)"
    )


class DSPyOptimizerService:
    """7-step prompt optimization pipeline powered by DSPy.

    Steps:
        1. Create OptimizationRun record
        2. Collect training data (pass/fail examples)
        3. Run DSPy BootstrapFewShot optimization
        4. Create candidate prompt version
        5. Test candidate against full eval suite
        6. Check cross-task regressions
        7. Deploy / flag / discard
    """

    MIN_IMPROVEMENT_PCT: float = 1.0
    MAX_REGRESSION_PCT: float = 2.0
    MAX_FEW_SHOT: int = 8

    def __init__(
        self,
        session_factory,
        eval_service,
        prompt_version_service,
        settings,
    ):
        self.session_factory = session_factory
        self.eval_service = eval_service
        self.prompt_version_service = prompt_version_service
        self.settings = settings

        # Override defaults from settings if provided
        if hasattr(settings, "optimization_min_improvement_pct"):
            self.MIN_IMPROVEMENT_PCT = settings.optimization_min_improvement_pct
        if hasattr(settings, "optimization_max_regression_pct"):
            self.MAX_REGRESSION_PCT = settings.optimization_max_regression_pct
        if hasattr(settings, "optimization_max_few_shot"):
            self.MAX_FEW_SHOT = settings.optimization_max_few_shot

    # ── Public API ────────────────────────────────────────────

    async def optimize(
        self,
        tenant_id: str,
        suite_id: uuid.UUID,
        trigger_eval_run_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Run the full 7-step optimization pipeline.

        Returns:
            Dict with optimization result:
                status: deployed | needs_review | no_improvement | error
                optimization_run_id: UUID of the run
                details: additional info
        """
        from life_graph.self_improving.models import OptimizationRun, EvalSuite

        run_id = uuid.uuid4()

        try:
            # ── Step 1: Create OptimizationRun record ─────────
            async with self.session_factory() as session:
                # Look up suite to get task_type
                suite = await session.get(EvalSuite, suite_id)
                if suite is None:
                    return {
                        "status": "error",
                        "optimization_run_id": run_id,
                        "details": f"EvalSuite {suite_id} not found",
                    }
                task_type = suite.task_type

                opt_run = OptimizationRun(
                    id=run_id,
                    tenant_id=tenant_id,
                    suite_id=suite_id,
                    trigger_eval_run_id=trigger_eval_run_id,
                    status="running",
                    started_at=datetime.now(timezone.utc),
                )
                session.add(opt_run)
                await session.commit()

            # ── Step 2: Collect training data ─────────────────
            training_data = await self._collect_training_data(trigger_eval_run_id)

            if not training_data["pass"] and not training_data["fail"]:
                await self._update_run_status(
                    run_id, "no_improvement", {"reason": "no_training_data"}
                )
                return {
                    "status": "no_improvement",
                    "optimization_run_id": run_id,
                    "details": "No training data available",
                }

            # ── Step 3: Get current prompt and run DSPy ───────
            current_prompt = await self.prompt_version_service.get_active_prompt(
                tenant_id, task_type
            )
            if current_prompt is None:
                await self._update_run_status(
                    run_id, "error", {"reason": "no_active_prompt"}
                )
                return {
                    "status": "error",
                    "optimization_run_id": run_id,
                    "details": f"No active prompt for task_type={task_type}",
                }

            optimized = await self._run_dspy_optimization(
                training_data, current_prompt
            )

            if optimized is None:
                await self._update_run_status(
                    run_id, "no_improvement", {"reason": "dspy_returned_no_change"}
                )
                return {
                    "status": "no_improvement",
                    "optimization_run_id": run_id,
                    "details": "DSPy optimization returned no change",
                }

            # ── Step 4: Create candidate prompt version ───────
            candidate_version = await self.prompt_version_service.create_version(
                tenant_id=tenant_id,
                task_type=task_type,
                prompt_text=optimized["prompt_text"],
                few_shot_examples=optimized.get("few_shot_examples"),
                created_by="auto_optimize",
                parent_version_id=current_prompt.id,
            )

            # ── Step 5: Test candidate against full suite ─────
            test_run = await self.eval_service.run_suite(
                tenant_id=tenant_id,
                suite_id=suite_id,
                prompt_version_id=candidate_version.id,
            )

            candidate_accuracy = test_run.accuracy_pct or 0.0
            baseline_accuracy = await self._get_baseline_accuracy(
                trigger_eval_run_id
            )
            improvement = candidate_accuracy - baseline_accuracy

            # ── Step 6: Check cross-task regressions ──────────
            regression_found = await self._check_cross_task_regressions(
                tenant_id, task_type, candidate_version.id
            )

            # ── Step 7: Deploy / flag / discard ───────────────
            result_details = {
                "baseline_accuracy": baseline_accuracy,
                "candidate_accuracy": candidate_accuracy,
                "improvement_pct": improvement,
                "regression_found": regression_found,
                "candidate_version_id": str(candidate_version.id),
                "test_eval_run_id": str(test_run.id),
            }

            if regression_found:
                status = "needs_review"
                await self._update_run_status(run_id, status, result_details)
            elif improvement >= self.MIN_IMPROVEMENT_PCT:
                status = "deployed"
                await self.prompt_version_service.activate_version(
                    tenant_id, candidate_version.id
                )
                await self._update_run_status(run_id, status, result_details)
            else:
                status = "no_improvement"
                await self._update_run_status(run_id, status, result_details)

            return {
                "status": status,
                "optimization_run_id": run_id,
                "details": result_details,
            }

        except Exception as e:
            logger.exception(
                "Optimization pipeline failed for suite %s", suite_id
            )
            await self._update_run_status(
                run_id, "error", {"error": str(e)}
            )
            return {
                "status": "error",
                "optimization_run_id": run_id,
                "details": str(e),
            }

    # ── Training Data Collection ──────────────────────────────

    async def _collect_training_data(
        self, run_id: uuid.UUID
    ) -> dict[str, list[dict]]:
        """Query EvalResult for pass/fail examples from a specific eval run."""
        from life_graph.self_improving.models import EvalResult

        data: dict[str, list[dict]] = {"pass": [], "fail": []}

        async with self.session_factory() as session:
            results = await session.execute(
                select(EvalResult).where(EvalResult.eval_run_id == run_id)
            )
            for row in results.scalars().all():
                entry = {
                    "input": row.input_text,
                    "expected_output": row.expected_output,
                    "actual_output": row.actual_output,
                    "score": row.score,
                }
                if row.passed:
                    data["pass"].append(entry)
                else:
                    data["fail"].append(entry)

        logger.info(
            "Collected training data for run %s: %d pass, %d fail",
            run_id,
            len(data["pass"]),
            len(data["fail"]),
        )
        return data

    # ── DSPy Optimization ─────────────────────────────────────

    async def _run_dspy_optimization(
        self,
        training_data: dict[str, list[dict]],
        current_prompt,
    ) -> dict[str, Any] | None:
        """Configure DSPy LM, build trainset, run BootstrapFewShot.

        Returns:
            Dict with optimized prompt_text and few_shot_examples,
            or None if optimization failed or DSPy unavailable.
        """
        if not DSPY_AVAILABLE:
            logger.warning("DSPy not available — returning None")
            return None

        try:
            # Configure DSPy to use LiteLLM via OpenRouter
            lm = dspy.LM(
                model=self.settings.optimization_model,
                api_key=self.settings.openrouter_api_key,
                api_base="https://openrouter.ai/api/v1",
            )
            dspy.configure(lm=lm)

            # Build trainset from pass/fail examples
            trainset = []
            for example in training_data["pass"]:
                trainset.append(
                    dspy.Example(
                        input=example["input"],
                        output=example["expected_output"],
                    ).with_inputs("input")
                )

            # Include some fail examples as negative signal
            for example in training_data["fail"][:3]:
                if example["expected_output"]:
                    trainset.append(
                        dspy.Example(
                            input=example["input"],
                            output=example["expected_output"],
                        ).with_inputs("input")
                    )

            if not trainset:
                logger.warning("No trainset examples — skipping optimization")
                return None

            # Define a simple signature for optimization
            class TaskSignature(dspy.Signature):
                """Process input and produce output."""
                input: str = dspy.InputField()
                output: str = dspy.OutputField()

            # Run BootstrapFewShot
            predictor = dspy.Predict(TaskSignature)

            def metric(example, prediction, trace=None):
                """Simple exact-match metric."""
                return prediction.output.strip() == example.output.strip()

            optimizer = BootstrapFewShot(
                metric=metric,
                max_bootstrapped_demos=self.MAX_FEW_SHOT,
                max_rounds=3,
            )

            optimized_predictor = optimizer.compile(
                predictor, trainset=trainset
            )

            # Extract optimized prompt and few-shot examples
            few_shot_examples = []
            if hasattr(optimized_predictor, "demos"):
                for demo in optimized_predictor.demos[: self.MAX_FEW_SHOT]:
                    few_shot_examples.append(
                        {
                            "input": getattr(demo, "input", ""),
                            "output": getattr(demo, "output", ""),
                        }
                    )

            # Build optimized prompt text
            optimized_prompt = current_prompt.prompt_text
            if few_shot_examples:
                examples_block = "\n\n## Examples:\n"
                for i, ex in enumerate(few_shot_examples, 1):
                    examples_block += (
                        f"\n### Example {i}:\n"
                        f"Input: {ex['input']}\n"
                        f"Output: {ex['output']}\n"
                    )
                optimized_prompt = optimized_prompt + examples_block

            return {
                "prompt_text": optimized_prompt,
                "few_shot_examples": few_shot_examples,
            }

        except Exception:
            logger.exception("DSPy optimization failed")
            return None

    # ── Cross-Task Regression Check ───────────────────────────

    async def _check_cross_task_regressions(
        self,
        tenant_id: str,
        task_type: str,
        candidate_version_id: uuid.UUID,
    ) -> bool:
        """Run eval on other task types; flag if >MAX_REGRESSION_PCT drop.

        Returns True if any regression detected.
        """
        from life_graph.self_improving.models import EvalSuite

        try:
            async with self.session_factory() as session:
                # Find suites for OTHER task types
                result = await session.execute(
                    select(EvalSuite).where(
                        EvalSuite.tenant_id == tenant_id,
                        EvalSuite.task_type != task_type,
                        EvalSuite.is_active == True,  # noqa: E712
                    )
                )
                other_suites = result.scalars().all()

            for suite in other_suites:
                try:
                    test_run = await self.eval_service.run_suite(
                        tenant_id=tenant_id,
                        suite_id=suite.id,
                        prompt_version_id=candidate_version_id,
                    )

                    # Compare against latest baseline for this suite
                    baseline = await self._get_latest_suite_accuracy(
                        suite.id
                    )
                    if baseline is not None:
                        drop = baseline - (test_run.accuracy_pct or 0.0)
                        if drop > self.MAX_REGRESSION_PCT:
                            logger.warning(
                                "Cross-task regression detected: "
                                "suite=%s task=%s drop=%.1f%%",
                                suite.id,
                                suite.task_type,
                                drop,
                            )
                            return True
                except Exception:
                    logger.exception(
                        "Failed cross-task check for suite %s", suite.id
                    )
                    # Conservative: flag as regression if we can't verify
                    return True

            return False

        except Exception:
            logger.exception("Cross-task regression check failed")
            return True  # Conservative: flag if check fails

    # ── Helpers ───────────────────────────────────────────────

    async def _get_baseline_accuracy(
        self, eval_run_id: uuid.UUID
    ) -> float:
        """Get accuracy from the trigger eval run."""
        from life_graph.self_improving.models import EvalRun

        async with self.session_factory() as session:
            run = await session.get(EvalRun, eval_run_id)
            if run and run.accuracy_pct is not None:
                return run.accuracy_pct
        return 0.0

    async def _get_latest_suite_accuracy(
        self, suite_id: uuid.UUID
    ) -> float | None:
        """Get accuracy from the most recent completed run for a suite."""
        from life_graph.self_improving.models import EvalRun

        async with self.session_factory() as session:
            result = await session.execute(
                select(EvalRun.accuracy_pct)
                .where(
                    EvalRun.suite_id == suite_id,
                    EvalRun.status == "completed",
                )
                .order_by(EvalRun.completed_at.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
            return row

    async def _update_run_status(
        self,
        run_id: uuid.UUID,
        status: str,
        result_data: dict | None = None,
    ) -> None:
        """Update OptimizationRun status and result."""
        from life_graph.self_improving.models import OptimizationRun

        async with self.session_factory() as session:
            run = await session.get(OptimizationRun, run_id)
            if run:
                run.status = status
                run.completed_at = datetime.now(timezone.utc)
                if result_data:
                    run.result = result_data
                await session.commit()
