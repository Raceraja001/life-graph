"""``as_of`` history after supersession (D1) and Tamil-safe decision/intention words (D10).

docs/audits/2026-11-26-m8-context-quality-evaluation.md §4. No database:
search, the entity index and the successor read are stand-ins. The Postgres
half is in tests/integration/test_context_snapshot_pg.py.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from life_graph import runtime
from life_graph.core.tenant import tenant_scope
from life_graph.services.memory import retrieval, snapshot

NOW = datetime.now(UTC)


def _mem(content, *, days_ago, **kw):
    created = NOW - timedelta(days=days_ago)
    base = {
        "id": uuid.uuid4(),
        "content": content,
        "status": "active",
        "source_type": "chat",
        "trust_tier": "self",
        "extraction_tier": None,
        "properties": {},
        "tags": None,
        "importance": 0.6,
        "confidence": 0.9,
        "access_count": 0,
        "last_accessed": None,
        "created_at": created,
        "valid_from": created,
        "valid_until": None,
        "supersedes": None,
        "superseded_by": None,
        "last_reinforced": None,
    }
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture
def salary(monkeypatch):
    """An old salary replaced 24 days ago by a new one; search returns both."""
    from life_graph.config import settings
    from life_graph.services import entities

    new = _mem("After the promotion my take-home salary is 1,80,000 a month.", days_ago=24)
    old = _mem(
        "The owner's take-home salary is 1,50,000 a month.",
        days_ago=300,
        status="superseded",
        superseded_by=new.id,
        properties={"superseded_at": new.created_at.isoformat()},
    )
    state = {"starts": {new.id: new.valid_from}, "calls": 0, "fail": False}

    class _Manager:
        async def generate_embedding(self, text_):
            return [0.1]

    class _Store:
        async def hybrid_search(self, **kw):
            rows = [new, old] if "superseded" in kw["statuses"] else [new]
            return [(m, 0.8) for m in rows]

    async def no_entities(tenant_id, text_):
        return []

    async def successor_starts(tenant_id, ids):
        state["calls"] += 1
        if state["fail"]:
            raise ConnectionError("database down")
        return {i: state["starts"][i] for i in ids if i in state["starts"]}

    monkeypatch.setattr(runtime, "get_memory_manager", lambda: _Manager())
    monkeypatch.setattr(runtime, "get_store", lambda: _Store())
    monkeypatch.setattr(entities, "known_in_text", no_entities)
    monkeypatch.setattr(settings, "memory_links", False)
    monkeypatch.setattr(retrieval, "_successor_starts", successor_starts)
    with tenant_scope("t-history"):
        yield SimpleNamespace(old=old, new=new, state=state)


QUESTION = "What was my take-home salary?"


async def test_as_of_before_the_successor_was_true_returns_the_replaced_value(salary):
    out = await retrieval.retrieve(QUESTION, as_of=NOW - timedelta(days=250), judge=False)
    assert [m.id for m in out] == [salary.old.id]


async def test_as_of_after_the_successor_was_true_returns_the_successor(salary):
    out = await retrieval.retrieve(QUESTION, as_of=NOW - timedelta(days=10), judge=False)
    assert [m.id for m in out] == [salary.new.id]


async def test_a_correction_backdated_before_as_of_keeps_the_old_row_out(salary):
    """The successor says it was true all along (valid from before as_of): the
    old row was simply wrong, so it is not history to answer from."""
    salary.state["starts"][salary.new.id] = NOW - timedelta(days=280)
    out = await retrieval.retrieve(QUESTION, as_of=NOW - timedelta(days=250), judge=False)
    assert salary.old.id not in [m.id for m in out]


async def test_a_current_time_question_is_unchanged_and_reads_no_successor(salary):
    out = await retrieval.retrieve(QUESTION, judge=False)
    assert [m.id for m in out] == [salary.new.id]
    assert salary.state["calls"] == 0


async def test_what_we_believed_then_keeps_its_own_rule(salary):
    # recorded_as_of after the supersession: the replacement had landed.
    out = await retrieval.retrieve(
        QUESTION,
        as_of=NOW - timedelta(days=250),
        recorded_as_of=NOW - timedelta(days=1),
        judge=False,
    )
    assert salary.old.id not in [m.id for m in out]
    assert salary.state["calls"] == 0


async def test_a_failed_successor_read_falls_back_to_dropping_the_old_row(salary):
    salary.state["fail"] = True
    out = await retrieval.retrieve(QUESTION, as_of=NOW - timedelta(days=250), judge=False)
    assert salary.old.id not in [m.id for m in out]


def test_visible_at_waives_only_the_replaced_yet_edge():
    old = _mem(
        "x", days_ago=300, status="superseded", properties={"superseded_at": NOW.isoformat()}
    )
    then = NOW - timedelta(days=250)
    assert retrieval.visible_at(old, valid_at=then, recorded_at=NOW) is False
    assert retrieval.visible_at(old, valid_at=then, recorded_at=NOW, kept_history={old.id})
    # Not yet true at valid_at, or not yet recorded by recorded_at: still out.
    early = NOW - timedelta(days=400)
    assert not retrieval.visible_at(old, valid_at=early, recorded_at=NOW, kept_history={old.id})
    before = NOW - timedelta(days=310)
    assert not retrieval.visible_at(old, valid_at=then, recorded_at=before, kept_history={old.id})


# ── D10: words for the decision and intention keyword match ──


def test_tamil_words_stay_whole():
    assert snapshot._words("பள்ளி கட்டணம்") == ["பள்ளி", "கட்டணம்"]
    assert snapshot._words("இலாவின் பள்ளி கட்டணம் எப்போது?") == [
        "இலாவின்",
        "பள்ளி",
        "கட்டணம்",
        "எப்போது",
    ]


def test_english_words_split_on_spaces_and_punctuation_as_before():
    assert snapshot._words("Ila's school-fee, due FRIDAY! due") == [
        "ila",
        "s",
        "school",
        "fee",
        "due",
        "friday",
    ]
    assert snapshot._words("Kovai Logistics 2027") == ["kovai", "logistics", "2027"]


def test_the_tsquery_is_quoted_words_ored_and_cannot_carry_operators():
    assert snapshot._tsquery("பள்ளி கட்டணம்") == "'பள்ளி' | 'கட்டணம்'"
    q = snapshot._tsquery("a & !b | (c:*) 'd' e<->f \\g")
    operands = q.split(" | ")
    assert operands == ["'a'", "'b'", "'c'", "'d'", "'e'", "'f'", "'g'"]
    assert all(re.fullmatch(r"'[^\s'\\&|!:()<>*]+'", o) for o in operands)


def test_no_words_means_no_query_and_at_most_32():
    assert snapshot._tsquery("?? !! ...") == "" and snapshot._tsquery("") == ""
    assert len(snapshot._tsquery(" ".join(f"w{i}" for i in range(100))).split(" | ")) == 32
