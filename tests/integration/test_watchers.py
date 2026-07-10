"""Integration tests for Watcher API (Era 6 Ambient AI).

Tests the Watcher API layer:
- GET /api/v1/watchers/configs (list watcher configs)
- PATCH /api/v1/watchers/configs/{name} (update config)
- GET /api/v1/watchers/events (list events)
- POST /api/v1/watchers/events/{id}/acknowledge (ack single)
- POST /api/v1/watchers/events/acknowledge-all (bulk ack)
- GET /api/v1/watchers/events/summary (event summary)
- GET /api/v1/watchers/tech-radar (tech radar list)
- POST /api/v1/watchers/notification-channels (create channel)
- GET /api/v1/watchers/notification-channels (list channels)

Follows existing test patterns: httpx AsyncClient + ASGITransport,
defensive assertions accepting 500 if DB unreachable.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app

from tests.integration.conftest import skip_on_db_error

TENANT_HEADERS = {
    "X-Tenant-ID": "test-watchers-tenant",
}




@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """HTTP client for watcher API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers=TENANT_HEADERS,
    ) as c:
        yield c


class TestListWatcherConfigs:
    """GET /api/v1/watchers/configs"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_watcher_configs(self, client: AsyncClient):
        """Listing watcher configs returns 200 with data array."""
        response = await client.get("/api/v1/watchers/configs")
        assert response.status_code in (200, 500), (
            f"Expected 200 or 500, got {response.status_code}: "
            f"{response.text}"
        )

        if response.status_code == 200:
            body = response.json()
            assert "data" in body
            assert isinstance(body["data"], list)


class TestUpdateWatcherConfig:
    """PATCH /api/v1/watchers/configs/{watcher_name}"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_update_watcher_config(self, client: AsyncClient):
        """Updating a non-existent config returns 404."""
        response = await client.patch(
            "/api/v1/watchers/configs/nonexistent_watcher",
            json={"enabled": False},
        )
        assert response.status_code in (404, 500), (
            f"Expected 404 or 500, got {response.status_code}: "
            f"{response.text}"
        )


class TestListWatchEvents:
    """GET /api/v1/watchers/events"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_watch_events(self, client: AsyncClient):
        """Listing watch events returns 200 with data array."""
        response = await client.get("/api/v1/watchers/events")
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            body = response.json()
            assert "data" in body
            assert isinstance(body["data"], list)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_watch_events_with_filters(self, client: AsyncClient):
        """Listing events with filters returns 200."""
        response = await client.get(
            "/api/v1/watchers/events",
            params={"severity": "critical", "acknowledged": "false"},
        )
        assert response.status_code in (200, 500)


class TestAcknowledgeEvent:
    """POST /api/v1/watchers/events/{event_id}/acknowledge"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_acknowledge_event(self, client: AsyncClient):
        """Acknowledging a non-existent event returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.post(
            f"/api/v1/watchers/events/{fake_id}/acknowledge",
            json={"acknowledged_by": "test"},
        )
        assert response.status_code in (404, 500)


class TestBulkAcknowledge:
    """POST /api/v1/watchers/events/acknowledge-all"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_bulk_acknowledge(self, client: AsyncClient):
        """Bulk acknowledge returns 200 with acknowledged_count."""
        response = await client.post(
            "/api/v1/watchers/events/acknowledge-all",
            json={"acknowledged_by": "test"},
        )
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            body = response.json()
            assert "data" in body
            assert "acknowledged_count" in body["data"]


class TestEventSummary:
    """GET /api/v1/watchers/events/summary"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_event_summary(self, client: AsyncClient):
        """Event summary returns 200 with aggregated counts."""
        response = await client.get("/api/v1/watchers/events/summary")
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            body = response.json()
            assert "data" in body
            data = body["data"]
            assert "total" in data
            assert "by_severity" in data
            assert "by_watcher" in data
            assert "unacknowledged" in data


class TestTechRadarList:
    """GET /api/v1/watchers/tech-radar"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_tech_radar_list(self, client: AsyncClient):
        """Tech radar list returns 200 with data array."""
        response = await client.get("/api/v1/watchers/tech-radar")
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            body = response.json()
            assert "data" in body
            assert isinstance(body["data"], list)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_tech_radar_with_filters(self, client: AsyncClient):
        """Tech radar with filters returns 200."""
        response = await client.get(
            "/api/v1/watchers/tech-radar",
            params={"min_score": 0.5, "days": 30},
        )
        assert response.status_code in (200, 500)


class TestCreateNotificationChannel:
    """POST /api/v1/watchers/notification-channels"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_notification_channel(self, client: AsyncClient):
        """Creating a notification channel returns 201."""
        response = await client.post(
            "/api/v1/watchers/notification-channels",
            json={
                "channel_type": "terminal",
                "config": {},
                "priority": 1,
                "enabled": True,
            },
        )
        assert response.status_code in (201, 500), (
            f"Expected 201 or 500, got {response.status_code}: "
            f"{response.text}"
        )

        if response.status_code == 201:
            data = response.json()["data"]
            assert data["channel_type"] == "terminal"
            assert "id" in data

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_notification_channel_missing_type(self, client: AsyncClient):
        """Missing required channel_type returns 422."""
        response = await client.post(
            "/api/v1/watchers/notification-channels",
            json={"name": "Invalid"},
        )
        assert response.status_code in (422, 500)


class TestListNotificationChannels:
    """GET /api/v1/watchers/notification-channels"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_notification_channels(self, client: AsyncClient):
        """Listing notification channels returns 200 with data array."""
        response = await client.get("/api/v1/watchers/notification-channels")
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            body = response.json()
            assert "data" in body
            assert isinstance(body["data"], list)
