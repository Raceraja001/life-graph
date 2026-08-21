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
        resp = await client.patch(f"/api/v1/memories/{row['id']}", json={"status": forbidden})
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


def _embeddings_available() -> bool:
    """True when the configured embedding backend is reachable.

    Vector search cannot return a row that has no embedding, so with
    LIFE_GRAPH_USE_LOCAL_LLM=true and LM Studio down these searches
    legitimately find nothing. Skip precisely rather than let the assertion
    pass on an empty result.
    """
    import socket
    from urllib.parse import urlparse

    from life_graph.config import settings

    if not settings.use_local_llm:
        return True  # a hosted backend; assume reachable
    u = urlparse(settings.lm_studio_url)
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex((u.hostname or "127.0.0.1", u.port or 80)) == 0


_needs_embeddings = pytest.mark.skipif(
    not _embeddings_available(),
    reason="vector search needs the embedding backend (LM Studio on :1234)",
)


@_needs_embeddings
@skip_on_db_error
@pytest.mark.asyncio
async def test_search_shows_pending_to_dashboard(client: AsyncClient):
    row = await _create(client, "pending searchable iota 6644 unicorn")
    if row is None:
        pytest.skip("DB unavailable")
    resp = await client.post(
        "/api/v1/search/",
        json={"query": "iota unicorn", "limit": 20, "include_pending": True},
    )
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        contents = str(resp.json())
        assert "6644" in contents, (
            "dashboard search (include_pending=true) must include pending memories"
        )


@_needs_embeddings
@skip_on_db_error
@pytest.mark.asyncio
async def test_search_without_include_pending_hides_pending(client: AsyncClient):
    """Agent contract: the MCP `search` tool never sets include_pending, so a
    pending memory must never reach it — that's the core approval-gate
    invariant (see docs/superpowers/specs/2026-07-23-memory-approval-gate-design.md).
    """
    row = await _create(client, "pending hidden from agents mu 9977 narwhal")
    if row is None:
        pytest.skip("DB unavailable")
    resp = await client.post("/api/v1/search/", json={"query": "mu narwhal", "limit": 20})
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        contents = str(resp.json())
        assert "9977" not in contents, "default (agent) search must NOT include pending memories"


@_needs_embeddings
@skip_on_db_error
@pytest.mark.asyncio
async def test_search_include_pending_shows_pending(client: AsyncClient):
    """Explicit opt-in (the dashboard's contract) must surface pending rows."""
    row = await _create(client, "pending visible with opt in nu 1234 platypus")
    if row is None:
        pytest.skip("DB unavailable")
    resp = await client.post(
        "/api/v1/search/",
        json={"query": "nu platypus", "limit": 20, "include_pending": True},
    )
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        contents = str(resp.json())
        assert "1234" in contents, "include_pending=true search must include pending memories"


@skip_on_db_error
@pytest.mark.asyncio
async def test_bulk_import_is_pending(client: AsyncClient):
    """Bulk-imported rows must be gated like any other user content.

    Only user content is gated (2026-07-23 ruling); system-derived writers
    stay active. Bulk import is external/imported content, so it starts
    pending — see docs/superpowers/specs/2026-07-23-memory-approval-gate-design.md.
    """
    text = "bulk import gate probe lambda 8866"
    resp = await client.post(
        "/api/v1/admin/bulk/import",
        json={"memories": [{"content": text}], "generate_embeddings": False},
    )
    assert resp.status_code in (201, 500)
    if resp.status_code != 201:
        pytest.skip("DB unavailable")
    assert resp.json()["data"]["imported"] == 1

    pending = await client.get("/api/v1/memories/", params={"status": "pending", "limit": "100"})
    assert pending.status_code == 200
    assert any(r["content"] == text for r in pending.json()["data"]), (
        "bulk-imported memory must land in the pending queue"
    )

    # Default listing shows pending + active (excludes only rejected), so the
    # row IS visible here too — but it must not have status="active".
    default_listing = await client.get("/api/v1/memories/", params={"limit": "100"})
    assert default_listing.status_code == 200
    matches = [r for r in default_listing.json()["data"] if r["content"] == text]
    if matches:
        assert matches[0]["status"] == "pending"


@skip_on_db_error
@pytest.mark.asyncio
async def test_default_list_hides_rejected(client: AsyncClient):
    row = await _create(client, "rejected hidden kappa 7755")
    if row is None:
        pytest.skip("DB unavailable")
    await client.post(f"/api/v1/memories/{row['id']}/reject")
    listing = await client.get("/api/v1/memories/", params={"limit": "100"})
    assert listing.status_code == 200
    ids = [r["id"] for r in listing.json()["data"]]
    assert row["id"] not in ids
    explicit = await client.get("/api/v1/memories/", params={"status": "rejected", "limit": "100"})
    assert explicit.status_code == 200
    assert row["id"] in [r["id"] for r in explicit.json()["data"]]
