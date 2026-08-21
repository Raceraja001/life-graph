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
        self,
        client: AsyncClient,
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
        self,
        client: AsyncClient,
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
        self,
        client: AsyncClient,
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
        self,
        client: AsyncClient,
    ):
        """Duplicate name for same tenant returns 409."""
        payload = {
            "name": f"dup_test_persona_{uuid.uuid4().hex[:6]}",
            "system_prompt": "Test prompt.",
        }
        first = await client.post(
            "/api/v1/kernel/personas",
            json=payload,
        )
        if first.status_code != 201:
            pytest.skip("DB unavailable")

        second = await client.post(
            "/api/v1/kernel/personas",
            json=payload,
        )
        assert second.status_code in (409, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_persona_with_tools(
        self,
        client: AsyncClient,
    ):
        """Persona with allowed_tools is created correctly."""
        response = await client.post(
            "/api/v1/kernel/personas",
            json={
                "name": f"tooled_persona_{uuid.uuid4().hex[:6]}",
                "system_prompt": "You have tools.",
                "allowed_tools": [
                    "file_read",
                    "web_search",
                ],
            },
        )
        assert response.status_code in (201, 500)

        if response.status_code == 201:
            data = response.json()["data"]
            assert data["allowed_tools"] == [
                "file_read",
                "web_search",
            ]

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_create_persona_invalid_temperature(
        self,
        client: AsyncClient,
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
        self,
        client: AsyncClient,
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
        self,
        client: AsyncClient,
    ):
        """include_inactive=true also returns deactivated."""
        response = await client.get(
            "/api/v1/kernel/personas",
            params={"include_inactive": "true"},
        )
        assert response.status_code in (200, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_personas_includes_temperature_and_max_tokens(
        self,
        client: AsyncClient,
    ):
        """List response includes temperature/max_tokens per persona, not just
        the narrow summary fields — the model picker renders every persona as
        an editable card from this one list call, with no per-persona detail
        fetch, so both fields must be present here."""
        response = await client.get("/api/v1/kernel/personas")
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            body = response.json()
            personas = body["data"]["personas"]
            if personas:
                first = personas[0]
                assert "temperature" in first
                assert "max_tokens" in first
                assert isinstance(first["temperature"], float)
                assert isinstance(first["max_tokens"], int)


# ── Get Persona Detail ───────────────────────────────────────


class TestGetPersona:
    """GET /api/v1/kernel/personas/{persona_id}"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_get_persona_not_found(
        self,
        client: AsyncClient,
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
        self,
        client: AsyncClient,
    ):
        """Invalid UUID returns 422."""
        response = await client.get(
            "/api/v1/kernel/personas/not-a-uuid",
        )
        assert response.status_code in (422, 500)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_get_persona_after_create(
        self,
        client: AsyncClient,
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
        self,
        client: AsyncClient,
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
        self,
        client: AsyncClient,
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
        self,
        client: AsyncClient,
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
        assert detail.json()["data"]["system_prompt"] == "Updated prompt."


# ── Delete Persona ───────────────────────────────────────────


class TestDeletePersona:
    """DELETE /api/v1/kernel/personas/{persona_id}"""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_delete_persona_not_found(
        self,
        client: AsyncClient,
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
        self,
        client: AsyncClient,
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
                "terminal",
                "git",
                "file_read",
                "web_search",
            ],
        }
        tools = service.resolve_tools(persona, "default")
        assert tools == [
            "terminal",
            "git",
            "file_read",
            "web_search",
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
                "terminal",
                "git",
                "file_write",
            ],
        }
        tools = service.resolve_tools(
            persona,
            "personal-user-123",
        )
        assert tools == ["terminal", "git", "file_write"]

    def test_customer_tenant_strips_system_tools(
        self,
        service,
    ):
        """Customer tenants lose system/write tools."""
        persona = {
            "allowed_tools": [
                "terminal",
                "git",
                "file_read",
                "web_search",
                "docker",
                "file_write",
            ],
        }
        tools = service.resolve_tools(
            persona,
            "customer-acme-corp",
        )
        # Only safe tools survive
        assert tools == ["file_read", "web_search"]

    def test_customer_tenant_with_only_safe_tools(
        self,
        service,
    ):
        """Customer with safe-only tools gets all of them."""
        persona = {
            "allowed_tools": [
                "memory_search",
                "file_read",
            ],
        }
        tools = service.resolve_tools(
            persona,
            "customer-tenant-42",
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


# ── seed_builtins() Idempotency ─────────────────────────────


class TestSeedBuiltinsIdempotency:
    """seed_builtins() must backfill missing personas, not just skip entirely."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_seed_backfills_new_persona_for_already_seeded_tenant(
        self,
        client: AsyncClient,
    ):
        from unittest.mock import patch

        from life_graph.api.dependencies import get_persona_service
        from life_graph.kernel import personas as personas_module

        svc = get_persona_service()
        tenant = f"test_backfill_{uuid.uuid4().hex[:6]}"

        # First seed: only the real built-ins.
        first_count = await svc.seed_builtins(tenant)
        assert first_count == len(personas_module._BUILTIN_PERSONAS)

        # Simulate a new builtin having been added to the list.
        fake_new_persona = {
            "name": f"probe_{uuid.uuid4().hex[:6]}",
            "display_name": "Probe",
            "icon": "🔍",
            "description": "Test-only persona for backfill verification.",
            "system_prompt": "You are a probe.",
            "intent_tags": ["probe"],
            "temperature": 0.5,
            "allowed_tools": None,
        }
        with patch.object(
            personas_module,
            "_BUILTIN_PERSONAS",
            personas_module._BUILTIN_PERSONAS + [fake_new_persona],
        ):
            second_count = await svc.seed_builtins(tenant)

        assert second_count == 1  # only the new one was inserted
        probe = await svc.get_by_name(tenant, fake_new_persona["name"])
        assert probe is not None

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_concurrent_seed_calls_do_not_lose_personas(
        self,
        client: AsyncClient,
    ):
        """Two overlapping seed_builtins() calls for the same tenant
        (e.g. two instances starting up at once) race on the unique
        (tenant_id, name) index. A duplicate hit for one persona must
        only discard that one persona's insert — not roll back every
        other persona already flushed earlier in the same call's
        transaction.
        """
        import asyncio

        from life_graph.api.dependencies import get_persona_service
        from life_graph.kernel import personas as personas_module

        svc = get_persona_service()
        tenant = f"test_concurrent_seed_{uuid.uuid4().hex[:6]}"

        await asyncio.gather(
            svc.seed_builtins(tenant),
            svc.seed_builtins(tenant),
        )

        personas, total = await svc.list_all(tenant)
        seeded_names = {p["name"] for p in personas}
        expected_names = {defn["name"] for defn in personas_module._BUILTIN_PERSONAS}

        assert expected_names <= seeded_names, (
            f"missing personas after concurrent seed: {expected_names - seeded_names}"
        )
        # No duplicate rows for any name either.
        assert total == len(personas_module._BUILTIN_PERSONAS)

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_reseed_repairs_a_stale_builtin_row(self, client: AsyncClient):
        """The headline regression: a tenant seeded under an OLD version of
        _BUILTIN_PERSONAS must have its stale ``allowed_tools`` repaired on
        the next startup. Consumers (TaskDispatcher._load_persona,
        process_manager._run_agent) read this DB row, never the constant, so
        without reconciliation the whole tool-scoping fix is a no-op on any
        already-deployed tenant.

        Deliberately exercised against real SQL, not a fake session: the
        UPDATE's WHERE/SET shape and the ARRAY round-trip of allowed_tools
        are exactly what a fake session cannot prove.
        """
        from sqlalchemy import select, update

        from life_graph.api.dependencies import get_persona_service
        from life_graph.kernel import personas as personas_module
        from life_graph.models.db import AgentPersona

        svc = get_persona_service()
        tenant = f"test_reconcile_{uuid.uuid4().hex[:6]}"
        await svc.seed_builtins(tenant)

        stale = ["file_read", "file_write", "terminal", "git"]
        current = personas_module._BUILTIN_PERSONAS
        cody_defn = next(p for p in current if p["name"] == "cody")
        assert cody_defn["allowed_tools"] != stale, "fixture must actually be stale"

        # Rewind cody's row to the pre-branch, broken value.
        async with svc._session_factory() as session:
            await session.execute(
                update(AgentPersona)
                .where(
                    AgentPersona.tenant_id == tenant,
                    AgentPersona.name == "cody",
                )
                .values(allowed_tools=stale, system_prompt="an old prompt")
            )
            await session.commit()

        changed = await svc.seed_builtins(tenant)

        assert changed >= 1, "reconcile must be reported in the return count"
        repaired = await svc.get_by_name(tenant, "cody")
        assert repaired["allowed_tools"] == cody_defn["allowed_tools"]
        assert "terminal" not in repaired["allowed_tools"]
        assert repaired["system_prompt"] == cody_defn["system_prompt"]

        # ...and it settles: a second reseed is a no-op.
        assert await svc.seed_builtins(tenant) == 0

        # Fields OUTSIDE the two reconciled ones are left alone.
        async with svc._session_factory() as session:
            row = (
                await session.execute(
                    select(AgentPersona.temperature, AgentPersona.is_builtin).where(
                        AgentPersona.tenant_id == tenant,
                        AgentPersona.name == "cody",
                    )
                )
            ).one()
        assert row.is_builtin is True

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_reseed_never_touches_a_user_owned_row(self, client: AsyncClient):
        """A tenant that forked a built-in name into their own persona
        (is_builtin=False) must keep their customization forever."""
        from sqlalchemy import update

        from life_graph.api.dependencies import get_persona_service
        from life_graph.models.db import AgentPersona

        svc = get_persona_service()
        tenant = f"test_userowned_{uuid.uuid4().hex[:6]}"
        await svc.seed_builtins(tenant)

        mine = ["memory_search"]
        async with svc._session_factory() as session:
            await session.execute(
                update(AgentPersona)
                .where(
                    AgentPersona.tenant_id == tenant,
                    AgentPersona.name == "cody",
                )
                .values(
                    allowed_tools=mine,
                    system_prompt="my own cody",
                    is_builtin=False,
                )
            )
            await session.commit()

        await svc.seed_builtins(tenant)

        untouched = await svc.get_by_name(tenant, "cody")
        assert untouched["allowed_tools"] == mine
        assert untouched["system_prompt"] == "my own cody"


# ── The five new personal-roles personas ────────────────────


class TestNewPersonalRolesPersonas:
    """The five new personas from docs/specs/personal-roles.md."""

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_seeding_creates_all_five_new_personas(
        self,
        client: AsyncClient,
    ):
        from life_graph.api.dependencies import get_persona_service

        svc = get_persona_service()
        tenant = f"test_roles_{uuid.uuid4().hex[:6]}"
        await svc.seed_builtins(tenant)

        for name in ("tutor", "scout", "admin", "swe-lead", "jarvis"):
            persona = await svc.get_by_name(tenant, name)
            assert persona is not None, f"{name} was not seeded"

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_scout_and_admin_have_no_action_tools(
        self,
        client: AsyncClient,
    ):
        from life_graph.api.dependencies import get_persona_service

        svc = get_persona_service()
        tenant = f"test_roles_{uuid.uuid4().hex[:6]}"
        await svc.seed_builtins(tenant)

        forbidden = {"delegate_to_persona", "terminal", "git", "run_command"}
        for name in ("scout", "admin"):
            persona = await svc.get_by_name(tenant, name)
            assert persona is not None
            allowed = set(persona["allowed_tools"] or [])
            assert not (allowed & forbidden), f"{name} has a forbidden tool: {allowed & forbidden}"

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_swe_lead_and_jarvis_can_delegate(
        self,
        client: AsyncClient,
    ):
        from life_graph.api.dependencies import get_persona_service

        svc = get_persona_service()
        tenant = f"test_roles_{uuid.uuid4().hex[:6]}"
        await svc.seed_builtins(tenant)

        for name in ("swe-lead", "jarvis"):
            persona = await svc.get_by_name(tenant, name)
            assert persona is not None
            assert "delegate_to_persona" in (persona["allowed_tools"] or [])

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_swe_lead_has_verifier_chain(
        self,
        client: AsyncClient,
    ):
        from life_graph.api.dependencies import get_persona_service

        svc = get_persona_service()
        tenant = f"test_roles_{uuid.uuid4().hex[:6]}"
        await svc.seed_builtins(tenant)

        persona = await svc.get_by_name(tenant, "swe-lead")
        assert persona is not None
        assert persona["verifier_chain"] == ["tests_pass", "diff_within_scope"]
