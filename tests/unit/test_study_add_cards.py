# Unit tests for life_graph.services.study.add_cards

from datetime import date

import pytest

from life_graph.services.study import add_cards, dedup_key
from tests.unit.fakes import FakeResult, FakeSession, sql

# Helper to create a session that will return specified rowcounts


def make_session(*rowcounts: int) -> FakeSession:
    """Return a FakeSession whose execute() will yield FakeResults with the given rowcounts.
    Each rowcount corresponds to one call to session.execute().
    """
    results = [FakeResult([], rowcount=rc) for rc in rowcounts]
    return FakeSession(*results)


@pytest.mark.asyncio
async def test_add_cards_inserts_new_cards():
    """When cards are unique, each insert should succeed and return the count."""
    session = make_session(1, 1, 1)
    tenant_id = "tenant1"
    today = date(2023, 1, 1)
    cards = [
        {"front": "Q1", "back": "A1"},
        {"front": "Q2", "back": "A2"},
        {"front": "Q3", "back": "A3"},
    ]
    added = await add_cards(session, tenant_id, cards, deck="deck1", today=today)
    assert added == 3
    # Each statement should be an insert for ReviewCard with correct values
    assert len(session.statements) == 3
    for stmt, card in zip(session.statements, cards, strict=True):
        from tests.unit.fakes import sql as stmt_sql

        stmt_text = stmt_sql(stmt)
        assert "INSERT" in stmt_text
        assert dedup_key(card["front"]) in stmt_text


@pytest.mark.asyncio
async def test_add_cards_skips_duplicate_front():
    """Cards with the same front should only insert once; the second insert returns 0 rows."""
    # First card inserted, second duplicate returns 0
    session = make_session(1, 0)
    tenant_id = "tenant2"
    today = date(2023, 2, 1)
    cards = [
        {"front": "Q1", "back": "A1"},
        {"front": "Q1", "back": "A1 duplicate"},
    ]
    added = await add_cards(session, tenant_id, cards, deck="deck2", today=today)
    assert added == 1
    assert len(session.statements) == 2
    # Verify that the second statement had the same dedup_key
    dedup1_sql = sql(session.statements[0])
    dedup2_sql = sql(session.statements[1])
    assert dedup1_sql.count(dedup_key(cards[0]["front"])) == 1
    assert dedup2_sql.count(dedup_key(cards[0]["front"])) == 1


@pytest.mark.asyncio
async def test_add_cards_empty_list():
    """When no cards are provided, add_cards should return 0 and make no statements."""
    session = FakeSession()
    tenant_id = "tenant3"
    today = date(2023, 3, 1)
    added = await add_cards(session, tenant_id, [], deck="deck3", today=today)
    assert added == 0
    assert session.statements == []
