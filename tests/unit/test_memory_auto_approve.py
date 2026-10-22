"""Which new memories skip the review queue: only what the owner, in their own
words, explicitly asked to be remembered."""

from __future__ import annotations

import pytest

from life_graph.core.memory_manager import _auto_approved
from life_graph.extraction.rules import ExtractedFact


def _fact(fact_type="explicit_save", confidence=0.9):
    return ExtractedFact(
        content="My car insurance renews in March.", fact_type=fact_type, confidence=confidence
    )


@pytest.mark.parametrize(
    ("fact", "tier", "approved"),
    [
        (_fact(), "self", True),
        (_fact(), "verified", False),  # system-produced
        (_fact(), "external", False),  # an API or MCP client
        (_fact(), None, False),
        (_fact("preference"), "self", False),  # inferred, not asked for
        (_fact(confidence=0.6), "self", False),  # not clearly asked
    ],
)
def test_auto_approval_rule(fact, tier, approved):
    assert _auto_approved(fact, tier) is approved
