"""The ingest near-duplicate merge keeps distinct facts and provenance (Stage 0 M1.5).

At cosine >= dedup_threshold (0.92) a new fact used to be merged into the
existing memory: its text dropped, the existing row's properties overwritten.
"Priya's birthday is 3 May" vs "… 4 May", or the same sentence about two
people, collapsed into one memory.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from life_graph.core.memory_manager import MemoryManager
from life_graph.extraction.rules import ExtractedFact
from life_graph.services.contradiction import ContradictionDetector, differs_in_detail

_EMB = [0.1, 0.2, 0.3]
_OLD = "00000000-0000-0000-0000-00000000000a"
_NEW = "00000000-0000-0000-0000-00000000000b"


def _memory(content, properties=None):
    return SimpleNamespace(
        id=_OLD,
        content=content,
        status="active",
        importance=0.5,
        tags=[],
        properties=properties or {},
        embedding=_EMB,
    )


def _manager(candidates):
    mgr = MemoryManager.__new__(MemoryManager)
    mgr._tagger = SimpleNamespace(score=lambda content, context: (0.5, "medium"))
    calls = SimpleNamespace(updates=[], stored=[], queued=[])

    async def find_exact_duplicate(content_hash):
        return None

    async def find_similarity_candidates(embedding, limit=15):
        return candidates

    async def touch(memory_id):
        return None

    async def update(memory_id, upd):
        calls.updates.append((memory_id, upd))
        return SimpleNamespace(id=memory_id)

    async def store(memory_create, **kwargs):
        calls.stored.append(memory_create)
        return SimpleNamespace(id=_NEW)

    mgr._store = SimpleNamespace(
        find_exact_duplicate=find_exact_duplicate,
        find_similarity_candidates=find_similarity_candidates,
        touch=touch,
        update=update,
        store=store,
    )
    mgr._contradiction_detector = ContradictionDetector(store=None)

    async def supersede(old_id, new_id, reason):
        raise AssertionError("nothing is superseded here")

    async def queue(old_id, new_id, reason, *, applied=True):
        calls.queued.append((old_id, new_id))

    mgr.supersede = supersede
    mgr._queue_contradiction_approval = queue
    return mgr, calls


async def _ingest(mgr, content, context=None):
    fact = ExtractedFact(content=content, fact_type="fact", confidence=0.8)
    await mgr._process_fact(fact, context=context, source="test", embedding=_EMB)


@pytest.mark.parametrize(
    ("existing", "new"),
    [
        ("Priya's birthday is 3 May", "Priya's birthday is 4 May"),
        ("Priya's birthday is 3 May", "Maha's birthday is 3 May"),
        ("The rent is 18000 a month", "The rent is 21000 a month"),
        ("Standup moved to Tuesday", "Standup moved to Thursday"),
        ("I fly to Chennai on the 12th", "I fly to Bangalore on the 12th"),
    ],
)
@pytest.mark.asyncio
async def test_a_near_duplicate_with_a_different_value_is_kept_as_its_own_memory(existing, new):
    mgr, calls = _manager([(_memory(existing), 0.97)])  # above dedup_threshold
    await _ingest(mgr, new)
    assert calls.updates == [], "merged: one of the two values was lost"
    assert [m.content for m in calls.stored] == [new]


@pytest.mark.asyncio
async def test_a_true_duplicate_still_merges_and_keeps_both_texts_and_the_old_provenance():
    old = _memory(
        "Priya's birthday is 3 May",
        properties={"capture_event_id": "cap-1", "source": "telegram", "entities": ["Priya"]},
    )
    mgr, calls = _manager([(old, 0.98)])
    await _ingest(mgr, "priya's birthday is on 3 May", context={"source": "email", "x": 1})

    assert calls.stored == []
    ((memory_id, upd),) = calls.updates
    assert memory_id == _OLD
    props = upd.properties
    assert props["capture_event_id"] == "cap-1" and props["source"] == "telegram"
    assert props["entities"] == ["Priya"]
    (seen,) = props["merged_observations"]
    assert seen["content"] == "priya's birthday is on 3 May"
    assert seen["source"] == "email" and "x" not in seen
    assert seen["similarity"] == 0.98


@pytest.mark.parametrize(
    ("a", "b", "differs"),
    [
        ("Priya's birthday is 3 May", "Priya's birthday is 4 May", True),
        ("Priya's birthday is 3 May", "Maha's birthday is 3 May", True),
        ("I like pizza", "I like pizza a lot", False),
        ("I like coffee", "I like Coffee in the morning", False),
        ("My sister lives in Pune", "my sister lives in pune now", False),
        ("Meeting at 10:30", "Meeting at 11:00", True),
        ("I use Python", "I use Python 3.12", True),
    ],
)
def test_differs_in_detail(a, b, differs):
    assert differs_in_detail(a, b) is differs
