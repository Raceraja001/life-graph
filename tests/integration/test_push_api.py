"""Integration tests for the Web Push subscription + test API.

Covers:
- POST /api/v1/push/subscriptions (subscribe)
- DELETE /api/v1/push/subscriptions (unsubscribe)
- GET /api/v1/push/vapid-key
- POST /api/v1/push/test

Every status is asserted exactly: ``skip_on_db_error`` skips when no
database is reachable, so a 500 is always a failure. See
docs/specs/web-push-notifications.md.
"""

from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import assert_ok, skip_on_db_error

TENANT = "test_push_tenant"
TENANT_HEADERS = {"X-Tenant-ID": TENANT, "X-User-ID": "push-test-user"}


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=TENANT_HEADERS
    ) as c:
        yield c


class TestSubscribe:
    @skip_on_db_error
    async def test_subscribe_returns_ok(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/push/subscriptions",
            json={
                "endpoint": "https://fcm.googleapis.com/fcm/send/test-endpoint",
                "keys": {"p256dh": "test-p256dh", "auth": "test-auth"},
            },
        )
        assert assert_ok(resp, 200)["data"]["ok"] is True

    @skip_on_db_error
    async def test_unsubscribe_returns_ok(self, client: AsyncClient):
        resp = await client.request(
            "DELETE",
            "/api/v1/push/subscriptions",
            json={"endpoint": "https://fcm.googleapis.com/fcm/send/test-endpoint"},
        )
        assert assert_ok(resp, 200)["data"]["ok"] is True


class TestVapidKey:
    @skip_on_db_error
    async def test_vapid_key_returns_key_field(self, client: AsyncClient):
        resp = await client.get("/api/v1/push/vapid-key")
        assert "key" in assert_ok(resp, 200)["data"]


class TestTestPush:
    @skip_on_db_error
    async def test_test_push_returns_delivered_count(self, client: AsyncClient):
        resp = await client.post("/api/v1/push/test")
        assert isinstance(assert_ok(resp, 200)["data"]["delivered"], int)
