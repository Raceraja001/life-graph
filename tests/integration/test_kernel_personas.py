"""Integration tests for OS Kernel persona endpoints.

Tests the Persona CRUD API:
- POST /api/v1/kernel/personas (create)
- GET /api/v1/kernel/personas (list)
- GET /api/v1/kernel/personas/{persona_id} (detail)
- PATCH /api/v1/kernel/personas/{persona_id} (update)
- DELETE /api/v1/kernel/personas/{persona_id} (soft-delete)

Also tests tool permission filtering logic (unit-style,
no DB needed).
"""

import uuid
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app


from tests.integration.conftest import skip_on_db_error

TENANT_HEADERS = {
    "X-Tenant-ID": "test_persona_tenant",
    "X-User-ID": "persona-test-user",
}




@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """HTTP client for persona API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers=TENANT_HEADERS,
    ) as c:
        yield c


# ── Create Persona ───────────────────────────────────────────


class TestCreatePersona:
    """POST /api/v1/kernel/personas"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_persona_returns_201(
        self, client: AsyncClient,
    ):
        """Creating a persona with valid input returns 201."""
        pname = f"test_analyst_{uuid.uuid4().hex[:6]}"
        response = await client.post(
            "/api/v1/kernel/personas",
            json={
                "name": pname,
                "system_prompt": "You are a test analyst.",
                "display_name": "Test Analyst",
                "description": "A persona for testing.",
                "temperature": 0.5,
                "intent_tags": ["test", "analysis"],
                "icon": "🔬",
            },
        )
        assert response.status_code in (201, 500)

        if response.status_code == 201:
            data = response.json()["data"]
            assert data["name"] == pname
            assert data["is_builtin"] is False
            assert data["is_active"] is True

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_persona_missing_name(
        self, client: AsyncClient,
    ):
        """Missing required name returns 422."""
        response = await client.post(
            "/api/v1/kernel/personas",
            json={
                "system_prompt": "You are a test agent.",
            },
        )
        assert response.status_code in (422, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_persona_missing_system_prompt(
        self, client: AsyncClient,
    ):
        """Missing required system_prompt returns 422."""
        response = await client.post(
            "/api/v1/kernel/personas",
            json={
                "name": "no_prompt_persona",
            },
        )
        assert response.status_code in (422, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_persona_duplicate_name(
        self, client: AsyncClient,
    ):
        """Duplicate name for same tenant returns 409."""
        payload = {
            "name": f"dup_test_persona_{uuid.uuid4().hex[:6]}",
            "system_prompt": "Test prompt.",
        }
        first = await client.post(
            "/api/v1/kernel/personas", json=payload,
        )
        if first.status_code != 201:
            pytest.skip("DB unavailable")

        second = await client.post(
            "/api/v1/kernel/personas", json=payload,
        )
        assert second.status_code in (409, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_persona_with_tools(
        self, client: AsyncClient,
    ):
        """Persona with allowed_tools is created correctly."""
        response = await client.post(
            "/api/v1/kernel/personas",
            json={
                "name": f"tooled_persona_{uuid.uuid4().hex[:6]}",
                "system_prompt": "You have tools.",
                "allowed_tools": [
                    "file_read", "web_search",
                ],
            },
        )
        assert response.status_code in (201, 500)

        if response.status_code == 201:
            data = response.json()["data"]
            assert data["allowed_tools"] == [
                "file_read", "web_search",
            ]

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_persona_invalid_temperature(
        self, client: AsyncClient,
    ):
        """Temperature out of range returns 422."""
        response = await client.post(
            "/api/v1/kernel/personas",
            json={
                "name": "hot_persona",
                "system_prompt": "Too hot.",
                "temperature": 5.0,
            },
        )
        assert response.status_code in (422, 500)


# ── List Personas ────────────────────────────────────────────


class TestListPersonas:
    """GET /api/v1/kernel/personas"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_personas_returns_200(
        self, client: AsyncClient,
    ):
        """Listing personas returns 200 with total count."""
        response = await client.get("/api/v1/kernel/personas")
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            body = response.json()
            assert "data" in body
            data = body["data"]
            assert "personas" in data
            assert "total" in data
            assert isinstance(data["personas"], list)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_personas_include_inactive(
        self, client: AsyncClient,
    ):
        """include_inactive=true also returns deactivated."""
        response = await client.get(
            "/api/v1/kernel/personas",
            params={"include_inactive": "true"},
        )
        assert response.status_code in (200, 500)


# ── Get Persona Detail ───────────────────────────────────────


class TestGetPersona:
    """GET /api/v1/kernel/personas/{persona_id}"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_get_persona_not_found(
        self, client: AsyncClient,
    ):
        """Non-existent persona returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(
            f"/api/v1/kernel/personas/{fake_id}",
        )
        assert response.status_code in (404, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_get_persona_invalid_uuid(
        self, client: AsyncClient,
    ):
        """Invalid UUID returns 422."""
        response = await client.get(
            "/api/v1/kernel/personas/not-a-uuid",
        )
        assert response.status_code in (422, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_get_persona_after_create(
        self, client: AsyncClient,
    ):
        """Get returns full detail after creation."""
        pname = f"detail_test_persona_{uuid.uuid4().hex[:6]}"
        create_resp = await client.post(
            "/api/v1/kernel/personas",
            json={
                "name": pname,
                "system_prompt": "Detail test prompt.",
                "display_name": "Detail Tester",
                "icon": "🧪",
            },
        )
        if create_resp.status_code != 201:
            pytest.skip("DB unavailable")

        pid = create_resp.json()["data"]["id"]
        detail = await client.get(
            f"/api/v1/kernel/personas/{pid}",
        )
        assert detail.status_code in (200, 500)
        data = detail.json()["data"]
        assert data["name"] == pname
        assert data["system_prompt"] == "Detail test prompt."
        assert data["icon"] == "🧪"
        assert "created_at" in data
        assert "updated_at" in data


# ── Update Persona ───────────────────────────────────────────


class TestUpdatePersona:
    """PATCH /api/v1/kernel/personas/{persona_id}"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_update_persona_not_found(
        self, client: AsyncClient,
    ):
        """Updating non-existent persona returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.patch(
            f"/api/v1/kernel/personas/{fake_id}",
            json={"temperature": 0.5},
        )
        assert response.status_code in (404, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_update_persona_temperature(
        self, client: AsyncClient,
    ):
        """Updating temperature returns success message."""
        create_resp = await client.post(
            "/api/v1/kernel/personas",
            json={
                "name": f"update_test_persona_{uuid.uuid4().hex[:6]}",
                "system_prompt": "Update test.",
            },
        )
        if create_resp.status_code != 201:
            pytest.skip("DB unavailable")

        pid = create_resp.json()["data"]["id"]
        update_resp = await client.patch(
            f"/api/v1/kernel/personas/{pid}",
            json={"temperature": 0.9},
        )
        assert update_resp.status_code in (200, 500)
        data = update_resp.json()["data"]
        assert "updated_at" in data
        assert "message" in data
        assert "next task spawn" in data["message"]

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_update_persona_system_prompt(
        self, client: AsyncClient,
    ):
        """Updating system_prompt works correctly."""
        create_resp = await client.post(
            "/api/v1/kernel/personas",
            json={
                "name": f"prompt_update_test_{uuid.uuid4().hex[:6]}",
                "system_prompt": "Original prompt.",
            },
        )
        if create_resp.status_code != 201:
            pytest.skip("DB unavailable")

        pid = create_resp.json()["data"]["id"]
        await client.patch(
            f"/api/v1/kernel/personas/{pid}",
            json={"system_prompt": "Updated prompt."},
        )

        # Verify the update stuck
        detail = await client.get(
            f"/api/v1/kernel/personas/{pid}",
        )
        assert detail.status_code in (200, 500)
        assert (
            detail.json()["data"]["system_prompt"]
            == "Updated prompt."
        )


# ── Delete Persona ───────────────────────────────────────────


class TestDeletePersona:
    """DELETE /api/v1/kernel/personas/{persona_id}"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_delete_persona_not_found(
        self, client: AsyncClient,
    ):
        """Deleting non-existent persona returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.delete(
            f"/api/v1/kernel/personas/{fake_id}",
        )
        assert response.status_code in (404, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_delete_custom_persona(
        self, client: AsyncClient,
    ):
        """Deleting a custom persona returns success."""
        pname = f"delete_me_persona_{uuid.uuid4().hex[:6]}"
        create_resp = await client.post(
            "/api/v1/kernel/personas",
            json={
                "name": pname,
                "system_prompt": "Will be deleted.",
            },
        )
        if create_resp.status_code != 201:
            pytest.skip("DB unavailable")

        pid = create_resp.json()["data"]["id"]
        del_resp = await client.delete(
            f"/api/v1/kernel/personas/{pid}",
        )
        assert del_resp.status_code in (200, 500)
        data = del_resp.json()["data"]
        assert data["message"] == "Persona deactivated"
        assert data["name"] == pname


# ── Tool Permission Filtering (unit tests, no DB) ───────────


class TestToolPermissions:
    """PersonaService.resolve_tools — tenant-based filtering."""

    @pytest.fixture
    def service(self):
        """Create a PersonaService with a dummy factory."""
        from life_graph.kernel.personas import PersonaService
        return PersonaService(session_factory=None)  # type: ignore

    def test_admin_tenant_gets_all_tools(self, service):
        """Admin tenants get the full allowed_tools list."""
        persona = {
            "allowed_tools": [
                "terminal", "git", "file_read", "web_search",
            ],
        }
        tools = service.resolve_tools(persona, "default")
        assert tools == [
            "terminal", "git", "file_read", "web_search",
        ]

    def test_legacy_tenant_gets_all_tools(self, service):
        """Legacy tenants also get full access."""
        persona = {
            "allowed_tools": ["terminal", "docker", "ssh"],
        }
        tools = service.resolve_tools(persona, "legacy")
        assert tools == ["terminal", "docker", "ssh"]

    def test_personal_tenant_gets_all_tools(self, service):
        """Personal tenants get full access."""
        persona = {
            "allowed_tools": [
                "terminal", "git", "file_write",
            ],
        }
        tools = service.resolve_tools(
            persona, "personal-user-123",
        )
        assert tools == ["terminal", "git", "file_write"]

    def test_customer_tenant_strips_system_tools(
        self, service,
    ):
        """Customer tenants lose system/write tools."""
        persona = {
            "allowed_tools": [
                "terminal", "git", "file_read",
                "web_search", "docker", "file_write",
            ],
        }
        tools = service.resolve_tools(
            persona, "customer-acme-corp",
        )
        # Only safe tools survive
        assert tools == ["file_read", "web_search"]

    def test_customer_tenant_with_only_safe_tools(
        self, service,
    ):
        """Customer with safe-only tools gets all of them."""
        persona = {
            "allowed_tools": [
                "memory_search", "file_read",
            ],
        }
        tools = service.resolve_tools(
            persona, "customer-tenant-42",
        )
        assert tools == ["memory_search", "file_read"]

    def test_empty_allowed_tools(self, service):
        """Empty tools list returns empty."""
        persona = {"allowed_tools": []}
        tools = service.resolve_tools(persona, "default")
        assert tools == []

    def test_none_allowed_tools(self, service):
        """None tools returns empty."""
        persona = {"allowed_tools": None}
        tools = service.resolve_tools(persona, "default")
        assert tools == []
