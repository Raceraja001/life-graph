"""A rule the owner sets ("always…", "never…", "from now on…") is kept like
"remember that…" (services/capture_processors.py promote_standing)."""

from __future__ import annotations

import pytest

from life_graph.extraction.rules import ExtractedFact
from life_graph.services.capture_processors import STANDING_MAX_CHARS, promote_standing


def _fact(kind: str) -> ExtractedFact:
    return ExtractedFact(
        content="The owner prefers local HTML files.", fact_type=kind, confidence=1.0
    )


@pytest.mark.parametrize(
    "message",
    [
        "create local HTML files instead of artifacts. always",
        "never push the life-graph-ui repo",
        "From now on use stubs for third-party info",
        "every time you finish, tell me what changed",
    ],
)
def test_a_rule_the_owner_sets_is_an_explicit_save(message):
    facts = promote_standing([_fact("preference"), _fact("decision")], message)
    assert [f.fact_type for f in facts] == ["explicit_save", "explicit_save"]


def test_only_rule_like_facts_are_promoted():
    facts = promote_standing([_fact("fact"), _fact("intention")], "always use tabs")
    assert [f.fact_type for f in facts] == ["fact", "intention"]


@pytest.mark.parametrize(
    "message",
    ["I prefer tea in the evening", "can you open it in a browser?", "", None],
)
def test_no_rule_word_changes_nothing(message):
    assert promote_standing([_fact("preference")], message)[0].fact_type == "preference"


def test_a_long_pasted_text_saying_always_is_not_a_rule():
    pasted = "Release notes: the service always retries. " + "x" * STANDING_MAX_CHARS
    assert promote_standing([_fact("preference")], pasted)[0].fact_type == "preference"
