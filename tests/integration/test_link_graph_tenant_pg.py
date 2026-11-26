"""The link walk (GET /memories/{id}/linked) stays inside one tenant.

``memory_links`` rows written before create_link checked both ends can belong
to tenant A yet point at tenant B's memory. The walk filtered the links by
tenant but loaded the memories they lead to by id alone, so B's content came
back. Such a row is written here directly, the way an old one would look.
"""

from __future__ import annotations

import hashlib
import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from life_graph.main import app
from tests.integration.conftest import skip_on_db_error


async def _seed(tenant: str, content: str) -> uuid.UUID:
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        m = Memory(
            content=content,
            tenant_id=tenant,
            content_hash=hashlib.sha256(f"{content}{uuid.uuid4()}".encode()).hexdigest(),
            importance=0.5,
            tags=["test"],
            status="active",
            trust_tier="verified",
            source_type="test",
        )
        s.add(m)
        await s.commit()
        return m.id


async def _raw_link(source: uuid.UUID, target: uuid.UUID, tenant: str) -> None:
    from life_graph.storage.database import async_session

    async with async_session() as s:
        await s.execute(
            text(
                "INSERT INTO memory_links (id, source_memory_id, target_memory_id,"
                " link_type, strength, properties, tenant_id)"
                " VALUES (:id, :s, :t, 'RELATED_TO', 0.5, '{}'::jsonb, :tenant)"
            ),
            {"id": uuid.uuid4(), "s": source, "t": target, "tenant": tenant},
        )
        await s.commit()


@pytest_asyncio.fixture
async def seeded() -> dict:
    run = uuid.uuid4().hex[:8]
    a, b = f"lgwa_{run}", f"lgwb_{run}"
    ids = {
        "a": a,
        "a1": await _seed(a, f"A start {run}"),
        "a2": await _seed(a, f"A neighbour {run}"),
        "b1": await _seed(b, f"B secret {run}"),
        "b2": await _seed(b, f"B second secret {run}"),
    }
    await _raw_link(ids["a1"], ids["a2"], a)
    # An old cross-tenant row, owned by A, leading to B, and on from there.
    await _raw_link(ids["a1"], ids["b1"], a)
    await _raw_link(ids["b1"], ids["b2"], a)
    return ids


@skip_on_db_error
async def test_link_graph_skips_another_tenants_memory(seeded):
    from life_graph.services.memory import links

    walked = await links.get_link_graph(seeded["a1"], depth=3, tenant_id=seeded["a"])

    assert {item["memory_id"] for item in walked} == {str(seeded["a2"])}
    assert all("secret" not in item.get("content", "") for item in walked)


@skip_on_db_error
async def test_linked_endpoint_shows_no_other_tenant_content(seeded):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Tenant-ID": seeded["a"]},
    ) as c:
        resp = await c.get(f"/api/v1/memories/{seeded['a1']}/linked", params={"depth": 3})

    assert resp.status_code == 200, resp.text
    assert str(seeded["a2"]) in resp.text
    for other in ("b1", "b2"):
        assert str(seeded[other]) not in resp.text
    assert "secret" not in resp.text
