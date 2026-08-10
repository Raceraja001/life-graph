# tests/unit/test_process_fact_merged_candidates.py
"""Unit tests for MemoryManager._process_fact()'s merged candidate-pool
logic: dedup near-match and the contradiction check now derive from one
find_similarity_candidates() call instead of two separate pgvector queries.
Covers: near-match short-circuits before contradiction check ever runs, and
the contradiction check only sees "active" status candidates."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from life_graph.core.memory_manager import MemoryManager
from life_graph.extraction.rules import ExtractedFact


def _memory(id_, *, status="active", importance=0.5, tags=None, properties=None, content=""):
    return SimpleNamespace(
        id=id_,
        status=status,
        importance=importance,
        tags=tags or [],
        properties=properties or {},
        content=content,
    )


def _make_manager(monkeypatch, *, candidates, exact_duplicate=None):
    mgr = MemoryManager.__new__(MemoryManager)
    mgr._tagger = SimpleNamespace(score=lambda content, context: (0.5, "medium"))

    async def fake_find_exact_duplicate(content_hash):
        return exact_duplicate

    candidate_calls = []

    async def fake_find_similarity_candidates(embedding, limit=15):
        candidate_calls.append(limit)
        return candidates

    touched = []

    async def fake_touch(memory_id):
        touched.append(memory_id)

    updated_calls = []

    async def fake_update(memory_id, update):
        updated_calls.append((memory_id, update))
        return SimpleNamespace(id=memory_id)

    stored_calls = []

    async def fake_store(memory_create, embedding=None, trust_tier=None):
        stored_calls.append(memory_create)
        return SimpleNamespace(id="new-memory", properties=memory_create.properties)

    mgr._store = SimpleNamespace(
        find_exact_duplicate=fake_find_exact_duplicate,
        find_similarity_candidates=fake_find_similarity_candidates,
        touch=fake_touch,
        update=fake_update,
        store=fake_store,
    )

    check_candidates_calls = []

    async def fake_check_candidates(content, active_candidates, embedding):
        check_candidates_calls.append(list(active_candidates))
        return []

    mgr._contradiction_detector = SimpleNamespace(check_candidates=fake_check_candidates)

    return mgr, candidate_calls, touched, updated_calls, stored_calls, check_candidates_calls


@pytest.mark.asyncio
async def test_near_match_short_circuits_before_contradiction_check(monkeypatch):
    near_dup = _memory("existing-1", status="active", content="I like pizza")
    mgr, candidate_calls, touched, updated_calls, stored_calls, check_calls = _make_manager(
        monkeypatch, candidates=[(near_dup, 0.95)]
    )
    fact = ExtractedFact(content="I like pizza a lot", fact_type="preference", confidence=0.8)

    result = await mgr._process_fact(fact, context=None, source="test", embedding=[0.1, 0.2])

    assert candidate_calls == [15]  # find_similarity_candidates called once
    assert updated_calls and updated_calls[0][0] == "existing-1"  # merge path taken
    assert touched == ["existing-1"]
    assert check_calls == []  # contradiction check never reached
    assert stored_calls == []  # no new memory created
    assert result is not None


@pytest.mark.asyncio
async def test_contradiction_check_only_sees_active_candidates(monkeypatch):
    active = _memory("active-1", status="active", content="I always use MongoDB")
    pending = _memory("pending-1", status="pending", content="I use Redis")
    mgr, candidate_calls, touched, updated_calls, stored_calls, check_calls = _make_manager(
        monkeypatch, candidates=[(active, 0.8), (pending, 0.78)]  # below dedup_threshold (0.92)
    )
    fact = ExtractedFact(content="I don't use MongoDB", fact_type="anti_preference", confidence=0.8)

    result = await mgr._process_fact(fact, context=None, source="test", embedding=[0.1, 0.2])

    assert updated_calls == []  # no near-match merge (below threshold)
    assert len(check_calls) == 1
    passed_candidates = check_calls[0]
    assert passed_candidates == [active]  # pending filtered out
    assert stored_calls  # new memory was stored
    assert result is not None
