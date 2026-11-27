"""Typed links in the context snapshot (D6, services/memory/snapshot.py).

The typed ``memory_links`` between included memories come back as
``relations`` (refs, type, strength; no content); a CONTRADICTS link is a
``linked_contradiction`` conflict instead; the learned ASSOCIATED links are
never relations. No database: the link read is a stand-in (the ``wired``
fixture of tests/unit/test_context_snapshot.py). The tenant-scoped SQL is
tests/integration/test_context_snapshot_pg.py.
"""

from __future__ import annotations

import json
import uuid

from life_graph.services.memory import snapshot
from life_graph.services.memory.snapshot import assemble_context, links_to_context
from tests.unit import test_context_snapshot as base

NOW, _mem = base.NOW, base._mem
#: The stand-in reads of tests/unit/test_context_snapshot.py, links included.
wired = base.wired


def _refs(rel) -> tuple[str, str, str, float]:
    return (rel.from_ref.id, rel.to_ref.id, rel.type, rel.strength)


async def test_typed_links_between_items_become_relations(wired):
    goal, project, task = _mem("goal"), _mem("project"), _mem("task")
    wired["found"] = [goal, project, task]
    wired["links"] = [
        (project.id, task.id, "LEADS_TO", 0.7),
        (goal.id, project.id, "LEADS_TO", 0.9),
        (task.id, goal.id, "BECAUSE", 0.55559),
    ]
    snap = await assemble_context("how does my goal connect to my projects", now=NOW)
    got = {_refs(r) for r in snap.relations}
    assert got == {
        (str(goal.id), str(project.id), "LEADS_TO", 0.9),
        (str(project.id), str(task.id), "LEADS_TO", 0.7),
        (str(task.id), str(goal.id), "BECAUSE", 0.5556),
    }
    assert snap.conflicts == ()
    # One read, with every included memory id.
    ((tenant, ids),) = wired["link_reads"]
    assert tenant == "t-snap" and set(ids) == {str(goal.id), str(project.id), str(task.id)}


async def test_contradicts_is_a_conflict_with_both_sides_not_a_relation(wired):
    inferred, stated = _mem("thinking of a new job"), _mem("I am not leaving")
    wired["found"] = [inferred, stated]
    wired["links"] = [
        (inferred.id, stated.id, "CONTRADICTS", 0.8),
        (stated.id, inferred.id, "CONTRADICTS", 0.8),  # the other way round: still one
    ]
    snap = await assemble_context("am I looking for a new job?", now=NOW)
    assert snap.relations == ()
    (conflict,) = snap.conflicts
    assert conflict.kind == "linked_contradiction"
    assert {(s.source_ref.id, s.status) for s in conflict.sides} == {
        (str(inferred.id), "active"),
        (str(stated.id), "active"),
    }
    assert {s.role for s in conflict.sides} == {"source", "target"}
    assert conflict.approval_id is None


def test_a_link_to_anything_that_is_not_an_item_is_never_shown():
    a, b = _mem("a"), _mem("b")
    elsewhere = uuid.uuid4()  # another tenant's memory, or one the budget left out
    items = [snapshot.memory_item(m, NOW, snapshot.DEFAULT_BUDGET) for m in (a, b)]
    rows = [
        (a.id, elsewhere, "LEADS_TO", 0.9),
        (elsewhere, b.id, "CONTRADICTS", 0.9),
        (a.id, a.id, "RELATED_TO", 0.9),
        (a.id, b.id, "ASSOCIATED", 0.9),
    ]
    assert links_to_context(rows, items) == ([], [])


def test_the_same_links_give_the_same_relations_whatever_the_read_order():
    mems = [_mem(f"m{i}") for i in range(4)]
    items = [snapshot.memory_item(m, NOW, snapshot.DEFAULT_BUDGET) for m in mems]
    rows = [
        (mems[0].id, mems[1].id, "LEADS_TO", 0.5),
        (mems[1].id, mems[2].id, "BECAUSE", 0.5),
        (mems[2].id, mems[3].id, "CONTRADICTS", 0.5),
        (mems[3].id, mems[0].id, "RELATED_TO", 0.5),
    ]
    assert links_to_context(rows, items) == links_to_context(list(reversed(rows)), items)


async def test_relations_only_between_what_the_budget_kept(wired):
    kept, dropped = _mem("kept", retrieval_score=0.9), _mem("x" * 400, retrieval_score=0.1)
    wired["found"] = [kept, dropped]
    wired["links"] = [(kept.id, dropped.id, "LEADS_TO", 0.9)]
    snap = await assemble_context("q", now=NOW, budget=snapshot.Budget(max_items=1))
    assert [i.source_ref.id for i in snap.items] == [str(kept.id)]
    assert snap.relations == ()
    assert wired["link_reads"] == [("t-snap", [str(kept.id)])]


async def test_relations_in_to_dict_and_compact_carry_refs_and_labels_only(wired):
    a, b = _mem("SECRET-A about the owner"), _mem("SECRET-B about the owner")
    wired["found"] = [a, b]
    wired["links"] = [(a.id, b.id, "EVIDENCED_BY", 0.6)]
    snap = await assemble_context("SECRET-QUERY", now=NOW)
    assert snap.to_dict()["relations"] == [
        {
            "from": {"kind": "memory", "id": str(a.id)},
            "to": {"kind": "memory", "id": str(b.id)},
            "type": "EVIDENCED_BY",
            "strength": 0.6,
        }
    ]
    compact = snap.compact()
    assert compact["v"] == 2  # added keys, same format
    assert compact["relations"] == [
        {"from": f"memory:{a.id}", "to": f"memory:{b.id}", "type": "EVIDENCED_BY", "strength": 0.6}
    ]
    assert "SECRET" not in json.dumps(compact)


async def test_a_failed_link_read_fails_the_snapshot_like_any_read(wired, monkeypatch):
    wired["found"] = [_mem("a"), _mem("b")]

    async def broken(tenant_id, ids):
        raise ConnectionError("database down")

    monkeypatch.setattr(snapshot, "_typed_links", broken)
    snap = await assemble_context("q", now=NOW)
    assert snap.items == () and snap.relations == () and snap.insufficient is True
    assert "relations" in snap.to_dict()["timings_ms"]


async def test_a_relation_alone_never_makes_the_question_supported(wired):
    goal, project = _mem("the platform team goal"), _mem("the route planner project")
    wired["found"] = [goal, project]
    without = await assemble_context("what is my blood group?", now=NOW)
    wired["links"] = [
        (goal.id, project.id, "LEADS_TO", 0.9),
        (project.id, goal.id, "CONTRADICTS", 0.9),
    ]
    linked = await assemble_context("what is my blood group?", now=NOW)
    assert linked.relations and linked.conflicts
    assert (linked.insufficient, linked.missing) == (without.insufficient, without.missing)
