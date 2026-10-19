"""get_by_intent picks deterministically: conversational personas first."""

from __future__ import annotations

from life_graph.kernel.personas import PersonaService
from tests.unit.fakes import FakeSession, session_factory, sql


async def test_get_by_intent_orders_conversational_personas_first():
    session = FakeSession(None)
    service = PersonaService(session_factory=session_factory(session))

    assert await service.get_by_intent("raja", "code") is None

    text = sql(session.statements[0])
    assert "'raja'" in text and "'code'" in text
    order = text.split("ORDER BY", 1)[1]
    # driver IS NOT NULL sorts false (no driver: cody) before true (code-fixer*).
    assert order.index("driver IS NOT NULL") < order.index("created_at") < order.index("name")
