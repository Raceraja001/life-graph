"""A duplicate capture leaves the original event alone (audit M9).

``CaptureService.ingest`` used to set ``status = "duplicate"`` on the ORIGINAL
row it matched, so a received-but-unprocessed capture was relabelled and the
retry sweep (which only retries ``received``) never picked it up again.

Telegram messages are also dated by their own ``date`` now, so a replayed
update matches the original's dedup window instead of "now".
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from life_graph.models.db import CaptureEvent
from life_graph.services.capture import CaptureService


class _Result:
    def __init__(self, row):
        self._row = row

    def scalars(self):
        return self

    def first(self):
        return self._row


class _Session:
    def __init__(self, row):
        self._row = row
        self.added = []

    async def execute(self, *_a, **_k):
        return _Result(self._row)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass


def _original(status: str) -> CaptureEvent:
    return CaptureEvent(
        id=uuid.uuid4(),
        tenant_id="t1",
        surface="telegram",
        modality="text",
        content="buy milk",
        content_hash="h",
        trust_tier="self",
        status=status,
        yield_count=0,
        occurred_at=datetime(2026, 11, 19, 8, 0, tzinfo=UTC),
        properties={"message_id": 7},
        created_at=datetime(2026, 11, 19, 8, 0, 1, tzinfo=UTC),
    )


async def test_duplicate_does_not_rewrite_the_original_status():
    original = _original("received")
    session = _Session(original)

    got = await CaptureService(session, event_bus=None).ingest(
        tenant_id="t1", surface="telegram", content="buy milk"
    )

    # The original row keeps its status, so the retry sweep still sees it.
    assert original.status == "received"
    # Callers (and the API response) still see the capture flagged duplicate.
    assert got.status == "duplicate"
    assert got.id == original.id
    assert got.content == original.content
    assert got.properties == original.properties
    assert got is not original
    assert session.added == []


async def test_duplicate_of_a_processed_capture_stays_processed():
    original = _original("processed")
    got = await CaptureService(_Session(original), event_bus=None).ingest(
        tenant_id="t1", surface="telegram", content="buy milk"
    )
    assert original.status == "processed"
    assert got.status == "duplicate"


async def test_telegram_capture_is_dated_by_the_message(monkeypatch):
    from life_graph.integrations.telegram import router

    calls = []

    class _Svc:
        def __init__(self, *_a, **_k):
            pass

        async def ingest(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(router, "CaptureService", _Svc)
    monkeypatch.setattr(router, "_reply", AsyncMock())
    session = AsyncMock()

    sent = int(datetime(2026, 11, 19, 7, 30, tzinfo=UTC).timestamp())
    msg = {"message_id": 42, "date": sent, "chat": {"id": 5}, "text": "buy milk"}
    await router._capture(msg, 5, "t1", "buy milk", session)

    assert calls[0]["occurred_at"] == datetime(2026, 11, 19, 7, 30, tzinfo=UTC)


async def test_telegram_capture_without_a_date_falls_back_to_now(monkeypatch):
    from life_graph.integrations.telegram import router

    calls = []

    class _Svc:
        def __init__(self, *_a, **_k):
            pass

        async def ingest(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(router, "CaptureService", _Svc)
    monkeypatch.setattr(router, "_reply", AsyncMock())

    for bad in (None, "yesterday", -1):
        calls.clear()
        msg = {"message_id": 42, "date": bad, "chat": {"id": 5}, "text": "x"}
        await router._capture(msg, 5, "t1", "x", AsyncMock())
        assert calls[0].get("occurred_at") is None
