"""Calibration scoring — pure functions, no DB or LLM.

All functions operate on plain data (lists/dicts) and return results.
Designed to be fully unit-testable without any infrastructure.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class BucketResult:
    """Calibration data for one confidence bucket."""

    range_label: str  # e.g. "0.50-0.60"
    range_low: float
    range_high: float
    count: int
    avg_confidence: float
    hit_rate: float  # fraction that were correct
    gap: float  # hit_rate - avg_confidence (positive = underconfident)


@dataclass
class CalibrationResult:
    """Full calibration analysis."""

    resolved_count: int
    ambiguous_count: int
    brier_score: float | None  # None if insufficient data
    buckets: list[BucketResult]
    estimate_multiplier: float | None  # None if < 5 samples
    bias_findings: list[dict]  # [{direction, domain, gap, count}]
    sufficient_data: bool  # True if >= 20 resolved


# ── Bucket boundaries ──────────────────────────────────────────────────
BUCKET_RANGES = [
    (0.50, 0.60, "0.50-0.60"),
    (0.60, 0.70, "0.60-0.70"),
    (0.70, 0.80, "0.70-0.80"),
    (0.80, 0.90, "0.80-0.90"),
    (0.90, 0.99, "0.90-0.99"),
]

MIN_RESOLVED_FOR_CALIBRATION = 20
MIN_SAMPLES_FOR_MULTIPLIER = 5
BIAS_GAP_THRESHOLD = 0.15
MIN_SAMPLES_FOR_BIAS = 5


def brier_score(predictions: list[dict]) -> float | None:
    """Calculate Brier score from resolved predictions.

    Each prediction dict must have:
      - confidence: float [0.5, 0.99]
      - outcome: 'correct' | 'incorrect'

    Returns Brier score (lower is better, 0 = perfect, 0.25 = random at 50%).
    Returns None if no valid predictions.
    """
    valid = [p for p in predictions if p.get("outcome") in ("correct", "incorrect")]
    if not valid:
        return None

    total = 0.0
    for p in valid:
        conf = p["confidence"]
        actual = 1.0 if p["outcome"] == "correct" else 0.0
        total += (conf - actual) ** 2

    return total / len(valid)


def bucket_analysis(predictions: list[dict]) -> list[BucketResult]:
    """Group predictions into confidence buckets and compute hit rates.

    Each prediction dict must have:
      - confidence: float [0.5, 0.99]
      - outcome: 'correct' | 'incorrect'
    """
    valid = [p for p in predictions if p.get("outcome") in ("correct", "incorrect")]
    results = []

    for low, high, label in BUCKET_RANGES:
        bucket_preds = [
            p
            for p in valid
            if low <= p["confidence"] < high
            or (high == 0.99 and p["confidence"] >= 0.90)
        ]
        if not bucket_preds:
            results.append(
                BucketResult(
                    range_label=label,
                    range_low=low,
                    range_high=high,
                    count=0,
                    avg_confidence=0.0,
                    hit_rate=0.0,
                    gap=0.0,
                )
            )
            continue

        avg_conf = sum(p["confidence"] for p in bucket_preds) / len(bucket_preds)
        hits = sum(1 for p in bucket_preds if p["outcome"] == "correct")
        hit_rate = hits / len(bucket_preds)

        results.append(
            BucketResult(
                range_label=label,
                range_low=low,
                range_high=high,
                count=len(bucket_preds),
                avg_confidence=avg_conf,
                hit_rate=hit_rate,
                gap=hit_rate - avg_conf,
            )
        )

    return results


def estimate_multiplier(predictions: list[dict]) -> float | None:
    """Geometric mean of actual/predicted outcomes.

    Winsorized at p90 to reduce outlier impact.
    Returns None if fewer than MIN_SAMPLES_FOR_MULTIPLIER valid samples.

    A multiplier > 1 means you're systematically underconfident.
    A multiplier < 1 means you're systematically overconfident.
    """
    valid = [p for p in predictions if p.get("outcome") in ("correct", "incorrect")]
    if len(valid) < MIN_SAMPLES_FOR_MULTIPLIER:
        return None

    ratios = []
    for p in valid:
        conf = max(p["confidence"], 0.01)  # Avoid division by zero
        actual = 1.0 if p["outcome"] == "correct" else 0.0
        # Ratio of actual outcome to predicted confidence, smoothed to avoid 0/x
        ratio = (actual + 0.01) / (conf + 0.01)
        ratios.append(ratio)

    # Winsorize at p10/p90
    ratios.sort()
    p10_idx = max(0, int(len(ratios) * 0.10))
    p90_idx = min(len(ratios) - 1, int(len(ratios) * 0.90))
    winsorized = ratios[p10_idx : p90_idx + 1]

    if not winsorized:
        return None

    # Geometric mean
    log_sum = sum(math.log(max(r, 0.001)) for r in winsorized)
    return math.exp(log_sum / len(winsorized))


def detect_bias(predictions: list[dict], domain: str | None = None) -> list[dict]:
    """Detect systematic over/underconfidence patterns.

    A bias is detected when:
      - |avg_confidence - hit_rate| >= BIAS_GAP_THRESHOLD (0.15)
      - Sample count >= MIN_SAMPLES_FOR_BIAS (5)

    Returns list of {direction, domain, gap, count, avg_confidence, hit_rate}
    """
    valid = [p for p in predictions if p.get("outcome") in ("correct", "incorrect")]
    if len(valid) < MIN_SAMPLES_FOR_BIAS:
        return []

    avg_conf = sum(p["confidence"] for p in valid) / len(valid)
    hits = sum(1 for p in valid if p["outcome"] == "correct")
    hit_rate = hits / len(valid)
    gap = hit_rate - avg_conf

    findings: list[dict] = []
    if abs(gap) >= BIAS_GAP_THRESHOLD:
        direction = "underconfident" if gap > 0 else "overconfident"
        findings.append(
            {
                "direction": direction,
                "domain": domain or "all",
                "gap": round(gap, 3),
                "count": len(valid),
                "avg_confidence": round(avg_conf, 3),
                "hit_rate": round(hit_rate, 3),
            }
        )

    return findings


def full_calibration(
    predictions: list[dict],
    domain: str | None = None,
) -> CalibrationResult:
    """Run complete calibration analysis.

    Each prediction dict must have:
      - confidence: float [0.5, 0.99]
      - outcome: 'correct' | 'incorrect' | 'ambiguous' | 'pending'
    """
    resolved = [p for p in predictions if p.get("outcome") in ("correct", "incorrect")]
    ambiguous = [p for p in predictions if p.get("outcome") == "ambiguous"]
    sufficient = len(resolved) >= MIN_RESOLVED_FOR_CALIBRATION

    return CalibrationResult(
        resolved_count=len(resolved),
        ambiguous_count=len(ambiguous),
        brier_score=brier_score(resolved) if sufficient else None,
        buckets=bucket_analysis(resolved) if sufficient else [],
        estimate_multiplier=estimate_multiplier(resolved),
        bias_findings=detect_bias(resolved, domain),
        sufficient_data=sufficient,
    )


def normalize_confidence(confidence: float) -> tuple[float, bool]:
    """Normalize confidence to [0.5, 0.99] range.

    If confidence < 0.5, the prediction should be negated and confidence
    flipped: e.g., 30% confident X will happen → 70% confident X won't happen.

    Returns (normalized_confidence, was_negated).
    """
    if confidence < 0.5:
        return (1.0 - confidence, True)
    return (min(confidence, 0.99), False)
