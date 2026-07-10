"""Unit tests for calibration scoring (Judgment Engine — Phase 4).

Tests all pure-math calibration functions with deterministic fixed data.
No DB, no mocks, just function calls and assertions.
"""

from __future__ import annotations

import pytest

from life_graph.scoring.calibration import (
    BIAS_GAP_THRESHOLD,
    MIN_RESOLVED_FOR_CALIBRATION,
    MIN_SAMPLES_FOR_BIAS,
    MIN_SAMPLES_FOR_MULTIPLIER,
    BucketResult,
    CalibrationResult,
    brier_score,
    bucket_analysis,
    detect_bias,
    estimate_multiplier,
    full_calibration,
    normalize_confidence,
)


# ---------------------------------------------------------------------------
# Helpers — deterministic prediction factories
# ---------------------------------------------------------------------------

def _pred(confidence: float, outcome: str) -> dict:
    """Create a single prediction dict."""
    return {"confidence": confidence, "outcome": outcome}


def _correct(confidence: float) -> dict:
    return _pred(confidence, "correct")


def _incorrect(confidence: float) -> dict:
    return _pred(confidence, "incorrect")


def _ambiguous(confidence: float) -> dict:
    return _pred(confidence, "ambiguous")


def _pending(confidence: float) -> dict:
    return _pred(confidence, "pending")


# ---------------------------------------------------------------------------
# Brier Score
# ---------------------------------------------------------------------------


class TestBrierScore:
    """Test Brier score calculation."""

    def test_perfect_predictions_near_zero(self) -> None:
        """All correct at high confidence → score near 0."""
        preds = [_correct(0.99) for _ in range(10)]
        score = brier_score(preds)
        assert score is not None
        assert score < 0.01  # Very close to 0

    def test_random_predictions_near_quarter(self) -> None:
        """50% confidence with 50/50 outcomes → score near 0.25."""
        preds = [_correct(0.50) for _ in range(50)] + [
            _incorrect(0.50) for _ in range(50)
        ]
        score = brier_score(preds)
        assert score is not None
        assert 0.20 <= score <= 0.30

    def test_all_wrong_high_confidence_near_one(self) -> None:
        """All wrong at high confidence → score near 1.0."""
        preds = [_incorrect(0.99) for _ in range(10)]
        score = brier_score(preds)
        assert score is not None
        assert score > 0.90

    def test_empty_list_returns_none(self) -> None:
        assert brier_score([]) is None

    def test_only_ambiguous_returns_none(self) -> None:
        preds = [_ambiguous(0.8) for _ in range(10)]
        assert brier_score(preds) is None

    def test_only_pending_returns_none(self) -> None:
        preds = [_pending(0.7) for _ in range(5)]
        assert brier_score(preds) is None

    def test_mixed_valid_and_invalid_ignores_invalid(self) -> None:
        """Only 'correct'/'incorrect' outcomes count."""
        preds = [
            _correct(0.99),
            _ambiguous(0.80),
            _pending(0.70),
            _correct(0.99),
        ]
        score = brier_score(preds)
        assert score is not None
        # Only the two correct@0.99 count → (0.99-1.0)^2 = 0.0001 each
        assert score == pytest.approx(0.0001, abs=0.001)

    def test_exact_brier_calculation(self) -> None:
        """Verify exact Brier score for a known case."""
        preds = [
            _correct(0.90),   # (0.9 - 1.0)^2 = 0.01
            _incorrect(0.60), # (0.6 - 0.0)^2 = 0.36
        ]
        score = brier_score(preds)
        assert score == pytest.approx((0.01 + 0.36) / 2, abs=1e-9)


# ---------------------------------------------------------------------------
# Bucket Analysis
# ---------------------------------------------------------------------------


class TestBucketAnalysis:
    """Test confidence bucket grouping and metrics."""

    def test_all_five_buckets_returned(self) -> None:
        """Even with no data, all 5 buckets should be present."""
        result = bucket_analysis([])
        assert len(result) == 5
        for b in result:
            assert isinstance(b, BucketResult)

    def test_empty_buckets_have_zero_count(self) -> None:
        result = bucket_analysis([])
        for b in result:
            assert b.count == 0
            assert b.avg_confidence == 0.0
            assert b.hit_rate == 0.0
            assert b.gap == 0.0

    def test_predictions_land_in_correct_buckets(self) -> None:
        """Predictions are grouped by their confidence value."""
        preds = [
            _correct(0.55),  # bucket 0.50-0.60
            _correct(0.65),  # bucket 0.60-0.70
            _correct(0.75),  # bucket 0.70-0.80
            _correct(0.85),  # bucket 0.80-0.90
            _correct(0.95),  # bucket 0.90-0.99
        ]
        result = bucket_analysis(preds)
        labels = [b.range_label for b in result if b.count > 0]
        assert len(labels) == 5
        for b in result:
            assert b.count == 1

    def test_hit_rate_calculation(self) -> None:
        """Hit rate is fraction of correct outcomes in bucket."""
        preds = [
            _correct(0.55),
            _correct(0.56),
            _incorrect(0.57),
            _incorrect(0.58),
        ]
        result = bucket_analysis(preds)
        bucket_050 = next(b for b in result if b.range_label == "0.50-0.60")
        assert bucket_050.count == 4
        assert bucket_050.hit_rate == pytest.approx(0.5)

    def test_gap_positive_means_underconfident(self) -> None:
        """Positive gap = hit_rate > avg_confidence → underconfident."""
        # All correct at low confidence (0.55) → hit_rate=1.0, avg_conf≈0.55
        preds = [_correct(0.55) for _ in range(5)]
        result = bucket_analysis(preds)
        bucket_050 = next(b for b in result if b.range_label == "0.50-0.60")
        assert bucket_050.gap > 0  # underconfident

    def test_gap_negative_means_overconfident(self) -> None:
        """Negative gap = hit_rate < avg_confidence → overconfident."""
        # All incorrect at high confidence (0.85) → hit_rate=0.0, avg_conf≈0.85
        preds = [_incorrect(0.85) for _ in range(5)]
        result = bucket_analysis(preds)
        bucket_080 = next(b for b in result if b.range_label == "0.80-0.90")
        assert bucket_080.gap < 0  # overconfident

    def test_avg_confidence_is_mean_of_bucket(self) -> None:
        preds = [_correct(0.62), _correct(0.68)]
        result = bucket_analysis(preds)
        bucket_060 = next(b for b in result if b.range_label == "0.60-0.70")
        assert bucket_060.avg_confidence == pytest.approx(0.65)


# ---------------------------------------------------------------------------
# Estimate Multiplier
# ---------------------------------------------------------------------------


class TestEstimateMultiplier:
    """Test the geometric-mean estimate multiplier."""

    def test_fewer_than_min_samples_returns_none(self) -> None:
        preds = [_correct(0.8) for _ in range(MIN_SAMPLES_FOR_MULTIPLIER - 1)]
        assert estimate_multiplier(preds) is None

    def test_exactly_min_samples_returns_value(self) -> None:
        preds = [_correct(0.8) for _ in range(MIN_SAMPLES_FOR_MULTIPLIER)]
        result = estimate_multiplier(preds)
        assert result is not None
        assert isinstance(result, float)

    def test_perfect_calibration_near_one(self) -> None:
        """When predictions match outcomes well, multiplier should be near 1.0.

        We use a mix of correct high-confidence and incorrect low-confidence
        predictions to approximate perfect calibration.
        """
        preds = (
            [_correct(0.90) for _ in range(9)]
            + [_incorrect(0.90)]  # ~90% hit rate at 0.90 confidence
        )
        result = estimate_multiplier(preds)
        assert result is not None
        assert 0.5 < result < 2.0  # Reasonable range for well-calibrated

    def test_winsorization_reduces_outlier_impact(self) -> None:
        """Outliers should be clipped, not dominate the result."""
        # 18 reasonable predictions + 2 extreme outliers
        base_preds = [_correct(0.80) for _ in range(18)]
        outlier_preds = [_incorrect(0.99), _incorrect(0.99)]
        with_outliers = estimate_multiplier(base_preds + outlier_preds)
        without_outliers = estimate_multiplier(base_preds)

        assert with_outliers is not None
        assert without_outliers is not None
        # Winsorized result should not be drastically different
        ratio = with_outliers / without_outliers
        assert 0.5 < ratio < 2.0

    def test_empty_returns_none(self) -> None:
        assert estimate_multiplier([]) is None

    def test_only_ambiguous_returns_none(self) -> None:
        preds = [_ambiguous(0.8) for _ in range(10)]
        assert estimate_multiplier(preds) is None


# ---------------------------------------------------------------------------
# Bias Detection
# ---------------------------------------------------------------------------


class TestDetectBias:
    """Test systematic bias detection."""

    def test_overconfident_pattern_detected(self) -> None:
        """High confidence + low hit rate → 'overconfident'."""
        preds = [_incorrect(0.90) for _ in range(10)]
        findings = detect_bias(preds)
        assert len(findings) == 1
        assert findings[0]["direction"] == "overconfident"
        assert findings[0]["domain"] == "all"
        assert findings[0]["gap"] < 0

    def test_underconfident_pattern_detected(self) -> None:
        """Low confidence + high hit rate → 'underconfident'."""
        preds = [_correct(0.55) for _ in range(10)]
        findings = detect_bias(preds)
        assert len(findings) == 1
        assert findings[0]["direction"] == "underconfident"
        assert findings[0]["gap"] > 0

    def test_no_bias_when_gap_small(self) -> None:
        """No finding when |gap| < BIAS_GAP_THRESHOLD."""
        # hit_rate ≈ avg_confidence → gap ≈ 0
        preds = (
            [_correct(0.75) for _ in range(7)]
            + [_incorrect(0.75) for _ in range(3)]
        )
        # avg_conf = 0.75, hit_rate = 0.70, gap = -0.05 (below 0.15)
        findings = detect_bias(preds)
        assert findings == []

    def test_fewer_than_min_samples_returns_empty(self) -> None:
        preds = [_correct(0.55) for _ in range(MIN_SAMPLES_FOR_BIAS - 1)]
        assert detect_bias(preds) == []

    def test_domain_label_passed_through(self) -> None:
        """Custom domain label appears in findings."""
        preds = [_incorrect(0.90) for _ in range(10)]
        findings = detect_bias(preds, domain="weather")
        assert findings[0]["domain"] == "weather"

    def test_finding_has_required_keys(self) -> None:
        preds = [_incorrect(0.90) for _ in range(10)]
        findings = detect_bias(preds)
        required_keys = {"direction", "domain", "gap", "count", "avg_confidence", "hit_rate"}
        assert required_keys.issubset(set(findings[0].keys()))

    def test_count_reflects_valid_only(self) -> None:
        preds = (
            [_incorrect(0.90) for _ in range(8)]
            + [_ambiguous(0.90) for _ in range(5)]
        )
        findings = detect_bias(preds)
        assert findings[0]["count"] == 8


# ---------------------------------------------------------------------------
# Full Calibration
# ---------------------------------------------------------------------------


class TestFullCalibration:
    """Test the aggregate calibration pipeline."""

    def test_insufficient_data_flags_false(self) -> None:
        """< 20 resolved → sufficient_data=False."""
        preds = [_correct(0.80) for _ in range(MIN_RESOLVED_FOR_CALIBRATION - 1)]
        result = full_calibration(preds)
        assert isinstance(result, CalibrationResult)
        assert result.sufficient_data is False
        assert result.brier_score is None
        assert result.buckets == []

    def test_sufficient_data_populates_all(self) -> None:
        """>= 20 resolved → brier_score and buckets populated."""
        preds = [_correct(0.80) for _ in range(25)]
        result = full_calibration(preds)
        assert result.sufficient_data is True
        assert result.brier_score is not None
        assert len(result.buckets) == 5
        assert result.resolved_count == 25

    def test_ambiguous_counted_separately(self) -> None:
        preds = (
            [_correct(0.80) for _ in range(20)]
            + [_ambiguous(0.70) for _ in range(5)]
            + [_pending(0.60) for _ in range(3)]
        )
        result = full_calibration(preds)
        assert result.resolved_count == 20
        assert result.ambiguous_count == 5

    def test_multiplier_returned_when_enough_samples(self) -> None:
        preds = [_correct(0.80) for _ in range(10)]
        result = full_calibration(preds)
        assert result.estimate_multiplier is not None

    def test_multiplier_none_when_few_samples(self) -> None:
        preds = [_correct(0.80) for _ in range(3)]
        result = full_calibration(preds)
        assert result.estimate_multiplier is None

    def test_bias_findings_populated(self) -> None:
        """Overconfident data produces bias findings."""
        preds = [_incorrect(0.90) for _ in range(25)]
        result = full_calibration(preds)
        assert len(result.bias_findings) >= 1
        assert result.bias_findings[0]["direction"] == "overconfident"

    def test_domain_forwarded_to_bias(self) -> None:
        preds = [_incorrect(0.90) for _ in range(25)]
        result = full_calibration(preds, domain="sports")
        assert result.bias_findings[0]["domain"] == "sports"

    def test_empty_predictions(self) -> None:
        result = full_calibration([])
        assert result.resolved_count == 0
        assert result.ambiguous_count == 0
        assert result.sufficient_data is False
        assert result.brier_score is None
        assert result.buckets == []
        assert result.estimate_multiplier is None
        assert result.bias_findings == []

    def test_all_pending_is_insufficient(self) -> None:
        preds = [_pending(0.70) for _ in range(30)]
        result = full_calibration(preds)
        assert result.resolved_count == 0
        assert result.sufficient_data is False


# ---------------------------------------------------------------------------
# Confidence Normalization
# ---------------------------------------------------------------------------


class TestNormalizeConfidence:
    """Test confidence normalization to [0.5, 0.99]."""

    def test_mid_range_unchanged(self) -> None:
        conf, negated = normalize_confidence(0.7)
        assert conf == 0.7
        assert negated is False

    def test_below_half_negated(self) -> None:
        conf, negated = normalize_confidence(0.3)
        assert conf == pytest.approx(0.7)
        assert negated is True

    def test_exactly_half_not_negated(self) -> None:
        conf, negated = normalize_confidence(0.5)
        assert conf == 0.5
        assert negated is False

    def test_above_cap_clamped(self) -> None:
        """Values above 0.99 are clamped."""
        conf, negated = normalize_confidence(1.0)
        assert conf == 0.99
        assert negated is False

    def test_at_cap_unchanged(self) -> None:
        conf, negated = normalize_confidence(0.99)
        assert conf == 0.99
        assert negated is False

    def test_very_low_confidence_negated_to_high(self) -> None:
        conf, negated = normalize_confidence(0.01)
        assert conf == pytest.approx(0.99)
        assert negated is True

    def test_just_below_half(self) -> None:
        conf, negated = normalize_confidence(0.49)
        assert conf == pytest.approx(0.51)
        assert negated is True

    def test_zero_confidence(self) -> None:
        conf, negated = normalize_confidence(0.0)
        assert conf == pytest.approx(1.0)
        assert negated is True
