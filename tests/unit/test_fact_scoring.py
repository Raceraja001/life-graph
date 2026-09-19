"""fact_set_f1: extractions compared as sets of facts, by meaning."""

from __future__ import annotations

import json

import pytest

from life_graph.self_improving.eval_scorer import EvalScorer
from life_graph.self_improving.fact_scoring import fact_set_f1, parse_facts, score_extraction

# Hand-made "embeddings": texts on the same axis mean the same thing.
_VECTORS = {
    "uses uv": [1.0, 0.0, 0.0],
    "prefers uv over pip": [0.95, 0.05, 0.0],
    "dentist on the 3rd": [0.0, 1.0, 0.0],
    "renew domain": [0.0, 0.0, 1.0],
}


async def _embed(texts: list[str]) -> list[list[float]]:
    return [_VECTORS[t] for t in texts]


def _facts(*contents: str) -> str:
    return json.dumps({"facts": [{"content": c} for c in contents]})


@pytest.mark.asyncio
async def test_paraphrases_match():
    result = await fact_set_f1(["prefers uv over pip"], ["uses uv"], _embed, 0.8)
    assert result["f1"] == 1.0


@pytest.mark.asyncio
async def test_partial_extraction_scores_precision_and_recall():
    result = await fact_set_f1(
        ["uses uv", "renew domain"], ["uses uv", "dentist on the 3rd"], _embed, 0.8
    )
    assert result["precision"] == 0.5
    assert result["recall"] == 0.5
    assert result["f1"] == 0.5


@pytest.mark.asyncio
async def test_matching_is_one_to_one():
    """Two predictions of the same fact count once, not twice."""
    result = await fact_set_f1(["uses uv", "prefers uv over pip"], ["uses uv"], _embed, 0.8)
    assert result["matched"] == 1
    assert result["precision"] == 0.5


@pytest.mark.asyncio
async def test_both_empty_is_correct():
    """'Nothing worth keeping' is a right answer the user confirmed."""
    result = await fact_set_f1([], [], _embed, 0.8)
    assert result["f1"] == 1.0


@pytest.mark.asyncio
async def test_extracting_from_nothing_scores_zero():
    result = await fact_set_f1(["uses uv"], [], _embed, 0.8)
    assert result["f1"] == 0.0


def test_parse_rejects_schema_echo_and_garbage():
    assert parse_facts('{"type": "object", "properties": {}}') is None
    assert parse_facts("not json") is None
    assert parse_facts(_facts("a", "")) == [{"content": "a"}]  # blank facts dropped


@pytest.mark.asyncio
async def test_invalid_model_output_fails_the_case():
    passed, score, reason = await score_extraction(_facts("uses uv"), "oops", _embed, 0.8, 0.8)
    assert not passed and score == 0.0 and "not a valid facts list" in reason


@pytest.mark.asyncio
async def test_scorer_routes_fact_set_f1_to_the_async_path():
    scorer = EvalScorer(embed=_embed)
    passed, score, _ = await scorer.score_async(
        "fact_set_f1", _facts("uses uv"), _facts("prefers uv over pip"), {}
    )
    assert passed and score == 1.0
    # Other types still go through the synchronous scorers unchanged.
    assert (await scorer.score_async("exact_match", "a", "A", {}))[0] is True
