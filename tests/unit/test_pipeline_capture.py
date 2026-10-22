"""Capture mode uses the LLM as primary extractor; rules/nlp are fallback."""

import pytest

from life_graph.extraction.pipeline import ExtractionPipeline
from life_graph.extraction.rules import ExtractedFact


class _Rules:
    def extract(self, text):
        return [ExtractedFact(content="fastapi → my fav", fact_type="fact", confidence=0.6)]


class _Spacy:
    def extract(self, text):
        return [ExtractedFact(content="Tech mention: fastapi", fact_type="fact", confidence=0.6)]


class _LLMok:
    async def extract(self, text):
        return [
            ExtractedFact(
                content="The user likes FastAPI",
                fact_type="preference",
                confidence=0.9,
                entities=["FastAPI"],
            )
        ]


class _LLMdown:
    async def extract(self, text):
        raise RuntimeError("llm down")


@pytest.mark.asyncio
async def test_capture_prefers_llm():
    p = ExtractionPipeline(
        rules_extractor=_Rules(), spacy_extractor=_Spacy(), llm_extractor=_LLMok()
    )
    result = await p.extract("i like fastapi", capture=True)
    contents = [f.content for f in result.facts]
    assert "The user likes FastAPI" in contents
    assert all("Tech mention" not in c and "→" not in c for c in contents)


class _LLMnothing:
    async def extract(self, text):
        return []


@pytest.mark.asyncio
async def test_capture_keeps_nothing_when_the_llm_finds_nothing():
    # "Nothing worth keeping" is the LLM's answer, not a failure: the regex
    # tier must not turn it into fragments like "fastapi → my fav".
    p = ExtractionPipeline(
        rules_extractor=_Rules(), spacy_extractor=_Spacy(), llm_extractor=_LLMnothing()
    )
    result = await p.extract("tests are running again", capture=True)
    assert result.facts == [] and result.llm_invoked


@pytest.mark.asyncio
async def test_capture_falls_back_on_llm_error():
    p = ExtractionPipeline(
        rules_extractor=_Rules(), spacy_extractor=_Spacy(), llm_extractor=_LLMdown()
    )
    result = await p.extract("i like fastapi", capture=True)
    assert result.facts  # rules/nlp fallback still produced something
