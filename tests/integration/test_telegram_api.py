"""The four management endpoints for the Telegram bridge.

Against a real database, because the thing worth testing here is the tenant
boundary and that boundary is enforced by a WHERE clause. A mocked session
would assert that the Python happy path was taken while leaving the filter
itself — the only line that stops one tenant revoking another's chat — untested.

The pairing code is the whole security story of the bridge: an inbound update
carries a chat id and no authentication, so a chat becomes a tenant's only by
redeeming a code minted here by an authenticated caller. Hence the tests below
that a code is single-use, that it belongs to the tenant that asked for it, and
that revoking somebody else's binding reads as a missing id rather than a
refusal.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from life_graph.main import app
from life_graph.models.db import TelegramBinding, TelegramPairingCode
from life_graph.services.telegram_binding import TelegramBindingService
from life_graph.storage.database import async_session
from tests.integration.conftest import skip_on_db_error

TENANT = "test_tgapi_tenant"
OTHER_TENANT = "test_tgapi_other"
CHAT = 6610001
OTHER_CHAT = 6610002

HEADERS = {"X-Tenant-ID": TENANT}
OTHER_HEADERS = {"X-Tenant-ID": OTHER_TENANT}

BASE = "/api/v1/integrations/telegram"


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=HEADERS) as c:
        yield c


@pytest_asyncio.fixture(autouse=True)
async def clean_slate():
    """Remove this module's rows before and after, leaving other tenants alone."""

    async def _purge():
        async with async_session() as session:
            await session.execute(
                delete(TelegramBinding).where(TelegramBinding.tenant_id.in_([TENANT, OTHER_TENANT]))
            )
            await session.execute(
                delete(TelegramPairingCode).where(
                    TelegramPairingCode.tenant_id.in_([TENANT, OTHER_TENANT])
                )
            )
            await session.commit()

    try:
        await _purge()
    except Exception:
        pytest.skip("database unreachable")
    yield
    await _purge()


async def _bind(tenant_id: str, chat_id: int) -> str:
    """Pair a chat the way the bot does, and return the binding id."""
    async with async_session() as session:
        service = TelegramBindingService(session)
        code = await service.issue_code(tenant_id)
        await session.commit()
        binding = await service.redeem_code(code.code, chat_id, username="tester")
        await session.commit()
        return str(binding.id)


# ── POST /pair ────────────────────────────────────────────────────


class TestPair:
    @skip_on_db_error
    async def test_a_code_is_issued(self, client: AsyncClient):
        resp = await client.post(f"{BASE}/pair")
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["code"] and data["expires_at"]

    @skip_on_db_error
    async def test_the_code_belongs_to_the_calling_tenant(self, client: AsyncClient):
        code = (await client.post(f"{BASE}/pair")).json()["data"]["code"]
        async with async_session() as session:
            row = await session.scalar(
                select(TelegramPairingCode).where(TelegramPairingCode.code == code)
            )
        assert row.tenant_id == TENANT

    @skip_on_db_error
    async def test_two_calls_give_two_different_codes(self, client: AsyncClient):
        first = (await client.post(f"{BASE}/pair")).json()["data"]["code"]
        second = (await client.post(f"{BASE}/pair")).json()["data"]["code"]
        assert first != second

    @skip_on_db_error
    async def test_a_missing_bot_username_does_not_fail_the_call(self, client: AsyncClient):
        # No token is configured in tests, so getMe cannot be called. The code
        # is what matters; the handle only makes the instructions friendlier.
        data = (await client.post(f"{BASE}/pair")).json()["data"]
        assert "bot_username" in data


# ── GET /bindings ─────────────────────────────────────────────────


class TestListBindings:
    @skip_on_db_error
    async def test_empty_when_nothing_is_paired(self, client: AsyncClient):
        resp = await client.get(f"{BASE}/bindings")
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"] == []

    @skip_on_db_error
    async def test_a_paired_chat_is_listed(self, client: AsyncClient):
        binding_id = await _bind(TENANT, CHAT)
        data = (await client.get(f"{BASE}/bindings")).json()["data"]
        assert [b["id"] for b in data] == [binding_id]
        assert data[0]["chat_id"] == CHAT

    @skip_on_db_error
    async def test_another_tenants_chat_is_not_listed(self, client: AsyncClient):
        await _bind(OTHER_TENANT, OTHER_CHAT)
        assert (await client.get(f"{BASE}/bindings")).json()["data"] == []

    @skip_on_db_error
    async def test_a_revoked_chat_is_not_listed(self, client: AsyncClient):
        binding_id = await _bind(TENANT, CHAT)
        await client.delete(f"{BASE}/bindings/{binding_id}")
        assert (await client.get(f"{BASE}/bindings")).json()["data"] == []


# ── DELETE /bindings/{id} ─────────────────────────────────────────


class TestRevoke:
    @skip_on_db_error
    async def test_revoking_deactivates_the_binding(self, client: AsyncClient):
        binding_id = await _bind(TENANT, CHAT)
        resp = await client.delete(f"{BASE}/bindings/{binding_id}")
        assert resp.status_code == 204, resp.text

        async with async_session() as session:
            row = await session.scalar(
                select(TelegramBinding).where(TelegramBinding.chat_id == CHAT)
            )
        # Deactivated, not deleted: the record of which chat had access survives.
        assert row is not None and row.active is False

    @skip_on_db_error
    async def test_a_revoked_chat_no_longer_resolves_to_a_tenant(self, client: AsyncClient):
        binding_id = await _bind(TENANT, CHAT)
        await client.delete(f"{BASE}/bindings/{binding_id}")

        async with async_session() as session:
            tenant = await TelegramBindingService(session).tenant_for_chat(CHAT)
        assert tenant is None, "a revoked chat must lose its ability to write"

    @skip_on_db_error
    async def test_another_tenants_binding_cannot_be_revoked(self, client: AsyncClient):
        binding_id = await _bind(OTHER_TENANT, OTHER_CHAT)
        resp = await client.delete(f"{BASE}/bindings/{binding_id}")
        # 404 rather than 403: confirming the id exists would leak that some
        # other tenant holds it.
        assert resp.status_code == 404, resp.text

        async with async_session() as session:
            row = await session.scalar(
                select(TelegramBinding).where(TelegramBinding.chat_id == OTHER_CHAT)
            )
        assert row.active is True, "the other tenant's binding must survive"

    @skip_on_db_error
    async def test_an_unknown_id_is_404_not_500(self, client: AsyncClient):
        resp = await client.delete(f"{BASE}/bindings/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404, resp.text

    @skip_on_db_error
    async def test_a_malformed_id_is_422(self, client: AsyncClient):
        assert (await client.delete(f"{BASE}/bindings/not-a-uuid")).status_code == 422

    @skip_on_db_error
    async def test_revoking_twice_is_404_the_second_time(self, client: AsyncClient):
        binding_id = await _bind(TENANT, CHAT)
        assert (await client.delete(f"{BASE}/bindings/{binding_id}")).status_code == 204
        assert (await client.delete(f"{BASE}/bindings/{binding_id}")).status_code == 404


# ── GET /status ───────────────────────────────────────────────────


class TestStatus:
    @skip_on_db_error
    async def test_status_reports_the_shape_the_dashboard_expects(self, client: AsyncClient):
        resp = await client.get(f"{BASE}/status")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert set(data) >= {"configured", "poller", "bound_chats", "last_update_at"}

    @skip_on_db_error
    async def test_bound_chats_counts_only_this_tenant(self, client: AsyncClient):
        await _bind(TENANT, CHAT)
        await _bind(OTHER_TENANT, OTHER_CHAT)
        assert (await client.get(f"{BASE}/status")).json()["data"]["bound_chats"] == 1

    @skip_on_db_error
    async def test_a_revoked_chat_is_not_counted(self, client: AsyncClient):
        binding_id = await _bind(TENANT, CHAT)
        await client.delete(f"{BASE}/bindings/{binding_id}")
        assert (await client.get(f"{BASE}/status")).json()["data"]["bound_chats"] == 0

    @skip_on_db_error
    async def test_an_unconfigured_bridge_says_so(self, client: AsyncClient):
        # No token is set in the test environment, which is exactly the state a
        # first-time user is in — the dashboard has to distinguish it from a
        # configured bridge whose poller has died.
        data = (await client.get(f"{BASE}/status")).json()["data"]
        if not data["configured"]:
            assert data["poller"] == "disabled"


# ── /health ───────────────────────────────────────────────────────


class TestHealthCheck:
    @skip_on_db_error
    async def test_health_reports_the_bridge(self, client: AsyncClient):
        body = (await client.get("/health")).json()
        assert "telegram" in body["checks"]

    @skip_on_db_error
    async def test_the_bridge_never_causes_a_503(self, client: AsyncClient):
        # Running the API without the ARQ worker is a normal way to develop, and
        # in that state the poller is legitimately absent. A health check that is
        # permanently red is a health check nobody reads.
        resp = await client.get("/health")
        if resp.json()["checks"]["postgres"]["status"] == "healthy":
            assert resp.status_code == 200, resp.text
