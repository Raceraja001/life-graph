import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from life_graph.api.search import AskRequest, ask_brain
from life_graph.services.memory.retrieval import is_valid_at


def _mem(content: str, *, days_ago: int = 10, valid_days: int | None = None, confidence: float = 0.8):
    now = datetime.now(UTC)
    v_from = now - timedelta(days=days_ago)
    v_until = (v_from + timedelta(days=valid_days)) if valid_days is not None else None
    return SimpleNamespace(
        id=uuid.uuid4(),
        content=content,
        reasoning=None,
        tags=[],
        properties={},
        importance=0.5,
        importance_tier="normal",
        confidence=confidence,
        source_type="conversation",
        source=None,
        trust_score=0.8,
        trust_tier="trusted",
        created_at=v_from,
        updated_at=v_from,
        valid_from=v_from,
        valid_until=v_until,
        access_count=0,
        last_accessed=None,
        decay_rate=0.01,
        status="active",
        owner="default",
        tenant_id="legacy",
        supersedes=None,
        superseded_by=None,
        extraction_tier=None,
        extraction_confidence=None,
    )


def test_is_valid_at_bitemporal_window():
    now = datetime.now(UTC)
    m = _mem("Active in Feb", days_ago=60, valid_days=30)
    # Before valid_from -> False
    assert is_valid_at(m, now - timedelta(days=70)) is False
    # Inside [valid_from, valid_until) -> True
    assert is_valid_at(m, now - timedelta(days=45)) is True
    # At/after valid_until -> False
    assert is_valid_at(m, now - timedelta(days=10)) is False


@pytest.mark.asyncio
async def test_ask_brain_abstains_when_no_memories(monkeypatch):
    class _Mgr:
        async def _generate_embedding(self, q):
            return [0.1] * 8

    class _Meta:
        async def track_query(self, *a, **kw):
            pass

    class _Synth:
        async def synthesize(self, *a, **kw):
            raise AssertionError("Should abstain without calling LLM synthesis")

    async def _fake_retrieve(q, limit=10, as_of=None):
        return []

    monkeypatch.setattr("life_graph.services.memory.retrieval.retrieve", _fake_retrieve)
    res = await ask_brain(
        AskRequest(question="What is my secret project?"),
        store=None,
        manager=_Mgr(),
        metamemory=_Meta(),
        synthesis=_Synth(),
    )
    assert res.answered is False
    assert res.abstained is True
    assert res.abstention_reason == "no_matching_memories"


@pytest.mark.asyncio
async def test_ask_brain_abstains_below_min_confidence(monkeypatch):
    class _Mgr:
        async def _generate_embedding(self, q):
            return [0.1] * 8

    class _Meta:
        async def track_query(self, *a, **kw):
            pass

    class _Synth:
        async def synthesize(self, *a, **kw):
            raise AssertionError("Should abstain below min_confidence")

    low_mem = _mem("Uncertain rumour", confidence=0.25)

    async def _fake_retrieve(q, limit=10, as_of=None):
        return [low_mem]

    monkeypatch.setattr("life_graph.services.memory.retrieval.retrieve", _fake_retrieve)
    res = await ask_brain(
        AskRequest(question="Is this confirmed?", min_confidence=0.6),
        store=None,
        manager=_Mgr(),
        metamemory=_Meta(),
        synthesis=_Synth(),
    )
    assert res.answered is False
    assert res.abstained is True
    assert res.abstention_reason == "low_confidence"


def test_provenance_order_prefers_verified_high_trust():
    from types import SimpleNamespace

    from life_graph.services.memory.retrieval import provenance_order

    low = SimpleNamespace(id="low", trust_score=0.3, confidence=0.4, trust_tier="inferred", source_type="chat")
    high = SimpleNamespace(id="high", trust_score=0.9, confidence=0.9, trust_tier="verified", source_type="user_explicit")
    # Close semantic scores (0.82 vs 0.80): provenance tie-breaker puts high first
    ordered = provenance_order([(low, 0.82), (high, 0.80)])
    assert [m.id for m, _ in ordered] == ["high", "low"]


def test_detect_knowledge_gaps_surfaces_low_confidence_and_superseded():
    from types import SimpleNamespace

    from life_graph.api.search import detect_knowledge_gaps

    assert detect_knowledge_gaps([], abstained=True, abstention_reason="no_matching_memories")
    mems = [SimpleNamespace(confidence=0.4, status="superseded", trust_score=0.3)]
    gaps = detect_knowledge_gaps(mems, abstained=False, abstention_reason=None)
    assert len(gaps) == 3


async def test_lm_client_embed_falls_back_to_ollama(monkeypatch):
    from life_graph.services.llm_client import LMStudioClient

    client = LMStudioClient(base_url="http://localhost:11435/v1")

    class FailingEmbeddings:
        async def create(self, **_kw):
            raise RuntimeError("501 not_supported_error")

    class FakeAsyncClient:
        embeddings = FailingEmbeddings()

    monkeypatch.setattr(client, "_get_async_client", lambda: FakeAsyncClient())

    async def fake_ollama_embed(texts):
        return [[0.25, 0.75] for _ in texts]

    monkeypatch.setattr(client, "_ollama_embed", fake_ollama_embed)
    vec = await client.embed("hello")
    assert vec == [0.25, 0.75]
    batch = await client.embed_batch(["a", "b"])
    assert batch == [[0.25, 0.75], [0.25, 0.75]]


def test_p2_cross_domain_and_challenge_mode():
    from datetime import UTC, datetime, timedelta
    from types import SimpleNamespace

    from life_graph.api.search import detect_challenge_prompts, summarize_cross_domain

    old_ts = datetime.now(UTC) - timedelta(days=120)
    mems = [
        SimpleNamespace(category="finance", memory_type="preference", created_at=old_ts, updated_at=old_ts, access_count=1),
        SimpleNamespace(category="hardware", memory_type="semantic", created_at=datetime.now(UTC), updated_at=None, access_count=5),
    ]
    domains = summarize_cross_domain(mems)
    assert domains == {"finance": 1, "hardware": 1}
    prompts = detect_challenge_prompts(mems)
    assert len(prompts) == 1
    assert "preference" in prompts[0].lower()


def test_p3_build_brief_evidence():
    from life_graph.services.brief import build_brief_evidence

    ev = build_brief_evidence(
        held=[{"id": "1"}],
        questions=[{"id": "q1"}],
        capture_summary={"total": 3},
        watcher_summary=None,
        big_decisions=[],
        approvals_line="2 pending",
    )
    sections = [item["section"] for item in ev]
    assert sections == ["held_notifications", "interview_questions", "captures", "approvals"]
    assert all("why" in item for item in ev)


def test_p3_durable_task_checkpoint_and_resume_guard():
    from types import SimpleNamespace

    from life_graph.services.dev_tasks import build_checkpoint, can_safely_resume

    task = SimpleNamespace(
        id="task-123",
        title="Refactor retrieval",
        status="queued",
        properties={"instruction": "Refactor retrieval", "interrupt_requeues": 1},
    )
    cp = build_checkpoint(
        task,
        stage="interrupted_restart",
        completed_steps=["edit_files"],
        artifacts=["life_graph/services/memory/retrieval.py"],
    )
    assert cp["idempotency_key"].startswith("task-123:")
    assert cp["completed_steps"] == ["edit_files"]
    assert cp["interrupt_requeues"] == 1
    assert can_safely_resume(task, precondition_ok=True) == (True, "ok")
    assert can_safely_resume(task, precondition_ok=False) == (False, "precondition_failed")


def test_p0_2_bitemporal_valid_and_transaction_time():
    from datetime import UTC, datetime
    from types import SimpleNamespace

    from life_graph.services.memory.retrieval import is_bitemporally_valid

    # Fact was valid in June 2026 (valid_from=Jun 1, valid_until=Jul 1),
    # but was only recorded on Aug 1 (late correction / past effective date).
    mem = SimpleNamespace(
        valid_from=datetime(2026, 6, 1, tzinfo=UTC),
        valid_until=datetime(2026, 7, 1, tzinfo=UTC),
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    # Valid in June if queried from today's transaction knowledge (recorded_at=Sep 1)
    assert is_bitemporally_valid(
        mem,
        valid_at=datetime(2026, 6, 15, tzinfo=UTC),
        recorded_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    # NOT known as of July 15 transaction time (before Aug 1 recording)
    assert not is_bitemporally_valid(
        mem,
        valid_at=datetime(2026, 6, 15, tzinfo=UTC),
        recorded_at=datetime(2026, 7, 15, tzinfo=UTC),
    )


# ── P5.1 True bitemporal history ─────────────────────────────────────────


def _bitemporal_mem(**over):
    """A memory row with both timelines set explicitly, as SQLAlchemy would hand it over."""
    base = {
        "valid_from": datetime(2026, 1, 1, tzinfo=UTC),
        "valid_until": None,
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "properties": {},
    }
    base.update(over)
    return SimpleNamespace(**base)


def test_p5_1_supersession_reconstructs_the_belief_that_was_current_then():
    """A corrected memory must come back for the window it was still believed in."""
    from life_graph.services.memory.retrieval import is_bitemporally_valid, is_known_at

    # "Raja lives in Bangalore", recorded Jan 1, corrected away on Jun 1.
    old_belief = _bitemporal_mem(
        properties={"superseded_at": datetime(2026, 6, 1, tzinfo=UTC)},
    )

    # Before the correction landed, this WAS what the system believed.
    assert is_known_at(old_belief, datetime(2026, 3, 1, tzinfo=UTC)) is True
    assert is_bitemporally_valid(
        old_belief,
        valid_at=datetime(2026, 3, 1, tzinfo=UTC),
        recorded_at=datetime(2026, 3, 1, tzinfo=UTC),
    )

    # The instant the correction landed, and ever after, it is history — not
    # current belief — even though its valid window never closed.
    assert is_known_at(old_belief, datetime(2026, 6, 1, tzinfo=UTC)) is False
    assert is_known_at(old_belief, datetime(2026, 9, 1, tzinfo=UTC)) is False
    assert not is_bitemporally_valid(
        old_belief,
        valid_at=datetime(2026, 9, 1, tzinfo=UTC),
        recorded_at=datetime(2026, 9, 1, tzinfo=UTC),
    )

    # Without a transaction-time anchor, supersession is not a constraint:
    # ordinary retrieval asks only "was this true in the world?".
    assert is_bitemporally_valid(old_belief, valid_at=datetime(2026, 9, 1, tzinfo=UTC))


def test_p5_1_superseded_at_read_from_attribute_as_well_as_properties():
    from life_graph.services.memory.retrieval import is_known_at

    on_attr = _bitemporal_mem(superseded_at=datetime(2026, 6, 1, tzinfo=UTC))
    assert is_known_at(on_attr, datetime(2026, 5, 1, tzinfo=UTC)) is True
    assert is_known_at(on_attr, datetime(2026, 7, 1, tzinfo=UTC)) is False


def test_p5_1_recorded_at_wins_over_created_at_for_in_place_edits():
    """created_at is not transaction time: an edited row keeps its original one."""
    from life_graph.services.memory.retrieval import is_known_at, recorded_time_of

    # Row created Jan 1, then corrected in place on Aug 1; the correction's
    # recorded_at is the only honest answer to "when did we know this?".
    edited = _bitemporal_mem(
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        properties={"recorded_at": "2026-08-01T00:00:00Z"},
    )
    assert recorded_time_of(edited) == datetime(2026, 8, 1, tzinfo=UTC)
    # created_at alone would wrongly claim we knew this in March.
    assert is_known_at(edited, datetime(2026, 3, 1, tzinfo=UTC)) is False
    assert is_known_at(edited, datetime(2026, 9, 1, tzinfo=UTC)) is True

    # With no recorded_at anywhere, created_at is still the fallback.
    plain = _bitemporal_mem(created_at=datetime(2026, 8, 1, tzinfo=UTC))
    assert recorded_time_of(plain) == datetime(2026, 8, 1, tzinfo=UTC)
    assert is_known_at(plain, datetime(2026, 3, 1, tzinfo=UTC)) is False


def test_p5_1_normalizes_naive_iso_and_offset_timestamps_to_utc():
    from datetime import timezone

    from life_graph.services.memory.retrieval import is_bitemporally_valid, is_valid_at

    # A naive column (SQLite, or a row built in a test) is read as UTC.
    naive = _bitemporal_mem(
        valid_from=datetime(2026, 6, 1),
        valid_until=datetime(2026, 7, 1),
        created_at=datetime(2026, 6, 1),
    )
    assert is_valid_at(naive, datetime(2026, 6, 15, tzinfo=UTC)) is True
    assert is_valid_at(naive, datetime(2026, 7, 15, tzinfo=UTC)) is False

    # ISO strings out of JSONB, including a non-UTC offset, land on the same line.
    ist = timezone(timedelta(hours=5, minutes=30))
    from_json = _bitemporal_mem(
        valid_from=None,
        properties={
            "valid_from": "2026-06-01T05:30:00+05:30",  # == 2026-06-01T00:00Z
            "superseded_at": "2026-07-01T05:30:00+05:30",
        },
    )
    assert is_valid_at(from_json, datetime(2026, 6, 1, tzinfo=UTC)) is True
    assert is_valid_at(from_json, datetime(2026, 5, 31, 23, 59, tzinfo=UTC)) is False
    # A query asked in IST must get the same answer as the same instant in UTC.
    assert not is_bitemporally_valid(
        from_json, recorded_at=datetime(2026, 7, 1, 5, 30, tzinfo=ist)
    )
    assert is_bitemporally_valid(
        from_json, recorded_at=datetime(2026, 7, 1, 5, 29, tzinfo=ist)
    )

    # A timestamp that is not a timestamp is ignored, not guessed at.
    junk = _bitemporal_mem(properties={"superseded_at": "not a date"})
    assert is_bitemporally_valid(junk, recorded_at=datetime(2026, 9, 1, tzinfo=UTC))


def test_p5_1_three_historical_question_forms():
    """The three questions bitemporality exists to answer, on one fact's history."""
    from life_graph.services.memory.retrieval import is_bitemporally_valid

    # What we recorded in March: "Raja is in Chennai from Jan, indefinitely".
    # On Jun 1 we learned he had actually left in May, so the Jan fact was
    # superseded and a corrected one recorded in its place.
    march_belief = _bitemporal_mem(
        valid_from=datetime(2026, 1, 1, tzinfo=UTC),
        valid_until=None,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        properties={"superseded_at": datetime(2026, 6, 1, tzinfo=UTC)},
    )
    correction = _bitemporal_mem(
        valid_from=datetime(2026, 1, 1, tzinfo=UTC),
        valid_until=datetime(2026, 5, 1, tzinfo=UTC),
        created_at=datetime(2026, 6, 1, tzinfo=UTC),
        properties={"recorded_at": datetime(2026, 6, 1, tzinfo=UTC)},
    )
    now = datetime(2026, 11, 14, tzinfo=UTC)

    # 1. "What did we believe on March 1?" — the original, not the correction.
    march = datetime(2026, 3, 1, tzinfo=UTC)
    assert is_bitemporally_valid(march_belief, recorded_at=march)
    assert not is_bitemporally_valid(correction, recorded_at=march)

    # 2. "What do we NOW believe was true on July 1?" — neither: the corrected
    #    fact ended in May, and the original is no longer believed at all.
    july = datetime(2026, 7, 1, tzinfo=UTC)
    assert not is_bitemporally_valid(march_belief, valid_at=july, recorded_at=now)
    assert not is_bitemporally_valid(correction, valid_at=july, recorded_at=now)
    # ... and on April 1 we now believe only the correction.
    april = datetime(2026, 4, 1, tzinfo=UTC)
    assert is_bitemporally_valid(correction, valid_at=april, recorded_at=now)
    assert not is_bitemporally_valid(march_belief, valid_at=april, recorded_at=now)

    # 3. "What did we believe on March 1 was true on July 1?" — the original,
    #    which back then still claimed to run indefinitely. Reconstructing
    #    March's answer must not leak June's knowledge.
    assert is_bitemporally_valid(march_belief, valid_at=july, recorded_at=march)
    assert not is_bitemporally_valid(correction, valid_at=july, recorded_at=march)
