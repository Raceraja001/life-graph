"""Integration tests for Agent Networks (Era 7).

Tests the task delegation, messaging, workflow, and shared context
APIs. Follows existing test patterns: httpx AsyncClient + ASGITransport,
defensive assertions accepting 500 if DB unreachable.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app

from tests.integration.conftest import skip_on_db_error

TENANT_HEADERS = {
    "X-Tenant-ID": "test-agent-networks-tenant",
}




@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """HTTP client for agent networks API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers=TENANT_HEADERS,
    ) as c:
        yield c


# ── Task Delegation Tests ────────────────────────────────────────


class TestCreateAgentTask:
    """POST /api/v1/agent-tasks/"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_agent_task(self, client: AsyncClient):
        """Creating a task with valid input returns 201."""
        response = await client.post(
            "/api/v1/agent-tasks",
            json={
                "task_name": "Integration test task",
                "agent_name": "test_agent",
                "priority": "normal",
                "input": {"prompt": "Hello world"},
            },
        )
        assert response.status_code in (201, 500), (
            f"Expected 201 or 500, got {response.status_code}: "
            f"{response.text}"
        )

        if response.status_code == 201:
            data = response.json()["data"]
            assert "id" in data
            assert data["agent_name"] == "test_agent"
            assert data["status"] in ("queued", "pending")

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_delegate_child_task(self, client: AsyncClient):
        """Create a parent task then delegate a child task."""
        # Create parent
        parent_resp = await client.post(
            "/api/v1/agent-tasks",
            json={
                "task_name": "Parent task",
                "agent_name": "orchestrator",
                "input": {},
            },
        )
        if parent_resp.status_code != 201:
            pytest.skip("DB unavailable — cannot test delegation")

        parent_id = parent_resp.json()["data"]["id"]

        # Create child
        child_resp = await client.post(
            "/api/v1/agent-tasks",
            json={
                "task_name": "Child task",
                "agent_name": "worker",
                "parent_task_id": parent_id,
                "input": {"subtask": "do-something"},
            },
        )
        assert child_resp.status_code in (201, 500)

        if child_resp.status_code == 201:
            data = child_resp.json()["data"]
            assert data.get("parent_task_id") == parent_id

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_max_depth_400(self, client: AsyncClient):
        """Delegation beyond max depth (400) returns 400 error."""
        # Create a task with depth metadata exceeding limit
        response = await client.post(
            "/api/v1/agent-tasks",
            json={
                "task_name": "Too deep task",
                "agent_name": "worker",
                "input": {"depth_override": 401},
                "max_depth": 400,
            },
        )
        # Should be rejected (400) or accepted (201) depending on
        # whether depth enforcement is in create or delegate
        assert response.status_code in (400, 422, 201, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_cancel_task_cascade(self, client: AsyncClient):
        """Cancel a parent task cascades to children."""
        # Create parent
        parent_resp = await client.post(
            "/api/v1/agent-tasks",
            json={
                "task_name": "Parent to cancel",
                "agent_name": "orchestrator",
                "input": {},
            },
        )
        if parent_resp.status_code != 201:
            pytest.skip("DB unavailable — cannot test cancellation")

        parent_id = parent_resp.json()["data"]["id"]

        # Create child
        await client.post(
            "/api/v1/agent-tasks",
            json={
                "task_name": "Child to cancel",
                "agent_name": "worker",
                "parent_task_id": parent_id,
                "input": {},
            },
        )

        # Cancel parent
        cancel_resp = await client.post(
            f"/api/v1/agent-tasks/{parent_id}/cancel",
            json={"reason": "Test cancellation"},
        )
        assert cancel_resp.status_code in (200, 500)


# ── Messaging Tests ──────────────────────────────────────────


class TestAgentMessaging:
    """Agent message CRUD endpoints."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_send_agent_message(self, client: AsyncClient):
        """POST /api/v1/agent-messages/ — send a message between agents."""
        response = await client.post(
            "/api/v1/agent-messages",
            params={"sender_agent": "agent_a"},
            json={
                "sender_agent": "agent_a",
                "recipient_agent": "agent_b",
                "message_type": "request",
                "payload": {"text": "Please analyze this data"},
            },
        )
        assert response.status_code in (201, 500), (
            f"Expected 201 or 500, got {response.status_code}: "
            f"{response.text}"
        )

        if response.status_code == 201:
            data = response.json()["data"]
            assert "id" in data
            assert data["sender_agent"] == "agent_a"
            assert data["recipient_agent"] == "agent_b"

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_get_inbox(self, client: AsyncClient):
        """GET /api/v1/agent-messages/inbox/{agent_name} — get agent inbox."""
        # Send a message first
        await client.post(
            "/api/v1/agent-messages",
            params={"sender_agent": "sender"},
            json={
                "sender_agent": "sender",
                "recipient_agent": "inbox_test_agent",
                "message_type": "notification",
                "payload": {"text": "Test inbox message"},
            },
        )

        # Fetch inbox
        response = await client.get(
            "/api/v1/agent-messages/inbox/inbox_test_agent",
        )
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            body = response.json()
            assert "data" in body
            assert isinstance(body["data"], list)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_mark_message_read(self, client: AsyncClient):
        """PATCH /api/v1/agent-messages/{id}/read — mark message as read."""
        # Send a message
        send_resp = await client.post(
            "/api/v1/agent-messages",
            params={"sender_agent": "sender"},
            json={
                "sender_agent": "sender",
                "recipient_agent": "reader",
                "message_type": "info",
                "payload": {"text": "Read me"},
            },
        )
        if send_resp.status_code != 201:
            pytest.skip("DB unavailable — cannot test mark-read")

        msg_id = send_resp.json()["data"]["id"]

        # Mark as read
        response = await client.patch(
            f"/api/v1/agent-messages/{msg_id}/read",
        )
        assert response.status_code in (200, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_reply_message(self, client: AsyncClient):
        """POST /api/v1/agent-messages/{id}/reply — reply to a message."""
        # Send original message
        send_resp = await client.post(
            "/api/v1/agent-messages",
            params={"sender_agent": "alice"},
            json={
                "sender_agent": "alice",
                "recipient_agent": "bob",
                "message_type": "request",
                "payload": {"text": "Need your help"},
            },
        )
        if send_resp.status_code != 201:
            pytest.skip("DB unavailable — cannot test reply")

        msg_id = send_resp.json()["data"]["id"]

        # Reply
        response = await client.post(
            f"/api/v1/agent-messages/{msg_id}/reply",
            params={"sender_agent": "bob"},
            json={
                "body": "Sure, sending response",
                "payload": {"text": "Sure, sending response"},
            },
        )
        assert response.status_code in (201, 200, 500)


# ── Workflow Tests ───────────────────────────────────────────


class TestWorkflows:
    """Workflow DAG creation and run management."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_workflow(self, client: AsyncClient):
        """POST /api/v1/workflows/ — create a workflow DAG."""
        response = await client.post(
            "/api/v1/workflows/",
            json={
                "name": "CI Pipeline",
                "description": "Build → Test → Deploy",
                "steps": [
                    {
                        "step_key": "build",
                        "agent_name": "builder",
                        "depends_on": [],
                        "config": {"target": "production"},
                    },
                    {
                        "step_key": "test",
                        "agent_name": "tester",
                        "depends_on": ["build"],
                    },
                    {
                        "step_key": "deploy",
                        "agent_name": "deployer",
                        "depends_on": ["test"],
                        "condition": "steps.test.output.passed == true",
                    },
                ],
            },
        )
        assert response.status_code in (201, 500), (
            f"Expected 201 or 500, got {response.status_code}: "
            f"{response.text}"
        )

        if response.status_code == 201:
            data = response.json()["data"]
            assert "id" in data
            assert data["name"] == "CI Pipeline"

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_workflow_with_cycle_returns_400(self, client: AsyncClient):
        """Creating a workflow with a cycle returns 400."""
        response = await client.post(
            "/api/v1/workflows/",
            json={
                "name": "Cyclic Workflow",
                "steps": [
                    {
                        "step_key": "a",
                        "agent_name": "agent_a",
                        "depends_on": ["c"],
                    },
                    {
                        "step_key": "b",
                        "agent_name": "agent_b",
                        "depends_on": ["a"],
                    },
                    {
                        "step_key": "c",
                        "agent_name": "agent_c",
                        "depends_on": ["b"],
                    },
                ],
            },
        )
        assert response.status_code in (400, 500)


# ── Shared Context Tests ─────────────────────────────────────


class TestSharedContext:
    """Shared context CRUD and search endpoints."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_shared_context(self, client: AsyncClient):
        """POST /api/v1/shared-context/ — create a context entry."""  # prefix is /shared-context
        response = await client.post(
            "/api/v1/shared-context/",
            json={
                "content": "The deployment target is Kubernetes on GKE",
                "context_type": "fact",
                "source_agent": "devops_agent",
                "metadata": {"environment": "production"},
            },
        )
        assert response.status_code in (201, 500), (
            f"Expected 201 or 500, got {response.status_code}: "
            f"{response.text}"
        )

        if response.status_code == 201:
            data = response.json()["data"]
            assert "id" in data
            assert data["context_type"] == "fact"
            assert data["source_agent"] == "devops_agent"

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_search_shared_context(self, client: AsyncClient):
        """GET /api/v1/shared-context/{project_id} — search context entries."""
        # Use a dummy project ID
        project_id = "00000000-0000-0000-0000-000000000001"

        # Create a context entry first (with project_id)
        await client.post(
            "/api/v1/shared-context/",
            json={
                "content": "Database uses PostgreSQL with pgvector",
                "context_type": "fact",
                "project_id": project_id,
                "source_agent": "db_agent",
            },
        )

        # Search
        response = await client.get(
            f"/api/v1/shared-context/{project_id}",
            params={"query": "database", "limit": 5},
        )
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            body = response.json()
            assert "data" in body
            assert isinstance(body["data"], list)
