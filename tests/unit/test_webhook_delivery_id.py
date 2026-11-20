"""Every attempt of one webhook delivery carries the same delivery id (audit L11).

The envelope is rebuilt (new timestamp, new signature) on each ARQ retry, so
without a stable id a receiver can't tell a retry from a new event.
"""

from __future__ import annotations

import contextlib
import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from life_graph.core.events import Event, EventType
from life_graph.core.tenant import tenant_scope
from life_graph.integrations import webhook as wh
from life_graph.services import safe_fetch


class _Recorder:
    """httpx.AsyncClient stand-in: records each post; fails the first N."""

    calls: list[dict] = []
    fail_first = 0

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, **kwargs):
        _Recorder.calls.append(kwargs)
        status = 503 if len(_Recorder.calls) <= _Recorder.fail_first else 200
        return httpx.Response(status, request=httpx.Request("POST", url))


@pytest.fixture
def hook(monkeypatch):
    async def _resolve(host, port):
        return {"93.184.216.34"}

    monkeypatch.setattr(safe_fetch, "_resolve", _resolve)
    _Recorder.calls = []
    _Recorder.fail_first = 0
    monkeypatch.setattr(httpx, "AsyncClient", _Recorder)

    row = SimpleNamespace(
        id=uuid.uuid4(),
        active=True,
        url="https://hooks.example.com/x",
        secret="s" * 20,
        failure_count=0,
        last_delivered_at=None,
    )
    session = MagicMock()
    session.get = AsyncMock(return_value=row)
    session.commit = AsyncMock()

    @contextlib.asynccontextmanager
    async def _session():
        yield session

    monkeypatch.setattr(wh, "async_session", _session)
    return row


@pytest.mark.asyncio
async def test_a_retry_carries_the_same_delivery_id(hook):
    _Recorder.fail_first = 1
    did = "11111111-2222-4333-8444-555555555555"

    with pytest.raises(httpx.HTTPStatusError):
        await wh.deliver_webhook({"job_id": "j1"}, str(hook.id), "memory:created", {}, did)
    result = await wh.deliver_webhook({"job_id": "j1"}, str(hook.id), "memory:created", {}, did)

    assert result["status"] == "delivered"
    sent = [c["headers"]["X-Webhook-Delivery"] for c in _Recorder.calls]
    assert sent == [did, did]
    bodies = [json.loads(c["content"])["delivery_id"] for c in _Recorder.calls]
    assert bodies == [did, did]


@pytest.mark.asyncio
async def test_a_job_queued_without_an_id_uses_the_arq_job_id(hook):
    await wh.deliver_webhook({"job_id": "arq-job-7"}, str(hook.id), "memory:created", {})
    await wh.deliver_webhook({"job_id": "arq-job-7"}, str(hook.id), "memory:created", {})
    assert [c["headers"]["X-Webhook-Delivery"] for c in _Recorder.calls] == ["arq-job-7"] * 2


@pytest.mark.asyncio
async def test_each_enqueue_gets_its_own_delivery_id(monkeypatch):
    rows = [SimpleNamespace(id=uuid.uuid4(), events="*") for _ in range(2)]
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)

    @contextlib.asynccontextmanager
    async def _session():
        yield session

    monkeypatch.setattr(wh, "async_session", _session)
    pool = MagicMock()
    pool.enqueue_job = AsyncMock()
    handler = wh.WebhookEventHandler(MagicMock())
    handler.set_arq_pool(pool)

    with tenant_scope("t1"):
        await handler._handle_event(Event(type=EventType.MEMORY_CREATED, payload={"a": 1}))  # noqa: SLF001

    ids = [c.kwargs["delivery_id"] for c in pool.enqueue_job.await_args_list]
    assert len(ids) == 2 and len(set(ids)) == 2
    assert all(uuid.UUID(i) for i in ids)
