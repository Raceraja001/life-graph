from datetime import date

import pytest

from life_graph.services.invoices import sweep_overdue
from tests.unit.fakes import FakeSession, session_factory, sql


@pytest.mark.asyncio
async def test_sweep_overdue_no_sent_invoices():
    """When there are no sent invoices, the function should return 0."""
    # Setup
    session = FakeSession([])  # Empty list for list_all
    tenant_id = "tenant1"
    today = date(2023, 1, 2)

    # Create a fake notifications object with a mock create method
    class MockNotifications:
        def __init__(self):
            self.created = []

        async def create(self, *args, **kwargs):
            self.created.append((args, kwargs))

    notifications = MockNotifications()

    # Execute
    result = await sweep_overdue(session_factory(session), tenant_id, today, notifications)

    # Assert
    assert result == 0
    assert len(notifications.created) == 0


@pytest.mark.asyncio
async def test_sweep_overdue_only_invoices_not_due():
    """When there are sent invoices but none are overdue, the function should return 0."""

    # Setup - use a simple object that satisfies basic needs
    class MockInvoice:
        def __init__(self, id, number, client_name, due_on, status, last_reminded_on=None):
            self.id = id
            self.number = number
            self.client_name = client_name
            self.due_on = due_on
            self.status = status
            self.last_reminded_on = last_reminded_on
            self.client_email = "client@example.com"  # Required by email_draft function
            self.currency = "INR"
            self.total = 0.0  # Required by _amount function

    tenant_id = "tenant1"
    today = date(2023, 1, 2)

    invoices = [
        MockInvoice(1, "INV-2023-0001", "Client A", date(2023, 1, 5), "sent"),
        MockInvoice(2, "INV-2023-0002", "Client B", date(2023, 1, 10), "sent"),
    ]

    session = FakeSession(invoices)

    # Create a fake notifications object with a mock create method
    class MockNotifications:
        def __init__(self):
            self.created = []

        async def create(self, *args, **kwargs):
            self.created.append((args, kwargs))

    notifications = MockNotifications()

    # Execute
    result = await sweep_overdue(session_factory(session), tenant_id, today, notifications)

    # Assert
    assert result == 0
    assert len(notifications.created) == 0


@pytest.mark.asyncio
async def test_sweep_overdue_with_overdue_invoices():
    """When there are overdue invoices, the function should return count of sent notifications."""

    # Setup - use a simple object that satisfies basic needs
    class MockInvoice:
        def __init__(self, id, number, client_name, due_on, status, last_reminded_on=None):
            self.id = id
            self.number = number
            self.client_name = client_name
            self.due_on = due_on
            self.status = status
            self.last_reminded_on = last_reminded_on
            self.client_email = "client@example.com"  # Required by email_draft function
            self.currency = "INR"
            self.total = 1000.0  # Required by _amount function

    tenant_id = "tenant1"
    today = date(2023, 1, 2)

    # Create one overdue invoice (due_on < today) and one not overdue
    invoices = [
        MockInvoice(1, "INV-2023-0001", "Client A", date(2023, 1, 5), "sent"),
        MockInvoice(2, "INV-2023-0002", "Client B", date(2023, 1, 1), "sent"),  # Overdue
    ]

    session = FakeSession(invoices)

    # Create a fake notifications object with a mock create method
    class MockNotifications:
        def __init__(self):
            self.created = []

        async def create(self, *args, **kwargs):
            self.created.append((args, kwargs))

    notifications = MockNotifications()

    # Execute
    result = await sweep_overdue(session_factory(session), tenant_id, today, notifications)

    # Assert
    assert result == 1  # Only one invoice was overdue
    assert len(notifications.created) == 1

    # Verify that the notification was created with correct parameters (basic check)
    args, kwargs = notifications.created[0]
    assert args[0] == tenant_id  # tenant_id
    assert kwargs["source_type"] == "invoice"
    assert kwargs["source_id"] == str(invoices[1].id)  # ID of the overdue invoice


@pytest.mark.asyncio
async def test_sweep_overdue_tenant_scope_in_sql():
    """The generated SQL should filter by tenant_id and status."""
    session = FakeSession([])
    notifications = None

    await sweep_overdue(session_factory(session), "tenant1", date(2023, 1, 2), notifications)

    # Inspect the executed statement
    stmt_sql = sql(session.statements[0])
    # Check that the query filters by tenant_id and status= 'sent'
    assert "'tenant1'" in stmt_sql
    assert "status = 'sent'" in stmt_sql
