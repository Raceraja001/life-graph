"""Unit tests for life_graph.services.study.get_card.

The function simply performs a ``SELECT`` for a :class:`ReviewCard` by tenant and id,
returning the row or ``None``.  The tests exercise the normal return path,
the not‑found path and an edge case where the result set contains more than one
row (``scalar_one_or_none`` returns the first).  The ``FakeSession`` helper is used
to stub the async SQLAlchemy session and capture the statement for inspection.
"""

from __future__ import annotations

import uuid
from datetime import date

from life_graph.models.assistant import ReviewCard
from life_graph.services.study import get_card
from tests.unit.fakes import FakeSession, sql


async def test_get_card_found() -> None:
    """When a matching card exists the function returns it."""
    tenant_id = "t1"
    card_id = uuid.uuid4()
    card = ReviewCard(
        id=card_id,
        tenant_id=tenant_id,
        deck="general",
        front="front",
        back="back",
        due_on=date.today(),
        interval_days=0,
        repetitions=0,
        ease=2.5,
        reviews=0,
        dedup_key="dedup",
    )
    session = FakeSession(card)
    result = await get_card(session, tenant_id, card_id)
    assert result is card
    stmt_sql = sql(session.statements[0])
    assert f"'{tenant_id}'" in stmt_sql
    assert f"'{card_id}'" in stmt_sql


async def test_get_card_not_found() -> None:
    """When no matching row exists ``None`` is returned."""
    session = FakeSession(None)
    result = await get_card(session, "t1", uuid.uuid4())
    assert result is None


async def test_get_card_multiple_rows() -> None:
    """If the query returns more than one row, ``scalar_one_or_none`` returns the first.

    The real database would raise an error but the fake returns the first row, which
    is what the test ensures.
    """
    tenant_id = "t1"
    card_id = uuid.uuid4()
    card1 = ReviewCard(
        id=card_id,
        tenant_id=tenant_id,
        deck="general",
        front="front1",
        back="back1",
        due_on=date.today(),
        interval_days=0,
        repetitions=0,
        ease=2.5,
        reviews=0,
        dedup_key="dedup1",
    )
    card2 = ReviewCard(
        id=card_id,
        tenant_id=tenant_id,
        deck="general",
        front="front2",
        back="back2",
        due_on=date.today(),
        interval_days=0,
        repetitions=0,
        ease=2.5,
        reviews=0,
        dedup_key="dedup2",
    )
    session = FakeSession(card1, card2)
    result = await get_card(session, tenant_id, card_id)
    assert result is card1
    stmt_sql = sql(session.statements[0])
    assert f"'{tenant_id}'" in stmt_sql
    assert f"'{card_id}'" in stmt_sql
