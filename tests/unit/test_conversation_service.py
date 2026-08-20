"""ConversationService.ask retrieves approved-only, synthesizes, persists both turns."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from life_graph.models.db import Conversation, ConversationMessage
from life_graph.services.conversation import ConversationNotFoundError, ConversationService


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

        # honor .order_by(Model.col.asc()/.desc()) so tests seeding multiple
        # rows (e.g. conversation history) see realistic ordering.
        order_by = list(getattr(stmt, "_order_by_clauses", ()) or ())
        for ob in reversed(order_by):
            descending = "DESC" in str(ob)
            col = getattr(ob, "element", ob)
            key = getattr(col, "key", None)
            if key is not None:
                rows = sorted(rows, key=lambda o, k=key: getattr(o, k, None), reverse=descending)

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
async def test_ask_persists_citations_from_synthesis_verbatim(monkeypatch):
    # Empty-id filtering now happens at the SOURCE (synthesis.py, before
    # renumbering — see test_synthesis_citations.py), so citations coming
    # back from synthesize() are already clean. ConversationService.ask no
    # longer re-filters them (a post-hoc filter here could desync the
    # answer's [Memory J] tokens from the ids list) — it just persists
    # whatever synthesis returns.
    store = []
    conv_id = uuid.uuid4()
    conv = Conversation(id=conv_id, tenant_id="t1", title=None)
    store.append(conv)

    def session_factory():
        return _FakeSession(store)

    engine = AsyncMock()
    engine.tri_search.return_value = {"memories": [{"id": "m1", "content": "insurance due Friday"}]}
    synthesis = AsyncMock()
    synthesis.synthesize.return_value = {
        "answer": "Answer [Memory 1].", "source_count": 1,
        "model": "test", "citations": ["m1"],
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

    with pytest.raises(ConversationNotFoundError):
        await svc.ask(conv_id, "question?")

    with pytest.raises(ConversationNotFoundError):
        await svc.ask(uuid.uuid4(), "question?")


@pytest.mark.asyncio
async def test_ask_ownership_check_precedes_retrieval(monkeypatch):
    """Ownership/existence must be checked BEFORE retrieval — no wasted
    embedding/DB work on a conversation we're about to reject."""
    store: list = []  # no conversation seeded — id below won't be found

    def session_factory():
        return _FakeSession(store)

    engine = AsyncMock()
    synthesis = AsyncMock()

    monkeypatch.setattr(
        "life_graph.services.conversation.get_current_tenant_id", lambda: "t1"
    )

    svc = ConversationService(session_factory, engine, synthesis)

    with pytest.raises(ConversationNotFoundError):
        await svc.ask(uuid.uuid4(), "question?")

    engine.tri_search.assert_not_called()
    synthesis.synthesize.assert_not_called()


@pytest.mark.asyncio
async def test_ask_bumps_updated_at_on_later_turns(monkeypatch):
    """A second `ask` on an already-titled conversation must still dirty
    updated_at, or list_recent's ordering goes stale after the first turn."""
    store = []
    conv_id = uuid.uuid4()
    old_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
    conv = Conversation(id=conv_id, tenant_id="t1", title="already titled")
    conv.updated_at = old_time
    store.append(conv)

    def session_factory():
        return _FakeSession(store)

    engine = AsyncMock()
    engine.tri_search.return_value = {"memories": [{"id": "m1", "content": "x"}]}
    synthesis = AsyncMock()
    synthesis.synthesize.return_value = {
        "answer": "ok.", "source_count": 1, "model": "test", "citations": [],
    }

    monkeypatch.setattr(
        "life_graph.services.conversation.get_current_tenant_id", lambda: "t1"
    )

    svc = ConversationService(session_factory, engine, synthesis)
    await svc.ask(conv_id, "second question")

    assert conv.title == "already titled"  # title untouched on later turns
    assert conv.updated_at > old_time  # but updated_at was bumped


@pytest.mark.asyncio
async def test_ask_passes_prior_turns_as_history_excluding_current_question(monkeypatch):
    store = []
    conv_id = uuid.uuid4()
    conv = Conversation(id=conv_id, tenant_id="t1", title="existing")
    store.append(conv)

    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    turn1 = ConversationMessage(
        id=uuid.uuid4(), conversation_id=conv_id, tenant_id="t1",
        role="user", content="first question", cited_memory_ids=[], created_at=t0,
    )
    turn2 = ConversationMessage(
        id=uuid.uuid4(), conversation_id=conv_id, tenant_id="t1",
        role="assistant", content="first answer", cited_memory_ids=[],
        created_at=t0 + timedelta(seconds=1),
    )
    store.extend([turn1, turn2])

    def session_factory():
        return _FakeSession(store)

    engine = AsyncMock()
    engine.tri_search.return_value = {"memories": [{"id": "m1", "content": "x"}]}
    synthesis = AsyncMock()
    synthesis.synthesize.return_value = {
        "answer": "ok.", "source_count": 1, "model": "test", "citations": [],
    }

    monkeypatch.setattr(
        "life_graph.services.conversation.get_current_tenant_id", lambda: "t1"
    )

    svc = ConversationService(session_factory, engine, synthesis)
    await svc.ask(conv_id, "second question")

    assert synthesis.synthesize.await_count == 1
    _, kwargs = synthesis.synthesize.call_args
    history = kwargs.get("history")
    assert history == [
        {"role": "user", "content": "first question"},
        {"role": "assistant", "content": "first answer"},
    ]
    assert all(h["content"] != "second question" for h in history)
