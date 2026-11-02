"""A capture is dated when it was captured, not when it arrived.

The Claude Code hook stamps ``properties.captured_at`` but sends no
``occurred_at``; captures delivered late from its offline queue were all dated
on arrival (2,844 from 2026-10-13 read 2026-11-02).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from life_graph.services.capture import CaptureService, captured_at


class _FakeResult:
    def scalars(self):
        return self

    def first(self):
        return None


class _FakeSession:
    def __init__(self):
        self.queries = []

    async def execute(self, query, *_a, **_k):
        self.queries.append(query)
        return _FakeResult()

    def add(self, obj):
        pass

    async def flush(self):
        pass


def test_captured_at_is_read_and_never_in_the_future():
    assert captured_at({"captured_at": "2026-10-13T04:47:12+00:00"}) == datetime(
        2026, 10, 13, 4, 47, 12, tzinfo=UTC
    )
    assert captured_at({"captured_at": "2026-10-13T04:47:12Z"}).tzinfo is not None
    assert captured_at({"captured_at": "2026-10-13T04:47:12"}).tzinfo == UTC
    later = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    assert captured_at({"captured_at": later}) <= datetime.now(UTC)
    assert captured_at({"captured_at": "yesterday"}) is None
    assert captured_at({"captured_at": 17}) is None
    assert captured_at(None) is None


async def test_a_late_capture_is_dated_when_it_was_captured():
    svc = CaptureService(_FakeSession(), event_bus=None)
    event = await svc.ingest(
        tenant_id="t1",
        surface="cli",
        content="proceed",
        properties={"captured_at": "2026-10-13T04:47:12+00:00"},
    )

    assert event.occurred_at == datetime(2026, 10, 13, 4, 47, 12, tzinfo=UTC)


async def test_an_explicit_occurred_at_still_wins():
    svc = CaptureService(_FakeSession(), event_bus=None)
    when = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
    event = await svc.ingest(
        tenant_id="t1",
        surface="cli",
        content="proceed",
        occurred_at=when,
        properties={"captured_at": "2026-10-13T04:47:12+00:00"},
    )

    assert event.occurred_at == when


async def test_dedup_looks_both_sides_of_the_capture_time():
    session = _FakeSession()
    svc = CaptureService(session, event_bus=None)
    await svc.ingest(
        tenant_id="t1",
        surface="cli",
        content="proceed",
        properties={"captured_at": "2026-10-13T04:47:12+00:00"},
    )

    sql = str(session.queries[0].compile(compile_kwargs={"literal_binds": True}))
    assert "occurred_at >=" in sql and "occurred_at <=" in sql
