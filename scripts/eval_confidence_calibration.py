#!/usr/bin/env python3
"""Evaluate evidence confidence calibration, ECE, Brier score, and abstention quality.

Usage:
    python scripts/eval_confidence_calibration.py [--dataset PATH] [--output PATH] [--verify]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from life_graph.core.evidence import (
    CONTRADICTED,
    SUPPORTED,
    decompose_memory_confidence,
    evaluate_confidence_calibration,
    extract_claim_evidence,
)

REF_NOW = datetime(2026, 11, 14, 12, 0, 0, tzinfo=timezone.utc)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate evidence confidence calibration.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("evals/confidence_calibration_dataset.json"),
        help="Path to evaluation dataset JSON.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evals/calibration_report.json"),
        help="Path to save evaluation report JSON.",
    )
    parser.add_argument(
        "--splits",
        type=str,
        default="calibration_set,held_out_set",
        help="Comma-separated splits to evaluate.",
    )
    parser.add_argument(
        "--bins",
        type=int,
        default=10,
        help="Number of equal-width bins for ECE calculation (default: 10).",
    )
    parser.add_argument(
        "--decision-threshold",
        type=float,
        default=0.50,
        help="Decision threshold for classification metrics (default: 0.50).",
    )
    parser.add_argument(
        "--abstain-threshold",
        type=float,
        default=0.40,
        help="Threshold below which system abstains (default: 0.40).",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Enforce acceptance criteria and exit non-zero on failure.",
    )
    return parser.parse_args()


def evaluate_split(
    samples: list[dict[str, Any]],
    *,
    num_bins: int = 10,
    decision_threshold: float = 0.5,
    abstain_threshold: float = 0.4,
    now: datetime = REF_NOW,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Run full extraction, verification, decomposition, and calibration on samples."""
    eval_inputs: list[dict[str, Any]] = []
    processed_details: list[dict[str, Any]] = []

    for s in samples:
        ans = s.get("answer") or s["claim"]
        mem = s["memory"]
        claims = extract_claim_evidence(ans, [mem], now=now)
        support_status = claims[0]["support_status"] if claims else "unsupported"
        pred_contradiction = (support_status == CONTRADICTED)

        decomp = decompose_memory_confidence(mem, now=now, support_status=support_status)
        conf = decomp["calibrated_confidence"]

        item_input: dict[str, Any] = {
            "confidence": conf,
            "correct": float(s["correct"]),
            "evidence_kind": s.get("evidence_kind") or decomp["evidence_kind"],
            "contradiction_predicted": pred_contradiction,
            "contradiction_ground_truth": bool(s.get("contradiction_ground_truth", False)),
        }
        eval_inputs.append(item_input)
        processed_details.append(
            {
                "id": s["id"],
                "scenario": s.get("scenario"),
                "claim": s["claim"],
                "support_status": support_status,
                "confidence": conf,
                "recommended_action": decomp["recommended_action"],
                "correct": s["correct"],
                "contradiction_predicted": pred_contradiction,
                "contradiction_ground_truth": s.get("contradiction_ground_truth", False),
            }
        )

    summary = evaluate_confidence_calibration(
        eval_inputs,
        num_bins=num_bins,
        decision_threshold=decision_threshold,
        abstain_threshold=abstain_threshold,
    )
    return summary, processed_details


def print_summary(split_name: str, summary: dict[str, Any]) -> None:
    print(f"\n{'='*25} Split: {split_name} {'='*25}")
    print(f"Sample Count:         {summary['count']}")
    print(f"Brier Score:          {summary['brier_score']:.4f}  (lower is better, <0.20 desired)")
    print(f"Expected Calib Error: {summary['ece']:.4f}  (ECE, lower is better, <0.20 desired)")
    print(f"Max Calib Error:      {summary['mce']:.4f}  (MCE)")
    print(f"Mean Confidence:      {summary['mean_confidence']:.4f}")
    print(f"Empirical Accuracy:   {summary['accuracy']:.4f}")
    print(f"Calibration Gap:      {summary['calibration_gap']:+.4f} (Mean Conf - Acc)")
    print(f"Precision:            {summary['precision']:.4f}")
    print(f"Recall:               {summary['recall']:.4f}")
    print(f"F1 Score:             {summary['f1']:.4f}")
    print(f"Abstention Rate:      {summary['abstention_rate']:.4f}")
    print(f"Abstention Precision: {summary['abstention_precision']:.4f} (abstained cases that were false)")
    print(f"Answering Accuracy:   {summary['answering_accuracy']:.4f} (accuracy when not abstaining)")

    if "contradiction_detection" in summary:
        cd = summary["contradiction_detection"]
        print(f"Contradiction Detection: P={cd['precision']:.4f}, R={cd['recall']:.4f}, F1={cd['f1']:.4f} (N={cd['count']})")

    print("\nReliability Bins:")
    print(f"  {'Bin':<4} {'Range':<14} {'Count':<6} {'Mean Conf':<10} {'Accuracy':<10} {'Gap':<8}")
    print(f"  {'-'*4} {'-'*14} {'-'*6} {'-'*10} {'-'*10} {'-'*8}")
    for b in summary.get("bins", []):
        if b["count"] > 0:
            rng_str = f"[{b['range'][0]:.2f}, {b['range'][1]:.2f}]"
            print(f"  {b['bin']:<4} {rng_str:<14} {b['count']:<6} {b['mean_confidence']:<10.4f} {b['accuracy']:<10.4f} {b['gap']:<8.4f}")

    print("\nBy Evidence Kind:")
    print(f"  {'Kind':<12} {'Count':<6} {'Brier':<8} {'ECE':<8} {'Mean Conf':<10} {'Accuracy':<10} {'F1':<6}")
    print(f"  {'-'*12} {'-'*6} {'-'*8} {'-'*8} {'-'*10} {'-'*10} {'-'*6}")
    for kind, stats in summary.get("by_evidence_kind", {}).items():
        print(f"  {kind:<12} {stats['count']:<6} {stats['brier_score']:<8.4f} {stats['ece']:<8.4f} {stats['mean_confidence']:<10.4f} {stats['accuracy']:<10.4f} {stats['f1']:<6.4f}")


def main() -> int:
    args = parse_args()
    if not args.dataset.exists():
        print(f"Error: Dataset file '{args.dataset}' does not exist.", file=sys.stderr)
        return 1

    with open(args.dataset, "r", encoding="utf-8") as f:
        data = json.load(f)

    splits = [s.strip() for s in args.splits.split(",") if s.strip()]
    report: dict[str, Any] = {
        "metadata": {
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "dataset_path": str(args.dataset),
            "bins": args.bins,
            "decision_threshold": args.decision_threshold,
            "abstain_threshold": args.abstain_threshold,
        },
        "splits": {},
    }

    all_passed = True
    for split_name in splits:
        if split_name not in data:
            print(f"Warning: Split '{split_name}' not found in dataset.", file=sys.stderr)
            continue
        summary, details = evaluate_split(
            data[split_name],
            num_bins=args.bins,
            decision_threshold=args.decision_threshold,
            abstain_threshold=args.abstain_threshold,
        )
        report["splits"][split_name] = {
            "summary": summary,
            "samples": details,
        }
        print_summary(split_name, summary)

        if args.verify:
            if summary["brier_score"] > 0.20:
                print(f"VERIFY FAILED: {split_name} Brier score {summary['brier_score']} > 0.20", file=sys.stderr)
                all_passed = False
            if summary["ece"] > 0.20:
                print(f"VERIFY FAILED: {split_name} ECE {summary['ece']} > 0.20", file=sys.stderr)
                all_passed = False
            if summary["abstention_precision"] < 0.85:
                print(f"VERIFY FAILED: {split_name} Abstention precision {summary['abstention_precision']} < 0.85", file=sys.stderr)
                all_passed = False

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\nSaved evaluation report to {args.output}")

    if args.verify and not all_passed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
