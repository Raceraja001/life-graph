#!/usr/bin/env python3
"""CLI runner for the contradiction and false-merge evaluation (M3).

Runs the labeled pairs in `evals/contradiction/pairs.json` through the
production ContradictionDetector and the ingest near-duplicate merge rule,
writes `evals/contradiction/report.json`, and prints the numbers.

`--verify` exits non-zero when any metric is worse than the recorded baseline
(`evals/contradiction/baseline.json`). Better numbers pass; record them on
purpose with `--write-baseline`, in the same change that improved them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from life_graph.evals.contradiction_benchmark import (  # noqa: E402
    BASELINE_PATH,
    PAIRS_PATH,
    baseline_of,
    regressions,
    run_contradiction_benchmark,
)

DEFAULT_OUTPUT = ROOT / "evals" / "contradiction" / "report.json"


def _print(report: dict) -> None:
    ov = report["overall"]
    print(
        f"Contradiction/false-merge eval: {ov['pairs']} pairs at assumed cosine "
        f"{report['assumed_cosine']} (dedup_threshold {report['thresholds']['dedup_threshold']})"
    )
    print(
        f"  contradiction P={ov['contradiction_precision']:.4f} "
        f"R={ov['contradiction_recall']:.4f} F1={ov['contradiction_f1']:.4f}"
    )
    print(
        f"  false-merge rate={ov['false_merge_rate']:.4f}  "
        f"paraphrase merge rate={ov['paraphrase_merge_rate']:.4f}"
    )
    for cat, entry in report["by_category"].items():
        parts = [f"{k}={v}" for k, v in entry.items() if k != "pairs"]
        print(f"  {cat:<20} n={entry['pairs']:<3} " + " ".join(parts))
    print(f"  missed contradictions: {', '.join(report['missed_contradictions']) or '-'}")
    print(f"  false contradictions:  {', '.join(report['false_contradictions']) or '-'}")
    print(f"  false merges:          {', '.join(report['false_merges']) or '-'}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", type=Path, default=PAIRS_PATH, help="Labeled pairs JSON")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Report JSON path")
    parser.add_argument("--baseline", type=Path, default=BASELINE_PATH, help="Baseline JSON")
    parser.add_argument(
        "--verify", action="store_true", help="Exit non-zero if any metric regressed"
    )
    parser.add_argument(
        "--write-baseline", action="store_true", help="Record this run as the new baseline"
    )
    args = parser.parse_args()

    report = run_contradiction_benchmark(args.pairs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    _print(report)

    if args.write_baseline:
        args.baseline.write_text(json.dumps(baseline_of(report), indent=2) + "\n", encoding="utf-8")
        print(f"Wrote baseline {args.baseline.name}")

    if args.verify:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        failures = regressions(report, baseline)
        if failures:
            for f in failures:
                print(f"FAIL: {f}", file=sys.stderr)
            return 1
        print("OK: no contradiction or false-merge metric regressed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
