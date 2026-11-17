"""Unit & regression tests for the Memory Evaluation Laboratory (P1).

Verifies single-variable ablation progression across separate tuning (`test_life.json`)
and held-out (`test_life_2.json`) datasets, temporal/supersession accuracy,
bitemporal validity, zero forgetting/deletion leakage, and abstention precision/recall.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from life_graph.services.memory_benchmark import (
    BENCHMARK_METHODS,
    evaluate_lifecycle_invariants,
    run_memory_benchmark,
)
from scripts.eval_memory_benchmark import verify_report


@pytest.fixture(scope="module")
def benchmark_report():
    return run_memory_benchmark()


def test_tuning_and_heldout_datasets_are_distinct_and_hashed(benchmark_report):
    tuning = benchmark_report["splits"]["tuning_dev"]
    held_out = benchmark_report["splits"]["held_out"]

    assert tuning["dataset_file"] == "evals/memory_structures/test_life.json"
    assert held_out["dataset_file"] == "evals/memory_structures/test_life_2.json"
    assert tuning["dataset_sha256"] != held_out["dataset_sha256"]
    assert tuning["question_count"] == 140
    assert held_out["question_count"] == 185
    assert tuple(tuning["methods"].keys()) == BENCHMARK_METHODS
    assert tuple(held_out["methods"].keys()) == BENCHMARK_METHODS


@pytest.mark.parametrize("split_name", ["tuning_dev", "held_out"])
def test_single_variable_ablation_ladder_improves_target_metrics(benchmark_report, split_name):
    methods = benchmark_report["splits"][split_name]["methods"]
    s1 = methods["1_lexical_bm25"]["overall"]
    s3 = methods["3_hybrid_rrf"]["overall"]
    s4 = methods["4_graph_entity_expansion"]["overall"]
    s5 = methods["5_rerank_temporal_provenance"]["overall"]
    s6 = methods["6_multistep_adaptive_abstain"]["overall"]

    # Hybrid RRF improves over pure lexical BM25 on Recall@1, Recall@5, and MRR
    assert s3["recall_at_1"] > s1["recall_at_1"]
    assert s3["recall_at_5"] > s1["recall_at_5"]
    assert s3["mrr"] > s1["mrr"]

    # Graph & alias expansion improves Recall@1, Recall@5, MRR, and full support
    assert s4["recall_at_1"] > s3["recall_at_1"]
    assert s4["recall_at_5"] >= s3["recall_at_5"] + 0.08
    assert s4["mrr"] > s3["mrr"]
    assert s4["full_support_at_5"] > s3["full_support_at_5"]

    # Temporal supersession reranking improves temporal accuracy, correction supersession, and R@1
    assert s5["recall_at_1"] >= s4["recall_at_1"]
    assert s5["temporal_accuracy"] >= s4["temporal_accuracy"] + 0.10
    assert s5["correction_supersession_rate"] >= s4["correction_supersession_rate"] + 0.20
    assert s5["full_support_at_5"] > s4["full_support_at_5"]

    # Multi-step adaptive abstention achieves >= 0.95 abstention precision & recall and >= 0.84 support@5
    assert s6["abstention_precision"] >= 0.95
    assert s6["abstention_recall"] >= 0.95
    assert s6["full_support_at_5"] >= 0.84


def test_lifecycle_invariants_bitemporal_forgetting_and_provenance():
    inv = evaluate_lifecycle_invariants()
    assert inv["bitemporal_accuracy"] == 1.0
    assert inv["forgetting_leakage_rate"] == 0.0
    assert inv["forgetting_clean"] is True
    assert inv["provenance_contradiction_gate_ok"] is True


def test_verify_report_passes_and_cli_writes_auditable_report(benchmark_report, tmp_path):
    assert verify_report(benchmark_report) == []
    out_file = tmp_path / "report.json"
    res = subprocess.run(
        [sys.executable, "scripts/eval_memory_benchmark.py", "--output", str(out_file), "--verify"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "OK: All memory evaluation laboratory gates passed." in res.stdout
    assert out_file.exists()
