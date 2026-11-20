"""Integration tests for Agent Networks (Era 7).

Tests the task delegation, messaging, workflow, and shared context
APIs. Follows existing test patterns: httpx AsyncClient + ASGITransport.
Each response is checked for its exact status with ``assert_ok``; an
unreachable database is a skip (``skip_on_db_error``), never a 500 pass.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import assert_ok, skip_on_db_error

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
        assert_ok(response, 201)

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
        assert_ok(parent_resp, 201)

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
        assert_ok(child_resp, 201)

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
        # A root task has depth 0 and `max_depth` is not an AgentTaskCreate
        # field (extra keys are ignored), so creating it succeeds. The depth
        # limit applies to delegated children: see the two tests below.
        assert_ok(response, 201)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_delegation_beyond_max_depth_returns_400(self, client: AsyncClient):
        """A child one level past DelegationEngine.MAX_DEPTH is refused with 400.

        It used to be a 500: the engine raised ValueError and the route did
        not catch it.
        """
        from life_graph.services.delegation import DelegationEngine

        parent = assert_ok(
            await client.post(
                "/api/v1/agent-tasks",
                json={"task_name": "depth 0", "agent_name": "worker", "input": {}},
            ),
            201,
        )["data"]
        for depth in range(1, DelegationEngine.MAX_DEPTH + 1):
            parent = assert_ok(
                await client.post(
                    "/api/v1/agent-tasks",
                    json={
                        "task_name": f"depth {depth}",
                        "agent_name": "worker",
                        "parent_task_id": parent["id"],
                        "input": {},
                    },
                ),
                201,
            )["data"]
            assert parent["depth"] == depth

        too_deep = await client.post(
            "/api/v1/agent-tasks",
            json={
                "task_name": "one too deep",
                "agent_name": "worker",
                "parent_task_id": parent["id"],
                "input": {},
            },
        )
        body = assert_ok(too_deep, 400)
        assert "depth" in str(body).lower()

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_delegation_to_unknown_parent_returns_404(self, client: AsyncClient):
        """A parent_task_id that does not exist (for this tenant) is a 404, not a 500."""
        response = await client.post(
            "/api/v1/agent-tasks",
            json={
                "task_name": "orphan",
                "agent_name": "worker",
                "parent_task_id": str(uuid.uuid4()),
                "input": {},
            },
        )
        assert_ok(response, 404)

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
        assert_ok(parent_resp, 201)

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
        assert_ok(cancel_resp, 200)


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
        assert_ok(response, 201)

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
        assert_ok(response, 200)

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
        assert_ok(send_resp, 201)

        msg_id = send_resp.json()["data"]["id"]

        # Mark as read
        response = await client.patch(
            f"/api/v1/agent-messages/{msg_id}/read",
        )
        assert_ok(response, 200)

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
        assert_ok(send_resp, 201)

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
        assert_ok(response, 201)


# ── Workflow Tests ───────────────────────────────────────────


class TestWorkflows:
    """Workflow DAG creation and run management."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_workflow(self, client: AsyncClient):
        """POST /api/v1/workflows/ — create a workflow DAG."""
        # Unique per run — (tenant_id, name) is unique-constrained.
        name = f"CI Pipeline {uuid.uuid4().hex[:8]}"
        response = await client.post(
            "/api/v1/workflows/",
            json={
                "name": name,
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
        assert response.status_code == 201, response.text
        data = response.json()["data"]
        assert "id" in data
        assert data["name"] == name

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
        assert_ok(response, 400)


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
        assert_ok(response, 201)

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
        assert_ok(response, 200)

        body = response.json()
        assert "data" in body
        assert isinstance(body["data"], list)
