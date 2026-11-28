"""ADR M8 §5.2 step 5: the world-change end and the supersession tiers.

Plain stand-ins only; tests/integration/test_supersession_tiers_pg.py runs
the same rules against Postgres (the daily cap, the undo paths).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from life_graph.config import settings
from life_graph.core.memory_manager import MemoryManager
from life_graph.core.tenant import tenant_scope
from life_graph.extraction.rules import ExtractedFact
from life_graph.services.memory import supersession

NOW = datetime(2026, 11, 28, 9, 30, tzinfo=UTC)
MARCH = datetime(2026, 3, 1, tzinfo=UTC)
JAN = datetime(2026, 1, 1, tzinfo=UTC)
_EMB = [0.1, 0.2, 0.3]
NEW_ID = "00000000-0000-0000-0000-00000000000b"
OLD_ID = "00000000-0000-0000-0000-00000000000a"


def _mem(status="active", *, valid_from=None, created_at=NOW, valid_until=None, **props):
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id="t1",
        status=status,
        superseded_by=None,
        supersedes=None,
        updated_at=None,
        valid_from=valid_from or created_at,
        created_at=created_at,
        valid_until=valid_until,
        properties=dict(props),
    )


# ── World change versus correction ────────────────────────────


def test_a_world_change_ends_the_old_fact_at_the_new_start():
    old = _mem(valid_from=JAN, created_at=JAN)
    new = _mem(valid_from=MARCH, world_time={"precision": "month", "rule": "since"})

    assert supersession.apply("t1", old, new, why="moved", world_change=True, now=NOW)

    assert old.valid_until == MARCH
    assert old.properties["valid_until_by"] == "supersession"
    assert old.properties["superseded_at"] == NOW.isoformat()


def test_a_valid_from_before_the_recorded_time_is_a_known_start():
    # No world_time mark, but valid_from is earlier than created_at.
    old = _mem(valid_from=JAN, created_at=JAN)
    new = _mem(valid_from=MARCH, created_at=NOW)

    assert supersession.world_start(new) == MARCH
    supersession.apply("t1", old, new, why="moved", world_change=True)

    assert old.valid_until == MARCH


def test_a_correction_never_gets_a_world_end():
    old = _mem(valid_from=JAN, created_at=JAN)
    new = _mem(valid_from=MARCH, correction=True, world_time={"rule": "since"})

    assert supersession.apply("t1", old, new, why="actually", world_change=True)

    assert old.status == "superseded"  # still history of belief
    assert old.valid_until is None
    assert "valid_until_by" not in old.properties


def test_an_unknown_start_ends_nothing():
    old = _mem(valid_from=JAN, created_at=JAN)
    new = _mem()  # valid_from == created_at: "no world time"

    supersession.apply("t1", old, new, why="x", world_change=True)

    assert old.valid_until is None and "valid_until_by" not in old.properties


def test_without_world_change_nothing_is_ended_even_with_a_start():
    old = _mem(valid_from=JAN, created_at=JAN)
    new = _mem(valid_from=MARCH, world_time={"rule": "since"})

    supersession.apply("t1", old, new, why="x")

    assert old.valid_until is None


def test_an_end_already_set_is_never_overwritten():
    # /deny and the stale-belief answers set valid_until = now themselves.
    owners = NOW - timedelta(days=1)
    old = _mem(valid_from=JAN, created_at=JAN, valid_until=owners)
    new = _mem(valid_from=MARCH, world_time={"rule": "since"})

    supersession.apply("t1", old, new, why="x", world_change=True)

    assert old.valid_until == owners and "valid_until_by" not in old.properties


def test_a_start_before_the_old_facts_own_start_ends_nothing():
    old = _mem(valid_from=MARCH, created_at=MARCH)
    new = _mem(valid_from=JAN, world_time={"rule": "since"})

    supersession.apply("t1", old, new, why="x", world_change=True)

    assert old.valid_until is None


# ── Undo clears only its own valid_until ──────────────────────


def test_undo_clears_the_valid_until_the_supersede_set():
    old = _mem(valid_from=JAN, created_at=JAN, slot="home.city")
    new = _mem(valid_from=MARCH, world_time={"rule": "since"})
    supersession.apply("t1", old, new, why="moved", world_change=True)

    assert supersession.undo("t1", old, new)

    assert old.status == "active" and old.valid_until is None
    assert old.properties == {"slot": "home.city"}
    assert new.supersedes is None


def test_undo_keeps_a_valid_until_someone_else_set():
    owners = NOW - timedelta(days=1)
    old = _mem(valid_from=JAN, created_at=JAN, valid_until=owners)
    new = _mem(valid_from=MARCH, world_time={"rule": "since"})
    supersession.apply("t1", old, new, why="x", world_change=True)

    assert supersession.undo("t1", old, new)

    assert old.status == "active" and old.valid_until == owners


def test_undo_keeps_another_writers_mark():
    old = _mem(valid_until=NOW, valid_until_by="owner")
    new = _mem()
    supersession.apply("t1", old, new, why="x")

    supersession.undo("t1", old, new)

    assert old.valid_until == NOW and old.properties == {"valid_until_by": "owner"}


# ── Tier rules ────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("kwargs", "tier"),
    [
        ({}, "high"),
        ({"confidence": 0.85}, "medium"),
        ({"new_active": False}, "medium"),
        ({"trust_tier": "external"}, "medium"),
        ({"trust_tier": "hostile_possible"}, "medium"),
        ({"trust_tier": "verified"}, "medium"),
        ({"polarity": "negate"}, "medium"),
        ({"certainty": "hedged"}, "medium"),
    ],
)
def test_slot_tier(kwargs, tier):
    args = {"new_active": True, "trust_tier": "self", "confidence": 0.95} | kwargs
    assert supersession.slot_tier(**args) == tier


def _cand(content, *, status="active", **props):
    base = {"changes_over_time": True}
    return SimpleNamespace(id=uuid.uuid4(), content=content, status=status, properties=base | props)


def _possible(candidates, **kw):
    args = {
        "content": "Anu's school is Vidya Mandir",
        "subject": "anu",
        "changes_over_time": True,
        "slot": None,
        "trust_tier": "self",
        "context": None,
        "candidates": candidates,
        "taken": set(),
        "low": 0.75,
        "high": 0.92,
    } | kw
    return supersession.possible_updates(**args)


def test_a_possible_update_is_found():
    old = _cand("Anu's school is Chettinad Vidyashram", subject="anu")
    found = _possible([(old, 0.8)])
    assert [i for i, _ in found] == [str(old.id)]
    assert found[0][1].startswith("Possible update")


@pytest.mark.parametrize(
    ("kw", "cand_kw", "score"),
    [
        ({"trust_tier": "external"}, {}, 0.8),
        ({"trust_tier": "hostile_possible"}, {}, 0.8),
        ({"changes_over_time": False}, {}, 0.8),
        ({}, {"changes_over_time": False}, 0.8),
        ({}, {}, 0.70),  # below the contradiction threshold
        ({}, {}, 0.95),  # a near-duplicate: dedup's call
        ({}, {"subject": "priya"}, 0.8),
        ({"context": {"project": "x"}}, {}, 0.8),
        ({"slot": "family.anu.school"}, {"slot": "family.anu.class"}, 0.8),
        ({}, {"status": "pending"}, 0.8),
    ],
)
def test_no_possible_update(kw, cand_kw, score):
    status = cand_kw.pop("status", "active")
    props = {"subject": "anu"} | cand_kw
    old = _cand("Anu's school is Chettinad Vidyashram", status=status, **props)
    assert _possible([(old, score)], **kw) == []


def test_a_taken_pair_is_not_a_possible_update():
    old = _cand("Anu's school is Chettinad Vidyashram", subject="anu")
    assert _possible([(old, 0.8)], taken={str(old.id)}) == []


def test_the_same_words_are_not_a_possible_update():
    old = _cand("Anu's school is Vidya Mandir", subject="anu")
    assert _possible([(old, 0.8)]) == []


# ── The daily cap ─────────────────────────────────────────────


class _Session:
    """Answers file_possible_update's three reads: seen, today's count, last."""

    def __init__(self, *, seen=False, count=0, last=None):
        self.seen, self.count, self.last = seen, count, last
        self.added, self.commits, self.calls = [], 0, 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, _query):
        self.calls += 1
        seen, count, last = self.seen, self.count, self.last
        return SimpleNamespace(
            first=lambda: ("id",) if seen else None,
            scalar_one=lambda: count,
            scalar_one_or_none=lambda: last,
        )

    def add(self, row):
        self.added.append(row)

    async def commit(self):
        self.commits += 1


@pytest.mark.asyncio
async def test_under_the_cap_a_low_item_is_queued(monkeypatch):
    s = _Session(count=supersession.LOW_TIER_DAILY_CAP - 1)
    monkeypatch.setattr(supersession, "async_session", lambda: s)

    assert await supersession.file_possible_update("t1", OLD_ID, NEW_ID, "why", now=NOW)

    (row,) = s.added
    assert row.kind == "contradiction" and row.title == "Possible update to review"
    assert row.payload == {
        "memory_id_old": OLD_ID,
        "memory_id_new": NEW_ID,
        "applied": False,
        "confidence": "low",
    }


@pytest.mark.asyncio
async def test_over_the_cap_it_is_counted_not_queued(monkeypatch):
    last = SimpleNamespace(payload={"confidence": "low", "not_queued": 2})
    s = _Session(count=supersession.LOW_TIER_DAILY_CAP, last=last)
    monkeypatch.setattr(supersession, "async_session", lambda: s)

    assert not await supersession.file_possible_update("t1", OLD_ID, NEW_ID, "why", now=NOW)

    assert s.added == []
    assert last.payload["not_queued"] == 3 and s.commits == 1


@pytest.mark.asyncio
async def test_a_pair_already_queued_is_not_queued_again(monkeypatch):
    s = _Session(seen=True)
    monkeypatch.setattr(supersession, "async_session", lambda: s)

    assert not await supersession.file_possible_update("t1", OLD_ID, NEW_ID, "why")
    assert s.added == [] and s.calls == 1


# ── The save path (MemoryManager._process_fact) ───────────────


def _manager(candidates, *, same_slot=(), clashes=None):
    """A MemoryManager over fakes. *clashes*: what the detector finds."""
    mgr = MemoryManager.__new__(MemoryManager)
    mgr._tagger = SimpleNamespace(score=lambda content, context: (0.5, "medium"))
    calls = SimpleNamespace(stored=[], superseded=[], queued=[], low=[])

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
        return clashes or []

    mgr._contradiction_detector = SimpleNamespace(check_candidates=check_candidates)

    async def no_op(*a, **k):
        return None

    async def slot_rows(slot):
        return list(same_slot)

    mgr._file_slot = no_op
    mgr._learn_names = no_op
    mgr._same_slot_active = slot_rows

    async def supersede(old_id, new_id, reason, **kw):
        calls.superseded.append((old_id, new_id, kw))

    async def queue(old_id, new_id, reason, **kw):
        calls.queued.append((old_id, kw))

    mgr.supersede = supersede
    mgr._queue_contradiction_approval = queue
    return mgr, calls


@pytest.fixture
def tiers_on(monkeypatch):
    monkeypatch.setattr(settings, "ingest_supersession_tiers", True)
    monkeypatch.setattr(settings, "dedup_enabled", False)


@pytest.fixture
def low_items(monkeypatch):
    filed = []

    async def file(tenant, old_id, new_id, reason, **kw):
        filed.append((tenant, old_id, new_id))
        return True

    monkeypatch.setattr(supersession, "file_possible_update", file)
    return filed


def _slot_fact(**kw):
    args = {
        "content": "I live in Coimbatore",
        "fact_type": "fact",
        "confidence": 0.95,
        "slot": "home.city",
    } | kw
    return ExtractedFact(**args)


async def _run(mgr, fact, trust="self"):
    with tenant_scope("t1"):
        await mgr._process_fact(fact, context=None, source="test", trust_tier=trust, embedding=_EMB)


@pytest.mark.asyncio
async def test_high_tier_applies_at_once_with_an_undoable_approval(tiers_on, low_items):
    mgr, calls = _manager([], same_slot=[(OLD_ID, "New value for home.city")])

    await _run(mgr, _slot_fact())

    assert calls.stored[0][1]["status"] == "active"
    assert calls.superseded == [(OLD_ID, NEW_ID, {"world_change": True})]
    assert calls.queued == [(OLD_ID, {"applied": True, "confidence": "high"})]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fact_kw", "trust"),
    [
        ({"confidence": 0.85, "fact_type": "explicit_save"}, "self"),  # 0.8-0.9: medium
        ({"fact_type": "intention"}, "self"),  # stays pending
        ({}, "external"),  # outside text never reaches high
        ({}, "hostile_possible"),
    ],
)
async def test_a_same_slot_change_below_high_waits(tiers_on, low_items, fact_kw, trust):
    mgr, calls = _manager([], same_slot=[(OLD_ID, "New value for home.city")])

    await _run(mgr, _slot_fact(**fact_kw), trust=trust)

    assert calls.superseded == []
    assert calls.queued == [(OLD_ID, {"applied": False, "confidence": "medium"})]


@pytest.mark.asyncio
async def test_a_detector_hit_is_medium_even_for_an_explicit_save(tiers_on, low_items):
    old = _cand("I prefer PostgreSQL")
    old.id = OLD_ID
    hit = SimpleNamespace(
        existing_memory_id=OLD_ID, resolution="supersede", reason="swap", conflict_type="swap"
    )
    mgr, calls = _manager([(old, 0.8)], clashes=[hit])
    fact = ExtractedFact(content="I prefer MongoDB", fact_type="explicit_save", confidence=0.95)

    await _run(mgr, fact)

    assert calls.stored[0][1]["status"] == "active"  # an explicit save is kept
    assert calls.superseded == []  # ...but the clash waits for the owner
    assert calls.queued == [(OLD_ID, {"applied": False, "confidence": "medium"})]
    assert low_items == []


@pytest.mark.asyncio
async def test_a_detector_hit_about_another_person_is_no_supersession(tiers_on, low_items):
    old = _cand("Priya prefers tea", subject="priya")
    old.id = OLD_ID
    hit = SimpleNamespace(
        existing_memory_id=OLD_ID, resolution="supersede", reason="swap", conflict_type="swap"
    )
    mgr, calls = _manager([(old, 0.8)], clashes=[hit])
    fact = ExtractedFact(content="I prefer coffee", fact_type="preference", confidence=0.95)

    await _run(mgr, fact)

    assert calls.queued == [] and calls.superseded == []


@pytest.mark.asyncio
async def test_low_tier_files_a_review_item_only(tiers_on, low_items):
    old = _cand("Anu's school is Chettinad Vidyashram", subject="anu")
    mgr, calls = _manager([(old, 0.8)])
    fact = ExtractedFact(
        content="Anu's school is Vidya Mandir",
        fact_type="fact",
        confidence=0.95,
        subject="anu",
        changes_over_time=True,
    )

    await _run(mgr, fact)

    assert calls.superseded == [] and calls.queued == []
    assert low_items == [("t1", str(old.id), NEW_ID)]


@pytest.mark.asyncio
@pytest.mark.parametrize("trust", ["external", "hostile_possible"])
async def test_outside_text_makes_no_low_item(tiers_on, low_items, trust):
    old = _cand("Anu's school is Chettinad Vidyashram", subject="anu")
    mgr, calls = _manager([(old, 0.8)])
    fact = ExtractedFact(
        content="Anu's school is Vidya Mandir",
        fact_type="fact",
        confidence=0.95,
        subject="anu",
        changes_over_time=True,
    )

    await _run(mgr, fact, trust=trust)

    assert low_items == [] and calls.superseded == []


@pytest.mark.asyncio
async def test_flag_off_is_todays_behaviour(monkeypatch, low_items):
    monkeypatch.setattr(settings, "ingest_supersession_tiers", False)
    monkeypatch.setattr(settings, "dedup_enabled", False)
    low = _cand("Anu's school is Chettinad Vidyashram", subject="anu")
    mgr, calls = _manager([(low, 0.8)], same_slot=[(OLD_ID, "New value for home.city")])
    fact = _slot_fact(confidence=0.85, fact_type="explicit_save", changes_over_time=True)

    await _run(mgr, fact)

    # Today: an active explicit save supersedes its slot at once, no tier, no
    # world end, and no low-tier item.
    assert calls.superseded == [(OLD_ID, NEW_ID, {})]
    assert calls.queued == [(OLD_ID, {"applied": True})]
    assert low_items == []
