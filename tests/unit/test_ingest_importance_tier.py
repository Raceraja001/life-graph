"""importance_tier reaches the stored row on ingest (code review, 2026-10-22).

``_process_fact`` computed the tier but only put it in the tags, and
``PostgresMemoryStore.store()`` had no way to receive it, so every memory was
stored ``importance_tier='normal'`` and the decay sweep's ``'critical'``
exemption never applied until consolidation happened to rescore it.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import life_graph.storage.postgres as pg
from life_graph.config import settings
from life_graph.core.memory_manager import MemoryManager
from life_graph.core.tenant import set_tenant_context
from life_graph.extraction.rules import ExtractedFact
from life_graph.models.schemas import MemoryCreate
from life_graph.services.embeddings import current_embedding_model


def _manager(score):
    mgr = MemoryManager.__new__(MemoryManager)
    mgr._tagger = SimpleNamespace(score=lambda content, context: score)
    stored = []

    async def none(*_a, **_k):
        return None

    async def no_candidates(*_a, **_k):
        return []

    async def fake_store(memory_create, **kwargs):
        stored.append((memory_create, kwargs))
        return SimpleNamespace(id="new", properties=memory_create.properties)

    mgr._store = SimpleNamespace(
        find_exact_duplicate=none,
        find_similarity_candidates=no_candidates,
        store=fake_store,
    )
    mgr._contradiction_detector = SimpleNamespace(check_candidates=no_candidates)
    return mgr, stored


@pytest.mark.asyncio
async def test_process_fact_passes_the_scored_tier_to_store():
    mgr, stored = _manager((0.95, "critical"))
    fact = ExtractedFact(content="Never deploy on Fridays", fact_type="constraint", confidence=0.9)

    await mgr._process_fact(fact, context=None, source="test", embedding=[0.1, 0.2])

    ((memory_create, kwargs),) = stored
    assert kwargs["importance_tier"] == "critical"
    assert memory_create.importance == 0.95


class _CaptureSession:
    def __init__(self):
        self.added = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        return False

    def add(self, row):
        self.added.append(row)

    async def commit(self):
        pass

    async def refresh(self, _row):
        pass


@pytest.mark.asyncio
async def test_store_writes_importance_tier_and_current_embedding_model(monkeypatch):
    set_tenant_context("acme", "user-1")
    session = _CaptureSession()
    monkeypatch.setattr(pg, "async_session", lambda: session)
    monkeypatch.setattr(settings, "use_local_llm", True)
    monkeypatch.setattr(settings, "lm_embedding_model", "bge-m3")

    await pg.PostgresMemoryStore().store(
        MemoryCreate(content="x", importance=0.9),
        embedding=[0.1, 0.2],
        status="active",
        importance_tier="critical",
    )

    (row,) = session.added
    assert row.importance_tier == "critical"
    # The same name the re-embed job compares against.
    assert row.embedding_model == current_embedding_model() == "bge-m3"


@pytest.mark.asyncio
async def test_store_without_tier_keeps_column_default(monkeypatch):
    set_tenant_context("acme", "user-1")
    session = _CaptureSession()
    monkeypatch.setattr(pg, "async_session", lambda: session)

    await pg.PostgresMemoryStore().store(MemoryCreate(content="x"), status="active")

    (row,) = session.added
    assert row.importance_tier in (None, "normal")  # default applied at flush
