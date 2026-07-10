"""Nightly Self-Heal Cron — Phase 5.

Runs scheduled evaluation + optimization for all auto-optimize-enabled
eval suites. Tracks consecutive failures per suite and escalates when
the max is exceeded.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update

logger = logging.getLogger(__name__)


async def nightly_self_heal(
    tenant_id: str,
    session_factory,
    eval_service,
    prompt_service,
    optimizer,
) -> dict[str, Any]:
    """Run the nightly self-healing pipeline for a single tenant.

    For each eval suite with auto_optimize_enabled:
        1. Get active prompt for task_type
        2. Run eval suite
        3. If accuracy < threshold → trigger optimization
        4. Handle result (deployed/needs_review/no_improvement/error)
        5. Track consecutive_failures
        6. Skip + escalate if consecutive_failures >= max

    Args:
        tenant_id: The tenant to run for.
        session_factory: Async session factory.
        eval_service: EvalService instance.
        prompt_service: PromptVersionService instance.
        optimizer: DSPyOptimizerService instance.

    Returns:
        Summary dict with per-suite results.
    """
    from life_graph.self_improving.models import EvalSuite, NightlyRunLog
    from life_graph.config import settings

    run_id = uuid.uuid4()
    started_at = datetime.now(timezone.utc)
    suite_results: list[dict[str, Any]] = []
    overall_status = "success"

    # Create NightlyRunLog record
    async with session_factory() as session:
        log = NightlyRunLog(
            id=run_id,
            tenant_id=tenant_id,
            status="running",
            started_at=started_at,
        )
        session.add(log)
        await session.commit()

    try:
        # Fetch auto-optimize-enabled suites
        async with session_factory() as session:
            result = await session.execute(
                select(EvalSuite).where(
                    EvalSuite.tenant_id == tenant_id,
                    EvalSuite.is_active == True,  # noqa: E712
                    EvalSuite.auto_optimize_enabled == True,  # noqa: E712
                )
            )
            suites = result.scalars().all()

        if not suites:
            logger.info(
                "No auto-optimize suites for tenant %s — skipping", tenant_id
            )
            await _finalize_log(
                session_factory,
                run_id,
                "success",
                {"message": "no_suites", "suites_processed": 0},
            )
            return {"status": "success", "suites_processed": 0}

        accuracy_threshold = getattr(
            settings, "eval_accuracy_threshold_pct", 90.0
        )

        for suite in suites:
            suite_result: dict[str, Any] = {
                "suite_id": str(suite.id),
                "task_type": suite.task_type,
                "suite_name": suite.name,
            }

            try:
                # Check consecutive failures — skip if too many
                max_consecutive = getattr(
                    suite, "max_consecutive_fails", 3
                )
                current_failures = getattr(
                    suite, "consecutive_failures", 0
                )

                if current_failures >= max_consecutive:
                    logger.warning(
                        "Suite %s (%s) hit %d consecutive failures — "
                        "escalating, skipping optimization",
                        suite.id,
                        suite.task_type,
                        current_failures,
                    )
                    suite_result["status"] = "escalated"
                    suite_result["reason"] = (
                        f"consecutive_failures={current_failures} "
                        f">= max={max_consecutive}"
                    )
                    suite_results.append(suite_result)
                    overall_status = "partial"
                    continue

                # Step 1: Get active prompt
                active_prompt = await prompt_service.get_active_prompt(
                    tenant_id, suite.task_type
                )
                if active_prompt is None:
                    suite_result["status"] = "skipped"
                    suite_result["reason"] = "no_active_prompt"
                    suite_results.append(suite_result)
                    continue

                # Step 2: Run eval suite
                eval_run = await eval_service.run_suite(
                    tenant_id=tenant_id,
                    suite_id=suite.id,
                    prompt_version_id=active_prompt.id,
                )

                accuracy = eval_run.accuracy_pct or 0.0
                suite_result["accuracy"] = accuracy
                suite_result["eval_run_id"] = str(eval_run.id)

                # Step 3: Check if optimization needed
                if accuracy >= accuracy_threshold:
                    suite_result["status"] = "healthy"
                    # Reset consecutive failures on success
                    await _reset_consecutive_failures(
                        session_factory, suite.id
                    )
                    suite_results.append(suite_result)
                    continue

                logger.info(
                    "Suite %s (%s) accuracy %.1f%% < threshold %.1f%% "
                    "— triggering optimization",
                    suite.id,
                    suite.task_type,
                    accuracy,
                    accuracy_threshold,
                )

                # Step 4: Trigger optimization
                opt_result = await optimizer.optimize(
                    tenant_id=tenant_id,
                    suite_id=suite.id,
                    trigger_eval_run_id=eval_run.id,
                )

                suite_result["optimization_status"] = opt_result["status"]
                suite_result["optimization_run_id"] = str(
                    opt_result["optimization_run_id"]
                )

                # Step 5: Handle result
                if opt_result["status"] == "deployed":
                    suite_result["status"] = "auto_fixed"
                    await _reset_consecutive_failures(
                        session_factory, suite.id
                    )
                elif opt_result["status"] == "needs_review":
                    suite_result["status"] = "needs_review"
                    await _increment_consecutive_failures(
                        session_factory, suite.id
                    )
                    overall_status = "partial"
                elif opt_result["status"] == "error":
                    suite_result["status"] = "error"
                    await _increment_consecutive_failures(
                        session_factory, suite.id
                    )
                    overall_status = "partial"
                else:
                    suite_result["status"] = "no_improvement"
                    await _increment_consecutive_failures(
                        session_factory, suite.id
                    )

            except Exception as e:
                logger.exception(
                    "Nightly self-heal failed for suite %s", suite.id
                )
                suite_result["status"] = "error"
                suite_result["error"] = str(e)
                await _increment_consecutive_failures(
                    session_factory, suite.id
                )
                overall_status = "partial"

            suite_results.append(suite_result)

        # Finalize
        summary = {
            "suites_processed": len(suites),
            "results": suite_results,
        }
        await _finalize_log(session_factory, run_id, overall_status, summary)

        return {"status": overall_status, **summary}

    except Exception as e:
        logger.exception(
            "Nightly self-heal failed entirely for tenant %s", tenant_id
        )
        await _finalize_log(
            session_factory, run_id, "error", {"error": str(e)}
        )
        return {"status": "error", "error": str(e)}


# ── Helpers ───────────────────────────────────────────────────


async def _finalize_log(
    session_factory,
    run_id: uuid.UUID,
    status: str,
    summary: dict,
) -> None:
    """Update NightlyRunLog with final status and summary."""
    from life_graph.self_improving.models import NightlyRunLog

    async with session_factory() as session:
        log = await session.get(NightlyRunLog, run_id)
        if log:
            log.status = status
            log.completed_at = datetime.now(timezone.utc)
            log.summary = summary
            await session.commit()


async def _reset_consecutive_failures(
    session_factory, suite_id: uuid.UUID
) -> None:
    """Reset consecutive_failures counter for a suite."""
    from life_graph.self_improving.models import EvalSuite

    async with session_factory() as session:
        suite = await session.get(EvalSuite, suite_id)
        if suite and hasattr(suite, "consecutive_failures"):
            suite.consecutive_failures = 0
            await session.commit()


async def _increment_consecutive_failures(
    session_factory, suite_id: uuid.UUID
) -> None:
    """Increment consecutive_failures counter for a suite."""
    from life_graph.self_improving.models import EvalSuite

    async with session_factory() as session:
        suite = await session.get(EvalSuite, suite_id)
        if suite and hasattr(suite, "consecutive_failures"):
            suite.consecutive_failures = (
                getattr(suite, "consecutive_failures", 0) + 1
            )
            await session.commit()
