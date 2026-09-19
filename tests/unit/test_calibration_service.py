"""CalibrationService: live reports, snapshot writes, and the shared reader.

The math itself is covered in test_calibration.py. These tests feed the
service plain prediction rows (``resolved_predictions`` is patched to filter
an in-memory list by window, as the SQL does) and a session fake that records
what would be written.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.sql.dml import Delete

from life_graph.models.db import CalibrationSnapshot
from life_graph.scoring.calibration import BucketResult, bucket_bias
from life_graph.services import calibration as calibration_mod
from life_graph.services.calibration import OVERALL, CalibrationService, latest_snapshot

NOW = datetime.now(UTC)


def _rows(n: int, *, confidence=0.9, correct=None, tags=(), days_ago=1):
    """n resolved predictions; the first ``correct`` of them came true."""
    correct = n if correct is None else correct
    return [
        {
            "confidence": confidence,
            "outcome": "correct" if i < correct else "incorrect",
            "domain_tags": list(tags),
            "resolved_at": NOW - timedelta(days=days_ago),
        }
        for i in range(n)
    ]


class _Session:
    def __init__(self):
        self.added = []
        self.executed = []

    def add(self, obj):
        self.added.append(obj)

    async def execute(self, stmt):
        self.executed.append(stmt)

    async def flush(self):
        pass


@pytest.fixture
def make_service(monkeypatch):
    def _make(rows, pending=0, bus=None):
        async def resolved(self, tenant_id, window_days=90, *, end=None):
            end = end or datetime.now(UTC)
            start = end - timedelta(days=window_days)
            return [r for r in rows if start < r["resolved_at"] <= end]

        async def pending_count(self, tenant_id):
            return pending

        monkeypatch.setattr(CalibrationService, "resolved_predictions", resolved)
        monkeypatch.setattr(CalibrationService, "pending_count", pending_count)
        session = _Session()
        return CalibrationService(session, bus), session

    return _make


# ── bucket_bias ──────────────────────────────────────────────


def _bucket(label, count, avg, hit):
    return BucketResult(label, 0.0, 0.0, count, avg, hit, hit - avg)


def test_bucket_bias_flags_only_large_gaps_with_enough_samples():
    findings = bucket_bias(
        [
            _bucket("0.60-0.70", 10, 0.65, 0.62),  # calibrated
            _bucket("0.80-0.90", 4, 0.85, 0.25),  # too few to call
            _bucket("0.90-0.99", 7, 0.92, 0.57),  # overconfident
            _bucket("0.50-0.60", 6, 0.55, 0.83),  # underconfident
        ],
        domain="infra",
    )
    assert [(f["bucket"], f["direction"]) for f in findings] == [
        ("0.90-0.99", "overconfident"),
        ("0.50-0.60", "underconfident"),
    ]
    assert findings[0] == {
        "kind": "bucket",
        "direction": "overconfident",
        "domain": "infra",
        "bucket": "0.90-0.99",
        "claimed": 0.92,
        "actual": 0.57,
        "n": 7,
        "gap": -0.35,
    }


# ── report ───────────────────────────────────────────────────


async def test_report_below_threshold_is_progress_not_a_curve(make_service):
    svc, _ = make_service(_rows(5) + _rows(2, days_ago=200), pending=3)
    report = await svc.report("t1")
    assert report["status"] == "insufficient_data"
    assert report["resolved_count"] == 5  # outside the 90-day window excluded
    assert report["required"] == 20
    assert report["pending_count"] == 3
    assert report["brier_score"] is None
    assert report["buckets"] == []
    assert report["trend"] is None


async def test_report_with_enough_data_has_curve_and_bias(make_service):
    # 20 predictions at 90%, only 12 came true: clearly overconfident.
    svc, _ = make_service(_rows(20, confidence=0.9, correct=12))
    report = await svc.report("t1")
    assert report["status"] == "ok"
    assert report["domain"] == OVERALL
    assert report["brier_score"] == pytest.approx((12 * 0.1**2 + 8 * 0.9**2) / 20)
    assert len(report["buckets"]) == 5
    top = next(b for b in report["buckets"] if b["range_label"] == "0.90-0.99")
    assert (top["count"], top["hit_rate"]) == (20, pytest.approx(0.6))
    kinds = {(f.get("kind", "overall"), f["direction"]) for f in report["bias_findings"]}
    assert ("bucket", "overconfident") in kinds


async def test_report_scopes_to_a_domain(make_service):
    rows = _rows(20, tags=["infra"]) + _rows(5, tags=["career"])
    svc, _ = make_service(rows)
    assert (await svc.report("t1", "infra"))["resolved_count"] == 20
    career = await svc.report("t1", "career")
    assert (career["resolved_count"], career["status"]) == (5, "insufficient_data")
    assert (await svc.report("t1"))["resolved_count"] == 25


async def test_report_trend_compares_with_previous_window(make_service):
    previous = _rows(20, confidence=0.9, correct=10, days_ago=120)  # Brier 0.41
    current = _rows(20, confidence=0.9, correct=18, days_ago=10)  # Brier 0.09
    svc, _ = make_service(previous + current)
    trend = (await svc.report("t1"))["trend"]
    assert trend["previous_brier"] == pytest.approx(0.41)
    assert trend["delta_pct"] < 0  # lower Brier = improvement


async def test_report_unresolved_rate_counts_ambiguous(make_service):
    rows = _rows(6)
    rows[0]["outcome"] = rows[1]["outcome"] = "ambiguous"
    svc, _ = make_service(rows)
    report = await svc.report("t1")
    assert (report["resolved_count"], report["ambiguous_count"]) == (4, 2)
    assert report["unresolved_rate"] == pytest.approx(0.333)


# ── recompute ────────────────────────────────────────────────


class _Bus:
    def __init__(self):
        self.events = []

    async def emit(self, event_type, payload):
        self.events.append((event_type, payload))


async def test_recompute_writes_overall_and_each_domain_with_enough_data(make_service):
    bus = _Bus()
    rows = _rows(20, tags=["infra"], correct=15) + _rows(3, tags=["career"])
    svc, session = make_service(rows, bus=bus)
    summary = await svc.recompute("t1")

    assert summary["resolved"] == 23
    assert sorted(summary["written"]) == ["infra", OVERALL]
    snaps = {s.domain: s for s in session.added}
    assert set(snaps) == {OVERALL, "infra"}  # career has 3: no fake curve
    assert all(isinstance(s, CalibrationSnapshot) for s in session.added)
    assert snaps[OVERALL].resolved_count == 23
    assert snaps["infra"].resolved_count == 20
    assert snaps["infra"].buckets and "range_label" in snaps["infra"].buckets[0]
    # Today's earlier row for each scope is replaced, not accumulated.
    assert sum(isinstance(s, Delete) for s in session.executed) == 2
    assert [e[1]["domains"] for e in bus.events] == [summary["written"]]


async def test_recompute_with_too_little_data_writes_nothing(make_service):
    bus = _Bus()
    svc, session = make_service(_rows(19), bus=bus)
    summary = await svc.recompute("t1")
    assert summary["written"] == []
    assert session.added == [] and session.executed == []
    assert bus.events == []


# ── latest_snapshot ──────────────────────────────────────────


class _ScalarsResult:
    def __init__(self, row):
        self._row = row

    def scalars(self):
        return self

    def first(self):
        return self._row


class _LookupSession:
    """Returns the queued rows in order, recording the domain each query asked for."""

    def __init__(self, *rows):
        self.rows = list(rows)
        self.domains = []

    async def execute(self, stmt):
        params = stmt.compile().params
        self.domains.append(next(v for k, v in params.items() if k.startswith("domain")))
        return _ScalarsResult(self.rows.pop(0))


async def test_latest_snapshot_defaults_to_overall():
    snap = object()
    session = _LookupSession(snap)
    assert await latest_snapshot(session, "t1") is snap
    assert session.domains == [OVERALL]


async def test_latest_snapshot_falls_back_to_overall_for_a_thin_domain():
    overall = object()
    session = _LookupSession(None, overall)
    assert await latest_snapshot(session, "t1", "infra") is overall
    assert session.domains == ["infra", OVERALL]


async def test_latest_snapshot_none_when_nothing_computed():
    session = _LookupSession(None, None)
    assert await latest_snapshot(session, "t1", "infra") is None


def test_module_exports_resolved_outcomes():
    # The worker and stats endpoint count "resolved" with this tuple; a
    # suggestion must never be in it.
    assert "suggested" not in calibration_mod.RESOLVED_OUTCOMES
    assert "pending" not in calibration_mod.RESOLVED_OUTCOMES


# ── nightly job ──────────────────────────────────────────────


async def test_nightly_job_recomputes_each_tenant_and_isolates_failures(monkeypatch):
    import contextlib

    from life_graph.workers import tasks

    class _Rows:
        def fetchall(self):
            return [("alice",), ("bob",)]

    class _S:
        commits = 0

        async def execute(self, stmt):
            return _Rows()

        async def commit(self):
            _S.commits += 1

    @contextlib.asynccontextmanager
    async def _factory():
        yield _S()

    async def recompute(self, tenant_id, window_days=90):
        if tenant_id == "bob":
            raise RuntimeError("boom")
        return {"resolved": 25, "written": ["overall", "infra"], "findings": 1}

    monkeypatch.setattr(tasks, "async_session", _factory)
    monkeypatch.setattr(CalibrationService, "recompute", recompute)

    result = await tasks.run_nightly_calibration({})
    assert result["tenants"] == 2
    assert result["snapshots"] == 2
    assert result["results"]["bob"] == {"status": "error"}
    assert _S.commits == 1  # only alice's session committed


def test_describe_finding_reads_as_a_sentence():
    from life_graph.services.calibration import describe_finding

    bucket = {
        "kind": "bucket",
        "direction": "overconfident",
        "claimed": 0.9,
        "actual": 0.591,
        "n": 22,
    }
    overall = {
        "direction": "overconfident",
        "avg_confidence": 0.896,
        "hit_rate": 0.609,
        "count": 23,
    }
    assert describe_finding(bucket) == (
        "When you say about 90%, you are right 59% of the time (22 predictions): overconfident."
    )
    assert describe_finding(overall) == (
        "Overall overconfident: average confidence 90%, right 61% of the time (23 predictions)."
    )
