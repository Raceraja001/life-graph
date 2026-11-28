"""One attribute under two slot keys (services/memory/supersession.py
``same_attribute`` / ``slot_pairs``, flag ``ingest_slot_pairing``).

The local model's slot keys drift between messages: the ingest eval's
qwen3:14b recording filed the old take-home salary as ``money.budget`` and the
new one as ``work.salary``, so the same-slot rule never paired them. Plain
stand-ins only.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from life_graph.config import settings
from life_graph.core.memory_manager import MemoryManager
from life_graph.core.tenant import tenant_scope
from life_graph.extraction.rules import ExtractedFact
from life_graph.services.memory import supersession

NEW_ID = "00000000-0000-0000-0000-00000000000b"
SALARY_OLD = "The owner's take-home salary is ₹1,50,000 a month."
SALARY_NEW = "The owner's take-home salary is ₹1,80,000 a month after the promotion."


# ── same_attribute (pure) ─────────────────────────────────────


@pytest.mark.parametrize(
    ("new_slot", "new", "old_slot", "old"),
    [
        # The recorded drift: one key names the attribute, the other nothing in it.
        ("work.salary", SALARY_NEW, "money.budget", SALARY_OLD),
        ("money.budget", SALARY_NEW, "work.salary", SALARY_OLD),
        # Someone's field under two spellings, a time word after the value.
        (
            "family.arjun.pay",
            "Arjun's take-home pay is ₹48,000 a month from November.",
            "family.arjun.take_home_pay",
            "Arjun's take-home pay is ₹65,000 a month.",
        ),
        # Same topic, both keys name it.
        (
            "money.car_loan_emi",
            "The owner's car loan EMI is ₹9,000 a month now.",
            "money.emi",
            "The owner's car loan EMI is ₹11,500 a month.",
        ),
        # A name as the value.
        (
            "vehicles.car",
            "The owner's car is a Nexon.",
            "vehicles.current_car",
            "The owner's car is a Swift.",
        ),
        # Tamil script in the attribute is one word (D10), and the same word in both.
        (
            "family.amma.dose",
            "Amma's மருந்து dose is 20 mg.",
            "family.amma.medicine_dose",
            "Amma's மருந்து dose is 10 mg.",
        ),
    ],
)
def test_one_attribute_under_two_keys(new_slot, new, old_slot, old):
    assert supersession.same_attribute(new_slot, new, old_slot, old)


@pytest.mark.parametrize(
    ("new_slot", "new", "old_slot", "old"),
    [
        # The same key is the plain same-slot rule's job, not this one.
        ("work.salary", SALARY_NEW, "work.salary", SALARY_OLD),
        # Something else about the attribute: no value right after "is".
        (
            "work.payday",
            "The owner's salary is credited on the 1st of every month.",
            "work.salary",
            "The owner's salary is ₹1,50,000 a month.",
        ),
        # Another attribute: the words before "is" differ.
        (
            "money.details",
            "The owner's salary account is with HDFC Bank.",
            "work.salary",
            "The owner's salary is ₹1,50,000 a month.",
        ),
        # Both keys name it from two topics: the model kept them apart.
        (
            "health.goal",
            "The owner's goal is 42 km at the Chennai marathon.",
            "money.goal",
            "The owner's goal is ₹6,00,000 in the emergency fund.",
        ),
        # A key names a word only one sentence has (another child).
        (
            "family.anu.fee",
            "The owner's fee for Anu's school is ₹45,000 a year.",
            "family.ila.school_fee",
            "The owner's fee for Ila's school is ₹40,000 a year.",
        ),
        # A number where the old value was a name, and another word after it.
        (
            "vehicles.car_age",
            "The owner's car is 5 years old.",
            "vehicles.car",
            "The owner's car is a white Nexon.",
        ),
        # Neither key names the attribute.
        (
            "money.budget",
            "The owner's take-home salary is ₹1,80,000 a month.",
            "money.income",
            SALARY_OLD,
        ),
        # No "is"/"are" frame at all.
        (
            "family.arjun.pay",
            "Arjun's salary dropped to ₹48,000 a month.",
            "family.arjun.salary",
            "Arjun's salary is ₹65,000 a month.",
        ),
        # The same value: a restatement, not a change.
        (
            "work.salary",
            "The owner's take-home salary is ₹1,50,000 a month now.",
            "money.budget",
            SALARY_OLD,
        ),
        # A past value ("was") is no frame: two past values can both be true.
        (
            "work.salary",
            "The owner's take-home salary was ₹1,80,000 a month.",
            "money.budget",
            "The owner's take-home salary was ₹1,50,000 a month.",
        ),
        # A Tamil word that differs by a case ending is another word, not the same one.
        (
            "family.amma.dose",
            "Amma's மருந்தின் dose is 20 mg.",
            "family.amma.medicine_dose",
            "Amma's மருந்து dose is 10 mg.",
        ),
        ("", SALARY_NEW, "money.budget", SALARY_OLD),
    ],
)
def test_not_one_attribute(new_slot, new, old_slot, old):
    assert not supersession.same_attribute(new_slot, new, old_slot, old)


# ── slot_pairs (the candidates) ───────────────────────────────


def _old(content=SALARY_OLD, *, status="active", **props):
    return SimpleNamespace(
        id=uuid.uuid4(), content=content, status=status, properties={"slot": "money.budget"} | props
    )


def _pairs(candidates, **kw):
    args = {
        "content": SALARY_NEW,
        "slot": "work.salary",
        "subject": "owner",
        "context": None,
        "candidates": [(c, 0.9) for c in candidates],
        "taken": set(),
    } | kw
    return supersession.slot_pairs(**args)


def test_a_pair_is_found_among_the_candidates():
    old = _old()
    found = _pairs([old])
    assert [i for i, _ in found] == [str(old.id)]
    assert "work.salary" in found[0][1] and "money.budget" in found[0][1]


@pytest.mark.parametrize(
    ("old_kw", "pair_kw"),
    [
        ({"status": "pending"}, {}),
        ({"polarity": "negate"}, {}),
        ({"certainty": "hedged"}, {}),
        ({"subject": "Arjun"}, {}),  # another person's salary
        ({"project": "farmlink"}, {"context": {"project": "jarvis"}}),  # another scope
        ({"slot": None}, {}),
        ({"slot": "not a slot"}, {}),
    ],
)
def test_no_pair(old_kw, pair_kw):
    assert _pairs([_old(**old_kw)], **pair_kw) == []


def test_a_taken_memory_is_not_paired_again():
    old = _old()
    assert _pairs([old], taken={str(old.id)}) == []


# ── The save path ─────────────────────────────────────────────


def _manager(candidates):
    mgr = MemoryManager.__new__(MemoryManager)
    mgr._tagger = SimpleNamespace(score=lambda content, context: (0.5, "medium"))
    calls = SimpleNamespace(stored=[], superseded=[], queued=[])

    async def find_exact_duplicate(content_hash):
        return None

    async def find_similarity_candidates(embedding, limit=15):
        return candidates

    async def store(memory_create, **kwargs):
        calls.stored.append((memory_create, kwargs))
        return SimpleNamespace(id=NEW_ID, tenant_id="t1")

    mgr._store = SimpleNamespace(
        find_exact_duplicate=find_exact_duplicate,
        find_similarity_candidates=find_similarity_candidates,
        store=store,
    )

    async def check_candidates(content, active, embedding, new_properties=None):
        return []

    async def no_op(*a, **k):
        return None

    async def no_same_slot(slot):
        return []

    async def supersede(old_id, new_id, reason, **kw):
        calls.superseded.append((old_id, new_id, kw))

    async def queue(old_id, new_id, reason, **kw):
        calls.queued.append((old_id, kw))

    mgr._contradiction_detector = SimpleNamespace(check_candidates=check_candidates)
    mgr._file_slot = no_op
    mgr._learn_names = no_op
    mgr._same_slot_active = no_same_slot
    mgr.supersede = supersede
    mgr._queue_contradiction_approval = queue
    return mgr, calls


@pytest.fixture
def low_items(monkeypatch):
    filed = []

    async def file(tenant, old_id, new_id, reason, **kw):
        filed.append(old_id)
        return True

    monkeypatch.setattr(supersession, "file_possible_update", file)
    return filed


async def _run(mgr, trust="self", **kw):
    fact = ExtractedFact(
        **{
            "content": SALARY_NEW,
            "fact_type": "fact",
            "confidence": 1.0,
            "slot": "work.salary",
        }
        | kw
    )
    with tenant_scope("t1"):
        await mgr._process_fact(
            fact, context=None, source="test", trust_tier=trust, embedding=[0.1, 0.2]
        )


@pytest.mark.asyncio
async def test_with_both_flags_the_owner_s_new_value_replaces_the_old_key(monkeypatch, low_items):
    monkeypatch.setattr(settings, "dedup_enabled", False)
    monkeypatch.setattr(settings, "ingest_supersession_tiers", True)
    monkeypatch.setattr(settings, "ingest_slot_pairing", True)
    old = _old()
    mgr, calls = _manager([(old, 0.9)])

    await _run(mgr)

    assert calls.stored[0][1]["status"] == "active"
    assert calls.superseded == [(str(old.id), NEW_ID, {"world_change": True})]
    assert calls.queued == [(str(old.id), {"applied": True, "confidence": "high"})]
    assert low_items == []


@pytest.mark.asyncio
async def test_outside_text_under_another_key_only_waits(monkeypatch, low_items):
    monkeypatch.setattr(settings, "dedup_enabled", False)
    monkeypatch.setattr(settings, "ingest_supersession_tiers", True)
    monkeypatch.setattr(settings, "ingest_slot_pairing", True)
    old = _old()
    mgr, calls = _manager([(old, 0.9)])

    await _run(mgr, trust="external")

    assert calls.superseded == []
    assert calls.queued == [(str(old.id), {"applied": False, "confidence": "medium"})]


@pytest.mark.asyncio
@pytest.mark.parametrize(("tiers", "pairing"), [(True, False), (False, True), (False, False)])
async def test_without_both_flags_another_key_is_not_paired(monkeypatch, low_items, tiers, pairing):
    monkeypatch.setattr(settings, "dedup_enabled", False)
    monkeypatch.setattr(settings, "ingest_supersession_tiers", tiers)
    monkeypatch.setattr(settings, "ingest_slot_pairing", pairing)
    old = _old()
    mgr, calls = _manager([(old, 0.9)])

    await _run(mgr)

    assert calls.superseded == []
    assert calls.queued == []
