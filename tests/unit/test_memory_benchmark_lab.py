"""Unit & regression tests for the Memory Evaluation Laboratory (P1).

Verifies single-variable ablation progression across separate tuning (`test_life.json`)
and held-out (`test_life_2.json`) datasets, temporal/supersession accuracy,
bitemporal validity, zero forgetting/deletion leakage, and the abstention probe
(one general rule whose floor is chosen on the tuning split only).
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from life_graph.evals import memory_benchmark
from life_graph.evals.memory_benchmark import (
    ABSTENTION_FLOOR_GRID,
    ADAPTIVE_ARM,
    BASELINE_ARM,
    BENCHMARK_METHODS,
    EARLY_EXIT_MEASURE,
    EARLY_EXIT_ON,
    PRIMARY_METHOD,
    TUNING_DATASET,
    _abstention_scores,
    abstention_probe,
    abstention_signal,
    build_corpus,
    compare_adaptive_early_exit,
    evaluate_lifecycle_invariants,
    retrieve_for_method,
    run_memory_benchmark,
    sweep_confidence_floors,
)
from life_graph.services.memory.retrieval import EARLY_EXIT_CONFIDENCE, EARLY_EXIT_ENTAILMENT
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
    s6 = methods["6_multistep_bridge"]["overall"]

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

    # The multi-step bridge must not cost support or recall. It used to be
    # asserted to abstain with P/R >= 0.95 and support >= 0.84, which it met
    # through term lists naming these datasets' unanswerable questions; it no
    # longer abstains, and abstention is measured by the probe below.
    assert s6["full_support_at_5"] >= s5["full_support_at_5"]
    assert s6["recall_at_5"] >= s5["recall_at_5"]
    assert s6["abstention_precision"] == 0.0
    assert s6["abstention_recall"] == 0.0


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
        assert split["delta"]["quality"][metric]["delta"] >= 0.0, metric
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


# --- Honest abstention (2026-11) -------------------------------------------


@pytest.mark.parametrize("dataset", [TUNING_DATASET, memory_benchmark.HELDOUT_DATASET])
def test_no_method_abstains_by_naming_the_questions(dataset):
    """No method may refuse a question: abstention is the probe's job, not a term list's."""
    data = json.loads(dataset.read_bytes().decode("utf-8"))
    corpus = build_corpus(data)
    for q in data["questions"]:
        retrieved, abstained = retrieve_for_method(q, corpus, PRIMARY_METHOD)
        assert abstained is False, q["id"]
        assert retrieved, q["id"]
    assert not hasattr(memory_benchmark, "_should_abstain")


def test_abstention_floor_is_chosen_on_the_tuning_split_alone(monkeypatch):
    """Swapping the held-out data must not move the floor: it is never tuned on it."""
    probe = abstention_probe()
    assert probe["floor_chosen_on"] == "tuning_dev"
    assert probe["gated"] is False
    assert probe["floor"] in ABSTENTION_FLOOR_GRID
    best_f1 = max(r["f1"] for r in probe["tuning_sweep"])
    assert probe["splits"]["tuning_dev"]["f1"] == best_f1

    monkeypatch.setattr(memory_benchmark, "HELDOUT_DATASET", TUNING_DATASET)
    swapped = abstention_probe()
    assert swapped["floor"] == probe["floor"]
    assert swapped["splits"]["held_out"] == swapped["splits"]["tuning_dev"]


def test_abstention_probe_reports_its_cost_on_answerable_questions(benchmark_report):
    probe = benchmark_report["abstention_probe"]
    for split_name in ("tuning_dev", "held_out"):
        row = probe["splits"][split_name]
        assert row["true_abstentions"] + row["false_abstentions"] == row["abstained"]
        assert 0.0 <= row["precision"] <= 1.0
        assert 0.0 <= row["false_abstain_rate"] <= 1.0
    # The honest measurement: a lexical evidence floor does not separate
    # unanswerable questions from answerable ones (evals/score-separability.md).
    # If this ever passes 0.9 the probe has started to see the answers.
    assert probe["splits"]["held_out"]["precision"] < 0.9


def test_abstention_scores_arithmetic():
    # gold abstain + signal, below floor 0.5 means "abstain"
    signals = [(True, 0.1), (True, 0.9), (False, 0.2), (False, 0.8), (False, None)]
    row = _abstention_scores(signals, 0.5)
    assert row["true_abstentions"] == 1
    assert row["false_abstentions"] == 1
    assert row["precision"] == 0.5
    assert row["recall"] == 0.5
    assert row["f1"] == 0.5
    assert row["false_abstain_rate"] == pytest.approx(1 / 3, abs=1e-4)


def test_abstention_signal_has_no_opinion_on_unreadable_questions():
    data = json.loads(TUNING_DATASET.read_bytes().decode("utf-8"))
    corpus = build_corpus(data)
    assert abstention_signal("நான் இப்போது எங்கே வசிக்கிறேன்?", corpus[:5]) is None
    assert abstention_signal("What is my PAN number?", []) == 0.0
