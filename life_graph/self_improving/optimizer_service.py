"""Few-shot prompt optimizer — replaces the DSPy optimizer.

The DSPy version could not run: dspy was never a dependency (so it always ran
in "degraded mode"), it was hardcoded to OpenRouter, and it read columns and
called methods that did not exist. This one does what that design reduced to
for a local, single-task setup, with no new dependency:

1. Evaluate the active prompt (or the built-in one) on the held-out cases.
2. Build a few candidates: the same prompt plus ``optimization_max_few_shot``
   worked examples drawn from the user's own reviewed captures (training
   split only — the held-out cases are never used as examples).
3. Evaluate each candidate on the same held-out cases, with the same runner
   production uses.
4. Deploy the best one only if it clears the gate (``gate``). Every candidate
   is kept as an inactive prompt version, and every run is recorded in
   optimization_runs, so a deploy is inspectable and one call rolls it back.

Deployment is automatic by the user's choice, so the gate is strict and
fail-closed: too few held-out cases, a gain under
``optimization_min_improvement_pct``, a lower mean F1, or more errors all block
it. A deploy creates a notification saying what changed and how to undo it.
"""

from __future__ import annotations

import logging
import random
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)

_MAX_EXAMPLE_CHARS = 1500  # keep few-shot prompts affordable on every extraction


@dataclass(frozen=True)
class RunMetrics:
    """What the gate compares between two eval runs of the same cases."""

    eval_run_id: str
    accuracy_pct: float
    mean_f1: float
    errored: int
    cases: int

    @classmethod
    def from_run(cls, run: Any) -> RunMetrics:
        results = list(getattr(run, "results", None) or [])
        scored = [float(r.score) for r in results if r.status != "error" and r.score is not None]
        return cls(
            eval_run_id=str(run.id),
            accuracy_pct=float(run.accuracy_pct or 0.0),
            mean_f1=round(sum(scored) / len(scored), 4) if scored else 0.0,
            errored=int(run.errored or 0),
            cases=int(run.total_cases or len(results)),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "eval_run_id": self.eval_run_id,
            "accuracy_pct": self.accuracy_pct,
            "mean_f1": self.mean_f1,
            "errored": self.errored,
            "cases": self.cases,
        }


def gate(
    baseline: RunMetrics, candidate: RunMetrics, *, min_holdout: int, min_gain_pct: float
) -> list[str]:
    """Reasons *not* to deploy. Empty means deploy. Pure, for testing."""
    reasons: list[str] = []
    if candidate.cases < min_holdout:
        reasons.append(f"only {candidate.cases} held-out cases (need {min_holdout})")
    if candidate.accuracy_pct < baseline.accuracy_pct + min_gain_pct:
        reasons.append(
            f"accuracy {candidate.accuracy_pct:.1f}% vs {baseline.accuracy_pct:.1f}% "
            f"(needs +{min_gain_pct:g} points)"
        )
    if candidate.mean_f1 < baseline.mean_f1:
        reasons.append(f"mean F1 dropped {baseline.mean_f1:.3f} -> {candidate.mean_f1:.3f}")
    if candidate.errored > baseline.errored:
        reasons.append(f"more errors ({candidate.errored} vs {baseline.errored})")
    return reasons


def select_few_shot_sets(pool: list[Any], *, k: int, n: int, seed: str) -> list[list[Any]]:
    """*n* distinct sets of *k* examples from the training pool.

    Deterministic per seed. Each set includes at least one example where the
    user kept something, when the pool has one — a set of only "extract
    nothing" examples would teach the model to extract nothing.
    """
    usable = [ex for ex in pool if len(ex.input_text) <= _MAX_EXAMPLE_CHARS]
    if k <= 0 or len(usable) < k:
        return []
    rng = random.Random(seed)
    with_facts = [ex for ex in usable if ex.expected]
    sets: list[list[Any]] = []
    seen: set[tuple[str, ...]] = set()
    for _ in range(n * 10):
        if len(sets) >= n:
            break
        chosen = rng.sample(usable, k)
        if with_facts and not any(ex.expected for ex in chosen):
            chosen[0] = rng.choice(with_facts)
            if len({ex.trace_id for ex in chosen}) < k:
                continue
        key = tuple(sorted(ex.trace_id for ex in chosen))
        if key in seen:
            continue
        seen.add(key)
        sets.append(chosen)
    return sets


class FewShotOptimizerService:
    """Evaluate, generate few-shot candidates, gate, and auto-deploy."""

    def __init__(self, session_factory, eval_service, prompt_version_service, settings):
        self.session_factory = session_factory
        self.eval_service = eval_service
        self.prompt_version_service = prompt_version_service
        self.settings = settings

    async def optimize(
        self,
        tenant_id: str,
        suite_id: uuid.UUID,
        *,
        train_pool: list[Any] | None = None,
    ) -> dict[str, Any]:
        """Run one optimization for a suite. Never raises; returns a status dict.

        status: deployed | no_improvement | skipped | error
        """
        from life_graph.self_improving.models import EvalSuite, OptimizationRun
        from life_graph.self_improving.schemas import PromptVersionCreate
        from life_graph.self_improving.task_runner import llm_fn_for

        run_id = uuid.uuid4()
        s = self.settings
        try:
            async with self.session_factory() as session:
                suite = await session.get(EvalSuite, suite_id)
            if suite is None or suite.tenant_id != tenant_id:
                return {
                    "status": "error",
                    "optimization_run_id": None,
                    "details": "suite not found",
                }
            task_type = suite.task_type
            if llm_fn_for(task_type) is None:
                return {
                    "status": "skipped",
                    "optimization_run_id": None,
                    "details": f"no runner for task {task_type}",
                }

            if train_pool is None:
                from life_graph.self_improving.suite_builder import sync_suite

                train_pool = (await sync_suite(tenant_id))["train_pool"]

            active = await self.prompt_version_service.get_active(tenant_id, task_type)
            base_version_id = str(active.id) if active else "default"
            if active:
                base_prompt = active.prompt_text
            else:
                from life_graph.extraction.llm import default_prompt

                base_prompt = default_prompt()

            baseline_run = await self.eval_service.run_eval(
                tenant_id, suite_id, base_version_id, trigger="regression_check"
            )
            baseline = RunMetrics.from_run(baseline_run)

            async with self.session_factory() as session:
                session.add(
                    OptimizationRun(
                        id=run_id,
                        tenant_id=tenant_id,
                        suite_id=suite_id,
                        task_type=task_type,
                        trigger_eval_run_id=baseline.eval_run_id,
                        trigger_accuracy_pct=Decimal(str(baseline.accuracy_pct)),
                        threshold_pct=Decimal(str(s.optimization_min_improvement_pct)),
                        training_positive_count=sum(1 for ex in train_pool if ex.expected),
                        training_negative_count=sum(1 for ex in train_pool if not ex.expected),
                        previous_version_id=base_version_id,
                        previous_accuracy_pct=Decimal(str(baseline.accuracy_pct)),
                        status="running",
                        started_at=datetime.now(UTC),
                    )
                )
                await session.commit()

            if baseline.accuracy_pct >= s.eval_accuracy_threshold_pct:
                # Already good: generating candidates would only add unused
                # prompt versions every night.
                return await self._finish(
                    run_id,
                    "no_improvement",
                    {"reason": "healthy", "baseline": baseline.as_dict()},
                )

            if baseline.cases < s.optimization_min_holdout:
                return await self._finish(
                    run_id,
                    "no_improvement",
                    {
                        "reason": "insufficient_holdout",
                        "baseline": baseline.as_dict(),
                        "min_holdout": s.optimization_min_holdout,
                    },
                )

            sets = select_few_shot_sets(
                train_pool,
                k=s.optimization_max_few_shot,
                n=s.optimization_candidates,
                seed=str(run_id),
            )
            if not sets:
                return await self._finish(
                    run_id,
                    "no_improvement",
                    {"reason": "not_enough_training_examples", "baseline": baseline.as_dict()},
                )

            candidates: list[tuple[str, RunMetrics]] = []
            for index, examples in enumerate(sets, start=1):
                version = await self.prompt_version_service.create(
                    tenant_id,
                    PromptVersionCreate(
                        task_type=task_type,
                        prompt_text=base_prompt,
                        few_shot_examples=[ex.as_few_shot() for ex in examples],
                        created_by="self_improving",
                        change_note=(
                            f"Candidate {index}/{len(sets)} of optimization {run_id}: "
                            f"{len(examples)} examples from reviewed captures"
                        ),
                    ),
                )
                candidate_run = await self.eval_service.run_eval(
                    tenant_id, suite_id, str(version.id), trigger="optimization_test"
                )
                candidates.append((str(version.id), RunMetrics.from_run(candidate_run)))

            best_id, best = max(candidates, key=lambda c: (c[1].accuracy_pct, c[1].mean_f1))
            blockers = gate(
                baseline,
                best,
                min_holdout=s.optimization_min_holdout,
                min_gain_pct=s.optimization_min_improvement_pct,
            )
            details = {
                "baseline": baseline.as_dict(),
                "best_candidate": {"version_id": best_id, **best.as_dict()},
                "candidates": [{"version_id": v, **m.as_dict()} for v, m in candidates],
                "gate": blockers or ["passed"],
            }

            async with self.session_factory() as session:
                opt_run = await session.get(OptimizationRun, run_id)
                opt_run.candidate_version_id = best_id
                opt_run.candidate_eval_run_id = best.eval_run_id
                opt_run.candidate_accuracy_pct = Decimal(str(best.accuracy_pct))
                await session.commit()

            if blockers:
                return await self._finish(run_id, "no_improvement", details)

            await self.prompt_version_service.activate(
                tenant_id,
                uuid.UUID(best_id),
                reason=(
                    f"Auto-deployed by optimization {run_id}: accuracy "
                    f"{baseline.accuracy_pct:.1f}% -> {best.accuracy_pct:.1f}%, mean F1 "
                    f"{baseline.mean_f1:.3f} -> {best.mean_f1:.3f} on {best.cases} held-out cases"
                ),
            )
            await self._notify_deployed(
                tenant_id, task_type, baseline, best, best_id, base_version_id
            )
            return await self._finish(run_id, "deployed", details)

        except Exception as exc:
            logger.exception("Optimization failed for suite %s", suite_id)
            return await self._finish(run_id, "error", {"error": str(exc)})

    async def _finish(self, run_id: uuid.UUID, status: str, details: dict) -> dict[str, Any]:
        from life_graph.self_improving.models import OptimizationRun

        try:
            async with self.session_factory() as session:
                opt_run = await session.get(OptimizationRun, run_id)
                if opt_run is not None:
                    opt_run.status = status
                    opt_run.regression_details = details
                    opt_run.completed_at = datetime.now(UTC)
                    if status == "error":
                        opt_run.error_message = str(details.get("error"))[:2000]
                    await session.commit()
        except Exception:
            logger.warning("Could not record optimization run %s", run_id, exc_info=True)
        return {"status": status, "optimization_run_id": run_id, "details": details}

    async def _notify_deployed(
        self,
        tenant_id: str,
        task_type: str,
        baseline: RunMetrics,
        best: RunMetrics,
        version_id: str,
        previous_version_id: str,
    ) -> None:
        """Tell the user what changed and how to undo it. Never raises."""
        undo = (
            f"POST /api/v1/self-improving/prompt-versions/{previous_version_id}/rollback"
            if previous_version_id != "default"
            else f"POST /api/v1/self-improving/prompt-versions/deactivate?task_type={task_type}"
        )
        try:
            from life_graph.api.dependencies import get_notification_engine

            await get_notification_engine().create(
                tenant_id,
                "Memory extraction improved itself",
                body=(
                    f"A new {task_type} prompt was deployed: {best.accuracy_pct:.0f}% of held-out "
                    f"captures handled well, up from {baseline.accuracy_pct:.0f}% "
                    f"({best.cases} cases, learned from your reviews). To undo: {undo}"
                ),
                priority="info",
                source_type="self_improving",
                source_id=version_id,
                metadata={
                    "task_type": task_type,
                    "version_id": version_id,
                    "previous_version_id": previous_version_id,
                    "baseline": baseline.as_dict(),
                    "candidate": best.as_dict(),
                },
            )
        except Exception:
            logger.warning("Deploy notification failed", exc_info=True)
