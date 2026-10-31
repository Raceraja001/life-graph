"""Cold labels, link pairs and strength order (services/memory_tiers.py,
services/associations.py, services/memory_retrieval.py; 2026-10-31)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from life_graph.services import associations, memory_context, memory_retrieval, memory_tiers


def _m(**kw):
    base = {
        "id": uuid.uuid4(),
        "content": "x",
        "status": "active",
        "importance": 0.5,
        "access_count": 0,
        "last_accessed": None,
        "created_at": datetime.now(UTC),
        "properties": {},
        "source_type": "capture",
        "trust_tier": "self",
    }
    base.update(kw)
    return SimpleNamespace(**base)


def test_cold_labels_say_what_the_memory_is():
    assert memory_tiers.label(_m()) == ""
    assert memory_tiers.label(_m(status="archived")) == "older note"
    replaced = _m(status="superseded")
    replaced.replaced = (datetime(2026, 3, 1, tzinfo=UTC), False)
    assert memory_tiers.label(replaced) == "later replaced on 2026-03-01"
    replaced.replaced = (datetime(2026, 3, 1, tzinfo=UTC), True)
    assert memory_tiers.label(replaced) == "later corrected on 2026-03-01"


def test_a_cold_memory_is_labelled_in_the_block_and_not_as_of():
    old = _m(
        status="superseded",
        content="The owner works at Nimbus Soft.",
        created_at=datetime(2025, 5, 2, tzinfo=UTC),
        properties={"changes_over_time": True},
    )
    old.replaced = (datetime(2026, 1, 9, tzinfo=UTC), False)
    block = memory_context.render([memory_context._row(old)])
    assert "- (2025-05-02 · later replaced on 2026-01-09) The owner works at Nimbus Soft." in block


def test_past_questions_read_the_cold_tier():
    assert memory_tiers.asks_about_past("Where did I work before?")
    assert memory_tiers.asks_about_past("What phone did I use earlier")
    assert not memory_tiers.asks_about_past("Where do I work?")


def test_bulk_clean_ups_are_never_cold():
    f = memory_tiers.filters()
    assert f["cold_tier"] is True and set(f["statuses"]) == {"archived", "superseded"}
    assert "fresh_start_2026-10-23" in f["bulk_archives"]


def test_link_pairs_are_undirected_unique_and_capped():
    a, b = uuid.uuid4(), uuid.uuid4()
    assert associations._pairs([a, b, a]) == associations._pairs([b, a])
    assert len(associations._pairs([a, b])) == 1
    many = [uuid.uuid4() for _ in range(20)]
    n = associations.MAX_GROUP
    assert len(associations._pairs(many)) == n * (n - 1) // 2
    assert associations._pairs([a]) == []


def test_strength_settles_near_ties_but_never_overrules_a_clear_match():
    now = datetime.now(UTC)
    weak = _m(importance=0.2, created_at=now - timedelta(days=400))
    strong = _m(importance=1.0, access_count=10, last_accessed=now)
    # A near tie: the stronger memory goes first.
    order = memory_retrieval.strength_order([(weak, 0.80), (strong, 0.78)])
    assert order[0][0] is strong
    # A clearly better match stays first.
    order = memory_retrieval.strength_order([(weak, 0.95), (strong, 0.60)])
    assert order[0][0] is weak
