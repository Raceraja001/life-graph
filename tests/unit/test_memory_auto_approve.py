"""Which new memories skip the review queue: what the owner, in their own words,
asked to be remembered, or stated as a firm fact, preference or decision."""

from __future__ import annotations

import pytest

from life_graph.core.memory_manager import _auto_approved
from life_graph.extraction.rules import ExtractedFact


def _fact(fact_type="explicit_save", confidence=0.9, content="My car insurance renews in March."):
    return ExtractedFact(content=content, fact_type=fact_type, confidence=confidence)


@pytest.mark.parametrize(
    ("fact", "tier", "kept"),
    [
        (_fact(), "self", "explicit_save"),
        (_fact(), "verified", None),  # system-produced
        (_fact(), "external", None),  # an API or MCP client
        (_fact(), None, None),
        (_fact(confidence=0.6), "self", None),  # not clearly asked
        # Firm statements in the owner's own words (2026-10-28).
        (
            _fact("preference", 1.0, "The owner prefers local HTML files to artifacts."),
            "self",
            "firm_owner_fact",
        ),
        (
            _fact("decision", 0.95, "The owner retired port 3001 for 3006."),
            "self",
            "firm_owner_fact",
        ),
        (
            _fact("fact", 0.9, "mediagrab is reachable only through Tailscale."),
            "self",
            "firm_owner_fact",
        ),
        (_fact("anti_preference", 0.9, "The owner avoids n8n."), "self", "firm_owner_fact"),
        # ...but not below 0.9, not from anyone else, and never a plan.
        (_fact("preference", 0.85, "The owner prefers Dify."), "self", None),
        (_fact("fact", 1.0, "The MCP server is on port 1044."), "external", None),
        (_fact("intention", 1.0, "The owner wants to build mockups."), "self", None),
    ],
)
def test_auto_approval_rule(fact, tier, kept):
    assert _auto_approved(fact, tier) == kept


@pytest.mark.parametrize(
    "content",
    [
        "The owner is considering building local HTML mockups.",
        "The owner is exploring OpenHands and Dify.",
        "The owner prefers focusing on the web app for now.",
        "The owner might move the API to port 9000.",
        "The owner is thinking about whether to reuse features.",
        "The owner considers Life Graph a potential platform.",
    ],
)
def test_hedged_statements_wait_for_review(content):
    assert _auto_approved(_fact("preference", 1.0, content), "self") is None


def test_a_clash_with_an_active_memory_waits_for_review():
    firm = _fact("decision", 1.0, "The owner moved the web app to port 3006.")
    assert _auto_approved(firm, "self", contradicts=True) is None
    # An explicit "remember this" still wins, as before: it supersedes at once,
    # undoable through the contradiction approval.
    assert _auto_approved(_fact(), "self", contradicts=True) == "explicit_save"
