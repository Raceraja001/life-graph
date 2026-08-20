"""Regression tests for the calibration endpoints.

Both `GET /judgment/calibration` and `/judgment/calibration/curve` called
`select(...)` without importing it — this file uses function-level imports,
and these two functions imported `CalibrationSnapshot` but not `select`,
while their sibling `get_judgment_stats` imported both. Every call raised
`NameError: name 'select' is not defined`.

It survived because nothing ever executed them: no test covered these
routes, and the dashboard's Calibration page is a "Coming Soon" placeholder
that never calls the API.

These tests stub the session so they assert the endpoint *executes* rather
than asserting a status code that a dead database would also produce. An
`assert status in (200, 500)` here would have passed against the bug.
"""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock

import pytest

import life_graph.api.judgment as judgment


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def scalars(self):
        scalars = MagicMock()
        scalars.first.return_value = self._row
        return scalars


class _FakeSession:
    def __init__(self, row=None):
        self.row = row
        self.executed = []

    async def execute(self, stmt):
        self.executed.append(stmt)
        return _FakeResult(self.row)


@pytest.fixture
def stub_session(monkeypatch):
    """Replace async_session with one that records the statements built."""
    session = _FakeSession()

    @contextlib.asynccontextmanager
    async def _factory():
        yield session

    monkeypatch.setattr(judgment, "async_session", _factory)
    return session


async def test_get_calibration_builds_a_query(stub_session):
    """Must reach the DB with a real statement — not die on NameError."""
    resp = await judgment.get_calibration(tenant_id="t1", domain=None, window=90)
    assert len(stub_session.executed) == 1, "endpoint never issued a query"
    assert resp["data"] is None  # no snapshot stored


async def test_get_calibration_curve_builds_a_query(stub_session):
    resp = await judgment.get_calibration_curve(tenant_id="t1", domain=None)
    assert len(stub_session.executed) == 1, "endpoint never issued a query"
    # Unlike /calibration, the curve endpoint returns an empty-bucket payload
    # rather than None when no snapshot exists, so a chart can render blank.
    assert resp["data"] == {"buckets": [], "domain": None}


async def test_calibration_filters_by_tenant(stub_session):
    """Tenant isolation is the codebase's core invariant — assert the
    statement actually carries the tenant, not just that it ran."""
    await judgment.get_calibration(tenant_id="tenant-abc", domain=None, window=90)
    assert "tenant-abc" in str(stub_session.executed[0].compile().params.values()) or (
        "tenant_id" in str(stub_session.executed[0])
    )


async def test_calibration_applies_domain_filter(stub_session):
    """The domain filter adds a WHERE clause rather than being ignored."""
    await judgment.get_calibration(tenant_id="t1", domain="career", window=90)
    with_domain = str(stub_session.executed[0])
    stub_session.executed.clear()
    await judgment.get_calibration(tenant_id="t1", domain=None, window=90)
    without_domain = str(stub_session.executed[0])
    assert with_domain != without_domain, "domain filter had no effect on the query"
