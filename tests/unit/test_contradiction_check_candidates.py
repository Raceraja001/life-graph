# tests/unit/test_contradiction_check_candidates.py
"""Unit tests for ContradictionDetector.check_candidates() — the DB-lookup-free
variant added so MemoryManager._process_fact() can reuse a candidate pool it
already fetched (find_similarity_candidates) instead of paying for a second
pgvector query. Confirms check_candidates() finds the same contradictions
check() would, and that check() still delegates to the same logic."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from life_graph.services.contradiction import ContradictionDetector


def _memory(content: str, embedding=None, status="active", properties=None):
    return SimpleNamespace(
        id="existing-1",
        content=content,
        status=status,
        properties=properties or {},
        embedding=embedding,
    )


@pytest.mark.asyncio
async def test_check_candidates_finds_negation_contradiction():
    detector = ContradictionDetector(store=None)  # no DB access needed
    existing = _memory("I always use MongoDB")

    contradictions = await detector.check_candidates(
        "I don't use MongoDB", [existing], new_embedding=[0.1, 0.2, 0.3]
    )

    assert len(contradictions) == 1
    assert contradictions[0].conflict_type == "negation"
    assert contradictions[0].existing_memory_id == "existing-1"


@pytest.mark.asyncio
async def test_check_candidates_no_contradiction_for_unrelated_content():
    detector = ContradictionDetector(store=None)
    existing = _memory("The weather is nice today")

    contradictions = await detector.check_candidates(
        "I enjoy reading books", [existing], new_embedding=[0.1, 0.2, 0.3]
    )

    assert contradictions == []


@pytest.mark.asyncio
async def test_check_candidates_empty_list_returns_empty():
    detector = ContradictionDetector(store=None)

    contradictions = await detector.check_candidates(
        "anything", [], new_embedding=[0.1, 0.2, 0.3]
    )

    assert contradictions == []


@pytest.mark.asyncio
async def test_check_and_check_candidates_agree_given_the_same_pool():
    """check() fetches its own candidates via search_similar; check_candidates()
    is handed them directly. Given the same pool, they must produce identical
    contradictions — check() is only a thin DB-fetch wrapper around the same
    underlying logic check_candidates() calls directly."""

    class FakeStore:
        async def search_similar(self, embedding, limit, filters):
            return [_memory("I always use MongoDB")]

    detector = ContradictionDetector(store=FakeStore())
    candidates = [_memory("I always use MongoDB")]

    via_check = await detector.check("I don't use MongoDB", [0.1, 0.2, 0.3])
    via_candidates = await detector.check_candidates(
        "I don't use MongoDB", candidates, [0.1, 0.2, 0.3]
    )

    assert len(via_check) == len(via_candidates) == 1
    assert via_check[0].conflict_type == via_candidates[0].conflict_type
