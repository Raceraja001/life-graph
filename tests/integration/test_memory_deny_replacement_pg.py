"""POST /memories/{id}/deny with a replacement, against the real database.

store.deny set the old row's superseded_by to the new id while the new row
was still only pending in the session. The flush wrote the UPDATE first, so
memories_superseded_by_fkey rejected it and the route answered 500. The
replacement is now inserted first, in the same transaction.
"""

from __future__ import annotations

import hashlib
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.integration.conftest import assert_ok, skip_on_db_error

TENANT = f"deny_{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture
async def client():
    from life_graph.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Tenant-ID": TENANT, "X-User-ID": "tester"},
    ) as c:
        yield c


async def _memory(content: str) -> uuid.UUID:
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        m = Memory(
            content=content,
            tenant_id=TENANT,
            content_hash=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
            status="active",
            trust_tier="self",
            source_type="test",
            properties={},
        )
        s.add(m)
        await s.commit()
        return m.id


async def _get(memory_id):
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return await s.get(Memory, memory_id)


@pytest.mark.asyncio
@skip_on_db_error
async def test_deny_with_replacement_links_both_rows(client):
    old_id = await _memory("I live in Chennai")

    r = await client.post(
        f"/api/v1/memories/{old_id}/deny", json={"replacement": "I live in Coimbatore"}
    )
    data = assert_ok(r, 200)["data"]

    new_id = uuid.UUID(data["replacement"]["id"])
    assert data["denied"]["status"] == "superseded"
    old, new = await _get(old_id), await _get(new_id)
    assert old.status == "superseded"
    assert old.superseded_by == new_id
    assert new.supersedes == old_id
    assert new.content == "I live in Coimbatore"
    assert new.tenant_id == TENANT


@pytest.mark.asyncio
@skip_on_db_error
async def test_deny_without_replacement_only_supersedes(client):
    old_id = await _memory("I drink coffee")

    data = assert_ok(await client.post(f"/api/v1/memories/{old_id}/deny", json={}), 200)["data"]

    assert data["replacement"] is None
    old = await _get(old_id)
    assert old.status == "superseded"
    assert old.superseded_by is None
