"""Linking memories stays inside one tenant (services/memory/links.py create_link).

The foreign keys only prove a memory exists in some tenant. Tenant A could
link its memory to B's, then reach B's content through ``/memories/{id}/linked``.
Both ends are now checked against the caller's tenant. Another tenant's memory
is a 404 with the same body as one that does not exist, so the route cannot be
used to learn which ids exist elsewhere.
"""

from __future__ import annotations

import hashlib
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, or_, select

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


async def _links_touching(memory_id: uuid.UUID) -> int:
    from life_graph.models.db import MemoryLink
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return await s.scalar(
            select(func.count())
            .select_from(MemoryLink)
            .where(
                or_(
                    MemoryLink.source_memory_id == memory_id,
                    MemoryLink.target_memory_id == memory_id,
                )
            )
        )


@pytest_asyncio.fixture
async def seeded() -> dict:
    run = uuid.uuid4().hex[:8]
    a, b = f"linka_{run}", f"linkb_{run}"
    return {
        "a": a,
        "b": b,
        "a1": await _seed(a, f"A's first note {run}"),
        "a2": await _seed(a, f"A's second note {run}"),
        "b1": await _seed(b, f"B's note {run}"),
    }


@skip_on_db_error
async def test_service_refuses_another_tenants_memory_either_end(seeded):
    from life_graph.core.errors import NotFoundError
    from life_graph.services.memory import links

    for source, target in ((seeded["a1"], seeded["b1"]), (seeded["b1"], seeded["a1"])):
        with pytest.raises(NotFoundError) as exc:
            await links.create_link(source, target, "RELATED_TO", tenant_id=seeded["a"])
        assert str(exc.value) == links.MEMORY_NOT_FOUND
    assert await _links_touching(seeded["b1"]) == 0

    # Its own two memories still link.
    link = await links.create_link(seeded["a1"], seeded["a2"], "RELATED_TO", tenant_id=seeded["a"])
    assert link.tenant_id == seeded["a"]


@skip_on_db_error
async def test_api_answers_another_tenants_memory_like_a_missing_one(seeded):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Tenant-ID": seeded["a"]},
    ) as c:

        async def post(source, target):
            return await c.post(
                f"/api/v1/memories/{source}/links",
                json={
                    "source_memory_id": str(source),
                    "target_memory_id": str(target),
                    "link_type": "RELATED_TO",
                },
            )

        other_target = await post(seeded["a1"], seeded["b1"])
        other_source = await post(seeded["b1"], seeded["a1"])
        missing = await post(seeded["a1"], uuid.uuid4())
        own = await post(seeded["a1"], seeded["a2"])

    assert other_target.status_code == 404, other_target.text
    assert other_source.status_code == 404, other_source.text
    assert missing.status_code == 404, missing.text

    def shape(resp):
        body = resp.json()
        return body["detail"], body["error"]["code"]

    assert shape(other_target) == shape(missing) == shape(other_source)
    assert await _links_touching(seeded["b1"]) == 0
    assert own.status_code == 201, own.text
