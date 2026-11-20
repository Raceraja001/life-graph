"""POST /internal/sync/analytics against a real database (audit M10).

Analytics items become *pending* memories (the review queue), with the
uzhavu_sync trust tier, and one item the database refuses does not fail the
rest of the batch: each insert runs in its own savepoint.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from life_graph.config import settings
from life_graph.main import app
from life_graph.models.db import CrossSystemSync, Memory
from life_graph.storage.database import async_session
from tests.integration.conftest import assert_ok, skip_on_db_error

KEY = "integration-internal-key"


@pytest_asyncio.fixture
async def client(monkeypatch):
    monkeypatch.setattr(settings, "internal_api_key", KEY)
    tenant = f"sync-{uuid.uuid4().hex[:8]}"
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-Tenant-ID": tenant, "X-Internal-API-Key": KEY},
    ) as c:
        c.tenant = tenant  # type: ignore[attr-defined]
        yield c


async def _memories(tenant: str) -> list[Memory]:
    async with async_session() as session:
        rows = await session.execute(select(Memory).where(Memory.tenant_id == tenant))
        return list(rows.scalars().all())


@pytest.mark.asyncio
@skip_on_db_error
async def test_items_become_pending_memories(client):
    body = assert_ok(
        await client.post(
            "/api/v1/internal/sync/analytics",
            json={
                "items": [
                    {"content": "Field 4 yield up 12%", "importance": 0.7, "tags": ["yield"]},
                    {"content": "Pump 2 ran 30h this week", "source": "uzhavu-iot"},
                ]
            },
        ),
        200,
    )

    assert (body["records_sent"], body["records_synced"], body["records_failed"]) == (2, 2, 0)
    rows = {m.content: m for m in await _memories(client.tenant)}
    assert set(rows) == {"Field 4 yield up 12%", "Pump 2 ran 30h this week"}
    for m in rows.values():
        assert m.status == "pending"
        assert m.source_type == "uzhavu_sync"
        assert m.trust_tier == "verified"
        assert m.content_hash
    assert rows["Field 4 yield up 12%"].importance == 0.7
    assert rows["Pump 2 ran 30h this week"].source == "uzhavu-iot"


@pytest.mark.asyncio
@skip_on_db_error
async def test_one_refused_item_does_not_fail_the_batch(client, monkeypatch):
    from life_graph.services import cross_system_sync

    # A row the database itself refuses: its primary key collides with an
    # existing memory. Validation cannot see that coming.
    taken = uuid.uuid4()
    async with async_session() as session:
        session.add(Memory(id=taken, tenant_id=client.tenant, content="already here"))
        await session.commit()

    real_memory = cross_system_sync.Memory

    def memory(**kwargs):
        row = real_memory(**kwargs)
        if kwargs["content"] == "collides":
            row.id = taken
        return row

    monkeypatch.setattr(cross_system_sync, "Memory", memory)

    body = assert_ok(
        await client.post(
            "/api/v1/internal/sync/analytics",
            json={"items": [{"content": "before"}, {"content": "collides"}, {"content": "after"}]},
        ),
        200,
    )

    assert (body["records_synced"], body["records_failed"]) == (2, 1)
    assert sorted(m.content for m in await _memories(client.tenant)) == [
        "after",
        "already here",
        "before",
    ]
    async with async_session() as session:
        record = await session.get(CrossSystemSync, uuid.UUID(body["id"]))
    assert record is not None and record.status == "completed"


@pytest.mark.asyncio
@skip_on_db_error
async def test_nul_bytes_are_refused_up_front(client):
    """PostgreSQL text and JSONB cannot hold NUL; that used to be a 500 for the batch."""
    response = await client.post(
        "/api/v1/internal/sync/analytics", json={"items": [{"content": "bad \u0000 byte"}]}
    )

    assert response.status_code == 422
    assert await _memories(client.tenant) == []


@pytest.mark.asyncio
@skip_on_db_error
async def test_out_of_range_importance_stores_nothing(client):
    response = await client.post(
        "/api/v1/internal/sync/analytics",
        json={"items": [{"content": "x", "importance": 5}]},
    )

    assert response.status_code == 422
    assert await _memories(client.tenant) == []
