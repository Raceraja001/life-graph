from datetime import UTC, datetime, timedelta

import pytest

from life_graph.models.assistant import PageMonitor
from life_graph.services.page_monitors import due_monitors
from tests.unit.fakes import FakeSession, sql

# Helper to create a PageMonitor instance


def _monitor(
    *,
    id: str,
    tenant_id: str,
    paused: bool = False,
    last_checked_at=None,
    interval_minutes=180,
    **kwargs,
) -> PageMonitor:
    # create a PageMonitor with minimal required fields
    return PageMonitor(
        id=id,
        tenant_id=tenant_id,
        name="test",
        url="http://example.com",
        mode="change",
        selector=None,
        threshold=None,
        pattern=None,
        interval_minutes=interval_minutes,
        paused=paused,
        last_checked_at=last_checked_at,
        last_hash=None,
        last_value=None,
        last_excerpt=None,
        last_error=None,
        consecutive_failures=0,
        created_at=datetime.now(tz=UTC),
        **kwargs,
    )


@pytest.mark.asyncio
async def test_due_monitors_returns_due(monkeypatch):
    # set up a monitor that is due (no last_checked_at)
    monitor = _monitor(id="m1", tenant_id="t1")
    session = FakeSession([monitor])
    now = datetime.now(tz=UTC)
    result = await due_monitors(session, "t1", now)
    assert result == [monitor]
    # verify tenant filter in SQL
    assert "t1" in sql(session.statements[0])


@pytest.mark.asyncio
async def test_due_monitors_filters_paused(monkeypatch):
    monitor = _monitor(id="m2", tenant_id="t1", paused=True)
    session = FakeSession([monitor])
    now = datetime.now(tz=UTC)
    result = await due_monitors(session, "t1", now)
    assert result == []


@pytest.mark.asyncio
async def test_due_monitors_skips_not_due(monkeypatch):
    # last_checked_at within interval so not due
    past = datetime.now(tz=UTC) - timedelta(minutes=10)
    monitor = _monitor(id="m3", tenant_id="t1", last_checked_at=past, interval_minutes=30)
    session = FakeSession([monitor])
    now = datetime.now(tz=UTC)
    result = await due_monitors(session, "t1", now)
    assert result == []
