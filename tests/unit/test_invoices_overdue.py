import re
from datetime import date

import pytest

from life_graph.services.invoices import overdue_count
from tests.unit.fakes import FakeSession, sql


@pytest.mark.asyncio
async def test_overdue_count_returns_correct_value():
    """The function should return the integer count returned by the query."""
    session = FakeSession(3)
    result = await overdue_count(session, "tenant1", date(2023, 1, 2))
    assert result == 3


@pytest.mark.asyncio
async def test_overdue_count_zero():
    """When the query returns 0, the function should return 0."""
    session = FakeSession(0)
    result = await overdue_count(session, "tenant1", date(2023, 1, 2))
    assert result == 0


@pytest.mark.asyncio
async def test_overdue_count_tenant_scope_in_sql():
    """The generated SQL should filter by tenant_id, status and due date."""
    session = FakeSession(0)
    await overdue_count(session, "tenant1", date(2023, 1, 2))
    # Inspect the executed statement
    stmt_sql = sql(session.statements[0])
    # Use regex to match the conditions regardless of quoting style
    assert re.search(r"tenant_id\s*=\s*'tenant1'", stmt_sql)
    assert re.search(r"status\s*=\s*'sent'", stmt_sql)
    assert re.search(r"due_on\s*<\s*'2023-01-02'", stmt_sql)
