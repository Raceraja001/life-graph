"""Memory approval gate — every new memory starts pending.

House convention: tests tolerate DB-unreachable (500) but never accept 422
for valid input.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import skip_on_db_error

TENANT_HEADERS = {"X-Tenant-ID": "test-approval"}


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=TENANT_HEADERS
    ) as c:
        yield c


@skip_on_db_error
@pytest.mark.asyncio
async def test_new_memory_is_pending(client: AsyncClient):
    resp = await client.post("/api/v1/memories/", json={"content": "approval gate test alpha"})
    assert resp.status_code in (200, 201, 500)
    if resp.status_code in (200, 201):
        data = resp.json()["data"]
        row = data[0] if isinstance(data, list) else data
        assert row["status"] == "pending"


@skip_on_db_error
@pytest.mark.asyncio
async def test_patch_cannot_set_approval_statuses(client: AsyncClient):
    create = await client.post("/api/v1/memories/", json={"content": "approval gate test beta"})
    if create.status_code not in (200, 201):
        pytest.skip("DB unavailable")
    data = create.json()["data"]
    row = data[0] if isinstance(data, list) else data
    for forbidden in ("pending", "rejected", "active"):
        resp = await client.patch(
            f"/api/v1/memories/{row['id']}", json={"status": forbidden}
        )
        assert resp.status_code == 422, f"PATCH status={forbidden} must be rejected"
