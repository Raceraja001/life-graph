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


@skip_on_db_error
@pytest.mark.asyncio
async def test_duplicate_of_pending_is_deduped(client: AsyncClient):
    text = "approval dedup probe gamma 7731"
    first = await client.post("/api/v1/memories/", json={"content": text})
    if first.status_code not in (200, 201):
        pytest.skip("DB unavailable")
    second = await client.post("/api/v1/memories/", json={"content": text})
    assert second.status_code in (200, 201)
    listing = await client.get("/api/v1/memories/", params={"status": "pending", "limit": "50"})
    if listing.status_code == 200:
        rows = [r for r in listing.json()["data"] if r["content"] == text]
        assert len(rows) == 1, "second capture must dedup against the pending row"


async def _create(client: AsyncClient, text: str) -> dict | None:
    resp = await client.post("/api/v1/memories/", json={"content": text})
    if resp.status_code not in (200, 201):
        return None
    data = resp.json()["data"]
    return data[0] if isinstance(data, list) else data


@skip_on_db_error
@pytest.mark.asyncio
async def test_approve_transitions_pending_to_active(client: AsyncClient):
    row = await _create(client, "approve me delta 1188")
    if row is None:
        pytest.skip("DB unavailable")
    resp = await client.post(f"/api/v1/memories/{row['id']}/approve")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "active"
    again = await client.post(f"/api/v1/memories/{row['id']}/approve")
    assert again.status_code == 200  # idempotent


@skip_on_db_error
@pytest.mark.asyncio
async def test_reject_and_active_reject_conflict(client: AsyncClient):
    row = await _create(client, "reject me epsilon 2299")
    if row is None:
        pytest.skip("DB unavailable")
    resp = await client.post(f"/api/v1/memories/{row['id']}/reject")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "rejected"
    row2 = await _create(client, "active then reject zeta 3311")
    await client.post(f"/api/v1/memories/{row2['id']}/approve")
    conflict = await client.post(f"/api/v1/memories/{row2['id']}/reject")
    assert conflict.status_code == 409


@skip_on_db_error
@pytest.mark.asyncio
async def test_bulk_and_count(client: AsyncClient):
    a = await _create(client, "bulk approval eta 4422")
    b = await _create(client, "bulk rejection theta 5533")
    if a is None or b is None:
        pytest.skip("DB unavailable")
    count_before = await client.get("/api/v1/memories/pending/count")
    assert count_before.status_code == 200
    assert count_before.json()["data"]["count"] >= 2
    resp = await client.post(
        "/api/v1/memories/approvals/bulk",
        json={"approve": [a["id"]], "reject": [b["id"]]},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["approved"] == 1 and body["rejected"] == 1
