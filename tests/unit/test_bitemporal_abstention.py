from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
import uuid

import pytest

from life_graph.api.search import AskRequest, ask_brain
from life_graph.services.memory_retrieval import is_valid_at


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

    monkeypatch.setattr("life_graph.services.memory_retrieval.retrieve", _fake_retrieve)
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

    monkeypatch.setattr("life_graph.services.memory_retrieval.retrieve", _fake_retrieve)
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
    from life_graph.services.memory_retrieval import provenance_order

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
        artifacts=["life_graph/services/memory_retrieval.py"],
    )
    assert cp["idempotency_key"].startswith("task-123:")
    assert cp["completed_steps"] == ["edit_files"]
    assert cp["interrupt_requeues"] == 1
    assert can_safely_resume(task, precondition_ok=True) == (True, "ok")
    assert can_safely_resume(task, precondition_ok=False) == (False, "precondition_failed")
