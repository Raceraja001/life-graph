"""Calibration endpoints: they now compute live instead of reading a snapshot.

History: both routes once died on a missing ``select`` import, and survived
because nothing called them (the dashboard page was a placeholder). They
then read "the latest snapshot" — which no job ever wrote, so they always
returned null. They now delegate to ``CalibrationService.report``, and these
tests pin that wiring: tenant and scope are passed through, and the curve
endpoint serves the same buckets the report computed.
"""

from __future__ import annotations

import contextlib

import pytest

import life_graph.api.judgment as judgment
from life_graph.services.calibration import CalibrationService


class _Session:
    def __init__(self):
        self.commits = 0

    async def commit(self):
        self.commits += 1


@pytest.fixture
def stub(monkeypatch):
    session = _Session()
    calls = {"report": [], "recompute": []}

    @contextlib.asynccontextmanager
    async def _factory():
        yield session

    async def report(self, tenant_id, domain=None, window_days=90):
        calls["report"].append((tenant_id, domain, window_days))
        return {
            "status": "ok",
            "domain": domain or "overall",
            "buckets": [{"range_label": "0.90-0.99", "count": 20}],
        }

    async def recompute(self, tenant_id, window_days=90):
        calls["recompute"].append((tenant_id, window_days))
        return {"resolved": 20, "written": ["overall"], "findings": 0}

    monkeypatch.setattr(judgment, "async_session", _factory)
    monkeypatch.setattr(CalibrationService, "report", report)
    monkeypatch.setattr(CalibrationService, "recompute", recompute)
    calls["session"] = session
    return calls


async def test_get_calibration_reports_for_tenant_and_scope(stub):
    resp = await judgment.get_calibration(tenant_id="tenant-abc", domain="infra", window=30)
    assert stub["report"] == [("tenant-abc", "infra", 30)]
    assert resp["data"]["status"] == "ok"


async def test_get_calibration_without_domain_means_overall(stub):
    resp = await judgment.get_calibration(tenant_id="t1", domain=None, window=90)
    assert stub["report"] == [("t1", None, 90)]
    assert resp["data"]["domain"] == "overall"


async def test_curve_serves_report_buckets_with_identity_line(stub):
    resp = await judgment.get_calibration_curve(tenant_id="t1", domain=None, window=90)
    assert resp["data"] == {
        "domain": "overall",
        "buckets": [{"range_label": "0.90-0.99", "count": 20}],
        "identity": [[0.5, 0.5], [1.0, 1.0]],
    }


async def test_recompute_endpoint_commits_snapshots(stub):
    resp = await judgment.recompute_calibration(tenant_id="t1", window=90)
    assert stub["recompute"] == [("t1", 90)]
    assert stub["session"].commits == 1
    assert resp["data"]["written"] == ["overall"]


async def test_refresh_after_resolve_never_raises(monkeypatch, stub):
    async def broken(self, tenant_id, window_days=90):
        raise RuntimeError("db down")

    monkeypatch.setattr(CalibrationService, "recompute", broken)
    await judgment._refresh_calibration("t1")  # logged, not raised
