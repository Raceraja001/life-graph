"""search_mode "judged": hybrid's candidates kept and ordered by the relevance
judge, as Jarvis does (2026-10-29). On the owner's memories it put the right
memory first for 89.2% of questions against 78.5% for hybrid, and it can return
nothing when nothing fits. The judge is the local model; here it is replaced by
a stand-in so the test checks the wiring, not the model.
"""

from __future__ import annotations

import hashlib
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from tests.integration.conftest import skip_on_db_error

TENANT = f"judged_{uuid.uuid4().hex[:8]}"
WORD = f"quasar{uuid.uuid4().hex[:6]}"


async def _seed(content: str) -> None:
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        s.add(
            Memory(
                content=content,
                tenant_id=TENANT,
                content_hash=hashlib.sha256(content.encode()).hexdigest(),
                status="active",
                trust_tier="self",
                source_type="test",
            )
        )
        await s.commit()


@pytest.fixture
def no_embedding_service(monkeypatch):
    """Embeddings cannot be written under pytest (tests/conftest.py fakes the
    Vector type): a fixed query vector, so the keyword leg finds the notes."""
    from life_graph.core.memory_manager import MemoryManager

    async def fixed(self, text):
        return [0.0] * 1024

    monkeypatch.setattr(MemoryManager, "_generate_embedding", fixed)


def _judge(monkeypatch, decide):
    from life_graph.services import memory_retrieval

    seen = {}

    async def judge(question, contents):
        seen["question"], seen["contents"] = question, list(contents)
        return decide(contents)

    monkeypatch.setattr(memory_retrieval, "judge", judge)
    return seen


async def _search(query: str, **body):
    from life_graph.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/v1/search/",
            json={"query": query, "index_only": False, **body},
            headers={"X-Tenant-ID": TENANT},
        )
    assert r.status_code == 200, r.text
    return r.json()["data"]


@pytest.mark.asyncio
@skip_on_db_error
async def test_the_judge_decides_what_comes_back_and_in_what_order(
    monkeypatch, no_embedding_service
):
    await _seed(f"The {WORD} renewal is due in March.")
    await _seed(f"The {WORD} sticker is blue.")
    await _seed(f"The {WORD} garage is on Anna Salai.")

    # Keeps the garage, then the renewal; drops the sticker.
    def decide(contents):
        order = [next(i for i, c in enumerate(contents) if w in c) for w in ("garage", "renewal")]
        return order

    seen = _judge(monkeypatch, decide)
    data = await _search(f"where is the {WORD} garage?", search_mode="judged", limit=5)
    assert data["search_mode"] == "judged"
    assert [m["content"] for m in data["memories"]] == [
        f"The {WORD} garage is on Anna Salai.",
        f"The {WORD} renewal is due in March.",
    ]
    assert seen["question"] == f"where is the {WORD} garage?"
    assert len(seen["contents"]) == 3  # every candidate went to the judge


@pytest.mark.asyncio
@skip_on_db_error
async def test_nothing_fits_returns_nothing(monkeypatch, no_embedding_service):
    await _seed(f"The {WORD} boat is moored at Kovalam.")
    _judge(monkeypatch, lambda contents: [])
    data = await _search(f"what does the {WORD} boat cost?", search_mode="judged")
    assert data["search_mode"] == "judged"
    assert data["memories"] == [] and data["total_count"] == 0


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_failed_judge_falls_back_to_the_search_order(monkeypatch, no_embedding_service):
    await _seed(f"The {WORD} kite is red.")
    _judge(monkeypatch, lambda contents: None)
    data = await _search(f"what colour is the {WORD} kite?", search_mode="judged")
    assert data["search_mode"] == "hybrid"  # what the caller actually got
    assert any("kite" in m["content"] for m in data["memories"])


@pytest.mark.asyncio
@skip_on_db_error
async def test_ask_uses_what_the_judge_kept(monkeypatch, no_embedding_service):
    from life_graph.api.dependencies import get_synthesis_service
    from life_graph.main import app

    await _seed(f"The {WORD} locker code is kept in Vaultwarden.")
    await _seed(f"The {WORD} lamp is in the hall.")
    _judge(monkeypatch, lambda contents: [i for i, c in enumerate(contents) if "locker" in c])
    told = {}

    class Synth:
        async def synthesize(self, question, memories, **_kw):
            told["memories"] = [m["content"] for m in memories]
            return {"answer": "In Vaultwarden.", "source_count": len(memories), "model": "x"}

    app.dependency_overrides[get_synthesis_service] = lambda: Synth()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/api/v1/search/ask",
                json={"question": f"where is the {WORD} locker code?"},
                headers={"X-Tenant-ID": TENANT},
            )
    finally:
        app.dependency_overrides.pop(get_synthesis_service, None)
    assert r.status_code == 200, r.text
    assert told["memories"] == [f"The {WORD} locker code is kept in Vaultwarden."]
