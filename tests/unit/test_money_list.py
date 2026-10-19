import uuid
from datetime import date
from decimal import Decimal

import pytest

from life_graph.models.assistant import MoneyTransaction
from life_graph.services.money import list_transactions
from tests.unit.fakes import FakeSession, sql


@pytest.mark.asyncio
async def test_list_transactions_order_and_tenant_scope():
    """Verify that list_transactions returns transactions in descending order and filters by tenant_id."""
    # Prepare two transactions with different dates
    t1 = MoneyTransaction(
        id=uuid.uuid4(),
        tenant_id="tenant1",
        occurred_on=date(2023, 1, 15),
        amount=Decimal("10.00"),
        direction="debit",
    )
    t2 = MoneyTransaction(
        id=uuid.uuid4(),
        tenant_id="tenant1",
        occurred_on=date(2023, 1, 10),
        amount=Decimal("5.00"),
        direction="credit",
    )
    # The session will return the list in the order we provide
    session = FakeSession([t1, t2])
    start = date(2023, 1, 1)
    end = date(2023, 2, 1)
    result = await list_transactions(session, "tenant1", start, end)
    # Results should be ordered by occurred_on descending
    assert result[0].occurred_on == t1.occurred_on
    assert result[1].occurred_on == t2.occurred_on
    # Verify that the executed statement contains the tenant_id filter
    stmt_sql = sql(session.statements[0])
    assert "tenant_id" in stmt_sql
    assert "'tenant1'" in stmt_sql
    # Verify order by clause
    assert "ORDER BY" in stmt_sql


@pytest.mark.asyncio
async def test_list_transactions_empty_result():
    """When no rows match, list_transactions returns an empty list."""
    session = FakeSession([])
    start = date(2023, 1, 1)
    end = date(2023, 2, 1)
    result = await list_transactions(session, "tenant2", start, end)
    assert result == []


@pytest.mark.asyncio
async def test_list_transactions_category_filter():
    """list_transactions applies the category filter when provided."""
    t1 = MoneyTransaction(
        id=uuid.uuid4(),
        tenant_id="tenant3",
        occurred_on=date(2023, 3, 5),
        amount=Decimal("20.00"),
        direction="debit",
        category="groceries",
    )
    session = FakeSession([t1])
    start = date(2023, 3, 1)
    end = date(2023, 4, 1)
    result = await list_transactions(session, "tenant3", start, end, category="groceries")
    assert len(result) == 1
    assert result[0].category == "groceries"
    # The statement should include the category filter
    stmt_sql = sql(session.statements[0])
    assert "category" in stmt_sql
    assert "'groceries'" in stmt_sql
