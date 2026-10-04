"""Search results carry their relevance score.

The hybrid ranker computed a score for every hit and `_to_memory_responses`
dropped it, so every caller — the MCP tool, the chat agent, the dashboard —
received `limit` rows with no way to tell a direct hit from the best of a bad
lot. The index projection had carried a score all along; only the full shape
discarded one.

What the score does NOT support is a threshold. Measured on this instance,
answerable and unanswerable questions overlap on the top score, on the margin
over second place, and on two relative measures — see
`evals/score-separability.md`. It orders results; it does not judge them.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from life_graph.api.search import _to_memory_responses


def _row(content: str):
    return SimpleNamespace(
        id=uuid.uuid4(),
        content=content,
        tags=[],
        properties={},
        importance=0.5,
        confidence=0.5,
        source_type="capture",
        created_at=datetime.now(UTC),
        status="active",
        access_count=0,
        reasoning=None,
        extraction_tier="llm",
        extraction_confidence=0.9,
        last_accessed=None,
        supersedes=None,
        superseded_by=None,
        reinforced_count=0,
        last_reinforced=None,
        impact_score=0.5,
    )


def test_each_result_carries_its_own_score():
    hits = [(_row("a strong match"), 0.83), (_row("a weak one"), 0.21)]

    responses = _to_memory_responses(hits)

    assert [r.score for r in responses] == [0.83, 0.21]


def test_the_order_of_scores_follows_the_order_of_hits():
    """The list is already ranked; pairing must not shuffle it."""
    hits = [(_row(f"m{i}"), 1.0 - i / 10) for i in range(5)]

    responses = _to_memory_responses(hits)

    assert [r.score for r in responses] == sorted((r.score for r in responses), reverse=True)


def test_score_is_none_when_nothing_scored_it():
    """Every other path — list, batch, recall — has no query to be relevant to,
    and a default of 0.0 there would read as 'scored, and irrelevant'."""
    from life_graph.models.schemas import MemoryResponse

    response = MemoryResponse.model_validate(_row("not from a search"))

    assert response.score is None
