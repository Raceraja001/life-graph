"""Extraction keeps who a fact is about, its "not" and "maybe", the reason and a correction.

The 2026-10-30 memory bake-off traced most wrong answers to these losses (a
colleague's "learning Japanese" became the owner's; "thinking about an electric
car" became "decided to buy one"). evals/memory_structures/extraction_meaning.json
measures the model; these tests pin the parsing and the rules around it.
"""

from __future__ import annotations

import json

import pytest

from life_graph.config import settings
from life_graph.core.memory_manager import _auto_approved
from life_graph.extraction.llm import _EXTRACTION_SCHEMA, LLMExtractor, _meaning
from life_graph.extraction.rules import ExtractedFact


class _FakeClient:
    def __init__(self, reply: str) -> None:
        self.reply = reply

    async def chat_local_only(self, **kwargs) -> str:
        return self.reply


@pytest.mark.parametrize(
    ("item", "expected"),
    [
        ({}, ("owner", "affirm", "firm", None, False)),
        ({"subject": "The owner"}, ("owner", "affirm", "firm", None, False)),
        ({"subject": "user"}, ("owner", "affirm", "firm", None, False)),
        ({"subject": " Ravi "}, ("Ravi", "affirm", "firm", None, False)),
        ({"polarity": "NEGATE"}, ("owner", "negate", "firm", None, False)),
        ({"polarity": "maybe"}, ("owner", "affirm", "firm", None, False)),
        ({"certainty": "hedged"}, ("owner", "affirm", "hedged", None, False)),
        (
            {"reason": "  Firebase got   too expensive "},
            ("owner", "affirm", "firm", "Firebase got too expensive", False),
        ),
        ({"correction": True}, ("owner", "affirm", "firm", None, True)),
        ({"correction": "yes"}, ("owner", "affirm", "firm", None, False)),
    ],
)
def test_meaning_falls_back_to_the_plain_reading(item, expected):
    out = _meaning(item)
    assert (
        out["subject"],
        out["polarity"],
        out["certainty"],
        out["reason"],
        out["correction"],
    ) == expected


def test_the_schema_asks_for_the_meaning():
    props = _EXTRACTION_SCHEMA["properties"]["facts"]["items"]["properties"]
    assert {"subject", "polarity", "certainty", "reason", "correction"} <= set(props)
    # Not required: a small model that skips them still gets the plain reading.
    assert "subject" not in _EXTRACTION_SCHEMA["properties"]["facts"]["items"]["required"]


@pytest.mark.asyncio
async def test_the_extractor_carries_the_fields(monkeypatch):
    monkeypatch.setattr(settings, "lm_structured_output", True)
    reply = json.dumps(
        {
            "facts": [
                {
                    "content": "Ravi (the owner's colleague) is learning Japanese.",
                    "fact_type": "fact",
                    "confidence": 0.95,
                    "entities": ["Ravi"],
                    "subject": "Ravi",
                },
                {
                    "content": "The owner is considering an electric car next year.",
                    "fact_type": "intention",
                    "confidence": 0.8,
                    "entities": [],
                    "certainty": "hedged",
                },
                {
                    "content": "FarmLink moved to PostgreSQL because Firebase got too expensive.",
                    "fact_type": "decision",
                    "confidence": 0.95,
                    "entities": ["FarmLink"],
                    "reason": "Firebase got too expensive",
                    "correction": True,
                },
            ]
        }
    )
    facts = await LLMExtractor(lm_client=_FakeClient(reply))._extract_local("…")
    assert [f.subject for f in facts] == ["Ravi", "owner", "owner"]
    assert [f.certainty for f in facts] == ["firm", "hedged", "firm"]
    assert facts[2].reason == "Firebase got too expensive" and facts[2].correction is True


def _fact(**kw) -> ExtractedFact:
    base = {
        "content": "The owner prefers local HTML files.",
        "fact_type": "preference",
        "confidence": 0.95,
    }
    return ExtractedFact(**{**base, **kw})


def test_a_hedged_fact_is_never_kept_unreviewed():
    assert _auto_approved(_fact(), "self") == "firm_owner_fact"
    # Worded without "maybe", but the extractor knew it was only being considered.
    assert _auto_approved(_fact(certainty="hedged"), "self") is None
    assert _auto_approved(_fact(fact_type="explicit_save", certainty="hedged"), "self") is None
