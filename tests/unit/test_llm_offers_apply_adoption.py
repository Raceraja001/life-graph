"""Unit tests for apply_adoption function.

These tests verify the behavior of apply_adoption when handling LLM offer adoption approval/rejection.
The tests mock refresh_adopted to avoid complex session setup requirements, while still testing:
1. Early returns when no offer_id is provided
2. Early returns when offer doesn't exist or tenant mismatch occurs
3. Correct status changes when adoption is approved or rejected
4. The fact that refresh_adopted is called appropriately in success cases
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

from life_graph.services.llm_offers import apply_adoption


async def test_apply_adoption_no_offer_id():
    """Test when approval has no offer_id in payload."""
    with patch("life_graph.services.llm_offers.refresh_adopted") as mock_refresh:
        # This tests the early return case where offer_id is not present in payload
        session = AsyncMock()
        approval = AsyncMock()
        approval.payload = {}
        approval.tenant_id = "tenant1"

        await apply_adoption(session, approval, True)

        # Should not call any methods on session since no offer_id
        session.get.assert_not_called()
        # refresh_adopted should also not have been called
        mock_refresh.assert_not_called()


async def test_apply_adoption_offer_not_found():
    """Test when offer with given ID doesn't exist."""
    with patch("life_graph.services.llm_offers.refresh_adopted") as mock_refresh:
        # Test for early return due to offer being None from get()
        session = AsyncMock()
        session.get.return_value = None

        approval = AsyncMock()
        approval.payload = {"offer_id": str(uuid.uuid4())}
        approval.tenant_id = "tenant1"

        await apply_adoption(session, approval, True)

        # Should call get() but return early
        session.get.assert_called_once()
        # refresh_adopted should also not have been called
        mock_refresh.assert_not_called()


async def test_apply_adoption_tenant_mismatch():
    """Test when offer tenant doesn't match approval tenant."""
    with patch("life_graph.services.llm_offers.refresh_adopted") as mock_refresh:
        # Test early return due to tenant mismatch
        offer_id = str(uuid.uuid4())

        session = AsyncMock()
        # Mock the returned offer object with wrong tenant
        mock_offer = AsyncMock()
        mock_offer.tenant_id = "wrong_tenant"
        session.get.return_value = mock_offer

        approval = AsyncMock()
        approval.payload = {"offer_id": offer_id}
        approval.tenant_id = "tenant1"

        await apply_adoption(session, approval, True)

        # Should have called get() and returned early
        session.get.assert_called_once()
        # refresh_adopted should also not have been called
        mock_refresh.assert_not_called()


async def test_apply_adoption_approve():
    """Test when adoption is approved."""
    with patch("life_graph.services.llm_offers.refresh_adopted") as mock_refresh:
        # Test the approve case
        offer_id = str(uuid.uuid4())

        session = AsyncMock()
        mock_offer = AsyncMock()
        mock_offer.tenant_id = "tenant1"
        mock_offer.id = offer_id
        session.get.return_value = mock_offer

        approval = AsyncMock()
        approval.payload = {"offer_id": offer_id}
        approval.tenant_id = "tenant1"

        await apply_adoption(session, approval, True)

        # Should have called get() and set status to "adopted"
        session.get.assert_called_once()
        assert mock_offer.status == "adopted"
        # Verify that refresh_adopted was called
        mock_refresh.assert_called_once_with(session)


async def test_apply_adoption_reject():
    """Test when adoption is rejected."""
    with patch("life_graph.services.llm_offers.refresh_adopted") as mock_refresh:
        # Test the reject case
        offer_id = str(uuid.uuid4())

        session = AsyncMock()
        mock_offer = AsyncMock()
        mock_offer.tenant_id = "tenant1"
        mock_offer.id = offer_id
        session.get.return_value = mock_offer

        approval = AsyncMock()
        approval.payload = {"offer_id": offer_id}
        approval.tenant_id = "tenant1"

        await apply_adoption(session, approval, False)

        # Should have called get() and set status to "rejected"
        session.get.assert_called_once()
        assert mock_offer.status == "rejected"
        # Verify that refresh_adopted was called
        mock_refresh.assert_called_once_with(session)
