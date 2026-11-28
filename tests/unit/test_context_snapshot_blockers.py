"""Eval-only option L (blockers, services/memory/snapshot_experiments.py).

O1 "What are my current priorities?" missed ``w_blocker`` (the Billing
migration is blocked). L pulls current, unresolved blocker and dependency
records for a priorities / "what is stopping me" / work-overview question,
with the same safety checks as C's pulls, and never a resolved dependency
(``w_dep``, resolved by ``w_dep_done``: forbidden-as-current). No database.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

from life_graph.services.memory import snapshot
from life_graph.services.memory import snapshot_experiments as xp
from life_graph.services.memory.snapshot import assemble_context
from tests.unit import test_context_snapshot as base
from tests.unit import test_context_snapshot_default_identity as ident
from tests.unit.test_context_snapshot_experiments import xwired  # noqa: F401 — fixture

NOW, _mem, _id = base.NOW, base._mem, ident._id
wired = base.wired

PRIORITIES = "What are my current priorities?"
BLOCKER = (
    "The Billing migration is blocked: PayFlow still has not given the owner sandbox API "
    "access, which she requested on 4 November."
)
DEP = "Route Planner v2 depends on the maps team finishing the new geocoding API."
DEP_DONE = "The maps team shipped the new geocoding API on 20 November, so Route Planner v2 can use it now."


@pytest.fixture
def bwired(xwired, monkeypatch):  # noqa: F811 — the fixture
    """xwired plus L's read (deliberately looser than its SQL) and the other pulls' reads."""
    state = xwired
    state.update({"blocker_rows": [], "reads": []})

    async def blockers(tenant_id, limit):
        state["reads"].append(("blockers", limit))
        return list(state["blocker_rows"])

    async def none(*a, **kw):
        return []

    monkeypatch.setattr(snapshot, "_blocker_memories", blockers)
    monkeypatch.setattr(snapshot, "_undated_intentions", none)
    monkeypatch.setattr(snapshot, "_goal_memories", none)
    return state


def _keys(snap) -> set[str]:
    return {i.content for i in snap.items}


def _reasons(snap) -> dict[str, str]:
    return {i.content: i.reason for i in snap.items}


def _work_world(state):
    blocker = _mem(
        BLOCKER, id=_id(1), tags=["work", "blocker"], created_at=NOW - timedelta(days=18)
    )
    dep = _mem(DEP, id=_id(2), tags=["work", "dependency"], created_at=NOW - timedelta(days=40))
    done = _mem(
        DEP_DONE, id=_id(3), tags=["work", "dependency"], created_at=NOW - timedelta(days=6)
    )
    state["found"] = [_mem("I want to become an engineering manager.", id=_id(9))]
    state["blocker_rows"] = [done, blocker, dep]
    return blocker, dep, done


# ── Letters, tunables, default ────────────────────────────────


def test_l_parses_and_is_tunable():
    assert xp.parse("L") == {xp.BLOCKERS} and xp.letters({xp.BLOCKERS}) == ["L"]
    assert xp.DEFAULT_TUNABLES.named()["BLOCKER_PULL"] == xp.BLOCKER_PULL


@pytest.mark.parametrize(("query", "as_of_days"), ident.QUESTIONS)
async def test_the_default_snapshot_never_reads_blockers(bwired, monkeypatch, query, as_of_days):
    ident.build_world(bwired)
    ident.install_conflict(monkeypatch)
    snap = await ident.snapshot_of(query, as_of_days)
    assert (ident._digest(snap.to_dict()), ident._digest(snap.compact())) == ident.EXPECTED[query]
    assert bwired["reads"] == []


# ── Pure parts ────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("query", "asks"),
    [
        (PRIORITIES, True),
        ("What is stopping me from finishing the migration?", True),
        ("Which project is held up by the missing PayFlow sandbox access?", True),
        ("Give me an overview of my work", True),
        ("en velai la enna thadai?", True),
        ("என் முன்னுரிமைகள் என்ன?", True),
        ("How do I take my coffee?", False),
        ("What is my monthly take-home salary?", False),
        ("Give me an overview of my finances", False),  # an overview, but not of work
    ],
)
def test_asks_for_blockers(query, asks):
    assert xp.asks_for_blockers(query) is asks


@pytest.mark.parametrize(
    ("query", "subject"),
    [
        (PRIORITIES, False),
        ("What is stopping me?", False),
        ("Which project is held up by the missing PayFlow sandbox access?", True),
    ],
)
def test_blocker_subject(query, subject):
    assert xp.blocker_subject(query) is subject


@pytest.mark.parametrize(
    ("tags", "text_", "blocker"),
    [
        (["work", "blocker"], BLOCKER, True),
        (["work", "dependency"], DEP, True),
        (["work", "dependency"], DEP_DONE, False),  # says it is over
        (None, "We are stuck waiting on legal review.", True),
        (None, "கட்டடப் பணி அனுமதிக்காகக் காத்திருக்கிறது.", True),
        (None, "The Billing migration is no longer blocked.", False),
        (["work"], "I lead the Route Planner v2 project.", False),
    ],
)
def test_is_blocker_text(tags, text_, blocker):
    assert xp.is_blocker_text(tags, text_) is blocker


def test_resolves_needs_the_words_the_tag_and_the_subject():
    dep = type("Row", (), {"content": DEP, "tags": ["work", "dependency"]})()
    assert xp.resolves(DEP_DONE, ["work", "dependency"], dep)
    assert not xp.resolves(DEP_DONE, ["work"], dep)  # no shared blocker/dependency tag
    assert not xp.resolves(
        "The maps team shipped a new logo.", ["dependency"], dep
    )  # too few shared subject words
    assert not xp.resolves(
        "The maps team is building the new geocoding API for Route Planner v2.",
        ["dependency"],
        dep,
    )  # not over


# ── L in the snapshot ─────────────────────────────────────────


async def test_blockers_bring_the_current_blocker_to_a_priorities_question(bwired):
    """O1: the blocker shares no word with "priorities"; L brings it, B keeps it."""
    _work_world(bwired)
    without = await assemble_context(PRIORITIES, now=NOW, experiments=xp.parse("B"))
    snap = await assemble_context(PRIORITIES, now=NOW, experiments=xp.parse("B,L"))
    assert BLOCKER not in _keys(without)
    assert _reasons(snap)[BLOCKER] == xp.BLOCKER_RECORD
    item = next(i for i in snap.items if i.content == BLOCKER)
    plain = snapshot.memory_item(bwired["blocker_rows"][1], NOW, snapshot.DEFAULT_BUDGET)
    assert (item.origin, item.confirmed, item.evidence) == (
        plain.origin,
        plain.confirmed,
        plain.evidence,
    )


async def test_a_resolved_dependency_is_never_pulled_as_current(bwired):
    """Adversarial: w_dep is resolved by the newer w_dep_done; neither is a current blocker."""
    _work_world(bwired)
    snap = await assemble_context(PRIORITIES, now=NOW, experiments=xp.parse("L"))
    assert DEP not in _keys(snap) and DEP_DONE not in _keys(snap)
    assert BLOCKER in _keys(snap)


async def test_a_typed_link_from_a_newer_done_record_resolves_a_blocker(bwired):
    blocker, _, _ = _work_world(bwired)
    gave = _mem(
        "PayFlow sent the sandbox keys today; that is sorted.",
        id=_id(4),
        created_at=NOW - timedelta(days=1),
    )
    bwired["touching"] = [(gave.id, blocker.id, "RELATED_TO", 0.8)]
    bwired["rows_by_id"] = [gave]
    snap = await assemble_context(PRIORITIES, now=NOW, experiments=xp.parse("L"))
    assert BLOCKER not in _keys(snap)


@pytest.mark.parametrize(
    "resolver",
    [
        {"created_at": NOW - timedelta(days=30)},  # older than the blocker: not a resolution
        {"trust_tier": "hostile_possible"},  # someone else's words cannot hide a blocker
        {"tenant_id": "t-other"},
        {"status": "pending"},
    ],
)
async def test_only_a_newer_trusted_record_resolves_a_blocker(bwired, resolver):
    blocker, _, _ = _work_world(bwired)
    kw = {"created_at": NOW - timedelta(days=1), **resolver}
    gave = _mem("PayFlow sandbox access: done.", id=_id(4), **kw)
    bwired["touching"] = [(gave.id, blocker.id, "RELATED_TO", 0.8)]
    bwired["rows_by_id"] = [gave]
    snap = await assemble_context(PRIORITIES, now=NOW, experiments=xp.parse("L"))
    assert BLOCKER in _keys(snap)


async def test_a_contradicts_link_is_not_a_resolution(bwired):
    blocker, _, _ = _work_world(bwired)
    gave = _mem("PayFlow access is done.", id=_id(4), created_at=NOW - timedelta(days=1))
    bwired["touching"] = [(gave.id, blocker.id, "CONTRADICTS", 1.0)]
    bwired["rows_by_id"] = [gave]
    snap = await assemble_context(PRIORITIES, now=NOW, experiments=xp.parse("L"))
    assert BLOCKER in _keys(snap)


@pytest.mark.parametrize(
    "bad",
    [
        {"trust_tier": "hostile_possible"},
        {"status": "pending"},
        {"status": "superseded"},
        {"superseded_by": uuid.UUID(int=77)},
        {"tenant_id": "t-other"},
        {"valid_until": NOW - timedelta(days=1)},
        {"created_at": NOW + timedelta(days=400), "valid_from": None},
    ],
)
async def test_blockers_never_bring_a_record_the_snapshot_would_not_show(bwired, bad):
    """Adversarial: another tenant's, hostile, pending, replaced, expired or not-yet-known."""
    bwired["blocker_rows"] = [_mem("The launch is blocked on legal review.", id=_id(5), **bad)]
    snap = await assemble_context(PRIORITIES, now=NOW, experiments=xp.parse("L"))
    assert "The launch is blocked on legal review." not in _keys(snap)


async def test_blockers_keep_the_cap_and_skip_other_questions(bwired):
    bwired["blocker_rows"] = [
        _mem(f"Project {n} is blocked on vendor {n}.", id=_id(40 + n), tags=["blocker"])
        for n in range(xp.BLOCKER_PULL + 3)
    ]
    snap = await assemble_context(PRIORITIES, now=NOW, experiments=xp.parse("L"))
    assert sum(1 for i in snap.items if i.reason == xp.BLOCKER_RECORD) == xp.BLOCKER_PULL
    bwired["reads"].clear()
    coffee = await assemble_context("How do I take my coffee?", now=NOW, experiments=xp.parse("L"))
    past = await assemble_context(
        PRIORITIES, as_of=NOW - timedelta(days=5), now=NOW, experiments=xp.parse("L")
    )
    assert bwired["reads"] == []
    assert not any(i.reason == xp.BLOCKER_RECORD for i in coffee.items + past.items)


async def test_a_question_with_its_own_subject_gets_only_the_blockers_about_it(bwired):
    _work_world(bwired)
    other = _mem("The office move is stuck waiting on the landlord.", id=_id(6), tags=["blocker"])
    bwired["blocker_rows"].append(other)
    snap = await assemble_context(
        "Which project is held up by the missing PayFlow sandbox access?",
        now=NOW,
        experiments=xp.parse("L"),
    )
    assert BLOCKER in _keys(snap) and other.content not in _keys(snap)
