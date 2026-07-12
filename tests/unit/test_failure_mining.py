"""Unit tests for failure-pattern mining (citation rule + parsing)."""

from __future__ import annotations

from life_graph.services.failure_mining import FailurePatternMiner


def test_citation_rule_drops_thinly_cited():
    patterns = [
        {"description": "abandons side projects at ~week 6", "decision_ids": ["a", "b", "c"]},
        {"description": "over-invests in tooling", "decision_ids": ["x", "y"]},  # only 2
        {"description": "uncited hunch", "decision_ids": []},
    ]
    kept = FailurePatternMiner.enforce_citation_rule(patterns)
    assert len(kept) == 1
    assert kept[0]["description"].startswith("abandons")


def test_citation_rule_dedupes_ids():
    patterns = [{"description": "p", "decision_ids": ["a", "a", "b", "c", "c"]}]
    kept = FailurePatternMiner.enforce_citation_rule(patterns)
    assert kept[0]["decision_ids"] == ["a", "b", "c"]


def test_citation_rule_respects_custom_threshold():
    patterns = [{"description": "p", "decision_ids": ["a", "b"]}]
    assert FailurePatternMiner.enforce_citation_rule(patterns, min_instances=2)
    assert not FailurePatternMiner.enforce_citation_rule(patterns, min_instances=3)


def test_parse_patterns_object_shape():
    raw = '{"patterns": [{"description": "d", "decision_ids": ["1", "2", "3"]}]}'
    out = FailurePatternMiner._parse_patterns(raw)
    assert out == [{"description": "d", "decision_ids": ["1", "2", "3"]}]


def test_parse_patterns_list_shape_and_coercion():
    raw = '[{"description": "d", "decision_ids": [1, 2]}]'
    out = FailurePatternMiner._parse_patterns(raw)
    assert out[0]["decision_ids"] == ["1", "2"]  # coerced to str


def test_parse_patterns_bad_json_is_empty():
    assert FailurePatternMiner._parse_patterns("not json") == []
    assert FailurePatternMiner._parse_patterns('{"patterns": "nope"}') == []


def test_parse_patterns_skips_missing_description():
    raw = '{"patterns": [{"decision_ids": ["1","2","3"]}, {"description": "ok", "decision_ids": []}]}'
    out = FailurePatternMiner._parse_patterns(raw)
    assert len(out) == 1
    assert out[0]["description"] == "ok"


async def test_mine_without_llm_returns_empty():
    miner = FailurePatternMiner(llm=None)
    assert await miner.mine([{"decision_id": "a", "title": "x", "status": "superseded", "domain_tags": []}]) == []
