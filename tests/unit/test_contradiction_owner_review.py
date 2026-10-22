"""Contradiction handling must not silently change the owner's memory.

Review 2026-10-22 found that contradiction handling rewrote memory without
the owner: a still-pending extraction superseded an active memory at once;
any two "use/like ..." statements with different objects counted as a
contradiction; the scope check looked only at the old memory; a candidate
with no embedding counted as similar; and dedup could merge "I use X" with
"I don't use X". These tests pin the fixed behaviour without a database.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from life_graph.config import settings
from life_graph.core.memory_manager import MemoryManager
from life_graph.extraction.rules import ExtractedFact
from life_graph.services.contradiction import (
    ContradictionDetector,
    _check_entity_swap,
    _check_scope_difference,
    differs_by_negation,
)

_EMB = [0.1, 0.2, 0.3]


def _memory(content, *, id_="old-1", embedding=_EMB, status="active", properties=None):
    return SimpleNamespace(
        id=id_,
        content=content,
        status=status,
        importance=0.5,
        tags=[],
        properties=properties or {},
        embedding=embedding,
    )


async def _detect(new, old, **kw):
    detector = ContradictionDetector(store=None)
    return await detector.check_candidates(new, [old], _EMB, **kw)


# ── Item 2: exclusive verbs only ──────────────────────────────


class TestExclusiveSwap:
    @pytest.mark.asyncio
    async def test_compatible_use_statements_do_not_contradict(self):
        assert await _detect("I use Python for scripts", _memory("I use VS Code")) == []

    @pytest.mark.parametrize(
        ("new", "old"),
        [
            ("I use FastAPI", "I use Django"),
            ("I like tea", "I like coffee"),
            ("I have a cat", "I have a dog"),
        ],
    )
    def test_plain_verbs_are_not_swaps(self, new, old):
        assert _check_entity_swap(new, old) is None

    @pytest.mark.parametrize(
        ("new", "old"),
        [
            ("I prefer PostgreSQL", "I prefer MongoDB"),
            ("I switched to FastAPI", "I use Django"),
            ("I use Django", "I switched to FastAPI"),
            ("My favourite editor is Helix", "My favorite editor is Vim"),
        ],
    )
    def test_exclusive_verbs_are_swaps(self, new, old):
        assert _check_entity_swap(new, old) is not None

    def test_favourites_for_different_slots_are_not_swaps(self):
        assert _check_entity_swap("My favourite food is dosa", "My favourite editor is Vim") is None

    def test_different_purposes_are_not_swaps(self):
        assert (
            _check_entity_swap("I prefer SQLite for tests", "I prefer Postgres for production")
            is None
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("new", "old"),
        [
            ("I no longer use Vim", "I use Vim"),
            ("I use VS Code instead of Vim", "I use Vim"),
            ("I don't use MongoDB", "I use MongoDB"),
        ],
    )
    async def test_explicit_change_of_mind_still_supersedes(self, new, old):
        found = await _detect(new, _memory(old))
        assert len(found) == 1
        assert found[0].resolution == "supersede"


# ── Item 2: symmetric scope ───────────────────────────────────


class TestSymmetricScope:
    @pytest.mark.asyncio
    async def test_new_memory_scoped_to_a_project_keeps_both(self):
        found = await _detect(
            "I prefer MongoDB",
            _memory("I prefer PostgreSQL"),
            new_properties={"project": "uzhavu"},
        )
        assert [c.resolution for c in found] == ["scope"]

    @pytest.mark.asyncio
    async def test_old_memory_scoped_keeps_both(self):
        found = await _detect(
            "I prefer MongoDB", _memory("I prefer PostgreSQL", properties={"module": "api"})
        )
        assert [c.resolution for c in found] == ["scope"]

    @pytest.mark.asyncio
    async def test_same_project_supersedes(self):
        found = await _detect(
            "I prefer MongoDB",
            _memory("I prefer PostgreSQL", properties={"project": "lg"}),
            new_properties={"project": "lg"},
        )
        assert [c.resolution for c in found] == ["supersede"]

    @pytest.mark.asyncio
    async def test_negation_in_a_different_project_keeps_both(self):
        found = await _detect(
            "I don't use MongoDB", _memory("I use MongoDB"), new_properties={"project": "a"}
        )
        assert [c.resolution for c in found] == ["scope"]

    def test_unscoped_pair_has_no_scope_difference(self):
        assert _check_scope_difference(_memory("x"), {}) is None


# ── Item 2: similarity ────────────────────────────────────────


class TestSimilarity:
    @pytest.mark.asyncio
    async def test_missing_embedding_is_skipped_not_assumed_similar(self):
        assert await _detect("I don't use MongoDB", _memory("I use MongoDB", embedding=None)) == []

    @pytest.mark.asyncio
    async def test_threshold_is_a_setting(self, monkeypatch):
        # cos([0.1,0.2,0.3], [0.3,0.2,0.1]) ~= 0.71
        old = _memory("I use MongoDB", embedding=[0.3, 0.2, 0.1])
        monkeypatch.setattr(settings, "contradiction_similarity_threshold", 0.75)
        assert await _detect("I don't use MongoDB", old) == []
        monkeypatch.setattr(settings, "contradiction_similarity_threshold", 0.7)
        assert len(await _detect("I don't use MongoDB", old)) == 1


# ── Items 1 and 3: MemoryManager._process_fact ────────────────


def _manager(candidates):
    """A MemoryManager over fakes; the real ContradictionDetector runs."""
    mgr = MemoryManager.__new__(MemoryManager)
    mgr._tagger = SimpleNamespace(score=lambda content, context: (0.5, "medium"))
    calls = SimpleNamespace(updated=[], stored=[], superseded=[], queued=[])

    async def find_exact_duplicate(content_hash):
        return None

    async def find_similarity_candidates(embedding, limit=15):
        return candidates

    async def touch(memory_id):
        return None

    async def update(memory_id, upd):
        calls.updated.append(memory_id)
        return SimpleNamespace(id=memory_id)

    async def store(memory_create, **kwargs):
        calls.stored.append((memory_create, kwargs))
        return SimpleNamespace(id="00000000-0000-0000-0000-00000000000b")

    mgr._store = SimpleNamespace(
        find_exact_duplicate=find_exact_duplicate,
        find_similarity_candidates=find_similarity_candidates,
        touch=touch,
        update=update,
        store=store,
    )
    mgr._contradiction_detector = ContradictionDetector(store=None)

    async def supersede(old_id, new_id, reason):
        calls.superseded.append((old_id, new_id))

    async def queue(old_id, new_id, reason, *, applied=True):
        calls.queued.append((old_id, new_id, applied))

    mgr.supersede = supersede
    mgr._queue_contradiction_approval = queue
    return mgr, calls


class TestDeferredSupersede:
    @pytest.mark.asyncio
    async def test_pending_memory_supersedes_nothing(self):
        old = _memory("I prefer PostgreSQL", id_="00000000-0000-0000-0000-00000000000a")
        mgr, calls = _manager([(old, 0.8)])
        fact = ExtractedFact(content="I prefer MongoDB", fact_type="preference", confidence=0.8)

        await mgr._process_fact(fact, context=None, source="test", embedding=_EMB)

        _, kwargs = calls.stored[0]
        assert kwargs["status"] == "pending"
        assert calls.superseded == []  # the old memory is untouched
        assert calls.queued == [(str(old.id), "00000000-0000-0000-0000-00000000000b", False)]
        props = calls.stored[0][0].properties
        assert props["contradictions"][0]["existing_id"] == str(old.id)

    @pytest.mark.asyncio
    async def test_explicit_owner_save_supersedes_at_once_and_stays_undoable(self):
        old = _memory("I prefer PostgreSQL", id_="00000000-0000-0000-0000-00000000000a")
        mgr, calls = _manager([(old, 0.8)])
        fact = ExtractedFact(content="I prefer MongoDB", fact_type="explicit_save", confidence=0.95)

        await mgr._process_fact(
            fact, context=None, source="test", trust_tier="self", embedding=_EMB
        )

        assert calls.stored[0][1]["status"] == "active"
        assert calls.superseded == [(str(old.id), "00000000-0000-0000-0000-00000000000b")]
        assert calls.queued[0][2] is True  # approval queued: reject undoes it

    @pytest.mark.asyncio
    async def test_compatible_statement_queues_nothing(self):
        mgr, calls = _manager([(_memory("I use VS Code"), 0.8)])
        fact = ExtractedFact(
            content="I use Python for scripts", fact_type="tool_usage", confidence=0.8
        )

        await mgr._process_fact(fact, context=None, source="test", embedding=_EMB)

        assert calls.queued == [] and calls.superseded == []
        assert "contradictions" not in calls.stored[0][0].properties


class TestDedupKeepsNegation:
    def test_differs_by_negation(self):
        assert differs_by_negation("I don't use MongoDB", "I use MongoDB")
        assert not differs_by_negation("I like pizza a lot", "I like pizza")

    @pytest.mark.asyncio
    async def test_negated_near_duplicate_is_not_merged(self):
        old = _memory("I use MongoDB", id_="00000000-0000-0000-0000-00000000000a")
        mgr, calls = _manager([(old, 0.97)])  # above dedup_threshold (0.92)
        fact = ExtractedFact(
            content="I don't use MongoDB", fact_type="anti_preference", confidence=0.8
        )

        await mgr._process_fact(fact, context=None, source="test", embedding=_EMB)

        assert calls.updated == []  # no merge
        assert len(calls.stored) == 1  # stored as its own memory
        assert calls.queued == [(str(old.id), "00000000-0000-0000-0000-00000000000b", False)]

    @pytest.mark.asyncio
    async def test_plain_near_duplicate_still_merges(self):
        old = _memory("I like pizza", id_="00000000-0000-0000-0000-00000000000a")
        mgr, calls = _manager([(old, 0.97)])
        fact = ExtractedFact(content="I like pizza a lot", fact_type="preference", confidence=0.8)

        await mgr._process_fact(fact, context=None, source="test", embedding=_EMB)

        assert calls.updated == [old.id]
        assert calls.stored == []
