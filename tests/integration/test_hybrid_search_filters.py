"""hybrid_search applies its filters, and /search/ask answers from active memories only.

Both were found on 2026-10-22: the default search mode accepted ``filters`` and
never used them, and ``ask`` searched every status, so 3,668 unreviewed
memories could reach an answer. Embeddings cannot be written under pytest
(tests/conftest.py fakes the Vector type), so these exercise the keyword leg,
which runs the same WHERE clauses.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from life_graph.core.tenant import set_tenant_context
from tests.integration.conftest import skip_on_db_error

TENANT = f"hyb_{uuid.uuid4().hex[:8]}"
WORD = f"zephyr{uuid.uuid4().hex[:6]}"


async def _seed(
    content, *, tags, importance=0.5, status="active", created_at=None, source_type="test"
):
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        m = Memory(
            content=content,
            tenant_id=TENANT,
            content_hash=hashlib.sha256(content.encode()).hexdigest(),
            importance=importance,
            tags=tags,
            status=status,
            trust_tier="verified",
            source_type=source_type,
        )
        if created_at is not None:
            m.created_at = created_at
        s.add(m)
        await s.commit()
        return m.id


async def _search(filters=None, statuses=("active",)):
    from life_graph.storage.postgres import PostgresMemoryStore

    set_tenant_context(TENANT)
    hits = await PostgresMemoryStore().hybrid_search(
        embedding=[0.0] * 1024, query_text=WORD, limit=20, filters=filters, statuses=statuses
    )
    return {m.content for m, _ in hits}


@pytest.mark.asyncio
@skip_on_db_error
async def test_hybrid_search_applies_its_filters():
    old = datetime.now(UTC) - timedelta(days=30)
    await _seed(f"{WORD} travel plan", tags=["travel"], importance=0.9)
    await _seed(f"{WORD} work note", tags=["work"], importance=0.3, source_type="cli")
    await _seed(f"{WORD} old travel", tags=["travel"], importance=0.9, created_at=old)
    await _seed(f"{WORD} unreviewed", tags=["travel"], status="pending")

    assert await _search() == {f"{WORD} travel plan", f"{WORD} work note", f"{WORD} old travel"}
    assert await _search({"tags": ["work"]}) == {f"{WORD} work note"}
    assert await _search({"min_importance": 0.8}) == {f"{WORD} travel plan", f"{WORD} old travel"}
    recent = {"created_after": datetime.now(UTC) - timedelta(days=1)}
    assert f"{WORD} old travel" not in await _search(recent)
    assert await _search({"source_type": "cli"}) == {f"{WORD} work note"}
    assert await _search({"tags": ["travel"], "min_importance": 0.8, **recent}) == {
        f"{WORD} travel plan"
    }
    # status in filters wins over the statuses argument
    assert await _search({"status": "pending"}) == {f"{WORD} unreviewed"}


@pytest.mark.asyncio
@skip_on_db_error
async def test_ask_answers_from_active_memories_only(monkeypatch):
    """Since 2026-10-29 ask finds memories the way Jarvis does
    (services/memory_retrieval.py), still from active memories only."""
    from httpx import ASGITransport, AsyncClient

    from life_graph.core.memory_manager import MemoryManager
    from life_graph.main import app
    from life_graph.storage.postgres import PostgresMemoryStore

    async def fixed(self, text):
        return [0.0] * 1024

    monkeypatch.setattr(MemoryManager, "_generate_embedding", fixed)
    seen = {}
    real = PostgresMemoryStore.hybrid_search

    async def spy(self, *args, **kwargs):
        seen["statuses"] = kwargs.get("statuses")
        seen["filters"] = kwargs.get("filters")
        return await real(self, *args, **kwargs)

    monkeypatch.setattr(PostgresMemoryStore, "hybrid_search", spy)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            "/api/v1/search/ask",
            json={"question": "where do I travel?"},
            headers={"X-Tenant-ID": TENANT},
        )
    if "statuses" not in seen:
        pytest.skip(f"ask did not reach the search (embedding unavailable): {resp.status_code}")
    assert seen["statuses"] == ("active",)
    assert not seen["filters"]


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_question_finds_a_note_by_any_of_its_words():
    """plainto_tsquery needed EVERY word to match, so a natural question found
    nothing by keyword; now any content word of it counts (RRF fusion)."""
    rare = f"quokka{uuid.uuid4().hex[:5]}"
    await _seed(f"The {rare} module runs on port 3006.", tags=["work"])
    from life_graph.storage.postgres import PostgresMemoryStore

    set_tenant_context(TENANT)
    hits = await PostgresMemoryStore().hybrid_search(
        embedding=[0.0] * 1024, query_text=f"which port does the {rare} thing use?", limit=5
    )
    assert hits and rare in hits[0][0].content
    assert 0.0 < hits[0][1] <= 1.0  # normalised: tri_search adds a graph boost on this scale
