"""The few-shot optimizer: candidate selection, the deploy gate, and the flow.

Deployment is automatic (the user's choice), so the gate is what stands
between a lucky candidate and every future extraction.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from life_graph.self_improving.models import EvalSuite
from life_graph.self_improving.optimizer_service import (
    FewShotOptimizerService,
    RunMetrics,
    gate,
    select_few_shot_sets,
)
from life_graph.self_improving.suite_builder import LabelledTrace


def _m(accuracy: float, f1: float, errored: int = 0, cases: int = 30) -> RunMetrics:
    return RunMetrics("run", accuracy, f1, errored, cases)


# ── gate ──────────────────────────────────────────────────────────────


def test_gate_passes_a_clear_improvement():
    assert gate(_m(60, 0.70), _m(70, 0.75), min_holdout=20, min_gain_pct=2) == []


def test_gate_blocks_small_gains():
    reasons = gate(_m(60, 0.70), _m(61, 0.75), min_holdout=20, min_gain_pct=2)
    assert any("needs +2" in r for r in reasons)


def test_gate_blocks_on_too_few_cases():
    reasons = gate(_m(10, 0.1, cases=5), _m(90, 0.9, cases=5), min_holdout=20, min_gain_pct=2)
    assert any("held-out cases" in r for r in reasons)


def test_gate_blocks_a_lower_mean_f1_even_with_higher_accuracy():
    reasons = gate(_m(60, 0.80), _m(70, 0.70), min_holdout=20, min_gain_pct=2)
    assert any("mean F1 dropped" in r for r in reasons)


def test_gate_blocks_more_errors():
    reasons = gate(_m(60, 0.7, errored=0), _m(70, 0.8, errored=2), min_holdout=20, min_gain_pct=2)
    assert any("more errors" in r for r in reasons)


# ── candidate selection ───────────────────────────────────────────────


def _pool(n_with: int, n_without: int, long: int = 0) -> list[LabelledTrace]:
    pool = [LabelledTrace(f"w{i}", f"text {i}", [{"content": f"fact {i}"}]) for i in range(n_with)]
    pool += [LabelledTrace(f"e{i}", f"noise {i}", []) for i in range(n_without)]
    pool += [LabelledTrace(f"l{i}", "x" * 5000, [{"content": "long"}]) for i in range(long)]
    return pool


def test_selection_is_deterministic_and_distinct():
    pool = _pool(10, 10)
    a = select_few_shot_sets(pool, k=3, n=3, seed="s")
    assert a == select_few_shot_sets(pool, k=3, n=3, seed="s")
    keys = {tuple(sorted(ex.trace_id for ex in s)) for s in a}
    assert len(keys) == len(a) == 3


def test_every_set_teaches_at_least_one_kept_fact():
    """A set of only 'extract nothing' examples would teach extracting nothing."""
    for s in select_few_shot_sets(_pool(1, 30), k=3, n=3, seed="x"):
        assert any(ex.expected for ex in s)


def test_overlong_inputs_are_not_used_as_examples():
    sets = select_few_shot_sets(_pool(3, 0, long=10), k=3, n=2, seed="y")
    assert all(ex.trace_id.startswith("w") for s in sets for ex in s)


def test_too_small_a_pool_yields_nothing():
    assert select_few_shot_sets(_pool(2, 0), k=3, n=3, seed="z") == []


# ── optimize() flow, with fakes ───────────────────────────────────────


class _FakeSession:
    """Just enough of an AsyncSession: get/add/commit over a dict."""

    def __init__(self, store: dict):
        self._store = store

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, _model, key):
        return self._store.get(str(key))

    def add(self, obj):
        self._store[str(obj.id)] = obj

    async def commit(self):
        return None


def _settings(**overrides):
    base = dict(
        optimization_min_improvement_pct=2.0,
        optimization_min_holdout=20,
        optimization_max_few_shot=3,
        optimization_candidates=3,
        eval_accuracy_threshold_pct=90.0,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _run(accuracy: float, f1: float, cases: int = 30):
    results = [SimpleNamespace(status="pass", score=Decimal(str(f1))) for _ in range(cases)]
    return SimpleNamespace(
        id=uuid.uuid4(),
        accuracy_pct=Decimal(str(accuracy)),
        errored=0,
        total_cases=cases,
        results=results,
    )


def _harness(baseline, candidates, settings=None):
    store: dict = {}
    suite_id = uuid.uuid4()
    store[str(suite_id)] = EvalSuite(
        id=suite_id, tenant_id="t", task_type="capture_extraction", name="s"
    )
    runs = iter([baseline, *candidates])

    async def run_eval(tenant_id, sid, version_id, trigger="manual", llm_fn=None):
        return next(runs)

    created: list = []
    activated: list = []

    async def create(tenant_id, data):
        version = SimpleNamespace(id=uuid.uuid4(), data=data)
        created.append(version)
        return version

    async def activate(tenant_id, version_id, reason=None):
        activated.append(str(version_id))

    async def get_active(tenant_id, task_type):
        return None

    optimizer = FewShotOptimizerService(
        session_factory=lambda: _FakeSession(store),
        eval_service=SimpleNamespace(run_eval=run_eval),
        prompt_version_service=SimpleNamespace(
            create=create, activate=activate, get_active=get_active
        ),
        settings=settings or _settings(),
    )
    return optimizer, suite_id, created, activated, store


@pytest.mark.asyncio
async def test_clear_winner_is_deployed(monkeypatch):
    notified = []

    async def _notify(self, *args):
        notified.append(args)

    monkeypatch.setattr(FewShotOptimizerService, "_notify_deployed", _notify)
    optimizer, suite_id, created, activated, _ = _harness(
        _run(60, 0.6), [_run(62, 0.6), _run(75, 0.8), _run(65, 0.7)]
    )

    out = await optimizer.optimize("t", suite_id, train_pool=_pool(10, 5))

    assert out["status"] == "deployed"
    assert len(created) == 3  # every candidate kept as a version
    assert activated == [str(created[1].id)]  # the best one
    assert notified, "a deploy must tell the user what changed and how to undo it"


@pytest.mark.asyncio
async def test_no_candidate_clears_the_gate():
    optimizer, suite_id, created, activated, store = _harness(
        _run(60, 0.6), [_run(61, 0.6), _run(60, 0.6), _run(59, 0.5)]
    )

    out = await optimizer.optimize("t", suite_id, train_pool=_pool(10, 5))

    assert out["status"] == "no_improvement"
    assert activated == []
    run = store[str(out["optimization_run_id"])]
    assert run.status == "no_improvement" and run.regression_details["gate"] != ["passed"]


@pytest.mark.asyncio
async def test_healthy_prompt_generates_no_candidates():
    optimizer, suite_id, created, activated, _ = _harness(_run(95, 0.95), [])

    out = await optimizer.optimize("t", suite_id, train_pool=_pool(10, 5))

    assert out["status"] == "no_improvement"
    assert out["details"]["reason"] == "healthy"
    assert created == []


@pytest.mark.asyncio
async def test_too_few_held_out_cases_stops_before_candidates():
    optimizer, suite_id, created, activated, _ = _harness(_run(40, 0.4, cases=5), [])

    out = await optimizer.optimize("t", suite_id, train_pool=_pool(10, 5))

    assert out["details"]["reason"] == "insufficient_holdout"
    assert created == [] and activated == []


@pytest.mark.asyncio
async def test_failures_are_recorded_not_raised():
    optimizer, suite_id, *_ = _harness(_run(60, 0.6), [])  # candidate runs exhausted

    out = await optimizer.optimize("t", suite_id, train_pool=_pool(10, 5))

    assert out["status"] == "error"
