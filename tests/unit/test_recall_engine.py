"""Unit tests for the proactive recall engine (`services/recall.py`).

Recall decides which memories are pushed at you unprompted. Getting it wrong
is quiet: you are shown the wrong things, or nagged about facts you already
confirmed, and nothing errors. The module sat at 16%.

No database — the store, ranker and context builder are fakes.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from life_graph.services.recall import (
    RecallEngine,
    _dict_to_memory_response,
    _has_any_tag,
)

# ── Fakes ─────────────────────────────────────────────────────────────


class _Memory:
    """Stand-in for the ORM row, with every column _retrieve_candidates reads."""

    def __init__(self, **kw):
        now = datetime.now(UTC)
        self.id = kw.get("id", uuid.uuid4())
        self.content = kw.get("content", "some memory")
        self.tags = kw.get("tags", [])
        self.properties = kw.get("properties", {})
        self.importance = kw.get("importance", 0.5)
        self.trust_score = kw.get("trust_score", 0.5)
        self.access_count = kw.get("access_count", 0)
        self.last_accessed = kw.get("last_accessed", now)
        self.created_at = kw.get("created_at", now)
        self.source_type = kw.get("source_type", "inferred")
        self.status = kw.get("status", "active")
        self.confidence = kw.get("confidence", 0.5)
        self.reasoning = kw.get("reasoning")
        self.extraction_tier = kw.get("extraction_tier")
        self.extraction_confidence = kw.get("extraction_confidence")
        self.supersedes = kw.get("supersedes")
        self.superseded_by = kw.get("superseded_by")
        self.last_reinforced = kw.get("last_reinforced")
        self.reinforced_count = kw.get("reinforced_count", 0)


def _engine(rows=()):
    store = MagicMock()

    async def _list(**kw):
        return list(rows), False

    store.list_memories = _list

    ranker = MagicMock()
    ranker.rank = lambda c, current_context=None: list(c)
    ranker.rerank = lambda c, max_results=5: list(c)[:max_results]

    builder = MagicMock()
    fingerprint = MagicMock()
    fingerprint.project = None
    fingerprint.as_dict = lambda: {}
    builder.build = lambda ctx: fingerprint

    engine = RecallEngine(store, ranker, builder)
    engine._trigger_matcher = MagicMock()

    async def _check_all(fp):
        return {"time": [], "context": []}

    engine._trigger_matcher.check_all = _check_all
    return engine


# ── _has_any_tag ──────────────────────────────────────────────────────


def test_has_any_tag_is_case_insensitive():
    assert _has_any_tag(["Decision"], {"decision"})
    assert _has_any_tag(["WARNING", "x"], {"warning"})


def test_has_any_tag_no_overlap():
    assert not _has_any_tag(["random"], {"decision"})
    assert not _has_any_tag([], {"decision"})


# ── _dict_to_memory_response ──────────────────────────────────────────


def test_dict_to_response_minimal():
    out = _dict_to_memory_response({"id": str(uuid.uuid4()), "content": "hi"})
    assert out is not None
    assert out.content == "hi"


def test_dict_to_response_generates_an_id_when_blank():
    out = _dict_to_memory_response({"id": "", "content": "hi"})
    assert out is not None and out.id


def test_dict_to_response_returns_none_on_a_bad_uuid():
    assert _dict_to_memory_response({"id": "not-a-uuid", "content": "hi"}) is None


def test_dict_to_response_returns_none_on_a_bad_number():
    assert _dict_to_memory_response({"id": str(uuid.uuid4()), "importance": "high"}) is None


# ── Candidate construction: provenance + reinforcement ────────────────


@pytest.mark.asyncio
async def test_candidates_carry_reinforcement_fields():
    """needs_verification is computed from these; omitting them nags the user.

    _dict_to_memory_response feeds last_reinforced/reinforced_count to
    DecayCalculator.needs_verification. When _retrieve_candidates does not
    put them on the candidate dict they read as None/0, so a memory the user
    has confirmed repeatedly is still surfaced as unverified.
    """
    reinforced = _Memory(
        content="I prefer Postgres",
        confidence=0.8,
        created_at=datetime.now(UTC) - timedelta(days=400),
        last_reinforced=datetime.now(UTC) - timedelta(days=2),
        reinforced_count=6,
    )
    engine = _engine([reinforced])

    candidates = await engine._retrieve_candidates(MagicMock(project=None))

    assert candidates[0]["reinforced_count"] == 6
    assert candidates[0]["last_reinforced"] is not None

    response = _dict_to_memory_response(candidates[0])
    assert response is not None
    assert response.needs_verification is False, (
        "a memory confirmed 6 times was flagged as needing verification"
    )


@pytest.mark.asyncio
async def test_candidates_carry_provenance_fields():
    mem = _Memory(
        extraction_tier="rules",
        extraction_confidence=0.95,
        supersedes=uuid.uuid4(),
        superseded_by=None,
    )
    candidates = await _engine([mem])._retrieve_candidates(MagicMock(project=None))

    assert candidates[0]["extraction_tier"] == "rules"
    assert candidates[0]["extraction_confidence"] == 0.95
    assert candidates[0]["supersedes"] is not None


@pytest.mark.asyncio
async def test_candidate_dict_supplies_everything_the_converter_reads():
    """Guards the class of bug directly: built keys must cover read keys."""
    import ast
    import inspect
    import textwrap

    from life_graph.services import recall

    src = textwrap.dedent(inspect.getsource(recall.RecallEngine._retrieve_candidates))
    built = {
        k.value
        for node in ast.walk(ast.parse(src))
        if isinstance(node, ast.Dict)
        for k in node.keys
        if isinstance(k, ast.Constant)
    }

    src2 = textwrap.dedent(inspect.getsource(recall._dict_to_memory_response))
    read = {
        node.args[0].value
        for node in ast.walk(ast.parse(src2))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    }

    missing = sorted(read - built)
    assert not missing, (
        f"_dict_to_memory_response reads keys _retrieve_candidates never sets: {missing}"
    )


# ── Anti-annoyance ────────────────────────────────────────────────────


def _cand(mem_id=None, tags=None):
    return {"id": str(mem_id or uuid.uuid4()), "tags": tags or []}


def test_anti_annoyance_passes_fresh_candidates():
    engine = _engine()
    cands = [_cand() for _ in range(3)]
    assert len(engine._apply_anti_annoyance(cands)) == 3


def test_anti_annoyance_suppresses_recently_surfaced():
    engine = _engine()
    c = _cand()
    engine._surfaced_memory_ids[c["id"]] = datetime.now(UTC)

    assert engine._apply_anti_annoyance([c]) == []


def test_anti_annoyance_releases_after_the_cooldown():
    from life_graph.services.recall import _COOLDOWN_SECONDS

    engine = _engine()
    c = _cand()
    engine._surfaced_memory_ids[c["id"]] = datetime.now(UTC) - timedelta(
        seconds=_COOLDOWN_SECONDS + 60
    )

    assert len(engine._apply_anti_annoyance([c])) == 1


def test_anti_annoyance_drops_categories_dismissed_three_times():
    engine = _engine()
    for _ in range(3):
        engine.dismiss(str(uuid.uuid4()), "noise")

    assert engine._apply_anti_annoyance([_cand(tags=["noise"])]) == []


def test_two_dismissals_are_not_enough_to_suppress():
    engine = _engine()
    for _ in range(2):
        engine.dismiss(str(uuid.uuid4()), "noise")

    assert len(engine._apply_anti_annoyance([_cand(tags=["noise"])])) == 1


def test_anti_annoyance_enforces_the_session_cap():
    from life_graph.services.recall import _MAX_SESSION_SURFACES

    engine = _engine()
    out = engine._apply_anti_annoyance([_cand() for _ in range(_MAX_SESSION_SURFACES + 5)])
    assert len(out) == _MAX_SESSION_SURFACES


def test_session_cap_accounts_for_already_surfaced():
    from life_graph.services.recall import _MAX_SESSION_SURFACES

    engine = _engine()
    engine._session_surface_count = _MAX_SESSION_SURFACES - 2

    assert len(engine._apply_anti_annoyance([_cand() for _ in range(5)])) == 2


def test_dismiss_also_starts_the_cooldown():
    engine = _engine()
    c = _cand()
    engine.dismiss(c["id"], "cat")

    assert engine._apply_anti_annoyance([c]) == []


# ── Categorization ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("tags", "bucket"),
    [
        (["identity"], 0),
        (["preference"], 0),
        (["style"], 0),
        (["value"], 0),
        (["decision"], 1),
        (["architecture"], 1),
        (["choice"], 1),
        (["warning"], 2),
        (["lesson"], 2),
        (["bug"], 2),
        (["contradiction"], 2),
    ],
)
def test_categorize_by_tag(tags, bucket):
    engine = _engine()
    buckets = engine._categorize_memories([{"id": str(uuid.uuid4()), "tags": tags}])
    assert len(buckets[bucket]) == 1
    assert sum(len(b) for b in buckets) == 1


def test_identity_wins_over_decision_when_both_tags_present():
    engine = _engine()
    identity, decisions, _ = engine._categorize_memories(
        [{"id": str(uuid.uuid4()), "tags": ["decision", "identity"]}]
    )
    assert len(identity) == 1 and len(decisions) == 0


def test_cold_start_memories_are_identity():
    engine = _engine()
    identity, _, _ = engine._categorize_memories(
        [{"id": str(uuid.uuid4()), "tags": [], "source_type": "cold_start"}]
    )
    assert len(identity) == 1


def test_untagged_memories_fall_through_to_decisions():
    engine = _engine()
    _, decisions, _ = engine._categorize_memories(
        [{"id": str(uuid.uuid4()), "tags": [], "source_type": "inferred"}]
    )
    assert len(decisions) == 1


def test_unconvertible_candidates_are_skipped_not_fatal():
    engine = _engine()
    buckets = engine._categorize_memories([{"id": "not-a-uuid", "tags": ["decision"]}])
    assert sum(len(b) for b in buckets) == 0


# ── Orchestration ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_session_start_tracks_what_it_surfaced():
    engine = _engine([_Memory(tags=["decision"]), _Memory(tags=["warning"])])

    result = await engine.session_start_recall({})

    assert engine._session_surface_count == 2
    assert len(engine._surfaced_memory_ids) == 2
    assert len(result.decisions) == 1
    assert len(result.warnings) == 1


@pytest.mark.asyncio
async def test_session_start_with_no_memories():
    result = await _engine([]).session_start_recall({})
    assert result.identity == [] and result.decisions == [] and result.warnings == []


@pytest.mark.asyncio
async def test_a_second_session_start_surfaces_nothing_new():
    """The cooldown must actually hold across calls on one engine."""
    engine = _engine([_Memory(tags=["decision"])])

    first = await engine.session_start_recall({})
    second = await engine.session_start_recall({})

    assert len(first.decisions) == 1
    assert len(second.decisions) == 0


@pytest.mark.asyncio
async def test_mid_session_respects_the_cap():
    from life_graph.services.recall import _MAX_SESSION_SURFACES

    engine = _engine([_Memory()])
    engine._session_surface_count = _MAX_SESSION_SURFACES

    assert await engine.mid_session_recall({}, "file_opened") == []


@pytest.mark.asyncio
async def test_mid_session_returns_at_most_the_configured_maximum():
    from life_graph.config import settings

    engine = _engine([_Memory() for _ in range(10)])
    out = await engine.mid_session_recall({}, "error_encountered")

    assert len(out) <= settings.recall_max_during_session
