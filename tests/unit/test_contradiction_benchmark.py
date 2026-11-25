"""Tests for the contradiction and false-merge evaluation (M3).

The eval measures production code (services/contradiction.py and the ingest
merge rule in core/memory_manager.py); these tests keep the measurement
honest: the labels are consistent, the merge rule is the one production runs,
and the committed baseline is what the code does today.
"""

from __future__ import annotations

import copy
import inspect
import json
import subprocess
import sys
from pathlib import Path

import pytest

from life_graph.config import settings
from life_graph.core.memory_manager import MemoryManager
from life_graph.evals.contradiction_benchmark import (
    BASELINE_PATH,
    NEGATIVE_CATEGORIES,
    PAIRS_PATH,
    POSITIVE_CATEGORIES,
    baseline_of,
    evaluate_pair,
    regressions,
    run_contradiction_benchmark,
    summarize,
    would_merge,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def report():
    return run_contradiction_benchmark()


def test_pairs_are_labeled_consistently():
    data = json.loads(PAIRS_PATH.read_text(encoding="utf-8"))
    pairs = data["pairs"]
    assert 30 <= len(pairs) <= 50
    assert len({p["id"] for p in pairs}) == len(pairs)
    cats = {p["category"] for p in pairs}
    assert cats == set(POSITIVE_CATEGORIES) | set(NEGATIVE_CATEGORIES)
    for p in pairs:
        assert p["contradiction"] is (p["category"] in POSITIVE_CATEGORIES), p["id"]
        assert p["distinct"] is (p["category"] != "paraphrase"), p["id"]
    # The assumed cosine must sit above both thresholds, or the eval would
    # measure nothing: every pair would be filtered out before the rules run.
    assert data["assumed_cosine"] >= settings.dedup_threshold
    assert data["assumed_cosine"] >= settings.contradiction_similarity_threshold


def test_merge_rule_is_the_one_memory_manager_runs():
    """would_merge mirrors _process_fact; if production changes, so must this."""
    src = inspect.getsource(MemoryManager._process_fact)
    assert "s >= settings.dedup_threshold" in src
    assert "not differs_by_negation(fact.content, m.content)" in src
    assert "not differs_in_detail(fact.content, m.content)" in src


def test_committed_baseline_matches_the_code_today(report):
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    assert regressions(report, baseline) == []
    assert baseline_of(report) == baseline


def test_value_change_recall_is_recorded_not_hidden(report):
    # Recorded as found on 2026-11-25: no rule catches a changed date, number,
    # place or person. A fix should raise this and re-record the baseline.
    entry = report["by_category"]["value_change"]
    assert entry["pairs"] >= 8
    assert "contradiction_recall" in entry


def test_below_thresholds_nothing_is_merged_or_flagged():
    pair = {
        "id": "x",
        "category": "negation",
        "existing": "I use Docker.",
        "new": "I don't use Docker.",
        "contradiction": True,
        "distinct": True,
    }
    hot = evaluate_pair(pair, 0.95)
    assert hot["predicted_contradiction"] is True
    cold = evaluate_pair({**pair, "cosine": 0.5}, 0.95)
    assert cold["predicted_contradiction"] is False
    assert cold["would_merge"] is False
    assert would_merge("I use Docker.", "I use Docker every day.", 0.95) is True
    assert would_merge("I use Docker.", "I use Docker every day.", 0.90) is False


def test_summarize_arithmetic():
    def row(cat, gold_c, pred_c, distinct, merged):
        return {
            "id": cat,
            "category": cat,
            "gold_contradiction": gold_c,
            "predicted_contradiction": pred_c,
            "gold_distinct": distinct,
            "would_merge": merged,
        }

    rows = [
        row("negation", True, True, True, False),
        row("value_change", True, False, True, True),
        row("compatible_addition", False, True, True, False),
        row("paraphrase", False, False, False, True),
    ]
    ov = summarize(rows)["overall"]
    assert ov["contradiction_precision"] == 0.5
    assert ov["contradiction_recall"] == 0.5
    assert ov["false_merge_rate"] == pytest.approx(1 / 3, abs=1e-4)
    assert ov["paraphrase_merge_rate"] == 1.0


def test_regressions_fail_only_when_worse(report):
    base = baseline_of(report)
    assert regressions(report, base) == []

    better = copy.deepcopy(report)
    better["overall"]["contradiction_recall"] = 1.0
    better["overall"]["false_merge_rate"] = 0.0
    assert regressions(better, base) == []

    worse = copy.deepcopy(report)
    worse["overall"]["contradiction_precision"] = base["overall"]["contradiction_precision"] - 0.1
    worse["overall"]["false_merge_rate"] = base["overall"]["false_merge_rate"] + 0.1
    worse["by_category"]["negation"]["contradiction_recall"] = -1.0
    found = regressions(worse, base)
    assert any(f.startswith("contradiction_precision") for f in found)
    assert any(f.startswith("false_merge_rate") for f in found)
    assert any(f.startswith("negation.contradiction_recall") for f in found)

    changed = copy.deepcopy(report)
    changed["dataset_sha256"] = "0" * 64
    assert any("pairs.json changed" in f for f in regressions(changed, base))


def test_cli_verify_passes_and_writes_report(tmp_path):
    out = tmp_path / "report.json"
    res = subprocess.run(
        [sys.executable, "scripts/eval_contradiction.py", "--output", str(out), "--verify"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "OK: no contradiction or false-merge metric regressed." in res.stdout
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["benchmark"] == "life_graph_contradiction_false_merge_v1"
    assert len(payload["pairs"]) == payload["overall"]["pairs"]
