"""Hostile-tier memories are left out of search and recall against Postgres.

See tests/unit/test_hostile_tier_search.py for why. Embeddings cannot be
written under pytest (tests/conftest.py fakes the Vector type), so the search
checks run the keyword leg, which has the same WHERE clauses.
"""

from __future__ import annotations

import hashlib
import uuid

import pytest

from life_graph.core.tenant import set_tenant_context
from tests.integration.conftest import skip_on_db_error

TENANT = f"hostile_{uuid.uuid4().hex[:8]}"
WORD = f"quokka{uuid.uuid4().hex[:6]}"
OWN = f"{WORD} owner's own note"
OTHER = f"{WORD} forwarded from a stranger"


async def _seed(content: str, trust_tier: str, status: str = "active") -> None:
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        s.add(
            Memory(
                content=content,
                tenant_id=TENANT,
                content_hash=hashlib.sha256(content.encode()).hexdigest(),
                importance=0.9,
                status=status,
                trust_tier=trust_tier,
                source_type="whatsapp" if trust_tier == "hostile_possible" else "manual",
            )
        )
        await s.commit()


@pytest.fixture
async def seeded():
    await _seed(OWN, "self")
    # Kept by the owner: active, still someone else's words.
    await _seed(OTHER, "hostile_possible")
    set_tenant_context(TENANT)


@pytest.mark.asyncio
@skip_on_db_error
async def test_hybrid_search_and_recall_leave_them_out_unless_asked(seeded):
    from life_graph.storage.postgres import PostgresMemoryStore

    store = PostgresMemoryStore()

    async def search(**kw):
        hits = await store.hybrid_search(embedding=[0.0] * 1024, query_text=WORD, limit=20, **kw)
        return {m.content for m, _ in hits}

    assert await search() == {OWN}
    assert await search(include_hostile=True) == {OWN, OTHER}

    pool = await store.list_recall_candidates(filters={"status": "active"}, limit=50)
    assert {m.content for m in pool} == {OWN}
    pool = await store.list_recall_candidates(
        filters={"status": "active"}, limit=50, include_hostile=True
    )
    assert {m.content for m in pool} == {OWN, OTHER}


@pytest.mark.asyncio
@skip_on_db_error
async def test_search_endpoint_shows_them_to_the_dashboard_only(seeded, monkeypatch):
    from httpx import ASGITransport, AsyncClient

    from life_graph.core.memory_manager import MemoryManager
    from life_graph.main import app

    async def fixed(self, text):
        return [0.0] * 1024

    monkeypatch.setattr(MemoryManager, "_generate_embedding", fixed)

    async def ask(include_pending: bool) -> str:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/v1/search/",
                json={
                    "query": WORD,
                    "limit": 20,
                    "search_mode": "hybrid",
                    "include_pending": include_pending,
                },
                headers={"X-Tenant-ID": TENANT},
            )
        assert resp.status_code == 200, resp.text
        return str(resp.json())

    # An agent (the MCP search tool never sets include_pending).
    agent = await ask(False)
    assert OWN in agent and OTHER not in agent
    # The owner's dashboard.
    dashboard = await ask(True)
    assert OWN in dashboard and OTHER in dashboard


SERVICE_KEY = "svc-hostile-key-0123456789"
OWNER_KEY = "owner-hostile-key-0123456789"
PENDING = f"{WORD} owner's note awaiting approval"


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_service_key_gets_pending_rows_but_never_hostile_ones(seeded, monkeypatch):
    """include_pending alone used to give any service-key caller the hostile rows."""
    from httpx import ASGITransport, AsyncClient

    from life_graph.config import settings
    from life_graph.core.memory_manager import MemoryManager
    from life_graph.main import app

    await _seed(PENDING, "self", status="pending")
    monkeypatch.setattr(settings, "api_key", "")
    monkeypatch.setattr(settings, "service_api_keys", f"{SERVICE_KEY},{OWNER_KEY}")
    monkeypatch.setattr(settings, "owner_api_keys", OWNER_KEY)

    async def fixed(self, text):
        return [0.0] * 1024

    monkeypatch.setattr(MemoryManager, "_generate_embedding", fixed)

    async def ask(key: str) -> str:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/v1/search/",
                json={"query": WORD, "limit": 20, "search_mode": "hybrid", "include_pending": True},
                headers={"X-Tenant-ID": TENANT, "Authorization": f"Bearer {key}"},
            )
        assert resp.status_code == 200, resp.text
        return str(resp.json())

    service = await ask(SERVICE_KEY)
    assert OWN in service and PENDING in service
    assert OTHER not in service
    owner = await ask(OWNER_KEY)
    assert OWN in owner and PENDING in owner and OTHER in owner
