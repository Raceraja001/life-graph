"""Async embedding paths (code review, 2026-10-22).

``EmbeddingService.embed()`` is synchronous and returns ``[]`` inside a
running event loop in local-LLM mode. Two async callers used it anyway:

* consolidation's distill step, so distilled principles had no vector;
* the bulk-import worker, which ``await``-ed the sync function — a TypeError
  caught per row, so no bulk-imported memory was ever embedded.

Outside local-LLM mode ``embed_async`` ran the sentence-transformers encode
directly on the event loop, blocking every request for its duration.

No real model or database: the fakes stand in for both (tests/conftest.py
fakes the Vector type, so vectors cannot be written under pytest anyway).
"""

from __future__ import annotations

import logging
import threading
import uuid

import pytest

from life_graph.config import settings
from life_graph.services.embeddings import EmbeddingService, current_embedding_model


class _Vec(list):
    def tolist(self):
        return list(self)


class _ThreadRecordingModel:
    """Stands in for SentenceTransformer; records which thread encoded."""

    def __init__(self):
        self.threads: list[int] = []

    def encode(self, texts, **_kw):
        self.threads.append(threading.get_ident())
        if isinstance(texts, str):
            return _Vec([0.5, 0.5])
        return [_Vec([0.5, 0.5]) for _ in texts]


class _LMClient:
    def __init__(self, vector):
        self.vector = vector
        self.calls: list[str] = []

    async def embed(self, text):
        self.calls.append(text)
        return self.vector

    async def embed_batch(self, texts):
        return [self.vector for _ in texts]


def _st_service(monkeypatch) -> tuple[EmbeddingService, _ThreadRecordingModel]:
    monkeypatch.setattr(settings, "use_local_llm", False)
    svc = EmbeddingService()
    svc._available = True
    model = _ThreadRecordingModel()
    svc._model = model
    return svc, model


# ── EmbeddingService ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_embed_async_runs_sentence_transformers_off_the_event_loop(monkeypatch):
    svc, model = _st_service(monkeypatch)

    vector = await svc.embed_async("hello")

    assert vector == [0.5, 0.5]
    assert model.threads and model.threads[0] != threading.get_ident()


@pytest.mark.asyncio
async def test_embed_batch_async_runs_off_the_event_loop(monkeypatch):
    svc, model = _st_service(monkeypatch)

    vectors = await svc.embed_batch_async(["a", "b"])

    assert vectors == [[0.5, 0.5], [0.5, 0.5]]
    assert model.threads and model.threads[0] != threading.get_ident()


@pytest.mark.asyncio
async def test_embed_async_local_mode_awaits_the_lm_client(monkeypatch):
    monkeypatch.setattr(settings, "use_local_llm", True)
    client = _LMClient([0.1, 0.2])
    svc = EmbeddingService(lm_client=client)

    assert await svc.embed_async("principle") == [0.1, 0.2]
    assert client.calls == ["principle"]


@pytest.mark.asyncio
async def test_sync_embed_inside_loop_warns_instead_of_failing_silently(monkeypatch, caplog):
    monkeypatch.setattr(settings, "use_local_llm", True)
    svc = EmbeddingService(lm_client=_LMClient([0.1]))

    with caplog.at_level(logging.WARNING, logger="life_graph.services.embeddings"):
        assert svc.embed("x") == []

    assert "embed_async" in caplog.text


def test_sync_embed_outside_loop_local_mode_still_works(monkeypatch):
    monkeypatch.setattr(settings, "use_local_llm", True)
    svc = EmbeddingService(lm_client=_LMClient([0.3]))

    assert svc.embed("x") == [0.3]


# ── Bulk-import worker ───────────────────────────────────────────────


class _Mem:
    def __init__(self, content):
        self.id = uuid.uuid4()
        self.content = content
        self.embedding = None
        self.embedding_model = "untouched"


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


class _WorkerSession:
    def __init__(self, memories):
        self._memories = memories
        self.statements = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        return False

    def add(self, _obj):
        pass

    async def execute(self, stmt):
        self.statements.append(stmt)
        return _Result(self._memories if stmt.is_select else [])

    async def commit(self):
        pass


class _AsyncOnlyService:
    """embed() is sync, as on the real service; awaiting it raised TypeError."""

    def __init__(self, vectors):
        self._vectors = dict(vectors)

    def embed(self, text):  # pragma: no cover - must not be used
        raise AssertionError("worker used the sync embed()")

    async def embed_async(self, text):
        return self._vectors.get(text, [])


@pytest.mark.asyncio
async def test_bulk_import_worker_writes_vectors_via_embed_async(monkeypatch):
    import life_graph.api.dependencies as deps
    import life_graph.workers.embeddings as worker

    monkeypatch.setattr(settings, "use_local_llm", True)
    monkeypatch.setattr(settings, "lm_embedding_model", "bge-m3")
    good, empty = _Mem("good"), _Mem("nothing comes back")
    session = _WorkerSession([good, empty])
    monkeypatch.setattr(worker, "async_session", lambda: session)
    monkeypatch.setattr(
        deps, "get_embedding_service", lambda: _AsyncOnlyService({"good": [0.4, 0.4]})
    )

    result = await worker.generate_embeddings_batch({}, [str(good.id), str(empty.id)], "acme")

    assert result == {"processed": 1, "failed": 1, "total": 2}
    assert good.embedding == [0.4, 0.4]
    assert good.embedding_model == "bge-m3" == current_embedding_model()
    # An empty vector is a failure: the row stays NULL for the re-embed job.
    assert empty.embedding is None
    assert empty.embedding_model == "untouched"
    select_stmt = next(s for s in session.statements if s.is_select)
    assert "tenant_id" in str(select_stmt.whereclause)
