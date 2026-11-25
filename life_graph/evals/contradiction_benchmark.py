"""Contradiction and false-merge evaluation (M3, 2026-11-25).

Two questions about what happens when a new fact arrives next to a stored one
that embeds almost the same:

* **Contradiction.** Does `ContradictionDetector.check_candidates` (the
  production detector, called as MemoryManager calls it) suggest a supersede
  when the new fact replaces the old one, and only then? Reported as
  precision/recall, overall and per category.
* **False merge.** Would the ingest near-duplicate merge fold two different
  facts into one memory? MemoryManager._process_fact merges a candidate when
  its cosine is at least `settings.dedup_threshold` and neither
  `differs_by_negation` nor `differs_in_detail` says the texts differ.
  `would_merge()` asks the same three questions with the same production
  helpers. The false-merge rate is the share of distinct-fact pairs it would
  merge; the paraphrase merge rate is the share of true duplicates it still
  merges (the price of erring towards "differs").

The pairs (evals/contradiction/pairs.json) are synthetic and labeled by hand.
There is no embedder here: every pair is scored at the dataset's
`assumed_cosine` (0.95, above both thresholds), which is the hard case the
rules exist for. So the numbers measure the text rules, not the embedder.

Nothing here changes production behaviour; it only measures it. The CI gate
(`scripts/eval_contradiction.py --verify`) fails only when a metric is worse
than the recorded baseline (evals/contradiction/baseline.json), so a fix that
improves a number passes and the baseline is then re-recorded on purpose.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from life_graph.config import settings
from life_graph.services.contradiction import (
    ContradictionDetector,
    differs_by_negation,
    differs_in_detail,
)

ROOT = Path(__file__).resolve().parents[2]
PAIRS_PATH = ROOT / "evals" / "contradiction" / "pairs.json"
BASELINE_PATH = ROOT / "evals" / "contradiction" / "baseline.json"

#: Categories whose pairs are contradictions (the new fact replaces the old).
POSITIVE_CATEGORIES = ("negation", "preference_swap", "value_change")
#: Categories whose pairs are both true at once, or the same fact twice.
NEGATIVE_CATEGORIES = ("compatible_addition", "scoped", "paraphrase")

#: Metrics where a higher value is better, and where a lower one is.
HIGHER_IS_BETTER = (
    "contradiction_precision",
    "contradiction_recall",
    "paraphrase_merge_rate",
)
LOWER_IS_BETTER = ("false_merge_rate",)


def _unit_pair(cosine: float) -> tuple[list[float], list[float]]:
    """Two unit vectors whose cosine is exactly *cosine*."""
    return [1.0, 0.0], [cosine, math.sqrt(max(0.0, 1.0 - cosine * cosine))]


def would_merge(new_text: str, existing_text: str, cosine: float) -> bool:
    """Whether MemoryManager._process_fact would merge these two as one memory.

    The same three conditions, with the same production helpers and threshold
    (core/memory_manager.py, the near-match dedup step).
    """
    return (
        cosine >= settings.dedup_threshold
        and not differs_by_negation(new_text, existing_text)
        and not differs_in_detail(new_text, existing_text)
    )


async def _detect(pair: dict[str, Any], cosine: float) -> list[Any]:
    new_vec, old_vec = _unit_pair(cosine)
    existing = SimpleNamespace(
        id=f"{pair['id']}-existing",
        content=pair["existing"],
        embedding=old_vec,
        properties=pair.get("existing_properties") or {},
        status="active",
    )
    detector = ContradictionDetector(store=None)  # type: ignore[arg-type]
    return await detector.check_candidates(
        pair["new"], [existing], new_vec, pair.get("new_properties") or {}
    )


def evaluate_pair(pair: dict[str, Any], assumed_cosine: float) -> dict[str, Any]:
    """One pair through the detector and the merge rule."""
    cosine = float(pair.get("cosine", assumed_cosine))
    found = asyncio.run(_detect(pair, cosine))
    supersede = [c for c in found if c.resolution == "supersede"]
    return {
        "id": pair["id"],
        "category": pair["category"],
        "gold_contradiction": bool(pair["contradiction"]),
        "gold_distinct": bool(pair["distinct"]),
        "cosine": cosine,
        "predicted_contradiction": bool(supersede),
        "conflict_types": sorted({c.conflict_type for c in found}),
        "would_merge": would_merge(pair["new"], pair["existing"], cosine),
    }


def _ratio(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Overall and per-category contradiction and merge metrics."""
    tp = sum(1 for r in rows if r["gold_contradiction"] and r["predicted_contradiction"])
    fp = sum(1 for r in rows if not r["gold_contradiction"] and r["predicted_contradiction"])
    fn = sum(1 for r in rows if r["gold_contradiction"] and not r["predicted_contradiction"])
    distinct = [r for r in rows if r["gold_distinct"]]
    duplicates = [r for r in rows if not r["gold_distinct"]]
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    overall = {
        "pairs": len(rows),
        "contradiction_pairs": tp + fn,
        "contradiction_precision": round(precision, 4),
        "contradiction_recall": round(recall, 4),
        "contradiction_f1": round(
            2 * precision * recall / (precision + recall) if (precision + recall) else 0.0, 4
        ),
        "false_merge_rate": _ratio(sum(1 for r in distinct if r["would_merge"]), len(distinct))
        or 0.0,
        "paraphrase_merge_rate": _ratio(
            sum(1 for r in duplicates if r["would_merge"]), len(duplicates)
        )
        or 0.0,
    }
    by_category: dict[str, dict[str, Any]] = {}
    for cat in POSITIVE_CATEGORIES + NEGATIVE_CATEGORIES:
        sub = [r for r in rows if r["category"] == cat]
        if not sub:
            continue
        flagged = sum(1 for r in sub if r["predicted_contradiction"])
        merged = sum(1 for r in sub if r["would_merge"])
        entry: dict[str, Any] = {"pairs": len(sub), "flagged": flagged, "merged": merged}
        if cat in POSITIVE_CATEGORIES:
            entry["contradiction_recall"] = _ratio(flagged, len(sub))
        else:
            entry["false_contradiction_rate"] = _ratio(flagged, len(sub))
        if cat == "paraphrase":
            entry["merge_rate"] = _ratio(merged, len(sub))
        else:
            entry["false_merge_rate"] = _ratio(merged, len(sub))
        by_category[cat] = entry
    return {"overall": overall, "by_category": by_category}


def run_contradiction_benchmark(pairs_path: Path = PAIRS_PATH) -> dict[str, Any]:
    raw = pairs_path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    assumed = float(data["assumed_cosine"])
    rows = [evaluate_pair(p, assumed) for p in data["pairs"]]
    summary = summarize(rows)
    try:
        dataset_file = str(pairs_path.relative_to(ROOT))
    except ValueError:
        dataset_file = str(pairs_path)
    return {
        "benchmark": "life_graph_contradiction_false_merge_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset_file": dataset_file,
        "dataset_sha256": hashlib.sha256(raw).hexdigest(),
        "assumed_cosine": assumed,
        "thresholds": {
            "dedup_threshold": settings.dedup_threshold,
            "contradiction_similarity_threshold": settings.contradiction_similarity_threshold,
        },
        **summary,
        "missed_contradictions": [
            r["id"] for r in rows if r["gold_contradiction"] and not r["predicted_contradiction"]
        ],
        "false_contradictions": [
            r["id"] for r in rows if not r["gold_contradiction"] and r["predicted_contradiction"]
        ],
        "false_merges": [r["id"] for r in rows if r["gold_distinct"] and r["would_merge"]],
        "pairs": rows,
    }


def baseline_of(report: dict[str, Any]) -> dict[str, Any]:
    """The numbers a later run is compared against."""
    by_cat = {}
    for cat, entry in report["by_category"].items():
        by_cat[cat] = {
            k: entry[k]
            for k in (
                "contradiction_recall",
                "false_contradiction_rate",
                "false_merge_rate",
                "merge_rate",
            )
            if k in entry
        }
    return {
        "dataset_sha256": report["dataset_sha256"],
        "overall": {k: report["overall"][k] for k in HIGHER_IS_BETTER + LOWER_IS_BETTER},
        "by_category": by_cat,
    }


#: Per-category metrics where a higher value is better; the rest are lower-is-better.
_CATEGORY_HIGHER = ("contradiction_recall", "merge_rate")


def regressions(report: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    """Every metric that is worse than the recorded baseline. Better is fine."""
    out: list[str] = []
    if report["dataset_sha256"] != baseline.get("dataset_sha256"):
        out.append(
            "pairs.json changed since the baseline was recorded; re-record it with "
            "--write-baseline in the same change"
        )
    cur = report["overall"]
    for key, was in baseline.get("overall", {}).items():
        now = cur[key]
        worse = now < was if key in HIGHER_IS_BETTER else now > was
        if worse:
            out.append(f"{key}: {now} (baseline {was})")
    for cat, metrics in baseline.get("by_category", {}).items():
        entry = report["by_category"].get(cat, {})
        for key, was in metrics.items():
            now = entry.get(key)
            if now is None or was is None:
                continue
            worse = now < was if key in _CATEGORY_HIGHER else now > was
            if worse:
                out.append(f"{cat}.{key}: {now} (baseline {was})")
    return out
