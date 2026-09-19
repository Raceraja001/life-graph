"""Nightly self-heal — refresh the eval suite from reviews, then optimize.

For each task the loop knows how to run (self_improving/task_runner.py):

1. Rebuild the tenant's eval suite from reviewed extraction traces
   (suite_builder.sync_suite) — new reviews add cases, edits update labels.
2. Skip while there are too few held-out cases to judge anything.
3. Otherwise run the optimizer, which evaluates the active prompt, tries
   few-shot candidates, and deploys one only if it clears the gate.

Only *errors* count toward ``consecutive_failures``. The previous version also
counted "no improvement", so a prompt that was already good would be escalated
and switched off after three quiet nights. It also crashed on its first query
(``EvalSuite.is_active`` does not exist) and called service methods that did
not exist, so it had never completed a run.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

logger = logging.getLogger(__name__)


async def nightly_self_heal(
    tenant_id: str,
    session_factory,
    eval_service,
    prompt_service,
    optimizer,
) -> dict[str, Any]:
    """Run the nightly self-improvement pass for one tenant. Never raises."""
    from life_graph.config import settings
    from life_graph.self_improving.models import EvalSuite, NightlyRunLog
    from life_graph.self_improving.suite_builder import TASK_TYPE, sync_suite
    from life_graph.self_improving.task_runner import optimizable_task_types

    log_id = uuid.uuid4()
    started = time.monotonic()
    async with session_factory() as session:
        session.add(
            NightlyRunLog(
                id=log_id, tenant_id=tenant_id, status="running", started_at=datetime.now(UTC)
            )
        )
        await session.commit()

    results: list[dict[str, Any]] = []
    counts = {"evaluated": 0, "triggered": 0, "deployed": 0, "flagged": 0}
    overall = "completed"
    try:
        for task_type in optimizable_task_types():
            if task_type != TASK_TYPE:
                continue  # only extraction has a suite builder today
            result: dict[str, Any] = {"task_type": task_type}
            try:
                synced = await sync_suite(tenant_id)
                result.update(
                    holdout=synced["holdout"],
                    train_pool=len(synced["train_pool"]),
                    cases_added=synced["added"],
                    cases_updated=synced["updated"],
                )
                async with session_factory() as session:
                    suite = (
                        await session.execute(
                            select(EvalSuite).where(
                                EvalSuite.tenant_id == tenant_id,
                                EvalSuite.task_type == task_type,
                            )
                        )
                    ).scalar_one()

                if not suite.auto_optimize_enabled:
                    result["status"] = "disabled"
                elif suite.consecutive_failures >= suite.max_consecutive_fails:
                    result["status"] = "escalated"
                    result["reason"] = (
                        f"{suite.consecutive_failures} consecutive errors — fix the cause, then "
                        "reset consecutive_failures on the suite"
                    )
                    counts["flagged"] += 1
                    overall = "partial"
                elif synced["holdout"] < settings.optimization_min_holdout:
                    result["status"] = "insufficient_data"
                    result["reason"] = (
                        f"{synced['holdout']} of {settings.optimization_min_holdout} "
                        "held-out cases so far — keep reviewing captures"
                    )
                else:
                    counts["evaluated"] += 1
                    counts["triggered"] += 1
                    outcome = await optimizer.optimize(
                        tenant_id, suite.id, train_pool=synced["train_pool"]
                    )
                    result["status"] = outcome["status"]
                    result["optimization_run_id"] = str(outcome.get("optimization_run_id"))
                    details = outcome.get("details") or {}
                    if isinstance(details, dict):
                        result["baseline"] = details.get("baseline")
                        result["gate"] = details.get("gate") or details.get("reason")
                    if outcome["status"] == "deployed":
                        counts["deployed"] += 1
                    await _record_outcome(session_factory, suite.id, outcome["status"] == "error")
                    if outcome["status"] == "error":
                        overall = "partial"
            except Exception as exc:
                logger.exception("Self-heal failed for %s/%s", tenant_id, task_type)
                result["status"] = "error"
                result["error"] = str(exc)
                overall = "partial"
            results.append(result)
    except Exception as exc:
        logger.exception("Nightly self-heal failed entirely for tenant %s", tenant_id)
        overall = "error"
        results.append({"status": "error", "error": str(exc)})

    summary = {"results": results, **counts}
    async with session_factory() as session:
        log = await session.get(NightlyRunLog, log_id)
        if log is not None:
            log.status = overall
            log.task_types_evaluated = counts["evaluated"]
            log.optimizations_triggered = counts["triggered"]
            log.optimizations_deployed = counts["deployed"]
            log.optimizations_flagged = counts["flagged"]
            log.duration_seconds = round(time.monotonic() - started, 2)
            log.summary = summary
            log.completed_at = datetime.now(UTC)
            await session.commit()
    return {"status": overall, **summary}


async def _record_outcome(session_factory, suite_id: uuid.UUID, errored: bool) -> None:
    """Count consecutive *errors*; any clean run (deployed or not) resets."""
    from life_graph.self_improving.models import EvalSuite

    async with session_factory() as session:
        suite = await session.get(EvalSuite, suite_id)
        if suite is not None:
            suite.consecutive_failures = suite.consecutive_failures + 1 if errored else 0
            await session.commit()
