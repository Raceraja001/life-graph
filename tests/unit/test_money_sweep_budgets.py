from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from life_graph.services.money import sweep_budgets
from tests.unit.fakes import FakeSession, session_factory


@pytest.mark.asyncio
async def test_sweep_budgets_no_budgets():
    """Test when there are no budgets for any categories."""
    # Setup
    session = FakeSession()  # Empty session - no budgets

    # Mock the summary function
    with patch(
        "life_graph.services.money.summary",
        return_value={
            "month": "2026-10",
            "total_spent": 1000.0,
            "income": 5000.0,
            "categories": [
                {"category": "food", "spent": 300.0, "budget": None, "percent_of_budget": None},
                {
                    "category": "transport",
                    "spent": 200.0,
                    "budget": None,
                    "percent_of_budget": None,
                },
            ],
        },
    ):
        # Execute
        result = await sweep_budgets(
            session_factory(session), "tenant123", "2026-10-15", MagicMock()
        )

    # Assert
    assert result == 0
    # Verify tenant filtering in the query by checking that it contains tenant_id
    assert any("tenant_id" in str(stmt) for stmt in session.statements)


@pytest.mark.asyncio
async def test_sweep_budgets_no_alerts_sent():
    """Test when there are budgets but no alerts have been sent yet."""
    # Setup
    # Mock a single budget with no alerts sent yet
    mock_budget = MagicMock()
    mock_budget.category = "food"
    mock_budget.monthly_limit = Decimal("400.0")
    mock_budget.alerts_sent = {}
    mock_budget.id = 1

    # Create session with the mock budget as the result
    session = FakeSession(mock_budget)

    # Mock summary response
    with patch(
        "life_graph.services.money.summary",
        return_value={
            "month": "2026-10",
            "total_spent": 1000.0,
            "income": 5000.0,
            "categories": [
                {"category": "food", "spent": 300.0, "budget": 400.0, "percent_of_budget": 75},
            ],
        },
    ):
        # Execute
        notifications = AsyncMock()
        result = await sweep_budgets(
            session_factory(session), "tenant123", "2026-10-15", notifications
        )

    # Assert - should be 0 because 75% < 80% threshold (no alert triggered)
    assert result == 0
    notifications.create.assert_not_called()


@pytest.mark.asyncio
async def test_sweep_budgets_alert_already_sent():
    """Test when alert level has already been sent for this category."""
    # Setup
    # Mock a budget with 80% alert already sent
    mock_budget = MagicMock()
    mock_budget.category = "food"
    mock_budget.monthly_limit = Decimal("400.0")
    mock_budget.alerts_sent = {"2026-10": [80, 100]}  # Both 80 and 100 sent
    mock_budget.id = 1

    # Create session with the mock budget as the result
    session = FakeSession(mock_budget)

    # Mock summary response
    with patch(
        "life_graph.services.money.summary",
        return_value={
            "month": "2026-10",
            "total_spent": 1000.0,
            "income": 5000.0,
            "categories": [
                {"category": "food", "spent": 420.0, "budget": 400.0, "percent_of_budget": 105},
            ],
        },
    ):
        # Execute
        notifications = AsyncMock()
        result = await sweep_budgets(
            session_factory(session), "tenant123", "2026-10-15", notifications
        )

    # Assert - should be 0 because 105% is already over 100% and the alert was sent
    assert result == 0  # No new alerts sent since 100% already sent
    notifications.create.assert_not_called()


@pytest.mark.asyncio
async def test_sweep_budgets_over_budget():
    """Test when spending exceeds 100% of budget."""
    # Setup
    # Mock a budget with no alerts sent
    mock_budget = MagicMock()
    mock_budget.category = "food"
    mock_budget.monthly_limit = Decimal("400.0")
    mock_budget.alerts_sent = {}
    mock_budget.id = 1

    # Create session with the mock budget as the result
    session = FakeSession(mock_budget)

    # Mock summary response
    with patch(
        "life_graph.services.money.summary",
        return_value={
            "month": "2026-10",
            "total_spent": 1000.0,
            "income": 5000.0,
            "categories": [
                {"category": "food", "spent": 500.0, "budget": 400.0, "percent_of_budget": 125},
            ],
        },
    ):
        # Execute
        notifications = AsyncMock()
        result = await sweep_budgets(
            session_factory(session), "tenant123", "2026-10-15", notifications
        )

    # Assert - should be 1 because 125% > 100% alert triggered
    assert result == 1  # One alert sent (100%)
    notifications.create.assert_called_once()


@pytest.mark.asyncio
async def test_sweep_budgets_under_budget():
    """Test when spending is below budget threshold."""
    # Setup
    # Mock a budget with no alerts sent
    mock_budget = MagicMock()
    mock_budget.category = "food"
    mock_budget.monthly_limit = Decimal("400.0")
    mock_budget.alerts_sent = {}
    mock_budget.id = 1

    # Create session with the mock budget as the result
    session = FakeSession(mock_budget)

    # Mock summary response
    with patch(
        "life_graph.services.money.summary",
        return_value={
            "month": "2026-10",
            "total_spent": 1000.0,
            "income": 5000.0,
            "categories": [
                {"category": "food", "spent": 300.0, "budget": 400.0, "percent_of_budget": 75},
            ],
        },
    ):
        # Execute
        notifications = AsyncMock()
        result = await sweep_budgets(
            session_factory(session), "tenant123", "2026-10-15", notifications
        )

    # Assert - should be 0 because 75% < 80% threshold
    assert result == 0  # No alerts sent since under 80%
    notifications.create.assert_not_called()


@pytest.mark.asyncio
async def test_sweep_budgets_budget_has_zero_limit():
    """Test when budget exists but has zero limit."""
    # Setup
    # Mock a budget with zero limit
    mock_budget = MagicMock()
    mock_budget.category = "food"
    mock_budget.monthly_limit = Decimal("0.0")
    mock_budget.alerts_sent = {}
    mock_budget.id = 1

    # Create session with the mock budget as the result
    session = FakeSession(mock_budget)

    # Mock summary response
    with patch(
        "life_graph.services.money.summary",
        return_value={
            "month": "2026-10",
            "total_spent": 1000.0,
            "income": 5000.0,
            "categories": [
                {
                    "category": "food",
                    "spent": 300.0,
                    "budget": 0.0,
                    "percent_of_budget": None,
                },  # No percent since budget is zero
            ],
        },
    ):
        # Execute
        notifications = AsyncMock()
        result = await sweep_budgets(
            session_factory(session), "tenant123", "2026-10-15", notifications
        )

    # Assert - should be 0 because a spend with no budget can't generate alerts
    assert result == 0  # No alerts sent since budget is zero
    notifications.create.assert_not_called()


@pytest.mark.asyncio
async def test_sweep_budgets_budget_with_none_alerts_sent():
    """Test when budget has None for alerts_sent."""
    # Setup
    # Mock a budget with None alerts_sent
    mock_budget = MagicMock()
    mock_budget.category = "food"
    mock_budget.monthly_limit = Decimal("400.0")
    mock_budget.alerts_sent = None
    mock_budget.id = 1

    # Create session with the mock budget as the result
    session = FakeSession(mock_budget)

    # Mock summary response
    with patch(
        "life_graph.services.money.summary",
        return_value={
            "month": "2026-10",
            "total_spent": 1000.0,
            "income": 5000.0,
            "categories": [
                {"category": "food", "spent": 420.0, "budget": 400.0, "percent_of_budget": 105},
            ],
        },
    ):
        # Execute
        notifications = AsyncMock()
        result = await sweep_budgets(
            session_factory(session), "tenant123", "2026-10-15", notifications
        )

    # Assert - should be 1 because 105% > 100% alert triggered
    assert result == 1  # One alert sent (100%)
    notifications.create.assert_called_once()


@pytest.mark.asyncio
async def test_sweep_budgets_at_80_percent():
    """Test when spending hits exactly the 80% threshold."""
    # Setup
    # Mock a budget with no alerts sent yet
    mock_budget = MagicMock()
    mock_budget.category = "food"
    mock_budget.monthly_limit = Decimal("400.0")
    mock_budget.alerts_sent = {}
    mock_budget.id = 1

    # Create session with the mock budget as the result
    session = FakeSession(mock_budget)

    # Mock summary response - exactly at 80%
    with patch(
        "life_graph.services.money.summary",
        return_value={
            "month": "2026-10",
            "total_spent": 1000.0,
            "income": 5000.0,
            "categories": [
                {"category": "food", "spent": 320.0, "budget": 400.0, "percent_of_budget": 80},
            ],
        },
    ):
        # Execute
        notifications = AsyncMock()
        result = await sweep_budgets(
            session_factory(session), "tenant123", "2026-10-15", notifications
        )

    # Assert - should be 1 because 80% triggers the 80% alert
    assert result == 1  # One alert sent (80%)
    notifications.create.assert_called_once()
