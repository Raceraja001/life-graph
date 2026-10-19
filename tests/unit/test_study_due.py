from datetime import date

import pytest

from life_graph.models.assistant import ReviewCard
from life_graph.services.study import count_due, due_cards
from tests.unit.fakes import FakeSession, sql


@pytest.mark.asyncio
async def test_count_due_returns_value_and_sql_tenant():
    today = date.today()
    # Fake session returns a scalar count of 3
    session = FakeSession([5])
    tenant_id = "tenant123"
    result = await count_due(session, tenant_id, today)
    assert result == 5
    # Verify SQL contains tenant filter and due_on <= today
    stmt_sql = sql(session.statements[0])
    assert "tenant_id" in stmt_sql
    assert tenant_id in stmt_sql
    assert "due_on" in stmt_sql
    assert str(today) in stmt_sql


@pytest.mark.asyncio
async def test_count_due_zero():
    session = FakeSession([0])
    tenant_id = "x"
    today = date.today()
    assert await count_due(session, tenant_id, today) == 0


@pytest.mark.asyncio
async def test_due_cards_returns_list_and_sql():
    today = date.today()
    tenant_id = "t1"
    card1 = ReviewCard(
        tenant_id=tenant_id,
        deck="deck1",
        front="q1",
        back="a1",
        due_on=today,
        dedup_key="hash1",
    )
    card2 = ReviewCard(
        tenant_id=tenant_id,
        deck="deck2",
        front="q2",
        back="a2",
        due_on=today,
        dedup_key="hash2",
    )
    session = FakeSession([card1, card2])
    cards = await due_cards(session, tenant_id, today)
    assert len(cards) == 2
    assert all(isinstance(c, ReviewCard) for c in cards)
    stmt_sql = sql(session.statements[0])
    assert "tenant_id" in stmt_sql
    assert tenant_id in stmt_sql
    assert "due_on" in stmt_sql
    assert str(today) in stmt_sql


@pytest.mark.asyncio
async def test_due_cards_empty():
    session = FakeSession([])
    cards = await due_cards(session, "any", date.today())
    assert cards == []
