"""Declining to answer has to reach the caller as more than prose.

The synthesis prompt has always told the model to say it has no answer, and a
local model obeys: 3 of 3 unanswerable gold questions declined, 5 of 5
answerable ones answered. But the refusal arrived as a sentence inside
`answer`, so nothing downstream could act on it without regex.

This cannot be solved in the ranking instead. Search always returns rows, and
no scoring signal separates an answerable question from an unanswerable one on
this instance — top score, margin over second, ratio and spread all overlap
(evals/score-separability.md). The judgement has to come from something that
reads meaning, which makes `answered` the only honest "I don't know" the API
has.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from life_graph.services.synthesis import (
    ABSTENTION_SENTENCE,
    _SYNTHESIS_SYSTEM_PROMPT,
    SynthesisService,
    _is_abstention,
)

MEMORIES = [{"id": "11111111-1111-1111-1111-111111111111", "content": "x", "tags": []}]


def _service(answer: str) -> SynthesisService:
    return SynthesisService(client=AsyncMock(chat=AsyncMock(return_value=answer)))


class TestTheFlag:
    @pytest.mark.asyncio
    async def test_the_refusal_sets_answered_false(self):
        result = await _service(ABSTENTION_SENTENCE).synthesize("anything?", MEMORIES)

        assert result["answered"] is False

    @pytest.mark.asyncio
    async def test_an_answer_sets_answered_true(self):
        result = await _service("You chose the Luminaux template.").synthesize("?", MEMORIES)

        assert result["answered"] is True

    @pytest.mark.asyncio
    async def test_no_memories_at_all_is_also_a_refusal(self):
        result = await _service("unused").synthesize("anything?", [])

        assert result["answered"] is False
        assert result["source_count"] == 0


class TestWhatCountsAsDeclining:
    @pytest.mark.parametrize(
        "answer",
        [
            ABSTENTION_SENTENCE,
            f"  {ABSTENTION_SENTENCE}  ",
            ABSTENTION_SENTENCE.upper(),
            f'"{ABSTENTION_SENTENCE}"',
            ABSTENTION_SENTENCE.rstrip("."),
        ],
    )
    def test_the_sentence_in_its_usual_disguises(self, answer):
        assert _is_abstention(answer)

    @pytest.mark.parametrize(
        "answer",
        [
            # The important half. A model that hedges and then answers has
            # answered; calling that a refusal would hide a real answer, which
            # is worse than reporting nothing.
            f"{ABSTENTION_SENTENCE} That said, you did mention Luminaux.",
            "I don't have enough memories about your car, but you drive to work.",
            "You chose the Luminaux template.",
            "",
        ],
    )
    def test_anything_longer_is_an_answer(self, answer):
        assert not _is_abstention(answer)


def test_the_prompt_and_the_parser_cannot_drift():
    """Both ends share one constant — that agreement is the whole mechanism."""
    assert ABSTENTION_SENTENCE in _SYNTHESIS_SYSTEM_PROMPT


def test_the_prompt_says_a_full_result_set_is_not_evidence():
    """The model is handed ten memories whatever it asks, so it has to be told
    that receiving them means nothing about their relevance."""
    assert "not evidence" in _SYNTHESIS_SYSTEM_PROMPT
