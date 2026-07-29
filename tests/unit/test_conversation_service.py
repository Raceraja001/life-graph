"""ConversationService.ask retrieves approved-only, synthesizes, persists both turns."""

import uuid
from unittest.mock import AsyncMock

import pytest

from life_graph.services.conversation import ConversationService


class _FakeResult:
    """Minimal stand-in for a SQLAlchemy Result (see test_governor.py's fake)."""

    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, store):
        self._store = store
        self.added = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def add(self, obj):
        self.added.append(obj)
        self._store.append(obj)

    async def flush(self):
        pass

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass

    async def get(self, model, pk):
        for o in self._store:
            if getattr(o, "id", None) == pk:
                return o
        return None

    async def execute(self, stmt):
        # ConversationService only ever selects ConversationMessage rows
        # (prior turns for history) within `ask` — return what's in the
        # store so far, in insertion order.
        from life_graph.models.db import ConversationMessage

        rows = [o for o in self._store if isinstance(o, ConversationMessage)]
        return _FakeResult(rows)


@pytest.mark.asyncio
async def test_ask_retrieves_active_only_and_persists(monkeypatch):
    store = []
    conv_id = uuid.uuid4()

    # seed a conversation
    from life_graph.models.db import Conversation
    conv = Conversation(id=conv_id, tenant_id="t1", title=None)
    store.append(conv)

    def session_factory():
        return _FakeSession(store)

    engine = AsyncMock()
    engine.tri_search.return_value = {
        "memories": [{"id": "m1", "content": "insurance due Friday"}]
    }
    synthesis = AsyncMock()
    synthesis.synthesize.return_value = {
        "answer": "Friday [Memory 1].", "source_count": 1,
        "model": "test", "citations": ["m1"],
    }

    monkeypatch.setattr(
        "life_graph.services.conversation.get_current_tenant_id", lambda: "t1"
    )

    svc = ConversationService(session_factory, engine, synthesis)
    result = await svc.ask(conv_id, "when is insurance due?")

    # retrieval was approved-only
    _, kwargs = engine.tri_search.call_args
    assert kwargs.get("statuses") == ("active",)
    # assistant turn returned with citations
    assert result["message"].role == "assistant"
    assert result["message"].cited_memory_ids == ["m1"]
    # both turns persisted
    roles = [getattr(o, "role", None) for o in store if hasattr(o, "role")]
    assert roles == ["user", "assistant"]
    # title set from first question
    assert conv.title == "when is insurance due?"
