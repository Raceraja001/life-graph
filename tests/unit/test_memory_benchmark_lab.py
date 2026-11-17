"""Unit & regression tests for the Memory Evaluation Laboratory (P1).

Verifies single-variable ablation progression across separate tuning (`test_life.json`)
and held-out (`test_life_2.json`) datasets, temporal/supersession accuracy,
bitemporal validity, zero forgetting/deletion leakage, and abstention precision/recall.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from life_graph.services.memory.retrieval import EARLY_EXIT_CONFIDENCE, EARLY_EXIT_ENTAILMENT
from life_graph.services.memory_benchmark import (
    ADAPTIVE_ARM,
    BASELINE_ARM,
    BENCHMARK_METHODS,
    EARLY_EXIT_MEASURE,
    EARLY_EXIT_ON,
    PRIMARY_METHOD,
    TUNING_DATASET,
    build_corpus,
    compare_adaptive_early_exit,
    evaluate_lifecycle_invariants,
    retrieve_for_method,
    run_memory_benchmark,
    sweep_confidence_floors,
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


# --- Adaptive early-exit ablation (Track 2) --------------------------------


@pytest.fixture(scope="module")
def early_exit_report():
    # One timing pass: the quality metrics and gate verdicts are deterministic and
    # repeating only sharpens latency numbers nothing here asserts on.
    return compare_adaptive_early_exit(passes=1, sweep=False)


def test_measure_mode_retrieves_exactly_what_the_untouched_ladder_does():
    """`measure` may only pay for the verdict — never change what comes back."""
    data = json.loads(TUNING_DATASET.read_bytes().decode("utf-8"))
    corpus = build_corpus(data)
    today = date.fromisoformat(data["today"])

    for q in data["questions"]:
        plain, plain_abstained = retrieve_for_method(q, corpus, PRIMARY_METHOD)
        trace: dict = {}
        measured, measured_abstained = retrieve_for_method(
            q,
            corpus,
            PRIMARY_METHOD,
            early_exit_mode=EARLY_EXIT_MEASURE,
            today=today,
            trace=trace,
        )
        assert [m.id for m in measured] == [m.id for m in plain], q["id"]
        assert measured_abstained == plain_abstained
        assert trace["early_exit"] is False


def test_early_exit_skips_expansion_only_when_evidence_is_sufficient():
    data = json.loads(TUNING_DATASET.read_bytes().decode("utf-8"))
    corpus = build_corpus(data)
    today = date.fromisoformat(data["today"])

    exited = 0
    for q in data["questions"]:
        trace: dict = {}
        retrieve_for_method(
            q, corpus, PRIMARY_METHOD, early_exit_mode=EARLY_EXIT_ON, today=today, trace=trace
        )
        assert trace["early_exit"] == trace["sufficient"]
        if trace["early_exit"]:
            exited += 1
            ev = trace["evidence"]
            assert ev["calibrated_confidence"] >= EARLY_EXIT_CONFIDENCE
            assert ev["keywords_covered"] or ev["entailment_score"] >= EARLY_EXIT_ENTAILMENT
    # The gate is strict by design, but it must not be dead code either.
    assert exited > 0


def test_early_exit_mode_requires_a_reference_date():
    data = json.loads(TUNING_DATASET.read_bytes().decode("utf-8"))
    corpus = build_corpus(data)
    with pytest.raises(ValueError, match="requires `today`"):
        retrieve_for_method(
            data["questions"][0], corpus, PRIMARY_METHOD, early_exit_mode=EARLY_EXIT_ON
        )


@pytest.mark.parametrize("split_name", ["tuning_dev", "held_out"])
def test_early_exit_reports_both_arms_with_quality_and_latency(early_exit_report, split_name):
    split = early_exit_report["splits"][split_name]
    assert set(split["arms"]) == {BASELINE_ARM, ADAPTIVE_ARM}
    assert split["arms"][BASELINE_ARM]["early_exit"]["exit_rate_pct"] == 0.0

    exited = split["arms"][ADAPTIVE_ARM]["early_exit"]
    assert exited["total_questions"] == split["question_count"]
    assert 0 < exited["early_exited"] <= exited["total_questions"]
    assert exited["exit_rate_pct"] == pytest.approx(
        100.0 * exited["early_exited"] / exited["total_questions"], abs=0.01
    )
    assert len(split["early_exited_question_ids"]) == exited["early_exited"]

    for arm in (BASELINE_ARM, ADAPTIVE_ARM):
        lat = split["arms"][arm]["latency_ms"]
        assert lat["count"] == split["question_count"]
        assert 0.0 < lat["min"] <= lat["p50"] <= lat["p95"] <= lat["max"]
        assert lat["min"] <= lat["mean"] <= lat["max"]


@pytest.mark.parametrize("split_name", ["tuning_dev", "held_out"])
def test_early_exit_does_not_regress_recall_or_abstention(early_exit_report, split_name):
    split = early_exit_report["splits"][split_name]
    for metric in ("recall_at_1", "recall_at_5", "mrr", "full_support_at_5"):
        assert split["delta"]["quality"][metric]["delta"] >= 0.0, metric
    for metric in ("abstention_precision", "abstention_recall"):
        assert split["delta"]["quality"][metric]["adaptive"] >= 0.95, metric
    assert split["gates"]["passed"]
    assert early_exit_report["gates_passed"]


def test_confidence_floor_sweep_exit_rate_is_monotone_in_the_floor():
    rows = sweep_confidence_floors(TUNING_DATASET, floors=(0.92, 0.88, 0.85), passes=1)
    assert [r["confidence_floor"] for r in rows] == [0.92, 0.88, 0.85]
    # Relaxing the floor can only admit more questions, never fewer.
    assert rows[0]["early_exited"] <= rows[1]["early_exited"] <= rows[2]["early_exited"]


def test_compare_early_exit_cli_writes_report_and_leaves_verify_green(tmp_path):
    out_file = tmp_path / "early_exit.json"
    res = subprocess.run(
        [
            sys.executable,
            "scripts/eval_memory_benchmark.py",
            "--compare-early-exit",
            "--output-early-exit",
            str(out_file),
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "OK: adaptive early exit costs no retrieval quality." in res.stdout
    assert "Baseline" in res.stdout and "Adaptive" in res.stdout
    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert payload["benchmark"] == "life_graph_adaptive_early_exit_comparison_v1"
    assert payload["gates_passed"] is True
    assert set(payload["splits"]) == {"tuning_dev", "held_out"}
