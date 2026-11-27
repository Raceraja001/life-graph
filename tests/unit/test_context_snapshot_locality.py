"""The context snapshot never calls a model: not on success, not on failure.

The real retrieve() runs (judge off) over a stand-in store; any chat client
being built or called fails the test. The query embedding is the only model
touch, and when it fails the snapshot says so instead of trying anything else.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from life_graph import runtime
from life_graph.core.tenant import tenant_scope
from life_graph.services.llm import client as llm_client
from life_graph.services.llm import resilient
from life_graph.services.memory import retrieval, snapshot
from life_graph.services.memory.snapshot import assemble_context

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)


class _ForbiddenError(AssertionError):
    pass


def _boom(*a, **kw):
    raise _ForbiddenError("a model client was used by the context snapshot")


def _mem(content):
    when = NOW - timedelta(days=3)
    return SimpleNamespace(
        id=uuid.uuid4(),
        content=content,
        status="active",
        source_type="chat",
        trust_tier="self",
        extraction_tier=None,
        properties={},
        tags=None,
        created_at=when,
        valid_from=when,
        valid_until=None,
        supersedes=None,
        superseded_by=None,
        last_reinforced=None,
        importance=0.5,
        access_count=0,
        last_accessed=None,
        confidence=0.9,
        trust_score=0.9,
    )


@pytest.fixture
def no_models(monkeypatch):
    """Every way to a chat model raises: client construction, chat, the judge."""
    from life_graph.config import settings
    from life_graph.services import entities

    monkeypatch.setattr(llm_client.LMStudioClient, "__init__", _boom)
    monkeypatch.setattr(resilient.ResilientLLM, "__init__", _boom)
    monkeypatch.setattr(runtime, "get_lm_client", _boom)
    monkeypatch.setattr(retrieval, "judge", _boom)

    async def none(tenant_id, text_):
        return []

    async def empty(*a, **kw):
        return []

    monkeypatch.setattr(entities, "known_in_text", none)
    monkeypatch.setattr(settings, "memory_links", False)
    monkeypatch.setattr(snapshot, "_memory_conflicts", empty)
    monkeypatch.setattr(snapshot, "_matching_decisions", empty)
    monkeypatch.setattr(snapshot, "_superseded_decisions", empty)
    monkeypatch.setattr(snapshot, "_open_intentions", empty)
    monkeypatch.setattr(snapshot, "_current_decisions", empty)
    monkeypatch.setattr(snapshot, "_due_intentions", empty)
    with tenant_scope("t-local"):
        yield


def _store(monkeypatch, hits, *, fail=False):
    calls = []

    class _Store:
        async def hybrid_search(self, **kw):
            calls.append(kw)
            if fail:
                raise ConnectionError("database down")
            return [(m, 0.7) for m in hits]

    monkeypatch.setattr(runtime, "get_store", lambda: _Store())
    return calls


def _embedder(monkeypatch, behaviour):
    calls = []

    class _Manager:
        async def generate_embedding(self, text_):
            calls.append(text_)
            if behaviour == "raise":
                raise TimeoutError("embedder down")
            return None if behaviour == "none" else [0.1, 0.2]

    monkeypatch.setattr(runtime, "get_memory_manager", lambda: _Manager())
    return calls


async def test_a_snapshot_runs_the_real_retrieve_without_any_model(monkeypatch, no_models):
    mems = [_mem("the car insurance renews in March"), _mem("frontend runs on 3006")]
    store_calls = _store(monkeypatch, mems)
    embeds = _embedder(monkeypatch, "ok")
    snap = await assemble_context("when does the car insurance renew?", now=NOW)
    assert not snap.insufficient
    assert {i.source_ref.id for i in snap.items} == {str(m.id) for m in mems}
    # One embedding, reused by both searches.
    assert len(embeds) == 1 and len(store_calls) == 2


@pytest.mark.parametrize("behaviour", ["none", "raise"])
async def test_embedding_failure_is_insufficient_not_a_fallback(monkeypatch, no_models, behaviour):
    store_calls = _store(monkeypatch, [_mem("x")])
    _embedder(monkeypatch, behaviour)
    snap = await assemble_context("anything", now=NOW)
    assert snap.insufficient is True and snap.items == ()
    assert "could not be embedded" in snap.explanation
    assert store_calls == []  # memory was not searched any other way


async def test_a_database_failure_is_insufficient_and_holds_nothing(monkeypatch, no_models):
    _store(monkeypatch, [], fail=True)
    _embedder(monkeypatch, "ok")
    snap = await assemble_context("anything", now=NOW)
    assert snap.insufficient is True and snap.items == ()
    assert "failed" in snap.explanation
