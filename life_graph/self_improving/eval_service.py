"""Eval service — manages eval suites, cases, and runs.

Provides the core loop: run all active cases, score each,
compute summary statistics, and persist results.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from life_graph.self_improving.eval_scorer import EvalScorer
from life_graph.self_improving.models import (
    EvalCase,
    EvalResult,
    EvalRun,
    EvalSuite,
)
from life_graph.self_improving.schemas import (
    EvalCaseBulkCreate,
    EvalCaseCreate,
    EvalCaseResponse,
    EvalResultResponse,
    EvalRunResponse,
    EvalSuiteCreate,
    EvalSuiteResponse,
    FailureAnalysis,
)

logger = logging.getLogger(__name__)


class EvalService:
    """Service layer for eval suite management and execution."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        scorer: EvalScorer | None = None,
    ) -> None:
        self._sf = session_factory
        self._scorer = scorer or EvalScorer()

    # ── Suite CRUD ────────────────────────────────────────────

    async def create_suite(
        self, tenant_id: str, data: EvalSuiteCreate,
    ) -> EvalSuiteResponse:
        """Create a new eval suite."""
        async with self._sf() as session:
            suite = EvalSuite(
                tenant_id=tenant_id,
                task_type=data.task_type,
                name=data.name,
                description=data.description,
                accuracy_threshold_pct=Decimal(str(data.accuracy_threshold_pct)),
                auto_optimize_enabled=data.auto_optimize_enabled,
                max_consecutive_fails=data.max_consecutive_fails,
            )
            session.add(suite)
            await session.commit()
            await session.refresh(suite)
            return EvalSuiteResponse.model_validate(suite)

    async def list_suites(
        self, tenant_id: str,
    ) -> list[EvalSuiteResponse]:
        """List all eval suites for a tenant with stats."""
        async with self._sf() as session:
            stmt = (
                select(EvalSuite)
                .where(EvalSuite.tenant_id == tenant_id)
                .order_by(EvalSuite.created_at.desc())
            )
            result = await session.execute(stmt)
            suites = result.scalars().all()
            return [EvalSuiteResponse.model_validate(s) for s in suites]

    # ── Case CRUD ─────────────────────────────────────────────

    async def add_case(
        self, suite_id: uuid.UUID, data: EvalCaseCreate,
    ) -> EvalCaseResponse:
        """Add a single test case and increment suite case_count."""
        async with self._sf() as session:
            case = EvalCase(
                suite_id=suite_id,
                input_text=data.input_text,
                expected_output=data.expected_output,
                scoring_type=data.scoring_type,
                scoring_config=data.scoring_config,
                metadata_=data.metadata,
                source=data.source,
            )
            session.add(case)

            # Increment case_count atomically
            await session.execute(
                update(EvalSuite)
                .where(EvalSuite.id == suite_id)
                .values(case_count=EvalSuite.case_count + 1)
            )

            await session.commit()
            await session.refresh(case)
            return EvalCaseResponse.model_validate(case)

    async def bulk_add_cases(
        self, suite_id: uuid.UUID, data: EvalCaseBulkCreate,
    ) -> list[EvalCaseResponse]:
        """Bulk import test cases."""
        async with self._sf() as session:
            cases = []
            for c in data.cases:
                case = EvalCase(
                    suite_id=suite_id,
                    input_text=c.input_text,
                    expected_output=c.expected_output,
                    scoring_type=c.scoring_type,
                    scoring_config=c.scoring_config,
                    metadata_=c.metadata,
                    source=c.source,
                )
                session.add(case)
                cases.append(case)

            # Increment case_count atomically
            await session.execute(
                update(EvalSuite)
                .where(EvalSuite.id == suite_id)
                .values(case_count=EvalSuite.case_count + len(data.cases))
            )

            await session.commit()
            for c in cases:
                await session.refresh(c)
            return [EvalCaseResponse.model_validate(c) for c in cases]

    # ── Run Execution ─────────────────────────────────────────

    async def run_eval(
        self,
        tenant_id: str,
        suite_id: uuid.UUID,
        prompt_version_id: str,
        trigger: str = "manual",
        llm_fn: Callable[..., Any] | None = None,
    ) -> EvalRunResponse:
        """Execute all active cases in a suite, score each, compute summary.

        Uses asyncio.Semaphore(5) for bounded parallelism.
        The llm_fn callback is expected to accept (prompt_text, input_text)
        and return (output, latency_ms, tokens, cost).
        """
        run_start = time.time()

        async with self._sf() as session:
            # Fetch active cases
            stmt = (
                select(EvalCase)
                .where(
                    EvalCase.suite_id == suite_id,
                    EvalCase.is_active.is_(True),
                )
            )
            result = await session.execute(stmt)
            cases = list(result.scalars().all())

            if not cases:
                raise ValueError(f"No active cases in suite {suite_id}")

            # Create run record
            run = EvalRun(
                suite_id=suite_id,
                prompt_version_id=prompt_version_id,
                trigger=trigger,
                status="running",
                total_cases=len(cases),
            )
            session.add(run)
            await session.commit()
            await session.refresh(run)
            run_id = run.id

        # Execute cases with bounded parallelism
        sem = asyncio.Semaphore(5)
        eval_results: list[dict[str, Any]] = []

        async def _eval_case(case: EvalCase) -> dict[str, Any]:
            async with sem:
                try:
                    t0 = time.time()

                    if llm_fn:
                        actual, latency_ms, tokens, cost = await llm_fn(
                            prompt_version_id, case.input_text,
                        )
                    else:
                        # Dry-run: use empty output
                        actual = ""
                        latency_ms = int((time.time() - t0) * 1000)
                        tokens = 0
                        cost = Decimal("0")

                    passed, score_val, reason = self._scorer.score(
                        case.scoring_type,
                        case.expected_output,
                        actual,
                        case.scoring_config,
                    )

                    return {
                        "case_id": case.id,
                        "status": "pass" if passed else "fail",
                        "actual_output": actual,
                        "score": Decimal(str(score_val)),
                        "failure_type": (
                            case.scoring_type if not passed else None
                        ),
                        "failure_reason": reason,
                        "similarity_score": (
                            Decimal(str(score_val))
                            if case.scoring_type == "semantic_similarity"
                            else None
                        ),
                        "latency_ms": latency_ms,
                        "tokens_used": tokens,
                        "cost_usd": cost,
                        "error_message": None,
                    }
                except Exception as exc:
                    logger.exception("Error evaluating case %s", case.id)
                    return {
                        "case_id": case.id,
                        "status": "error",
                        "actual_output": None,
                        "score": None,
                        "failure_type": "runtime_error",
                        "failure_reason": str(exc),
                        "similarity_score": None,
                        "latency_ms": None,
                        "tokens_used": None,
                        "cost_usd": None,
                        "error_message": str(exc),
                    }

        tasks = [_eval_case(c) for c in cases]
        eval_results = await asyncio.gather(*tasks)

        # Persist results and compute summary
        async with self._sf() as session:
            for r in eval_results:
                result_obj = EvalResult(
                    run_id=run_id,
                    case_id=r["case_id"],
                    status=r["status"],
                    actual_output=r["actual_output"],
                    score=r["score"],
                    failure_type=r["failure_type"],
                    failure_reason=r["failure_reason"],
                    similarity_score=r["similarity_score"],
                    latency_ms=r["latency_ms"],
                    tokens_used=r["tokens_used"],
                    cost_usd=r["cost_usd"],
                    error_message=r["error_message"],
                )
                session.add(result_obj)

            # Compute summary stats
            passed_count = sum(1 for r in eval_results if r["status"] == "pass")
            failed_count = sum(1 for r in eval_results if r["status"] == "fail")
            errored_count = sum(1 for r in eval_results if r["status"] == "error")
            total = len(eval_results)
            accuracy = (
                Decimal(str(round(passed_count / total * 100, 2)))
                if total > 0 else None
            )

            latencies = [
                r["latency_ms"] for r in eval_results
                if r["latency_ms"] is not None
            ]
            avg_lat = sum(latencies) / len(latencies) if latencies else None
            p95_lat = (
                sorted(latencies)[int(len(latencies) * 0.95)]
                if latencies else None
            )
            total_tokens = sum(
                r["tokens_used"] for r in eval_results
                if r["tokens_used"] is not None
            )
            total_cost = sum(
                r["cost_usd"] for r in eval_results
                if r["cost_usd"] is not None
            )
            duration = time.time() - run_start

            # Update run record
            now = datetime.now(timezone.utc)
            await session.execute(
                update(EvalRun)
                .where(EvalRun.id == run_id)
                .values(
                    status="completed",
                    passed=passed_count,
                    failed=failed_count,
                    errored=errored_count,
                    accuracy_pct=accuracy,
                    avg_latency_ms=avg_lat,
                    p95_latency_ms=p95_lat,
                    total_tokens=total_tokens,
                    total_cost_usd=total_cost,
                    duration_seconds=duration,
                    completed_at=now,
                )
            )

            # Update suite stats
            await session.execute(
                update(EvalSuite)
                .where(EvalSuite.id == suite_id)
                .values(
                    last_run_at=now,
                    last_accuracy_pct=accuracy,
                )
            )

            await session.commit()

        # Fetch the completed run with results
        return await self.get_run(run_id)

    # ── Run Queries ───────────────────────────────────────────

    async def get_run(self, run_id: uuid.UUID) -> EvalRunResponse:
        """Get an eval run with all results."""
        async with self._sf() as session:
            stmt = (
                select(EvalRun)
                .options(selectinload(EvalRun.results))
                .where(EvalRun.id == run_id)
            )
            result = await session.execute(stmt)
            run = result.scalar_one_or_none()
            if not run:
                raise ValueError(f"Run {run_id} not found")
            return EvalRunResponse.model_validate(run)

    async def get_failures(
        self, run_id: uuid.UUID,
    ) -> list[FailureAnalysis]:
        """Get failure analysis with grouping by failure_type."""
        async with self._sf() as session:
            stmt = (
                select(EvalResult)
                .where(
                    EvalResult.run_id == run_id,
                    EvalResult.status == "fail",
                )
            )
            result = await session.execute(stmt)
            failures = list(result.scalars().all())

            if not failures:
                return []

            # Group by failure_type
            grouped: dict[str, list[EvalResult]] = defaultdict(list)
            for f in failures:
                key = f.failure_type or "unknown"
                grouped[key].append(f)

            total_failures = len(failures)
            analyses = []
            for ftype, items in grouped.items():
                analyses.append(
                    FailureAnalysis(
                        failure_type=ftype,
                        count=len(items),
                        percentage=round(len(items) / total_failures * 100, 2),
                        examples=[
                            EvalResultResponse.model_validate(i)
                            for i in items[:5]  # Limit examples
                        ],
                    )
                )

            return sorted(analyses, key=lambda a: a.count, reverse=True)
