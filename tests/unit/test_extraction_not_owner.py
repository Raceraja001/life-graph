"""Pasted text and tool or agent messages are not the owner speaking.

A spec pasted for a coding agent became 8 "decisions" of the owner's
(2026-10-29); task notifications and agent replies were extracted the same way.
"""

from __future__ import annotations

import pytest

from life_graph.extraction import pipeline as pipeline_module
from life_graph.extraction.llm import default_prompt
from life_graph.extraction.pipeline import ExtractionPipeline, not_the_owners_words


def test_pasted_blocks_and_tool_messages_are_removed():
    text = (
        '<pasted_content id="p1">\nAdd a setting APP_MODE.\n</pasted_content>\ndo this '
        "<task-notification><status>completed</status></task-notification>"
        "<agent-message from='x'>done</agent-message> and I prefer tea"
    )

    assert not_the_owners_words(text).split() == ["do", "this", "and", "I", "prefer", "tea"]


def test_the_owners_own_words_stay():
    assert not_the_owners_words("I prefer <b>tea</b> in the evening") == (
        "I prefer <b>tea</b> in the evening"
    )
    assert not_the_owners_words("") == ""


@pytest.mark.asyncio
async def test_a_message_that_is_only_pasted_text_is_not_extracted(monkeypatch):
    called = []

    class _LLM:
        async def extract(self, text):
            called.append(text)
            return []

    p = ExtractionPipeline.__new__(ExtractionPipeline)
    p._llm = _LLM()
    monkeypatch.setattr(pipeline_module.settings, "capture_llm_clean", True)
    result = await p.extract('<pasted_content id="p1">\nspec\n</pasted_content>', capture=True)

    assert result.facts == [] and called == []


def test_the_prompt_keeps_questions_out_of_decisions():
    prompt = default_prompt()

    assert "A question is at most an intention, never a preference or decision" in prompt
