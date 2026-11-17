#!/usr/bin/env python3
"""CLI runner for the Life Graph Memory Evaluation Laboratory (P1).

Runs the 6-stage single-variable retrieval & lifecycle ablation benchmark across
separate tuning (`test_life.json`) and held-out (`test_life_2.json`) datasets,
writes `evals/memory_benchmark_report.json`, and enforces regression thresholds
when `--verify` is passed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from life_graph.services.memory_benchmark import run_memory_benchmark  # noqa: E402

DEFAULT_OUTPUT = ROOT / "evals" / "memory_benchmark_report.json"


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
        s6 = split["6_multistep_adaptive_abstain"]["overall"]

        if s3["recall_at_5"] < s1["recall_at_5"]:
            failures.append(
                f"{split_name}: 3_hybrid_rrf R@5 ({s3['recall_at_5']}) < 1_lexical_bm25 ({s1['recall_at_5']})"
            )
        if s4["recall_at_5"] < s3["recall_at_5"] + 0.05:
            failures.append(
                f"{split_name}: 4_graph_entity_expansion R@5 ({s4['recall_at_5']}) did not improve over 3_hybrid_rrf ({s3['recall_at_5']})"
            )
        if s5["temporal_accuracy"] < s4["temporal_accuracy"] + 0.08:
            failures.append(
                f"{split_name}: 5_rerank_temporal_provenance temporal_accuracy ({s5['temporal_accuracy']}) did not improve over 4_graph_entity_expansion ({s4['temporal_accuracy']})"
            )
        if s6["full_support_at_5"] < s5["full_support_at_5"] + 0.05:
            failures.append(
                f"{split_name}: 6_multistep_adaptive_abstain full_support_at_5 ({s6['full_support_at_5']}) did not improve over 5_rerank_temporal_provenance ({s5['full_support_at_5']})"
            )
        if s6["abstention_precision"] < 0.90 or s6["abstention_recall"] < 0.90:
            failures.append(
                f"{split_name}: 6_multistep_adaptive_abstain abstention P/R ({s6['abstention_precision']}/{s6['abstention_recall']}) < 0.90"
            )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT, help="Output JSON report path"
    )
    parser.add_argument(
        "--verify", action="store_true", help="Exit non-zero if any regression gate fails"
    )
    args = parser.parse_args()

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
