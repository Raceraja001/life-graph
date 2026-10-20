"""Tests for delete_link function in memory_links service."""

import uuid
from unittest.mock import patch

import pytest

from life_graph.services.memory_links import delete_link
from tests.unit.fakes import FakeResult, FakeSession


@pytest.mark.asyncio
async def test_delete_link_success():
    """Test deleting an existing link returns True."""
    # Mock the tenant ID
    with patch("life_graph.services.memory_links.get_current_tenant_id") as mock_tenant:
        mock_tenant.return_value = "test_tenant"

        # Create a fake session that will return rowcount=1 when execute is called (successful deletion)
        session = FakeSession(FakeResult(rowcount=1))

        # Patch the async_session to return our fake session
        with patch("life_graph.services.memory_links.async_session", return_value=session):
            # Call the function
            link_id = uuid.uuid4()
            result = await delete_link(link_id)

            # Verify result and that proper statement was executed
            assert result is True
            assert len(session.statements) == 1


@pytest.mark.asyncio
async def test_delete_link_not_found():
    """Test deleting a non-existing link returns False."""
    # Mock the tenant ID
    with patch("life_graph.services.memory_links.get_current_tenant_id") as mock_tenant:
        mock_tenant.return_value = "test_tenant"

        # Create a fake session that will return rowcount=0 when execute is called (no matching rows)
        session = FakeSession(FakeResult(rowcount=0))

        # Patch the async_session to return our fake session
        with patch("life_graph.services.memory_links.async_session", return_value=session):
            # Call the function
            link_id = uuid.uuid4()
            result = await delete_link(link_id)

            # Verify result and that proper statement was executed
            assert result is False
            assert len(session.statements) == 1


@pytest.mark.asyncio
async def test_delete_link_wrong_tenant():
    """Test that delete_link correctly filters by tenant."""
    # Mock the tenant ID
    with patch("life_graph.services.memory_links.get_current_tenant_id") as mock_tenant:
        mock_tenant.return_value = "test_tenant"

        # Create a fake session that will return rowcount=0 when execute is called
        # (since the filter by tenant should prevent deletion)
        session = FakeSession(FakeResult(rowcount=0))

        # Patch the async_session to return our fake session
        with patch("life_graph.services.memory_links.async_session", return_value=session):
            # Call the function
            link_id = uuid.uuid4()
            result = await delete_link(link_id)

            # Verify result - should be False since no rows match tenant filter
            assert result is False
            assert len(session.statements) == 1
