"""Tenant webhooks and webhook channels cannot target the private network
(audit 2026-11-19, M6).

Every path runs services/safe_fetch.check_url: at create time (422) and again
before each delivery. ``/webhooks/{id}/test`` reports only delivered/failed,
never the target's status code or connection error.
"""

from __future__ import annotations

import contextlib
import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import HTTPException

from life_graph.config import settings
from life_graph.core.tenant import tenant_scope
from life_graph.services import safe_fetch

PRIVATE_URLS = [
    "http://127.0.0.1:8080/api/v1/memories",
    "http://169.254.169.254/latest/meta-data/",
    "http://10.0.0.5/admin",
    "http://[::1]:6379/",
    "file:///etc/passwd",
]


@pytest.fixture
def public_dns(monkeypatch):
    """Resolve every name to a public address, so no test needs real DNS."""

    async def _resolve(host, port):
        return {"93.184.216.34"}

    monkeypatch.setattr(safe_fetch, "_resolve", _resolve)


@contextlib.asynccontextmanager
async def _no_db():
    raise AssertionError("the DB must not be touched for a refused URL")
    yield  # pragma: no cover


class _FakeClient:
    """Stands in for httpx.AsyncClient; records posts, returns or raises."""

    posts: list = []

    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs
        _FakeClient.last_kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, **kwargs):
        _FakeClient.posts.append(url)
        outcome = _FakeClient.outcome
        if isinstance(outcome, Exception):
            raise outcome
        return httpx.Response(outcome, request=httpx.Request("POST", url))


@pytest.fixture
def fake_http(monkeypatch):
    _FakeClient.posts = []
    _FakeClient.outcome = 200
    _FakeClient.last_kwargs = {}
    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)
    return _FakeClient


# ── The shared guard ──────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("url", PRIVATE_URLS)
async def test_guard_refuses_private_targets(url):
    from life_graph.api.url_guard import require_public_url

    with pytest.raises(HTTPException) as exc:
        await require_public_url(url)
    assert exc.value.status_code == 422
    # The detail never echoes what the host resolved to.
    assert "127.0.0.1" not in exc.value.detail and "10.0.0.5" not in exc.value.detail


@pytest.mark.asyncio
async def test_guard_allows_public_and_allowlisted(public_dns, monkeypatch):
    from life_graph.api.url_guard import require_public_url

    await require_public_url("https://hooks.example.com/x")
    monkeypatch.setattr(settings, "fetch_allow_hosts", "nas.lan")

    async def _private(host, port):
        return {"192.168.1.20"}

    monkeypatch.setattr(safe_fetch, "_resolve", _private)
    await require_public_url("http://nas.lan:5678/hook")
    with pytest.raises(HTTPException):
        await require_public_url("http://other.lan/hook")


# ── Tenant webhooks (api/admin.py) ────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("url", PRIVATE_URLS[:3])
async def test_create_webhook_refuses_private_url(monkeypatch, url):
    from life_graph.api import admin

    monkeypatch.setattr(admin, "async_session", _no_db)
    body = admin.WebhookCreate(url=url, secret="s" * 20)
    with tenant_scope("t1"), pytest.raises(HTTPException) as exc:
        await admin.create_webhook(body)
    assert exc.value.status_code == 422


def _session_with(webhook):
    @contextlib.asynccontextmanager
    async def _session():
        s = MagicMock()
        s.get = AsyncMock(return_value=webhook)
        yield s

    return _session


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "outcome",
    [
        httpx.ConnectError("connection to 10.1.2.3:22 refused"),
        500,
        302,
    ],
)
async def test_test_endpoint_reports_only_failed(monkeypatch, public_dns, fake_http, outcome):
    from life_graph.api import admin

    wid = uuid.uuid4()
    hook = SimpleNamespace(id=wid, tenant_id="t1", url="https://hooks.example.com/x")
    monkeypatch.setattr(admin, "async_session", _session_with(hook))
    fake_http.outcome = outcome

    with tenant_scope("t1"):
        resp = await admin.test_webhook(wid)
    data = resp["data"] if isinstance(resp, dict) else json.loads(resp.body)["data"]

    assert data["delivery_status"] == "failed"
    assert "http_status" not in data and "error" not in data
    assert "10.1.2.3" not in json.dumps(data)
    assert fake_http.last_kwargs.get("follow_redirects") is False


@pytest.mark.asyncio
async def test_test_endpoint_delivered(monkeypatch, public_dns, fake_http):
    from life_graph.api import admin

    wid = uuid.uuid4()
    hook = SimpleNamespace(id=wid, tenant_id="t1", url="https://hooks.example.com/x")
    monkeypatch.setattr(admin, "async_session", _session_with(hook))

    with tenant_scope("t1"):
        resp = await admin.test_webhook(wid)
    data = resp["data"] if isinstance(resp, dict) else json.loads(resp.body)["data"]
    assert data["delivery_status"] == "delivered"


@pytest.mark.asyncio
async def test_test_endpoint_refuses_a_stored_private_url(monkeypatch, fake_http):
    from life_graph.api import admin

    wid = uuid.uuid4()
    hook = SimpleNamespace(id=wid, tenant_id="t1", url="http://127.0.0.1:6379/")
    monkeypatch.setattr(admin, "async_session", _session_with(hook))

    with tenant_scope("t1"), pytest.raises(HTTPException) as exc:
        await admin.test_webhook(wid)
    assert exc.value.status_code == 422
    assert fake_http.posts == []


# ── Delivery (integrations/webhook.py) ────────────────────────


@pytest.mark.asyncio
async def test_delivery_skips_a_private_url(monkeypatch, fake_http):
    from life_graph.integrations import webhook as wh

    hook = SimpleNamespace(
        id=uuid.uuid4(), active=True, url="http://169.254.169.254/", secret="s" * 20
    )
    monkeypatch.setattr(wh, "async_session", _session_with(hook))

    result = await wh.deliver_webhook({}, str(hook.id), "memory:created", {"a": 1})
    assert result["status"] == "skipped"
    assert fake_http.posts == []


@pytest.mark.asyncio
async def test_delivery_to_a_public_url_does_not_follow_redirects(
    monkeypatch, public_dns, fake_http
):
    from life_graph.integrations import webhook as wh

    hook = SimpleNamespace(
        id=uuid.uuid4(),
        active=True,
        url="https://hooks.example.com/x",
        secret="s" * 20,
        failure_count=0,
        last_delivered_at=None,
    )
    session = MagicMock()
    session.get = AsyncMock(return_value=hook)
    session.commit = AsyncMock()

    @contextlib.asynccontextmanager
    async def _session():
        yield session

    monkeypatch.setattr(wh, "async_session", _session)
    result = await wh.deliver_webhook({}, str(hook.id), "memory:created", {"a": 1})
    assert result["status"] == "delivered"
    assert fake_http.last_kwargs.get("follow_redirects") is False


# ── Notification channels (watchers) ──────────────────────────


@pytest.mark.asyncio
async def test_webhook_channel_send_refuses_private_url(fake_http):
    from life_graph.watchers.channels.webhook_channel import WebhookChannel

    ok = await WebhookChannel().send(
        config={"url": "http://127.0.0.1:8080/api/v1/admin"},
        event_id="e1",
        severity="info",
        title="t",
        details="d",
        watcher_name="w",
    )
    assert ok is False
    assert fake_http.posts == []


@pytest.mark.asyncio
async def test_create_webhook_channel_refuses_private_url(monkeypatch):
    from life_graph.api import watchers as watchers_api
    from life_graph.watchers.schemas import NotificationChannelCreate

    monkeypatch.setattr(watchers_api, "async_session", _no_db)
    body = NotificationChannelCreate(channel_type="webhook", config={"url": "http://10.0.0.5/hook"})
    with tenant_scope("t1"), pytest.raises(HTTPException) as exc:
        await watchers_api.create_notification_channel(body)
    assert exc.value.status_code == 422
