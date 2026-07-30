"""Fallback path no longer emits Entity(...)/Tech mention: fragments, and floors confidence."""

from life_graph.extraction.nlp import SpacyExtractor
from life_graph.extraction.pipeline import _drop_low_confidence
from life_graph.extraction.rules import ExtractedFact


def test_no_standalone_entity_or_tech_facts():
    ex = SpacyExtractor()
    facts = ex.extract("I switched from MySQL to Postgres and use FastAPI")
    assert all("Entity (" not in f.content and "Tech mention:" not in f.content for f in facts)


def test_confidence_floor():
    facts = [
        ExtractedFact(content="keep", fact_type="fact", confidence=0.6),
        ExtractedFact(content="drop", fact_type="fact", confidence=0.3),
    ]
    kept = _drop_low_confidence(facts, 0.45)
    assert [f.content for f in kept] == ["keep"]
