#!/usr/bin/env python3
"""CLI runner for the Life Graph Memory Evaluation Laboratory (P1).

Runs the 6-stage single-variable retrieval & lifecycle ablation benchmark across
separate tuning (`test_life.json`) and held-out (`test_life_2.json`) datasets,
writes `evals/memory_benchmark_report.json`, and enforces regression thresholds
when `--verify` is passed.

Abstention is reported (the report's `abstention_probe`), not gated. The gate that
required method 6 to abstain with precision and recall >= 0.90 was removed in
2026-11: method 6 met it through term lists naming the datasets' own unanswerable
questions, so it measured the lists. See life_graph/evals/memory_benchmark.py.

With `--compare-early-exit` it instead runs the adaptive early-exit ablation — the
top-of-ladder method with the gate off and then on, per split — printing the quality
and latency comparison and writing `evals/adaptive_early_exit_benchmark.json`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from life_graph.evals.memory_benchmark import (  # noqa: E402
    ADAPTIVE_ARM,
    BASELINE_ARM,
    compare_adaptive_early_exit,
    run_memory_benchmark,
)

DEFAULT_OUTPUT = ROOT / "evals" / "memory_benchmark_report.json"
DEFAULT_EARLY_EXIT_OUTPUT = ROOT / "evals" / "adaptive_early_exit_benchmark.json"

ARM_LABELS = {BASELINE_ARM: "Baseline", ADAPTIVE_ARM: "Adaptive"}

# Ladder gates, set from the numbers measured on 2026-11-25 after the lab's
# stage 4-5 lists stopped naming held-out people, places and products. Before
# that, the held-out split was not held out for those stages, and the old
# margins (+0.05 R@5, +0.08 temporal) were met partly by those names.
#
#
# Re-measured later on 2026-11-25, once stages 5-6 stopped reading the gold
# question `kind` (they classify the question text instead) and the scorer
# stopped using the lab's own slot rules (it reads gold `must_not` traps only).
#
# Stage 4 (graph/alias expansion) R@5 gain: +0.136 tuning, +0.041 held-out.
STAGE4_MIN_RECALL_GAIN = 0.03
# Stage 5 (temporal rerank) temporal-accuracy gain: +0.040 tuning, +0.019
# held-out (one question each). It was +0.120/+0.058 while it read gold kinds.
STAGE5_MIN_TEMPORAL_GAIN = 0.01
# Stage 6 (bridge hop) does not reliably help: on tuning it costs 0.0072
# support, on held-out it adds 0.0054 support and leaves R@5 unchanged. The
# gate only caps its cost; it is not a claim that the stage improves anything.
BRIDGE_MAX_COST = 0.02


def verify_report(report: dict) -> list[str]:
    failures: list[str] = []
    lifecycle = report.get("lifecycle_invariants", {})
    if lifecycle.get("bitemporal_accuracy") != 1.0:
        failures.append(f"bitemporal_accuracy={lifecycle.get('bitemporal_accuracy')} != 1.0")
    if lifecycle.get("forgetting_leakage_rate", 1.0) > 0.0 or not lifecycle.get("forgetting_clean"):
        failures.append(f"forgetting_leakage_rate={lifecycle.get('forgetting_leakage_rate')} > 0.0")
    if not lifecycle.get("provenance_contradiction_gate_ok"):
        failures.append("provenance_contradiction_gate_ok is False")

    for split_name in ("tuning_dev", "held_out"):
        split = report["splits"][split_name]["methods"]
        s1 = split["1_lexical_bm25"]["overall"]
        s3 = split["3_hybrid_rrf"]["overall"]
        s4 = split["4_graph_entity_expansion"]["overall"]
        s5 = split["5_rerank_temporal_provenance"]["overall"]
        s6 = split["6_multistep_bridge"]["overall"]

        if s3["recall_at_5"] < s1["recall_at_5"]:
            failures.append(
                f"{split_name}: 3_hybrid_rrf R@5 ({s3['recall_at_5']}) < 1_lexical_bm25 ({s1['recall_at_5']})"
            )
        if s4["recall_at_5"] < s3["recall_at_5"] + STAGE4_MIN_RECALL_GAIN:
            failures.append(
                f"{split_name}: 4_graph_entity_expansion R@5 ({s4['recall_at_5']}) did not improve over 3_hybrid_rrf ({s3['recall_at_5']})"
            )
        if s5["temporal_accuracy"] < s4["temporal_accuracy"] + STAGE5_MIN_TEMPORAL_GAIN:
            failures.append(
                f"{split_name}: 5_rerank_temporal_provenance temporal_accuracy ({s5['temporal_accuracy']}) did not improve over 4_graph_entity_expansion ({s4['temporal_accuracy']})"
            )
        # The bridge hop is measured to cost a little (see BRIDGE_MAX_COST), so
        # this only stops it from costing more.
        if s6["full_support_at_5"] < s5["full_support_at_5"] - BRIDGE_MAX_COST:
            failures.append(
                f"{split_name}: 6_multistep_bridge full_support_at_5 ({s6['full_support_at_5']}) is more than {BRIDGE_MAX_COST} below 5_rerank_temporal_provenance ({s5['full_support_at_5']})"
            )
        if s6["recall_at_5"] < s5["recall_at_5"] - BRIDGE_MAX_COST:
            failures.append(
                f"{split_name}: 6_multistep_bridge R@5 ({s6['recall_at_5']}) is more than {BRIDGE_MAX_COST} below 5_rerank_temporal_provenance ({s5['recall_at_5']})"
            )
    return failures


def _display_path(path: Path) -> str:
    """Repo-relative when it is in the repo; an output path need not be."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def print_early_exit_comparison(report: dict) -> None:
    """Print the baseline-vs-adaptive comparison, the paired saving, and the sweep."""
    thresholds = report["thresholds"]
    print(
        f"Adaptive early-exit ablation — method {report['method']}, "
        f"confidence >= {thresholds['calibrated_confidence']} and "
        f"entailment >= {thresholds['entailment']} "
        f"({report['timing_passes']} timing passes, fastest kept per question)\n"
    )

    header = (
        f"{'Split':<12} {'Mode':<9} {'ExitRate':>9} {'R@1':>7} {'R@5':>7} "
        f"{'MRR':>7} {'Support@5':>10} {'p50 (ms)':>9} {'p95 (ms)':>9}"
    )
    print(header)
    print("-" * len(header))
    for split_name, split in report["splits"].items():
        for arm in (BASELINE_ARM, ADAPTIVE_ARM):
            ov = split["arms"][arm]["overall"]
            lat = split["arms"][arm]["latency_ms"]
            exit_pct = split["arms"][arm]["early_exit"]["exit_rate_pct"]
            print(
                f"{split_name:<12} {ARM_LABELS[arm]:<9} {exit_pct:>8.2f}% "
                f"{ov['recall_at_1']:>7.4f} {ov['recall_at_5']:>7.4f} {ov['mrr']:>7.4f} "
                f"{ov['full_support_at_5']:>10.4f} {lat['p50']:>9.3f} {lat['p95']:>9.3f}"
            )
        print("-" * len(header))

    for split_name, split in report["splits"].items():
        delta = split["delta"]
        paired = delta["on_early_exited_questions"]
        exited = split["arms"][ADAPTIVE_ARM]["early_exit"]
        print(
            f"\n[{split_name}] {exited['early_exited']}/{exited['total_questions']} questions "
            f"early exited ({exited['exit_rate_pct']}%); "
            f"abstention P/R {delta['quality']['abstention_precision']['adaptive']:.4f}/"
            f"{delta['quality']['abstention_recall']['adaptive']:.4f}"
        )
        for metric in ("recall_at_1", "recall_at_5", "mrr", "full_support_at_5"):
            d = delta["quality"][metric]
            print(
                f"    {metric:<20} {d['baseline']:.4f} -> {d['adaptive']:.4f} "
                f"(delta {d['delta']:+.4f})"
            )
        for stat in ("mean", "p50", "p95"):
            d = delta["latency"][stat]
            rel = "n/a" if d["relative_pct"] is None else f"{d['relative_pct']:+.2f}%"
            print(
                f"    latency {stat:<12} {d['baseline_ms']:.3f} -> {d['adaptive_ms']:.3f} ms "
                f"({rel})"
            )
        if paired["count"]:
            print(
                f"    on the {paired['count']} early-exited questions: "
                f"{paired['baseline']['mean']:.3f} -> {paired['adaptive']['mean']:.3f} ms mean "
                f"({paired['mean_saving_ms']:.3f} ms, {paired['mean_saving_pct']:.2f}% saved)"
            )
        failed = [k for k, ok in split["gates"]["checks"].items() if not ok]
        print(f"    quality gates: {'PASS' if split['gates']['passed'] else 'FAIL ' + str(failed)}")

    sweep = report.get("confidence_floor_sensitivity")
    if sweep:
        print("\nCalibrated-confidence floor sensitivity (gate on, floor varied):\n")
        sweep_header = (
            f"{'Split':<12} {'Floor':>6} {'ExitRate':>9} {'R@1':>7} {'R@5':>7} "
            f"{'MRR':>7} {'Support@5':>10} {'p50 (ms)':>9}"
        )
        print(sweep_header)
        print("-" * len(sweep_header))
        for split_name, rows in sweep.items():
            for row in rows:
                print(
                    f"{split_name:<12} {row['confidence_floor']:>6.2f} "
                    f"{row['exit_rate_pct']:>8.2f}% {row['recall_at_1']:>7.4f} "
                    f"{row['recall_at_5']:>7.4f} {row['mrr']:>7.4f} "
                    f"{row['full_support_at_5']:>10.4f} {row['latency_p50_ms']:>9.3f}"
                )
            print("-" * len(sweep_header))

    print(
        "\nOK: adaptive early exit stays within its retrieval-quality tolerances."
        if report["gates_passed"]
        else "\nFAIL: adaptive early exit regressed retrieval quality."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT, help="Output JSON report path"
    )
    parser.add_argument(
        "--verify", action="store_true", help="Exit non-zero if any regression gate fails"
    )
    parser.add_argument(
        "--compare-early-exit",
        action="store_true",
        help="Run the adaptive early-exit ablation (gate off vs on) instead of the ladder",
    )
    parser.add_argument(
        "--output-early-exit",
        type=Path,
        default=DEFAULT_EARLY_EXIT_OUTPUT,
        help="Output JSON path for the adaptive early-exit comparison",
    )
    args = parser.parse_args()

    if args.compare_early_exit:
        comparison = compare_adaptive_early_exit()
        args.output_early_exit.parent.mkdir(parents=True, exist_ok=True)
        args.output_early_exit.write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
        print_early_exit_comparison(comparison)
        print(f"Wrote {_display_path(args.output_early_exit)}")
        if not comparison["gates_passed"]:
            return 1
        # `--verify` alongside this flag still runs the full ladder gates below.
        if not args.verify:
            return 0

    report = run_memory_benchmark()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    for split_name, split in report["splits"].items():
        print(f"[{split_name}] {split['dataset_file']} ({split['question_count']} questions)")
        for method, mrep in split["methods"].items():
            ov = mrep["overall"]
            print(
                f"  {method:32s} R@1={ov['recall_at_1']:.4f} R@5={ov['recall_at_5']:.4f} "
                f"MRR={ov['mrr']:.4f} Support@5={ov['full_support_at_5']:.4f} "
                f"Temp={ov['temporal_accuracy']:.4f} Supersede={ov['correction_supersession_rate']:.4f} "
                f"AbstainP={ov['abstention_precision']:.4f} AbstainR={ov['abstention_recall']:.4f}"
            )

    probe = report["abstention_probe"]
    print(
        f"Abstention probe (not gated), floor {probe['floor']} chosen on {probe['floor_chosen_on']}:"
    )
    for split_name, row in probe["splits"].items():
        print(
            f"  [{split_name}] P={row['precision']:.4f} R={row['recall']:.4f} "
            f"F1={row['f1']:.4f} false-abstain rate={row['false_abstain_rate']:.4f}"
        )

    if args.verify:
        failures = verify_report(report)
        if failures:
            for f in failures:
                print(f"FAIL: {f}", file=sys.stderr)
            return 1
        print("OK: All memory evaluation laboratory gates passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
