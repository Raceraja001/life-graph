"""Tests for delete_link function in memory_links service."""

import uuid
from unittest.mock import patch

import pytest

from life_graph.services.memory_links import delete_link
from tests.unit.fakes import FakeResult, FakeSession, sql


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
async def test_delete_link_filters_by_link_and_tenant():
    """The DELETE is scoped to this link AND the current tenant: without the
    tenant filter one tenant could delete another's links by id."""
    with patch("life_graph.services.memory_links.get_current_tenant_id") as mock_tenant:
        mock_tenant.return_value = "test_tenant"
        session = FakeSession(FakeResult(rowcount=1))

        with patch("life_graph.services.memory_links.async_session", return_value=session):
            link_id = uuid.uuid4()
            assert await delete_link(link_id) is True

    (stmt,) = session.statements
    text = sql(stmt)
    assert text.startswith("DELETE FROM memory_links")
    assert "'test_tenant'" in text
    assert link_id.hex in text.replace("-", "")
    assert session.commits == 1
