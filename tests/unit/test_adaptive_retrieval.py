"""Retrieval that knows when to stop, and an answer that knows what it stands on.

Improvement plan §3.C (adaptive retrieval) and §3.A (memory that understands
its limitations). Two behaviours are pinned here:

* A top hit carrying the owner's own fresh words, accounting for every content
  word of the question, ends retrieval: entity and link expansion are skipped,
  so a sufficient answer does not pay for candidates it cannot use.
* Evidence that contradicts the question, or that resolves to nothing, comes
  back labelled — as an abstention indicator on the collection and on each
  memory, and as ``/ask``'s ``epistemic_status``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from life_graph.api.search import (
    EPISTEMIC_CONTRADICTED,
    EPISTEMIC_EXPLICIT,
    EPISTEMIC_INFERRED,
    EPISTEMIC_STALE,
    EPISTEMIC_UNSUPPORTED,
    AskRequest,
    ask_brain,
    classify_epistemic_status,
)
from life_graph.services.memory.retrieval import (
    EARLY_EXIT_CONFIDENCE,
    RetrievalResult,
    assess_candidate_evidence,
    assess_hit_evidence,
    retrieve,
)

#: The question every early-exit test asks, and the memory that answers it
#: outright: every content word of the question is in the memory's own text.
QUESTION = "What is my home insurance renewal month?"
ANSWER = "My home insurance renewal month is March."


def _mem(content: str, **overrides):
    now = datetime.now(UTC)
    base = {
        "id": uuid.uuid4(),
        "content": content,
        "reasoning": None,
        "tags": [],
        "properties": {},
        "importance": 0.6,
        "confidence": 1.0,
        "source_type": "user_explicit",
        "trust_tier": "self",
        "trust_score": 0.95,
        "status": "active",
        "access_count": 1,
        "created_at": now,
        "updated_at": now,
        "last_accessed": None,
        "valid_from": None,
        "valid_until": None,
        "capture_event_id": None,
        "supersedes": None,
        "superseded_by": None,
        "reinforced_count": 0,
        "last_reinforced": None,
        "impact_score": 0.5,
        "needs_verification": False,
        "extraction_tier": None,
        "extraction_confidence": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture
def wired(monkeypatch):
    """`retrieve`'s collaborators, each recording whether it was consulted.

    Everything is local and in-process: the embedding, the hybrid store, the
    relevance judge, the entity index and the link graph.
    """
    from life_graph.core.tenant import tenant_scope
    from life_graph.services import entities
    from life_graph.services.memory import associations

    calls = {"entities": 0, "neighbours": 0, "judge": 0}
    state: dict[str, list] = {"hits": [], "neighbours": [], "named": []}

    class _Manager:
        async def generate_embedding(self, text):
            return [0.1] * 8

    class _Store:
        async def hybrid_search(self, **_kw):
            return [(m, 0.9 - i * 0.01) for i, m in enumerate(state["hits"])]

    class _Client:
        async def chat_local_only(self, messages, **_kw):
            calls["judge"] += 1
            listing = messages[-1]["content"]
            count = listing.count("\n") - listing[: listing.index("Notes:")].count("\n")
            kept = ", ".join(str(i + 1) for i in range(max(count, 0)))
            return f'{{"relevant": [{kept}]}}'

    async def _known_in_text(_tenant, _text):
        calls["entities"] += 1
        return state["named"]

    async def _memories_for(_tenant, _ids, limit=8):
        return state["named_memories"]

    async def _neighbours(_tenant, _ids, limit=6):
        calls["neighbours"] += 1
        return state["neighbours"]

    import life_graph.runtime as runtime

    monkeypatch.setattr(runtime, "get_memory_manager", lambda: _Manager())
    monkeypatch.setattr(runtime, "get_store", lambda: _Store())
    monkeypatch.setattr(runtime, "get_lm_client", lambda: _Client())
    monkeypatch.setattr(entities, "known_in_text", _known_in_text)
    monkeypatch.setattr(entities, "memories_for", _memories_for)
    monkeypatch.setattr(entities, "alias_hint", lambda *_a, **_k: None)
    monkeypatch.setattr(associations, "neighbours", _neighbours)
    monkeypatch.setattr("life_graph.config.settings.memory_links", True)
    state["named_memories"] = []
    with tenant_scope("t_adaptive"):
        yield SimpleNamespace(calls=calls, state=state)


# ── §3.C early exit ───────────────────────────────────────────


def test_a_sufficient_top_hit_is_recognised_without_any_search_score():
    assessment = assess_hit_evidence(QUESTION, _mem(ANSWER))

    assert assessment["sufficient"] is True
    assert assessment["keywords_covered"] is True
    assert assessment["entailment_score"] == 1.0
    assert assessment["calibrated_confidence"] >= EARLY_EXIT_CONFIDENCE


async def test_early_exit_skips_entity_and_neighbour_expansion(wired):
    """The answer is already in hand: expanding can only add distractors."""
    wired.state["hits"] = [_mem(ANSWER)]
    wired.state["named"] = [(uuid.uuid4(), "home insurance")]
    wired.state["named_memories"] = [_mem("Car insurance renews in July.")]
    wired.state["neighbours"] = [_mem("The insurance broker is called Vantage.")]

    out = await retrieve(QUESTION, limit=6)

    assert [m.content for m in out] == [ANSWER]
    assert out.early_exit is True
    assert wired.calls["neighbours"] == 0, "neighbour expansion ran despite a sufficient top hit"
    assert wired.calls["entities"] == 0, "entity expansion ran despite a sufficient top hit"


async def test_an_insufficient_top_hit_still_expands(wired):
    """The gate is real: a partial match keeps both expansions."""
    wired.state["hits"] = [_mem("Insurance is handled by the broker.")]
    wired.state["named"] = []
    wired.state["neighbours"] = [_mem("The broker renewal pack arrives in February.")]

    out = await retrieve(QUESTION, limit=6)

    assert out.early_exit is False
    assert wired.calls["neighbours"] == 1
    assert wired.calls["entities"] == 1
    assert len(out) == 2


async def test_early_exit_does_not_fire_on_stale_or_inferred_evidence(wired):
    """Same words, weaker evidence: a guess is never sufficient on its own."""
    guess = _mem(ANSWER, source_type="distillation", trust_tier="unverified", confidence=0.6)
    wired.state["hits"] = [guess]
    wired.state["neighbours"] = []

    out = await retrieve(QUESTION, limit=6)

    assert out.early_exit is False
    assert wired.calls["neighbours"] == 1


# ── §3.C abstention indicators ────────────────────────────────


def test_contradictory_candidates_are_reported_as_contradiction_not_thin_evidence():
    question = "Do I drink coffee every morning?"
    against = _mem("I no longer drink coffee every morning.")
    for_ = _mem("I drink coffee every morning.")

    assessment = assess_candidate_evidence(question, [against, for_])

    assert assessment["abstain"] is True
    assert assessment["abstention_reason"] == "contradictory_evidence"
    assert assessment["contradicted"] == [str(against.id)]
    assert assessment["unresolvable"] == []
    assert assessment["supported"] == 1


def test_unresolvable_candidates_are_reported_when_nothing_resolves():
    question = "Which bank holds my emergency fund?"
    thin = _mem(
        "The cat prefers tuna.",
        source_type="distillation",
        trust_tier="quarantined",
        confidence=0.1,
    )
    gone = _mem("", status="deleted")

    assessment = assess_candidate_evidence(question, [thin, gone])

    assert assessment["abstain"] is True
    assert assessment["abstention_reason"] == "unresolvable_missing_evidence"
    assert set(assessment["unresolvable"]) == {str(thin.id), str(gone.id)}
    assert assessment["supported"] == 0


def test_one_supported_candidate_is_not_an_abstention():
    assessment = assess_candidate_evidence(QUESTION, [_mem(ANSWER)])

    assert assessment["abstain"] is False
    assert assessment["abstention_reason"] is None


async def test_retrieve_attaches_the_abstention_indicator_to_what_it_returns(wired):
    question = "Do I drink coffee every morning?"
    against = _mem("I no longer drink coffee every morning.")
    wired.state["hits"] = [against]
    wired.state["neighbours"] = []

    out = await retrieve(question, limit=6)

    assert isinstance(out, RetrievalResult)
    assert out.abstain is True
    assert out.abstention_reason == "contradictory_evidence"
    assert out.evidence["contradicted"] == [str(against.id)]
    # And on the memory itself, for a caller that reads rows rather than the
    # collection it got them in.
    assert out[0].retrieval_evidence["support_status"] == "contradicted"


async def test_a_good_answer_carries_no_abstention_indicator(wired):
    wired.state["hits"] = [_mem(ANSWER)]
    wired.state["neighbours"] = []

    out = await retrieve(QUESTION, limit=6)

    assert out.abstain is False
    assert out.abstention_reason is None
    assert out[0].retrieval_evidence["support_status"] == "supported"


def test_a_failed_assessment_claims_nothing_either_way(monkeypatch):
    """A broken assessment must not invent support — nor an abstention."""

    def _boom(*_a, **_k):
        raise RuntimeError("entailment backend exploded")

    monkeypatch.setattr("life_graph.core.evidence.verify_claim_support", _boom)
    assessment = assess_candidate_evidence(QUESTION, [_mem(ANSWER)])

    assert assessment["abstain"] is False
    assert assessment["supported"] == 0
    assert assessment["per_memory"][0]["recommended_action"] == "abstain"


# ── §3.A epistemic status and lineage ─────────────────────────


def test_epistemic_status_is_worst_first():
    now = datetime.now(UTC)
    explicit = _mem(ANSWER)
    inferred = _mem(ANSWER, source_type="distillation", trust_tier="unverified")
    stale = _mem(ANSWER, valid_until=now - timedelta(days=1))
    contradicted = _mem("I no longer renew in March.", properties={"contradicted": True})

    assert classify_epistemic_status([explicit], abstained=False, now=now) == EPISTEMIC_EXPLICIT
    assert classify_epistemic_status([inferred], abstained=False, now=now) == EPISTEMIC_INFERRED
    assert classify_epistemic_status([explicit, stale], abstained=False, now=now) == EPISTEMIC_STALE
    assert (
        classify_epistemic_status(
            [explicit, inferred, stale, contradicted], abstained=False, now=now
        )
        == EPISTEMIC_CONTRADICTED
    )
    assert classify_epistemic_status([], abstained=False, now=now) == EPISTEMIC_UNSUPPORTED
    assert classify_epistemic_status([explicit], abstained=True, now=now) == EPISTEMIC_UNSUPPORTED


def test_epistemic_status_reads_retrievals_own_contradiction_finding():
    """Retrieval already checked the question against the text; don't re-derive it."""
    row = _mem(ANSWER)
    row.retrieval_evidence = {"contradicted": True, "support_status": "contradicted"}

    assert classify_epistemic_status([row], abstained=False) == EPISTEMIC_CONTRADICTED


def _ask_deps(rows, *, answer="Your home insurance renews in March.", answered=True):
    class _Mgr:
        async def _generate_embedding(self, _q):
            return [0.1] * 8

    class _Meta:
        async def track_query(self, *_a, **_kw):
            return None

    class _Synth:
        async def synthesize(self, _q, _memories):
            return {
                "answer": answer,
                "answered": answered,
                "source_count": len(rows),
                "model": "local-test",
            }

    return {"store": None, "manager": _Mgr(), "metamemory": _Meta(), "synthesis": _Synth()}


async def test_ask_brain_returns_epistemic_status_and_source_lineage(monkeypatch):
    row = _mem(
        ANSWER,
        capture_event_id=uuid.uuid4(),
        properties={"source_excerpt": "renewal is in March, every year"},
    )
    rows = RetrievalResult([row], evidence=assess_candidate_evidence(QUESTION, [row]))

    async def _retrieve(_q, limit=10, as_of=None):
        return rows

    monkeypatch.setattr("life_graph.services.memory.retrieval.retrieve", _retrieve)
    res = await ask_brain(AskRequest(question=QUESTION), **_ask_deps(rows))
    payload = res["data"]

    assert payload.epistemic_status == EPISTEMIC_EXPLICIT
    lineage = payload.source_lineage
    assert [item["memory_id"] for item in lineage] == [str(row.id)]
    assert lineage[0]["evidence_kind"] == "said"
    assert lineage[0]["source_available"] is True
    assert lineage[0]["lineage"]["capture_event_id"] == str(row.capture_event_id)
    assert lineage[0]["lineage"]["excerpt"] == "renewal is in March, every year"


async def test_ask_brain_reports_contradicted_evidence_rather_than_plain_agreement(monkeypatch):
    question = "Do I drink coffee every morning?"
    row = _mem("I no longer drink coffee every morning.")
    rows = RetrievalResult(
        [row],
        abstain=True,
        abstention_reason="contradictory_evidence",
        evidence=assess_candidate_evidence(question, [row]),
    )

    async def _retrieve(_q, limit=10, as_of=None):
        return rows

    monkeypatch.setattr("life_graph.services.memory.retrieval.retrieve", _retrieve)
    res = await ask_brain(AskRequest(question=question), **_ask_deps(rows, answer="You used to."))

    assert res["data"].epistemic_status == EPISTEMIC_CONTRADICTED
    assert res["data"].source_lineage


async def test_ask_brain_abstention_is_unsupported_and_still_discloses_lineage(monkeypatch):
    row = _mem(ANSWER, confidence=0.2)

    async def _retrieve(_q, limit=10, as_of=None):
        return RetrievalResult([row])

    monkeypatch.setattr("life_graph.services.memory.retrieval.retrieve", _retrieve)
    res = await ask_brain(AskRequest(question=QUESTION, min_confidence=0.8), **_ask_deps([row]))

    assert res["data"].abstained is True
    assert res["data"].epistemic_status == EPISTEMIC_UNSUPPORTED
    assert [item["memory_id"] for item in res["data"].source_lineage] == [str(row.id)]


async def test_ask_brain_without_memories_is_unsupported(monkeypatch):
    async def _retrieve(_q, limit=10, as_of=None):
        return RetrievalResult([])

    monkeypatch.setattr("life_graph.services.memory.retrieval.retrieve", _retrieve)
    res = await ask_brain(AskRequest(question=QUESTION), **_ask_deps([]))

    assert res["data"].abstained is True
    assert res["data"].epistemic_status == EPISTEMIC_UNSUPPORTED
    assert res["data"].source_lineage == []
