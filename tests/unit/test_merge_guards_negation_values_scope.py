"""Near-duplicate merge guards for negation, value words and scope (2026-11-25).

The contradiction/false-merge eval (evals/contradiction) found the ingest
merge folding different facts into one memory: a negation outside the
use/like/prefer verbs ("Priya does not eat meat"), a number or colour word
("class four" / "class five", "white" / "grey"), and the same sentence for
two projects. Each case here was merged before the fix.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from life_graph.core.memory_manager import MemoryManager
from life_graph.evals.contradiction_benchmark import would_merge
from life_graph.extraction.rules import ExtractedFact
from life_graph.services.contradiction import (
    ContradictionDetector,
    differs_by_negation,
    differs_in_detail,
    differs_in_scope,
)

_EMB = [0.1, 0.2, 0.3]


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("Priya eats meat.", "Priya does not eat meat."),
        ("I am allergic to peanuts.", "I am not allergic to peanuts."),
        ("Arun drinks alcohol.", "Arun has never drunk alcohol."),
        ("Nila walks to school.", "Nila no longer walks to school."),
        ("The office is open on Saturday.", "The office isn't open on Saturday."),
        ("I can swim.", "I can't swim."),
        ("I can swim.", "I can’t swim."),
        ("I can swim.", "I cannot swim."),
        ("I take my coffee with sugar.", "I take my coffee without sugar."),
        ("Ravi has a passport.", "Ravi has no passport."),
        ("I sleep well.", "I dont sleep well."),
    ],
)
def test_a_negation_on_one_side_only_differs(a, b):
    assert differs_by_negation(a, b)
    assert differs_by_negation(b, a)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("Priya does not eat meat.", "Priya really does not eat meat."),
        ("I can't swim.", "I cannot swim at all."),
        ("Priya eats meat.", "Priya eats meat often."),
        ("I like pizza a lot", "I like pizza"),
        # "now", "know", "note" are not negators
        ("I know Tamil now.", "I know Tamil."),
        ("I keep a notebook.", "I keep a notebook for notes."),
    ],
)
def test_same_polarity_does_not_differ_by_negation(a, b):
    assert not differs_by_negation(a, b)


@pytest.mark.parametrize(
    ("a", "b", "differs"),
    [
        ("My son is in class four.", "My son is in class five.", True),
        ("We have three cats.", "We have two cats.", True),
        ("I walk ten km.", "I walk twenty km.", True),
        ("The loan is two lakh.", "The loan is three lakh.", True),
        ("Our car is a white hatchback.", "Our car is a grey hatchback.", True),
        ("I like the light theme.", "I like the dark theme.", True),
        ("I drink coffee.", "I drink green tea.", True),
        # same value in another spelling, or in both texts: still one fact
        ("Our car is grey.", "Our car is gray.", False),
        ("My son is in class four.", "My son is in class four now.", False),
        ("Our car is a white hatchback.", "Our car is a white hatchback indeed.", False),
        # "one" is mostly a pronoun, so it is not a value on its own
        ("The red one is mine.", "The red one is mine for sure.", False),
    ],
)
def test_number_and_colour_words_are_details(a, b, differs):
    assert differs_in_detail(a, b) is differs
    assert differs_in_detail(b, a) is differs


@pytest.mark.parametrize(
    ("a", "b", "differs"),
    [
        ({"project": "alpha"}, {"project": "beta"}, True),
        ({"module": "frontend"}, {"module": "backend"}, True),
        ({}, {"project": "beta"}, True),
        ({"project": "alpha"}, None, True),
        ({"project": "alpha", "source": "x"}, {"project": "alpha", "source": "y"}, False),
        ({"source": "telegram"}, {"source": "email"}, False),
        (None, None, False),
    ],
)
def test_differs_in_scope(a, b, differs):
    assert differs_in_scope(a, b) is differs
    assert differs_in_scope(b, a) is differs


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("We prefer pytest.", "We prefer unittest."),
        ("I switched to poetry.", "I use pip."),
        ("My favourite editor is vim.", "My favourite editor is emacs."),
    ],
)
def test_an_entity_swap_in_lowercase_differs(a, b):
    assert differs_in_detail(a, b)
    assert differs_in_detail(b, a)


def test_compatible_uses_are_not_a_swap():
    # Plain "use" on both sides is no swap; capitalised values still differ.
    assert not differs_in_detail("I use pip.", "I use pip daily.")


def test_would_merge_respects_scope():
    assert not would_merge(
        "Prefer spaces.", "Prefer spaces.", 0.95, {"module": "backend"}, {"module": "frontend"}
    )
    assert would_merge(
        "Prefer spaces.", "Prefer spaces always.", 0.95, {"module": "x"}, {"module": "x"}
    )


# ── Through MemoryManager._process_fact ──────────────────────


def _manager(existing_content, existing_properties=None):
    old = SimpleNamespace(
        id="00000000-0000-0000-0000-00000000000a",
        content=existing_content,
        status="active",
        importance=0.5,
        tags=[],
        properties=existing_properties or {},
        embedding=_EMB,
    )
    mgr = MemoryManager.__new__(MemoryManager)
    mgr._tagger = SimpleNamespace(score=lambda content, context: (0.5, "medium"))
    calls = SimpleNamespace(updates=[], stored=[])

    async def find_exact_duplicate(content_hash):
        return None

    async def find_similarity_candidates(embedding, limit=15):
        return [(old, 0.97)]  # above dedup_threshold

    async def touch(memory_id):
        return None

    async def update(memory_id, upd):
        calls.updates.append((memory_id, upd))
        return SimpleNamespace(id=memory_id)

    async def store(memory_create, **kwargs):
        calls.stored.append(memory_create)
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
        raise AssertionError("nothing is superseded here")

    async def queue(old_id, new_id, reason, *, applied=True):
        return None

    mgr.supersede = supersede
    mgr._queue_contradiction_approval = queue
    return mgr, calls


async def _ingest(mgr, content, context=None):
    fact = ExtractedFact(content=content, fact_type="fact", confidence=0.8)
    await mgr._process_fact(fact, context=context, source="test", embedding=_EMB)


@pytest.mark.parametrize(
    ("existing", "new"),
    [
        ("Priya eats meat.", "Priya does not eat meat."),
        ("I am allergic to peanuts.", "I am not allergic to peanuts."),
        ("My son is in class four.", "My son is in class five."),
        ("Our car is a white hatchback.", "Our car is a grey hatchback."),
    ],
)
@pytest.mark.asyncio
async def test_negated_or_changed_value_is_kept_as_its_own_memory(existing, new):
    mgr, calls = _manager(existing)
    await _ingest(mgr, new)
    assert calls.updates == [], "merged: the negation or the value was lost"
    assert [m.content for m in calls.stored] == [new]


@pytest.mark.asyncio
async def test_same_text_for_another_project_is_kept_as_its_own_memory():
    mgr, calls = _manager("Prefer spaces.", {"module": "frontend"})
    await _ingest(mgr, "Prefer spaces always.", context={"module": "backend"})
    assert calls.updates == []
    assert [m.content for m in calls.stored] == ["Prefer spaces always."]


@pytest.mark.asyncio
async def test_same_project_paraphrase_still_merges():
    mgr, calls = _manager("Prefer spaces.", {"module": "backend"})
    await _ingest(mgr, "Prefer spaces always.", context={"module": "backend"})
    assert calls.stored == []
    assert len(calls.updates) == 1
