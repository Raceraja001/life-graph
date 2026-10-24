"""memory_save's result reaches the phone as a "saved" event (api/jarvis.py),
after the chat stream has trimmed it (services/chat_stream.py)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def no_db(monkeypatch):
    """memory_save with its store, embedder, task lookup and entity index faked."""
    from life_graph.api import dependencies
    from life_graph.services import entities
    from life_graph.tools import memory_search

    async def store_row(create, **_kw):
        return SimpleNamespace(id=uuid.uuid4(), content=create.content)

    store = SimpleNamespace(
        find_exact_duplicate=AsyncMock(return_value=None),
        find_similar=AsyncMock(return_value=[]),
        store=AsyncMock(side_effect=store_row),
    )
    manager = SimpleNamespace(generate_embedding=AsyncMock(return_value=None))
    monkeypatch.setattr(dependencies, "get_store", lambda: store)
    monkeypatch.setattr(dependencies, "get_memory_manager", lambda: manager)
    monkeypatch.setattr(memory_search, "_owner_message", AsyncMock(return_value="remember this"))
    monkeypatch.setattr(entities, "known_in_text", AsyncMock(return_value=[]), raising=False)
    monkeypatch.setattr(entities, "link", AsyncMock(), raising=False)
    return store


@pytest.mark.asyncio
async def test_a_long_tamil_save_still_reaches_the_phone_with_its_undo(no_db):
    from life_graph.api.jarvis import _app_event
    from life_graph.core.tenant import tenant_scope
    from life_graph.services.chat_stream import map_bus_event
    from life_graph.tools.memory_search import memory_save

    # ~600 characters: well under memory_save's limit, but over 2,000 once escaped.
    fact = " ".join(["என் பள்ளிக் கட்டணம் வெள்ளிக்கிழமை செலுத்த வேண்டும்."] * 12)
    with tenant_scope("t_save_result"):
        result = await memory_save(fact)

    streamed = map_bus_event(
        {"depth": 0, "event": {"type": "tool_result", "name": "memory_save", "result": result}},
        set(),
    )
    event = _app_event(streamed, {})
    assert event is not None and event["type"] == "saved"
    assert event["content"] == fact and event["pending"] is False
