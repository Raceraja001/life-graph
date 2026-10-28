"""Unit tests for LLM offers file_adoption function.

Tests that cover all 4 decision points in file_adoption, plus tenant scoping.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

from life_graph.services.llm_offers import file_adoption
from tests.unit.fakes import FakeSession


async def test_file_adoption_already_exists():
    """Test case when Approval already exists for this offer - should return early."""
    # Create mock offer
    offer = AsyncMock()
    offer.id = uuid.uuid4()
    offer.tenant_id = "tenant1"
    offer.evaluation = {"passed": 5, "total": 10}
    offer.terms = {"trains_on_prompts": "yes", "commercial_use": "no"}
    offer.model_id = "openrouter/gpt-4"

    # Mock existing approval
    existing_approval = AsyncMock()
    existing_approval.id = uuid.uuid4()

    # Set up session to return existing approval
    session = FakeSession(existing_approval)

    await file_adoption(session, offer)

    # Should not add new approval (no add calls)
    assert len(session.added) == 0

    # Should only execute one query (for checking existing approval)
    assert len(session.statements) == 1


async def test_file_adoption_no_existing_approval():
    """Test case when no approval exists yet - should create a new one."""
    # Create mock offer
    offer = AsyncMock()
    offer.id = uuid.uuid4()
    offer.tenant_id = "tenant1"
    offer.evaluation = {
        "passed": 5,
        "total": 10,
        "honest": 4,
        "avg_s": 2.5,
        "edits_ok": 3,
        "edits_failed": 1,
    }
    offer.terms = {"trains_on_prompts": "yes", "commercial_use": "no"}
    offer.model_id = "openrouter/gpt-4"

    # Mock session to return no existing approval
    session = FakeSession(None)  # None indicates no existing approval

    await file_adoption(session, offer)

    # Should have added an Approval
    assert len(session.added) == 1

    # Verify the approval details
    approval = session.added[0]
    assert approval.tenant_id == "tenant1"
    assert approval.kind == "model_adoption"
    assert approval.source_ref == str(offer.id)
    assert approval.source == "llm_offers"
    assert approval.title == f"Adopt free model {offer.model_id}"
    assert "passed 5/10 coding tasks" in approval.detail
    assert "trains on prompts: yes" in approval.detail
    assert "commercial use: no" in approval.detail


async def test_file_adoption_missing_evaluation_data():
    """Test case when evaluation data is missing - should handle gracefully."""
    # Create mock offer with minimal data
    offer = AsyncMock()
    offer.id = uuid.uuid4()
    offer.tenant_id = "tenant1"
    offer.evaluation = {}
    offer.terms = {}
    offer.model_id = "openrouter/gpt-4"

    session = FakeSession(None)  # None indicates no existing approval

    await file_adoption(session, offer)

    # Should have added an Approval
    assert len(session.added) == 1

    # Verify the approval has default values for missing data
    approval = session.added[0]
    assert "unknown" in approval.detail  # checks for default 'unknown' values
