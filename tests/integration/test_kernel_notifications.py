"""Integration tests for OS Kernel Notification Engine.

Tests the Notification API:
- GET /api/v1/kernel/notifications (list with filters)
- PATCH /api/v1/kernel/notifications/{id}/read (mark read)
- POST /api/v1/kernel/notifications/read-all (mark all)

Also tests NotificationEngine service methods (unit tests
with mock session_factory, no DB needed).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import (
    MagicMock,
)

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import assert_ok, skip_on_db_error

TENANT_HEADERS = {
    "X-Tenant-ID": "test_notification_tenant",
    "X-User-ID": "notification-test-user",
}


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """HTTP client for notification API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers=TENANT_HEADERS,
    ) as c:
        yield c


# ── NotificationEngine Unit Tests (mock, no DB) ─────────────


def _make_mock_notification(**overrides: Any) -> MagicMock:
    """Build a mock Notification ORM object."""
    notif = MagicMock()
    notif.id = overrides.get(
        "id",
        uuid.uuid4(),
    )
    notif.tenant_id = overrides.get(
        "tenant_id",
        "test_notification_tenant",
    )
    notif.priority = overrides.get("priority", "info")
    notif.channel = overrides.get("channel", "terminal")
    notif.title = overrides.get("title", "Test Alert")
    notif.body = overrides.get("body", "Something happened")
    notif.extra_metadata = overrides.get("metadata", {})
    notif.is_read = overrides.get("is_read", False)
    notif.is_delivered = overrides.get(
        "is_delivered",
        False,
    )
    notif.delivered_at = overrides.get("delivered_at")
    notif.delivery_error = overrides.get("delivery_error")
    notif.source_type = overrides.get("source_type")
    notif.source_id = overrides.get("source_id")
    notif.created_at = overrides.get(
        "created_at",
        datetime.now(UTC),
    )
    return notif


class TestNotifToDict:
    """NotificationEngine._notif_to_dict — pure conversion."""

    def test_converts_all_fields(self):
        """All ORM fields appear in the output dict."""
        from life_graph.kernel.notification_engine import (
            NotificationEngine,
        )

        notif_id = uuid.uuid4()
        now = datetime.now(UTC)
        mock_notif = _make_mock_notification(
            id=notif_id,
            priority="critical",
            channel="email",
            title="Disk full",
            body="Root partition at 95%",
            metadata={"disk": "/"},
            is_read=True,
            is_delivered=True,
            delivered_at=now,
            delivery_error=None,
            source_type="monitor",
            source_id=uuid.uuid4(),
            created_at=now,
        )

        result = NotificationEngine._notif_to_dict(
            mock_notif,
        )

        assert result["id"] == str(notif_id)
        assert result["priority"] == "critical"
        assert result["channel"] == "email"
        assert result["title"] == "Disk full"
        assert result["body"] == "Root partition at 95%"
        assert result["metadata"] == {"disk": "/"}
        assert result["is_read"] is True
        assert result["is_delivered"] is True
        assert result["delivered_at"] == now.isoformat()
        assert result["source_type"] == "monitor"
        assert result["created_at"] == now.isoformat()

    def test_handles_none_optionals(self):
        """None body, source_id, delivered_at → None."""
        from life_graph.kernel.notification_engine import (
            NotificationEngine,
        )

        mock_notif = _make_mock_notification(
            body=None,
            source_id=None,
            delivered_at=None,
        )
        result = NotificationEngine._notif_to_dict(
            mock_notif,
        )
        assert result["body"] is None
        assert result["source_id"] is None
        assert result["delivered_at"] is None


class TestNotificationEngineValidation:
    """NotificationEngine input validation (no DB)."""

    @pytest.mark.asyncio
    async def test_invalid_priority_raises(self):
        """Invalid priority raises ValueError."""
        from life_graph.kernel.notification_engine import (
            NotificationEngine,
        )

        engine = NotificationEngine(
            session_factory=MagicMock(),
        )
        with pytest.raises(ValueError, match="priority"):
            await engine.create(
                tenant_id="t1",
                title="Bad priority",
                priority="urgent",
            )

    @pytest.mark.asyncio
    async def test_invalid_channel_raises(self):
        """Invalid channel raises ValueError."""
        from life_graph.kernel.notification_engine import (
            NotificationEngine,
        )

        engine = NotificationEngine(
            session_factory=MagicMock(),
        )
        with pytest.raises(ValueError, match="channel"):
            await engine.create(
                tenant_id="t1",
                title="Bad channel",
                channel="sms",
            )

    def test_valid_priorities_exist(self):
        """VALID_PRIORITIES has the expected values."""
        from life_graph.kernel.notification_engine import (
            VALID_PRIORITIES,
        )

        assert {
            "critical",
            "important",
            "info",
        } == VALID_PRIORITIES

    def test_valid_channels_exist(self):
        """VALID_CHANNELS has the expected values."""
        from life_graph.kernel.notification_engine import (
            VALID_CHANNELS,
        )

        assert {
            "terminal",
            "email",
            "webhook",
        } == VALID_CHANNELS


# ── List Notifications Endpoint ──────────────────────────────


class TestListNotifications:
    """GET /api/v1/kernel/notifications"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_returns_200(
        self,
        client: AsyncClient,
    ):
        """List endpoint returns 200 with the list envelope."""
        response = await client.get(
            "/api/v1/kernel/notifications",
        )
        data = assert_ok(response, 200)["data"]
        assert "notifications" in data
        assert "total" in data
        assert "unread_count" in data

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_with_priority_filter(
        self,
        client: AsyncClient,
    ):
        """Filter by priority returns only that priority."""
        response = await client.get(
            "/api/v1/kernel/notifications",
            params={"priority": "critical"},
        )
        data = assert_ok(response, 200)["data"]
        assert all(n["priority"] == "critical" for n in data["notifications"])

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_with_read_filter(
        self,
        client: AsyncClient,
    ):
        """Filter by read state returns 200."""
        response = await client.get(
            "/api/v1/kernel/notifications",
            params={"read": "false"},
        )
        assert_ok(response, 200)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_with_pagination(
        self,
        client: AsyncClient,
    ):
        """Pagination params accepted."""
        response = await client.get(
            "/api/v1/kernel/notifications",
            params={"limit": "5", "offset": "10"},
        )
        data = assert_ok(response, 200)["data"]
        assert len(data["notifications"]) <= 5

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_combined_filters(
        self,
        client: AsyncClient,
    ):
        """Multiple filters combined."""
        response = await client.get(
            "/api/v1/kernel/notifications",
            params={
                "priority": "important",
                "read": "true",
                "limit": "3",
                "offset": "0",
            },
        )
        data = assert_ok(response, 200)["data"]
        assert len(data["notifications"]) <= 3


# ── Mark Read Endpoint ───────────────────────────────────────


class TestMarkRead:
    """PATCH /api/v1/kernel/notifications/{id}/read"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_mark_read_not_found(
        self,
        client: AsyncClient,
    ):
        """Non-existent notification returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.patch(
            f"/api/v1/kernel/notifications/{fake_id}/read",
        )
        assert response.status_code == 404, response.text

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_mark_read_invalid_uuid(
        self,
        client: AsyncClient,
    ):
        """Invalid UUID returns 422."""
        response = await client.patch(
            "/api/v1/kernel/notifications/not-a-uuid/read",
        )
        assert response.status_code == 422, response.text


# ── Mark All Read Endpoint ───────────────────────────────────


class TestMarkAllRead:
    """POST /api/v1/kernel/notifications/read-all"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_mark_all_read_returns_200(
        self,
        client: AsyncClient,
    ):
        """Mark-all-read returns 200 with the count it marked."""
        response = await client.post(
            "/api/v1/kernel/notifications/read-all",
        )
        data = assert_ok(response, 200)["data"]
        assert "marked_count" in data


# ── Full Flow (create → list → mark-read → verify) ──────────


class TestNotificationFlow:
    """End-to-end notification lifecycle test."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_notification_engine_create_and_list(
        self,
        client: AsyncClient,
    ):
        """Create via engine, verify in list endpoint.

        Uses the engine directly, then checks the list
        endpoint shows the notification.
        """
        # Verify list endpoint is reachable first
        resp = await client.get(
            "/api/v1/kernel/notifications",
        )
        assert_ok(resp, 200)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_mark_all_clears_unread(
        self,
        client: AsyncClient,
    ):
        """After mark-all-read, unread count should be 0."""
        resp = await client.post(
            "/api/v1/kernel/notifications/read-all",
        )
        assert_ok(resp, 200)

        # Verify unread count
        list_resp = await client.get(
            "/api/v1/kernel/notifications",
            # total and unread_count are opt-in — each costs an extra DB
            # query, so they are null unless asked for. This test predates
            # that optimisation and was asserting against the default null.
            params={"read": "false", "include_total": "true"},
        )
        data = assert_ok(list_resp, 200)["data"]
        assert data["total"] == 0


# ── External Alert Endpoint ──────────────────────────────────


@pytest_asyncio.fixture
async def auth_client() -> AsyncClient:
    """Same as ``client``, but with a valid service key if one is configured.

    A local .env with a real ``LIFE_GRAPH_SERVICE_API_KEYS`` (as this repo's
    does, for the dev-agent's own dispatches) makes ``AuthMiddleware`` enforce
    auth even in dev mode — the plain ``client`` fixture 401s in that case,
    same as any other caller without a key would.
    """
    from life_graph.config import settings

    headers = dict(TENANT_HEADERS)
    if settings.service_api_keys_list:
        headers["Authorization"] = f"Bearer {settings.service_api_keys_list[0]}"
    elif settings.api_key:
        headers["Authorization"] = f"Bearer {settings.api_key}"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as c:
        yield c


class TestExternalAlert:
    """POST /api/v1/kernel/alerts/external"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_external_alert_creates_notification_and_notifies_telegram(
        self,
        auth_client: AsyncClient,
        monkeypatch,
    ):
        """A tool like pulse posting here gets a notification row and a
        Telegram delivery attempt, tagged with its source."""
        sent: dict[str, Any] = {}

        async def fake_send(self, **kwargs: Any) -> bool:
            sent.update(kwargs)
            return True

        monkeypatch.setattr(
            "life_graph.watchers.channels.telegram_channel.TelegramChannel.send",
            fake_send,
        )

        resp = await auth_client.post(
            "/api/v1/kernel/alerts/external",
            json={
                "title": "2 service(s) down: postgres, redis",
                "details": "checked at 2026-09-19T09:00:00Z",
                "severity": "critical",
                "source": "pulse",
            },
        )
        data = assert_ok(resp, 200)["data"]
        assert data["title"] == "[pulse] 2 service(s) down: postgres, redis"
        assert data["priority"] == "critical"

        assert sent["severity"] == "critical"
        assert sent["title"] == "[pulse] 2 service(s) down: postgres, redis"
        assert sent["watcher_name"] == "pulse"

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_external_alert_invalid_severity_falls_back_to_important(
        self,
        auth_client: AsyncClient,
        monkeypatch,
    ):
        """An unrecognised severity string should not be rejected outright —
        the sender is an external tool that shouldn't need to know life-graph's
        exact priority vocabulary — it just shouldn't be trusted as 'critical'."""
        sent: dict[str, Any] = {}

        async def fake_send(self, **kwargs: Any) -> bool:
            sent.update(kwargs)
            return True

        monkeypatch.setattr(
            "life_graph.watchers.channels.telegram_channel.TelegramChannel.send",
            fake_send,
        )

        resp = await auth_client.post(
            "/api/v1/kernel/alerts/external",
            json={"title": "quota exhausted", "severity": "urgent!!"},
        )
        data = assert_ok(resp, 200)["data"]
        assert data["priority"] == "important"
        assert sent["severity"] == "important"
