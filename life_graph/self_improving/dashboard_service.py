"""Dashboard Service — Phase 6 (partial).

Provides aggregated views for the self-improving agent dashboard:
accuracy trends, per-task status, auto-fix history, cost tracking,
and pending reviews.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, func, case, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class DashboardService:
    """Read-only analytics service for the self-improving dashboard."""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    async def get_overview(self, tenant_id: str) -> dict[str, Any]:
        """Overall accuracy, tasks monitored, auto-fixes this week, pending reviews, costs."""
        from life_graph.self_improving.models import (
            EvalRun,
            EvalSuite,
            OptimizationRun,
        )

        async with self.session_factory() as session:
            # Overall accuracy (average of most recent run per suite)
            latest_runs_subq = (
                select(
                    EvalRun.suite_id,
                    func.max(EvalRun.completed_at).label("latest"),
                )
                .join(EvalSuite, EvalRun.suite_id == EvalSuite.id)
                .where(
                    EvalSuite.tenant_id == tenant_id,
                    EvalRun.status == "completed",
                )
                .group_by(EvalRun.suite_id)
                .subquery()
            )

            avg_result = await session.execute(
                select(func.avg(EvalRun.accuracy_pct))
                .join(
                    latest_runs_subq,
                    and_(
                        EvalRun.suite_id == latest_runs_subq.c.suite_id,
                        EvalRun.completed_at == latest_runs_subq.c.latest,
                    ),
                )
                .join(EvalSuite, EvalRun.suite_id == EvalSuite.id)
                .where(EvalSuite.tenant_id == tenant_id)
            )
            overall_accuracy = avg_result.scalar_one_or_none() or 0.0

            # Tasks monitored (active suites count)
            suite_count = await session.execute(
                select(func.count(EvalSuite.id)).where(
                    EvalSuite.tenant_id == tenant_id,
                )
            )
            tasks_monitored = suite_count.scalar_one_or_none() or 0

            # Auto-fixes this week
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            fixes_result = await session.execute(
                select(func.count(OptimizationRun.id)).where(
                    OptimizationRun.tenant_id == tenant_id,
                    OptimizationRun.status == "deployed",
                    OptimizationRun.completed_at >= week_ago,
                )
            )
            auto_fixes_week = fixes_result.scalar_one_or_none() or 0

            # Pending reviews
            reviews_result = await session.execute(
                select(func.count(OptimizationRun.id)).where(
                    OptimizationRun.tenant_id == tenant_id,
                    OptimizationRun.status == "needs_review",
                )
            )
            pending_reviews = reviews_result.scalar_one_or_none() or 0

            # Total eval cost (sum of cost_usd from runs)
            cost_result = await session.execute(
                select(func.sum(EvalRun.total_cost_usd))
                .join(EvalSuite, EvalRun.suite_id == EvalSuite.id)
                .where(
                    EvalSuite.tenant_id == tenant_id,
                )
            )
            total_eval_cost = cost_result.scalar_one_or_none() or 0.0

        return {
            "overall_accuracy_pct": round(overall_accuracy, 1),
            "tasks_monitored": tasks_monitored,
            "auto_fixes_this_week": auto_fixes_week,
            "pending_reviews": pending_reviews,
            "total_eval_cost_usd": round(total_eval_cost, 4),
        }

    async def get_accuracy_trends(
        self, tenant_id: str, days: int = 30
    ) -> list[dict[str, Any]]:
        """Time series of accuracy per task_type over the last N days."""
        from life_graph.self_improving.models import EvalRun, EvalSuite

        since = datetime.now(timezone.utc) - timedelta(days=days)

        async with self.session_factory() as session:
            result = await session.execute(
                select(
                    EvalSuite.task_type,
                    func.date(EvalRun.completed_at).label("date"),
                    func.avg(EvalRun.accuracy_pct).label("avg_accuracy"),
                )
                .join(EvalSuite, EvalRun.suite_id == EvalSuite.id)
                .where(
                    EvalSuite.tenant_id == tenant_id,
                    EvalRun.status == "completed",
                    EvalRun.completed_at >= since,
                )
                .group_by(EvalSuite.task_type, func.date(EvalRun.completed_at))
                .order_by(func.date(EvalRun.completed_at))
            )
            rows = result.all()

        return [
            {
                "task_type": row.task_type,
                "date": str(row.date),
                "accuracy_pct": round(row.avg_accuracy, 1) if row.avg_accuracy else 0.0,
            }
            for row in rows
        ]

    async def get_per_task_accuracy(
        self, tenant_id: str
    ) -> list[dict[str, Any]]:
        """Current accuracy per task_type with color-coded status."""
        from life_graph.self_improving.models import EvalRun, EvalSuite
        from life_graph.config import settings

        threshold = getattr(settings, "eval_accuracy_threshold_pct", 90.0)

        async with self.session_factory() as session:
            # Get latest run per suite
            latest_subq = (
                select(
                    EvalRun.suite_id,
                    func.max(EvalRun.completed_at).label("latest"),
                )
                .join(EvalSuite, EvalRun.suite_id == EvalSuite.id)
                .where(
                    EvalSuite.tenant_id == tenant_id,
                    EvalRun.status == "completed",
                )
                .group_by(EvalRun.suite_id)
                .subquery()
            )

            result = await session.execute(
                select(
                    EvalSuite.task_type,
                    EvalSuite.name,
                    EvalRun.accuracy_pct,
                    EvalRun.completed_at,
                )
                .join(EvalSuite, EvalRun.suite_id == EvalSuite.id)
                .join(
                    latest_subq,
                    and_(
                        EvalRun.suite_id == latest_subq.c.suite_id,
                        EvalRun.completed_at == latest_subq.c.latest,
                    ),
                )
                .where(EvalSuite.tenant_id == tenant_id)
            )
            rows = result.all()

        tasks = []
        for row in rows:
            accuracy = row.accuracy_pct or 0.0
            if accuracy >= threshold:
                status_color = "green"
            elif accuracy >= threshold - 10:
                status_color = "yellow"
            else:
                status_color = "red"

            tasks.append(
                {
                    "task_type": row.task_type,
                    "suite_name": row.name,
                    "accuracy_pct": round(accuracy, 1),
                    "status": status_color,
                    "last_eval": row.completed_at.isoformat()
                    if row.completed_at
                    else None,
                }
            )

        return tasks

    async def get_auto_fixes(
        self, tenant_id: str, days: int = 7
    ) -> list[dict[str, Any]]:
        """Deployed optimizations in the last N days."""
        from life_graph.self_improving.models import OptimizationRun, EvalSuite

        since = datetime.now(timezone.utc) - timedelta(days=days)

        async with self.session_factory() as session:
            result = await session.execute(
                select(OptimizationRun, EvalSuite.task_type, EvalSuite.name)
                .join(EvalSuite, OptimizationRun.suite_id == EvalSuite.id)
                .where(
                    OptimizationRun.tenant_id == tenant_id,
                    OptimizationRun.status == "deployed",
                    OptimizationRun.completed_at >= since,
                )
                .order_by(desc(OptimizationRun.completed_at))
            )
            rows = result.all()

        fixes = []
        for opt_run, task_type, suite_name in rows:
            improvement = 0.0
            if opt_run.result and isinstance(opt_run.result, dict):
                improvement = opt_run.result.get("improvement_pct", 0.0)

            fixes.append(
                {
                    "id": str(opt_run.id),
                    "task_type": task_type,
                    "suite_name": suite_name,
                    "improvement_pct": round(improvement, 1),
                    "deployed_at": opt_run.completed_at.isoformat()
                    if opt_run.completed_at
                    else None,
                }
            )

        return fixes

    async def get_cost_trends(
        self, tenant_id: str, days: int = 30
    ) -> list[dict[str, Any]]:
        """Daily eval + optimization costs over the last N days."""
        from life_graph.self_improving.models import EvalRun, EvalSuite

        since = datetime.now(timezone.utc) - timedelta(days=days)

        async with self.session_factory() as session:
            result = await session.execute(
                select(
                    func.date(EvalRun.completed_at).label("date"),
                    func.sum(EvalRun.total_cost_usd).label("eval_cost"),
                    func.count(EvalRun.id).label("run_count"),
                )
                .join(EvalSuite, EvalRun.suite_id == EvalSuite.id)
                .where(
                    EvalSuite.tenant_id == tenant_id,
                    EvalRun.completed_at >= since,
                )
                .group_by(func.date(EvalRun.completed_at))
                .order_by(func.date(EvalRun.completed_at))
            )
            rows = result.all()

        return [
            {
                "date": str(row.date),
                "eval_cost_usd": round(row.eval_cost or 0.0, 4),
                "run_count": row.run_count,
            }
            for row in rows
        ]

    async def get_pending_reviews(
        self, tenant_id: str
    ) -> list[dict[str, Any]]:
        """Optimization runs with status='needs_review'."""
        from life_graph.self_improving.models import OptimizationRun, EvalSuite

        async with self.session_factory() as session:
            result = await session.execute(
                select(OptimizationRun, EvalSuite.task_type, EvalSuite.name)
                .join(EvalSuite, OptimizationRun.suite_id == EvalSuite.id)
                .where(
                    OptimizationRun.tenant_id == tenant_id,
                    OptimizationRun.status == "needs_review",
                )
                .order_by(desc(OptimizationRun.started_at))
            )
            rows = result.all()

        reviews = []
        for opt_run, task_type, suite_name in rows:
            details = opt_run.result or {}
            reviews.append(
                {
                    "id": str(opt_run.id),
                    "task_type": task_type,
                    "suite_name": suite_name,
                    "baseline_accuracy": details.get("baseline_accuracy"),
                    "candidate_accuracy": details.get("candidate_accuracy"),
                    "regression_found": details.get("regression_found", False),
                    "started_at": opt_run.started_at.isoformat()
                    if opt_run.started_at
                    else None,
                }
            )

        return reviews
