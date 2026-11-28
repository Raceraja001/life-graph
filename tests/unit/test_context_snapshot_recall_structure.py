"""Eval-only structural recall options H-K (services/memory/snapshot_experiments.py).

H undated open intentions, I goal records, J overview cut, K domain hold.
Each: the miss it fixes (docs/audits/2026-11-28-m8-context-precision-evaluation.md
§5: O3 ``i_aws_book``, O1/O2 ``l_aws_goal``, O9/O10 the cut's tail) and the
adversarial cases it must not get wrong. No database: the stand-ins of
test_context_snapshot_experiments.py plus the two new reads.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

from life_graph import runtime
from life_graph.services.memory import snapshot
from life_graph.services.memory import snapshot_experiments as xp
from life_graph.services.memory.snapshot import assemble_context
from tests.unit import test_context_snapshot as base
from tests.unit import test_context_snapshot_default_identity as ident
from tests.unit.test_context_snapshot_experiments import xwired  # noqa: F401 — fixture

NOW, _mem, _intention, _id = base.NOW, base._mem, ident._intention, ident._id
wired = base.wired


@pytest.fixture
def rwired(xwired, monkeypatch):  # noqa: F811 — the fixture
    """xwired plus H's and I's reads, deliberately looser than their SQL."""
    state = xwired
    state.update({"undated": [], "goal_rows": [], "reads": []})

    async def undated(tenant_id, ref, limit):
        state["reads"].append(("undated", limit))
        return list(state["undated"])

    async def goals(tenant_id, limit):
        state["reads"].append(("goals", limit))
        return list(state["goal_rows"])

    monkeypatch.setattr(snapshot, "_undated_intentions", undated)
    monkeypatch.setattr(snapshot, "_goal_memories", goals)
    return state


def _keys(snap) -> set[str]:
    return {i.content for i in snap.items}


def _reasons(snap) -> dict[str, str]:
    return {i.content: i.reason for i in snap.items}


def _undated(n: int, content: str, **kw):
    row = {"trigger_type": "nudge", "trigger_time": None, "context_match": None}
    row.update(kw)
    return _intention(n, content, **row)


# ── Letters ───────────────────────────────────────────────────


def test_the_new_options_parse_and_are_tunable():
    assert xp.parse("H,I,J,K") == {xp.UNDATED, xp.GOALS, xp.OVERVIEW, xp.DOMAIN}
    assert xp.letters(xp.parse("undated,goals,overview,domain")) == ["H", "I", "J", "K"]
    named = xp.DEFAULT_TUNABLES.named()
    for name in (
        "SIDE_PULL",
        "INTENTION_FLOOR",
        "GOAL_PULL",
        "OVERVIEW_MIN_KEEP",
        "OVERVIEW_FLOOR",
    ):
        assert named[name] == getattr(xp, name)


def test_no_mode_uses_the_new_options():
    for m in xp.MODES.values():
        assert not m.experiments & {xp.UNDATED, xp.GOALS, xp.OVERVIEW, xp.DOMAIN}


@pytest.mark.parametrize(("query", "as_of_days"), ident.QUESTIONS)
async def test_the_default_snapshot_never_reads_them(rwired, monkeypatch, query, as_of_days):
    ident.build_world(rwired)
    ident.install_conflict(monkeypatch)
    snap = await ident.snapshot_of(query, as_of_days)
    assert (ident._digest(snap.to_dict()), ident._digest(snap.compact())) == ident.EXPECTED[query]
    assert rwired["reads"] == []


# ── Pure parts ────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("query", "kind", "whole"),
    [
        ("Which of my commitments are still not done?", xp.COMMITMENT, True),
        ("What are my current priorities?", xp.COMMITMENT, True),
        ("What are my active goals?", xp.GOAL, True),
        ("என் இலக்குகள் என்ன?", xp.GOAL, False),  # has a subject word: by support only
        ("How does my goal of becoming an engineering manager connect?", xp.GOAL, False),
        ("What tasks do I have on the Billing migration?", xp.COMMITMENT, False),
        ("How do I take my coffee?", xp.COMMITMENT, False),
    ],
)
def test_asks_for_a_kind_as_a_whole(query, kind, whole):
    assert xp.asks_for(query, xp.classify(query), kind) is whole


@pytest.mark.parametrize(
    ("query", "due"),
    [
        ("Which deadlines are coming up in the next few days?", True),
        ("What is due tomorrow?", True),
        ("naalaikku enna kedu?", True),
        ("Which of my commitments are still not done?", False),
    ],
)
def test_asks_for_due(query, due):
    assert xp.asks_for_due(query) is due


@pytest.mark.parametrize(
    ("tags", "fact_type", "text_", "goal"),
    [
        (["learning", "goal"], "intention", "The owner plans to pass the AWS exam.", True),
        (["fitness"], "intention", "The owner wants to run a half marathon.", True),
        (["இலக்கு"], None, "ஒரு வீடு வாங்க", True),
        (None, "intention", "Call the plumber about the leak.", False),
        (["finance"], "fact", "I want a cheaper phone plan.", False),  # not an intention
        (None, None, "My goal is to save more.", False),  # no type the gate can read
    ],
)
def test_is_goal_memory(tags, fact_type, text_, goal):
    assert xp.is_goal_memory(tags, fact_type, text_) is goal


def test_cosine():
    assert xp.cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert xp.cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert xp.cosine([1.0], [1.0, 0.0]) is None
    assert xp.cosine([], [1.0]) is None and xp.cosine(None, [1.0]) is None
    assert xp.cosine([0.0, 0.0], [1.0, 0.0]) is None


@pytest.mark.parametrize(
    ("query", "overview"),
    [
        (
            "What financial constraints should you consider before recommending "
            "that I buy a new laptop for ₹1,20,000?",
            True,
        ),
        (
            "What information is missing before you can reliably recommend whether "
            "I should take a second home loan?",
            True,
        ),
        ("Give me an overview of my finances", True),
        ("en panam vishayam ellam sollu", True),
        ("என் நிதி நிலை எப்படி?", True),
        ("How big is our emergency fund?", False),
        ("What is my monthly take-home salary?", False),
        ("Did I decide to hire a caregiver for my mother?", False),
    ],
)
def test_is_overview(query, overview):
    assert xp.is_overview(query) is overview


@pytest.mark.parametrize(
    ("query", "domains"),
    [
        ("What financial constraints should I consider?", {"finance"}),
        ("en kadan evvalavu?", {"finance"}),
        ("அம்மாவின் உடல்நலம் எப்படி?", {"family", "health"}),
        ("How is my career going?", {"work"}),
        ("How do I take my coffee?", set()),
    ],
)
def test_query_domains(query, domains):
    assert xp.query_domains(query) == domains


def test_overview_tunables_only_loosen():
    t = xp.overview_tunables(xp.MODES["precision"].tunables)
    assert t.min_keep == xp.OVERVIEW_MIN_KEEP and t.cosine_floor == xp.OVERVIEW_FLOOR
    loose = xp.DEFAULT_TUNABLES.with_values({"COSINE_FLOOR": 0.5, "MIN_KEEP": 12})
    assert xp.overview_tunables(loose) == loose.with_values(
        {"RELATIVE_FLOOR": min(loose.relative_floor, loose.overview_floor)}
    )


# ── H: undated open intentions ────────────────────────────────

COMMITMENTS = "Which of my commitments are still not done?"


async def test_undated_adds_an_open_intention_with_no_due_time_to_a_commitment_question(rwired):
    """O3: "Book the AWS exam slot" has no due time and shares no word with the question."""
    rwired["due"] = [_intention(30, "Send the runbook")]
    rwired["undated"] = [_undated(31, "Book the AWS exam slot after the practice tests")]
    without = await assemble_context(COMMITMENTS, now=NOW, experiments=xp.parse("B"))
    snap = await assemble_context(COMMITMENTS, now=NOW, experiments=xp.parse("B,H"))
    assert "Book the AWS exam slot after the practice tests" not in _keys(without)
    assert _reasons(snap)["Book the AWS exam slot after the practice tests"] == (
        xp.UNDATED_INTENTION
    )
    assert snap.insufficient is False


@pytest.mark.parametrize(
    "bad",
    [
        {"trigger_time": NOW + timedelta(days=40)},  # dated, just not soon
        {"context_match": {"due_by": (NOW + timedelta(days=30)).isoformat()}},
        {"expires_at": NOW + timedelta(days=30)},
        {"tenant_id": "t-other"},
        {"status": "completed"},
        {"status": "dismissed"},
    ],
)
async def test_undated_never_adds_a_dated_or_foreign_intention(rwired, bad):
    """Adversarial: the read is looser than the SQL; the Python checks hold alone."""
    rwired["undated"] = [_undated(31, "Book the AWS exam slot", **bad)]
    snap = await assemble_context(COMMITMENTS, now=NOW, experiments=xp.parse("H"))
    assert "Book the AWS exam slot" not in _keys(snap)


async def test_undated_is_not_a_deadline_answer_and_not_for_as_of(rwired, monkeypatch):
    class _Manager:  # the intention's meaning is far from every question
        async def generate_embedding(self, text_):
            return [0.9, -0.4] if text_ == "Book the AWS exam slot" else [0.1, 0.2]

    monkeypatch.setattr(runtime, "get_memory_manager", _Manager)
    rwired["undated"] = [_undated(31, "Book the AWS exam slot")]
    deadlines = await assemble_context(
        "Which deadlines are coming up in the next few days?", now=NOW, experiments=xp.parse("H")
    )
    past = await assemble_context(
        COMMITMENTS, as_of=NOW - timedelta(days=5), now=NOW, experiments=xp.parse("H")
    )
    assert "Book the AWS exam slot" not in _keys(deadlines) | _keys(past)


async def test_undated_matches_an_unrelated_question_only_by_words_or_meaning(rwired, monkeypatch):
    """Adversarial: a fact question gets an undated intention only when it is about it."""
    near, far = "Book the AWS exam slot", "Fix the garden tap"

    class _Manager:
        async def generate_embedding(self, text_):
            return [0.9, -0.4] if text_ == far else [0.1, 0.2]

    monkeypatch.setattr(runtime, "get_memory_manager", _Manager)
    rwired["undated"] = [_undated(31, near), _undated(32, far)]
    by_meaning = await assemble_context(
        "When is my certification test?", now=NOW, experiments=xp.parse("H")
    )
    assert near in _keys(by_meaning) and far not in _keys(by_meaning)
    strict = xp.DEFAULT_TUNABLES.with_values({"INTENTION_FLOOR": 1.01})
    by_words = await assemble_context(
        "When do I book the AWS exam?", now=NOW, experiments=xp.parse("H"), tunables=strict
    )
    assert near in _keys(by_words) and far not in _keys(by_words)


# ── I: goal records ───────────────────────────────────────────

GOALS = "What are my active goals?"


def _goal_world(state):
    found = _mem("I'm not looking for a new job.", id=_id(1))
    aws = _mem(
        "The owner plans to pass the AWS Solutions Architect exam by March 2027.",
        id=_id(2),
        tags=["learning", "goal", "aws"],
        properties={"fact_type": "intention"},
    )
    marathon = _mem(
        "The owner wants to run the Chennai half marathon.",
        id=_id(3),
        tags=["fitness"],
        properties={"fact_type": "intention"},
    )
    errand = _mem(
        "Call the plumber about the kitchen leak.",
        id=_id(4),
        properties={"fact_type": "intention"},
    )
    state["found"] = [found]
    state["goal_rows"] = [aws, marathon, errand]
    return aws, marathon, errand


async def test_goals_bring_the_goal_records_to_a_goal_question(rwired):
    aws, marathon, errand = _goal_world(rwired)
    without = await assemble_context(GOALS, now=NOW, experiments=xp.parse("B"))
    snap = await assemble_context(GOALS, now=NOW, experiments=xp.parse("B,I"))
    assert aws.content not in _keys(without)
    assert _reasons(snap)[aws.content] == xp.GOAL_RECORD
    assert marathon.content in _keys(snap) and errand.content not in _keys(snap)
    # Labels are the record's own, exactly as any memory item gets them.
    item = next(i for i in snap.items if i.content == aws.content)
    plain = snapshot.memory_item(aws, NOW, snapshot.DEFAULT_BUDGET)
    assert (item.origin, item.confirmed, item.evidence, item.label) == (
        plain.origin,
        plain.confirmed,
        plain.evidence,
        plain.label,
    )


async def test_goals_with_a_subject_bring_only_the_goals_about_it(rwired):
    aws, marathon, _ = _goal_world(rwired)
    snap = await assemble_context("What is my AWS exam goal?", now=NOW, experiments=xp.parse("B,I"))
    assert aws.content in _keys(snap) and marathon.content not in _keys(snap)
    none = await assemble_context("How do I take my coffee?", now=NOW, experiments=xp.parse("I"))
    assert not {aws.content, marathon.content} & _keys(none)


@pytest.mark.parametrize(
    "bad",
    [
        {"trust_tier": "hostile_possible"},
        {"status": "pending"},
        {"status": "superseded"},
        {"superseded_by": uuid.UUID(int=77)},
        {"tenant_id": "t-other"},
        {"valid_until": NOW - timedelta(days=1)},
    ],
)
async def test_goals_never_bring_a_record_the_snapshot_would_not_show(rwired, bad):
    """Adversarial: another tenant's, hostile, pending, replaced or expired goals."""
    rwired["goal_rows"] = [_mem("My goal is to visit Japan.", id=_id(5), tags=["goal"], **bad)]
    snap = await assemble_context(GOALS, now=NOW, experiments=xp.parse("I"))
    assert "My goal is to visit Japan." not in _keys(snap)


async def test_goals_respect_the_pull_limit_and_as_of(rwired):
    rwired["goal_rows"] = [
        _mem(f"goal {n}", id=_id(40 + n), tags=["goal"]) for n in range(xp.GOAL_PULL + 3)
    ]
    snap = await assemble_context(GOALS, now=NOW, experiments=xp.parse("I"))
    assert sum(1 for i in snap.items if i.reason == xp.GOAL_RECORD) == xp.GOAL_PULL
    past = await assemble_context(
        GOALS, as_of=NOW - timedelta(days=5), now=NOW, experiments=xp.parse("I")
    )
    assert not any(i.reason == xp.GOAL_RECORD for i in past.items)


# ── J, K: overview questions and the cut ──────────────────────

OVERVIEW_Q = "What financial constraints should you consider before I buy a new laptop?"


def _finance_world(state):
    hits = [
        _mem(f"finance note {n}", id=_id(n), tags=["finance"] if n != 4 else ["work"])
        for n in range(1, 11)
    ]
    state["found"] = hits
    # A drop after the fourth hit: F alone keeps four.
    state["cosines"] = {
        str(_id(n)): c
        for n, c in zip(
            range(1, 11), (0.70, 0.69, 0.68, 0.67, 0.50, 0.49, 0.48, 0.47, 0.46, 0.20), strict=True
        )
    }
    return hits


async def test_overview_loosens_the_cut_for_an_overview_question_only(rwired):
    _finance_world(rwired)
    only_f = await assemble_context(OVERVIEW_Q, now=NOW, experiments=xp.parse("F"))
    with_j = await assemble_context(OVERVIEW_Q, now=NOW, experiments=xp.parse("F,J"))
    narrow = await assemble_context(
        "How big is our emergency fund?", now=NOW, experiments=xp.parse("F,J")
    )
    assert len(only_f.items) == 4
    # At least OVERVIEW_MIN_KEEP, then the looser floor (0.6 x 0.70): the 0.46
    # hit stays, the 0.20 one goes.
    assert len(with_j.items) == 9 > xp.OVERVIEW_MIN_KEEP
    assert "finance note 10" not in _keys(with_j)
    assert len(narrow.items) == 4
    only_j = await assemble_context(OVERVIEW_Q, now=NOW, experiments=xp.parse("J"))
    assert len(only_j.items) == 10  # alone it changes nothing


async def test_domain_holds_the_named_domain_through_the_cut(rwired):
    _finance_world(rwired)
    with_k = await assemble_context(OVERVIEW_Q, now=NOW, experiments=xp.parse("F,K"))
    kept = _keys(with_k)
    assert {f"finance note {n}" for n in (1, 2, 3, 5, 6, 7, 8, 9, 10)} <= kept
    assert "finance note 4" in kept  # above the cut anyway
    narrow = await assemble_context(
        "How big is our emergency fund money?", now=NOW, experiments=xp.parse("F,K")
    )
    assert len(narrow.items) == 4  # not an overview question: no hold
    other = await assemble_context(
        "What should I consider about my health?", now=NOW, experiments=xp.parse("F,K")
    )
    assert len(other.items) == 4  # a domain none of them is tagged with
