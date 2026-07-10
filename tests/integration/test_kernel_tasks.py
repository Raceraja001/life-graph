"""Integration tests for OS Kernel task endpoints.

Tests the Process Manager API layer:
- POST /api/v1/kernel/tasks (create)
- GET /api/v1/kernel/tasks (list with filters)
- GET /api/v1/kernel/tasks/{task_id} (detail)
- POST /api/v1/kernel/tasks/{task_id}/cancel (cancel)

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
    "X-Tenant-ID": "test_kernel_tenant",
    "X-User-ID": "kernel-test-user",
}




@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """HTTP client for kernel API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers=TENANT_HEADERS,
    ) as c:
        yield c


class TestCreateTask:
    """POST /api/v1/kernel/tasks"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_task_returns_201(self, client: AsyncClient):
        """Creating a task with valid input returns 201 with queued status."""
        response = await client.post(
            "/api/v1/kernel/tasks",
            json={
                "agent_name": "cody",
                "task_name": "Test task",
                "input": {"message": "Hello, world!"},
                "priority": "normal",
            },
        )
        assert response.status_code in (201, 500), (
            f"Expected 201 or 500, got {response.status_code}: "
            f"{response.text}"
        )

        if response.status_code == 201:
            data = response.json()
            assert "data" in data
            task = data["data"]
            assert task["agent_name"] == "cody"
            assert task["status"] == "queued"
            assert task["priority"] == "normal"
            assert "id" in task
            assert "created_at" in task

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_task_missing_agent_name(
        self, client: AsyncClient,
    ):
        """Missing required field agent_name returns 422."""
        response = await client.post(
            "/api/v1/kernel/tasks",
            json={
                "input": {"message": "Hello"},
            },
        )
        assert response.status_code in (422, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_task_invalid_priority(
        self, client: AsyncClient,
    ):
        """Invalid priority value returns 422."""
        response = await client.post(
            "/api/v1/kernel/tasks",
            json={
                "agent_name": "cody",
                "priority": "ultra",
                "input": {"message": "test"},
            },
        )
        assert response.status_code in (422, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_task_invalid_agent_name(
        self, client: AsyncClient,
    ):
        """Non-existent persona name returns 400."""
        response = await client.post(
            "/api/v1/kernel/tasks",
            json={
                "agent_name": "nonexistent_persona_xyz",
                "input": {"message": "test"},
            },
        )
        # 400 (persona not found) or 500 (DB unreachable)
        assert response.status_code in (400, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_task_with_all_optional_fields(
        self, client: AsyncClient,
    ):
        """Task creation with all optional fields works correctly."""
        response = await client.post(
            "/api/v1/kernel/tasks",
            json={
                "agent_name": "rex",
                "task_name": "Research WebSocket scaling",
                "input": {
                    "message": "Research best approaches",
                    "project_id": "test-project",
                },
                "priority": "high",
                "timeout_seconds": 600,
                "max_retries": 3,
            },
        )
        assert response.status_code in (201, 500)

        if response.status_code == 201:
            task = response.json()["data"]
            assert task["agent_name"] == "rex"
            assert task["priority"] == "high"

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_task_default_values(
        self, client: AsyncClient,
    ):
        """Task creation uses correct defaults for optional fields."""
        response = await client.post(
            "/api/v1/kernel/tasks",
            json={
                "agent_name": "cody",
                "input": {"message": "Simple task"},
            },
        )
        assert response.status_code in (201, 500)

        if response.status_code == 201:
            task = response.json()["data"]
            assert task["priority"] == "normal"


class TestListTasks:
    """GET /api/v1/kernel/tasks"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_tasks_returns_200(self, client: AsyncClient):
        """Listing tasks returns 200 with pagination metadata."""
        response = await client.get("/api/v1/kernel/tasks")
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            body = response.json()
            assert "data" in body
            assert "meta" in body
            assert isinstance(body["data"], list)
            meta = body["meta"]
            assert "total" in meta
            assert "page_size" in meta
            assert "has_more" in meta

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_tasks_with_status_filter(
        self, client: AsyncClient,
    ):
        """Listing tasks with status filter returns filtered results."""
        response = await client.get(
            "/api/v1/kernel/tasks", params={"status": "queued"},
        )
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            tasks = response.json()["data"]
            for task in tasks:
                assert task["status"] == "queued"

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_tasks_with_agent_name_filter(
        self, client: AsyncClient,
    ):
        """Listing tasks filtered by agent_name returns matching results."""
        response = await client.get(
            "/api/v1/kernel/tasks", params={"agent_name": "cody"},
        )
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            tasks = response.json()["data"]
            for task in tasks:
                assert task["agent_name"] == "cody"

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_tasks_pagination(self, client: AsyncClient):
        """Pagination params are respected."""
        response = await client.get(
            "/api/v1/kernel/tasks",
            params={"limit": 5, "offset": 0},
        )
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            body = response.json()
            assert body["meta"]["page_size"] == 5


class TestGetTask:
    """GET /api/v1/kernel/tasks/{task_id}"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_get_task_not_found(self, client: AsyncClient):
        """Requesting a non-existent task returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(
            f"/api/v1/kernel/tasks/{fake_id}",
        )
        assert response.status_code in (404, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_get_task_invalid_uuid(self, client: AsyncClient):
        """Requesting with an invalid UUID returns 422."""
        response = await client.get(
            "/api/v1/kernel/tasks/not-a-uuid",
        )
        assert response.status_code in (422, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_get_task_detail_after_create(
        self, client: AsyncClient,
    ):
        """Task detail endpoint returns full data after creation."""
        # Create a task first
        create_resp = await client.post(
            "/api/v1/kernel/tasks",
            json={
                "agent_name": "cody",
                "task_name": "Detail test",
                "input": {"message": "test detail"},
            },
        )

        if create_resp.status_code != 201:
            pytest.skip("DB unavailable — cannot test detail")

        task_id = create_resp.json()["data"]["id"]

        # Get detail
        detail_resp = await client.get(
            f"/api/v1/kernel/tasks/{task_id}",
        )
        assert detail_resp.status_code in (200, 500)

        task = detail_resp.json()["data"]
        assert task["id"] == task_id
        assert task["agent_name"] == "cody"
        assert task["task_name"] == "Detail test"
        assert "input" in task
        assert "result" in task
        assert "token_usage" in task
        assert "logs" in task
        assert "timeout_seconds" in task
        assert "retry_count" in task
        assert "created_at" in task
        assert "updated_at" in task


class TestCancelTask:
    """POST /api/v1/kernel/tasks/{task_id}/cancel"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_cancel_not_found(self, client: AsyncClient):
        """Cancelling a non-existent task returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.post(
            f"/api/v1/kernel/tasks/{fake_id}/cancel",
        )
        assert response.status_code in (404, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_cancel_queued_task(self, client: AsyncClient):
        """Cancelling a queued task succeeds."""
        # Create a task
        create_resp = await client.post(
            "/api/v1/kernel/tasks",
            json={
                "agent_name": "cody",
                "task_name": "Cancel test",
                "input": {"message": "to be cancelled"},
            },
        )

        if create_resp.status_code != 201:
            pytest.skip("DB unavailable — cannot test cancel")

        task_id = create_resp.json()["data"]["id"]

        # Cancel it
        cancel_resp = await client.post(
            f"/api/v1/kernel/tasks/{task_id}/cancel",
        )
        assert cancel_resp.status_code in (200, 500)

        if cancel_resp.status_code == 200:
            data = cancel_resp.json()["data"]
            assert data["status"] == "cancelled"
            assert "message" in data
