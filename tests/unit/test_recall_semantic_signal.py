"""The semantic signal in proactive recall must actually be computed.

`_retrieve_candidates` set `semantic_score` to a literal 0.5 for every
candidate, with a comment saying so. Semantic is 0.20 of the ranker's weight —
joint largest with context — so a fifth of every score was the same number for
every candidate, and the ranking was really being decided by the remaining
0.80. The fix embeds the context fingerprint once and compares it against the
vectors the candidates already carry.

These tests pin the three things that can regress: that the score varies with
the candidate, that a missing or broken embedding backend leaves the old
neutral value rather than raising inside a hook with a 10-second budget, and
that the fingerprint is embedded as prose rather than as a field dump.
"""

from __future__ import annotations

import math
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from life_graph.services.context import ContextFingerprint
from life_graph.services.recall import RecallEngine, _cosine


def _memory(content: str, embedding: list[float] | None) -> SimpleNamespace:
    return SimpleNamespace(
        id="00000000-0000-0000-0000-00000000000a",
        content=content,
        tags=[],
        properties={},
        importance=0.5,
        trust_score=0.5,
        access_count=0,
        last_accessed=None,
        created_at=None,
        source_type="capture",
        status="active",
        confidence=0.5,
        reasoning=None,
        extraction_tier="llm",
        extraction_confidence=0.9,
        supersedes=None,
        superseded_by=None,
        last_reinforced=None,
        reinforced_count=0,
        impact_score=0.5,
        embedding=embedding,
    )


@pytest.fixture
def fingerprint() -> ContextFingerprint:
    return ContextFingerprint(project="life-graph", git_branch="fix/recall", topics=["memory"])


def _engine(embedder, memories):
    store = SimpleNamespace(list_recall_candidates=AsyncMock(return_value=memories))
    return RecallEngine(store, SimpleNamespace(), SimpleNamespace(), embedding_service=embedder)


class TestTheSignalIsComputed:
    @pytest.mark.asyncio
    async def test_scores_differ_per_candidate(self, fingerprint):
        """The whole point: a constant cannot reorder anything."""
        near = _memory("about memory recall", [1.0, 0.0, 0.0])
        far = _memory("about billing", [0.0, 1.0, 0.0])
        embedder = SimpleNamespace(embed_async=AsyncMock(return_value=[1.0, 0.0, 0.0]))

        candidates = await _engine(embedder, [near, far])._retrieve_candidates(fingerprint)

        assert candidates[0]["semantic_score"] == pytest.approx(1.0)
        assert candidates[1]["semantic_score"] == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_the_fingerprint_is_embedded_as_prose(self, fingerprint):
        embedder = SimpleNamespace(embed_async=AsyncMock(return_value=[1.0, 0.0]))

        await _engine(embedder, [_memory("x", [1.0, 0.0])])._retrieve_candidates(fingerprint)

        embedded = embedder.embed_async.await_args.args[0]
        assert "project life-graph" in embedded
        assert "on branch fix/recall" in embedded

    @pytest.mark.asyncio
    async def test_a_negative_similarity_clamps_to_zero(self, fingerprint):
        """Cosine is -1..1; every other signal is 0..1, so a negative score
        would subtract from a weighted sum that assumes it cannot."""
        opposed = _memory("opposite", [-1.0, 0.0])
        embedder = SimpleNamespace(embed_async=AsyncMock(return_value=[1.0, 0.0]))

        candidates = await _engine(embedder, [opposed])._retrieve_candidates(fingerprint)

        assert candidates[0]["semantic_score"] == 0.0


class TestItFailsOpen:
    @pytest.mark.asyncio
    async def test_no_embedding_service_keeps_the_neutral_value(self, fingerprint):
        store = SimpleNamespace(
            list_recall_candidates=AsyncMock(return_value=[_memory("x", [1.0, 0.0])])
        )
        engine = RecallEngine(store, SimpleNamespace(), SimpleNamespace())

        candidates = await engine._retrieve_candidates(fingerprint)

        assert candidates[0]["semantic_score"] == 0.5

    @pytest.mark.asyncio
    async def test_a_failing_backend_does_not_raise(self, fingerprint):
        """This runs inside a hook with a hard time budget — a dead embedder
        must cost a worse ranking, not a broken session."""
        embedder = SimpleNamespace(embed_async=AsyncMock(side_effect=RuntimeError("down")))

        candidates = await _engine(embedder, [_memory("x", [1.0, 0.0])])._retrieve_candidates(
            fingerprint
        )

        assert candidates[0]["semantic_score"] == 0.5

    @pytest.mark.asyncio
    async def test_a_candidate_without_a_vector_is_left_alone(self, fingerprint):
        embedder = SimpleNamespace(embed_async=AsyncMock(return_value=[1.0, 0.0]))

        candidates = await _engine(embedder, [_memory("x", None)])._retrieve_candidates(fingerprint)

        assert candidates[0]["semantic_score"] == 0.5

    @pytest.mark.asyncio
    async def test_an_empty_fingerprint_skips_the_embedding_call(self):
        """Nothing to match on — spending an embedding round trip on an empty
        string would be latency for no signal."""
        embedder = SimpleNamespace(embed_async=AsyncMock(return_value=[1.0, 0.0]))

        await _engine(embedder, [_memory("x", [1.0, 0.0])])._retrieve_candidates(
            ContextFingerprint()
        )

        embedder.embed_async.assert_not_awaited()


class TestCosine:
    def test_identical_vectors(self):
        assert _cosine([1.0, 2.0], [1.0, 2.0]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        assert _cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    @pytest.mark.parametrize(
        "a,b",
        [([], [1.0]), ([1.0], []), ([1.0, 2.0], [1.0]), ([0.0, 0.0], [1.0, 1.0])],
    )
    def test_unusable_inputs_return_none(self, a, b):
        """Length mismatch and zero vectors both have no defined similarity;
        returning 0.0 would be a claim, and None lets the caller keep 0.5."""
        assert _cosine(a, b) is None

    def test_matches_the_textbook_definition(self):
        a, b = [1.0, 2.0, 3.0], [4.0, 5.0, 6.0]
        expected = sum(x * y for x, y in zip(a, b, strict=False)) / (
            math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
        )
        assert _cosine(a, b) == pytest.approx(expected)
