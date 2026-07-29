"""ConversationService.ask retrieves approved-only, synthesizes, persists both turns."""

import uuid
from unittest.mock import AsyncMock

import pytest

from life_graph.models.db import Conversation
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
        # ConversationService only issues simple `select(Model).where(col
        # == value)` queries — filter the store by entity type and (if
        # present) a single equality where-clause, honoring any `.limit()`.
        entity = stmt.column_descriptions[0]["entity"]
        rows = [o for o in self._store if isinstance(o, entity)]

        where = stmt.whereclause
        if where is not None:
            col_name = getattr(where.left, "key", None)
            value = getattr(where.right, "value", None)
            if col_name is not None:
                rows = [o for o in rows if getattr(o, col_name, None) == value]

        if stmt._limit_clause is not None:
            rows = rows[: stmt._limit_clause.value]

        return _FakeResult(rows)

    async def delete(self, obj):
        if obj in self._store:
            self._store.remove(obj)


@pytest.mark.asyncio
async def test_ask_retrieves_active_only_and_persists(monkeypatch):
    store = []
    conv_id = uuid.uuid4()

    # seed a conversation
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


@pytest.mark.asyncio
async def test_ask_filters_out_empty_citation(monkeypatch):
    store = []
    conv_id = uuid.uuid4()
    conv = Conversation(id=conv_id, tenant_id="t1", title=None)
    store.append(conv)

    def session_factory():
        return _FakeSession(store)

    engine = AsyncMock()
    engine.tri_search.return_value = {"memories": [{"content": "no id here"}]}
    synthesis = AsyncMock()
    synthesis.synthesize.return_value = {
        "answer": "Answer.", "source_count": 1,
        "model": "test", "citations": ["", "m1"],
    }

    monkeypatch.setattr(
        "life_graph.services.conversation.get_current_tenant_id", lambda: "t1"
    )

    svc = ConversationService(session_factory, engine, synthesis)
    result = await svc.ask(conv_id, "question?")

    assert result["message"].cited_memory_ids == ["m1"]
    assert result["citations"] == ["m1"]


@pytest.mark.asyncio
async def test_create_returns_conversation_with_tenant_set(monkeypatch):
    store = []

    def session_factory():
        return _FakeSession(store)

    monkeypatch.setattr(
        "life_graph.services.conversation.get_current_tenant_id", lambda: "t1"
    )

    svc = ConversationService(session_factory, AsyncMock(), AsyncMock())
    conv = await svc.create()

    assert conv.tenant_id == "t1"
    assert conv in store


@pytest.mark.asyncio
async def test_list_recent_filters_by_tenant(monkeypatch):
    mine = Conversation(id=uuid.uuid4(), tenant_id="t1", title="mine")
    other = Conversation(id=uuid.uuid4(), tenant_id="t2", title="other")
    store = [mine, other]

    def session_factory():
        return _FakeSession(store)

    monkeypatch.setattr(
        "life_graph.services.conversation.get_current_tenant_id", lambda: "t1"
    )

    svc = ConversationService(session_factory, AsyncMock(), AsyncMock())
    result = await svc.list_recent()

    assert result == [mine]


@pytest.mark.asyncio
async def test_get_thread_returns_none_for_foreign_tenant(monkeypatch):
    conv_id = uuid.uuid4()
    conv = Conversation(id=conv_id, tenant_id="t2", title="not mine")
    store = [conv]

    def session_factory():
        return _FakeSession(store)

    monkeypatch.setattr(
        "life_graph.services.conversation.get_current_tenant_id", lambda: "t1"
    )

    svc = ConversationService(session_factory, AsyncMock(), AsyncMock())
    result = await svc.get_thread(conv_id)

    assert result is None


@pytest.mark.asyncio
async def test_delete_false_for_foreign_tenant_true_for_own(monkeypatch):
    foreign_id = uuid.uuid4()
    own_id = uuid.uuid4()
    foreign = Conversation(id=foreign_id, tenant_id="t2", title="not mine")
    own = Conversation(id=own_id, tenant_id="t1", title="mine")
    store = [foreign, own]

    def session_factory():
        return _FakeSession(store)

    monkeypatch.setattr(
        "life_graph.services.conversation.get_current_tenant_id", lambda: "t1"
    )

    svc = ConversationService(session_factory, AsyncMock(), AsyncMock())

    assert await svc.delete(foreign_id) is False
    assert foreign in store  # untouched

    assert await svc.delete(own_id) is True
    assert own not in store


@pytest.mark.asyncio
async def test_ask_raises_for_foreign_or_missing_conversation(monkeypatch):
    conv_id = uuid.uuid4()
    conv = Conversation(id=conv_id, tenant_id="t2", title=None)
    store = [conv]

    def session_factory():
        return _FakeSession(store)

    monkeypatch.setattr(
        "life_graph.services.conversation.get_current_tenant_id", lambda: "t1"
    )

    svc = ConversationService(session_factory, AsyncMock(), AsyncMock())

    with pytest.raises(ValueError):
        await svc.ask(conv_id, "question?")

    with pytest.raises(ValueError):
        await svc.ask(uuid.uuid4(), "question?")
