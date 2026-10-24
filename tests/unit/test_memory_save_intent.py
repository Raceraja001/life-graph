"""Which owner messages count as asking Jarvis to remember (memory_save) or to
forget (memory_forget)."""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from life_graph.services.lead import PERSONAL_TOOLS
from life_graph.tools.memory_search import SAVE_INTENT, asks_to_forget, asks_to_save


@pytest.mark.parametrize(
    "message",
    [
        "Remember that my car insurance renews on 5 March",
        "please save this: I'm allergic to peanuts",
        "note that the school fees are due Friday",
        "Don't forget I moved to Chennai",
        "keep in mind I prefer morning meetings",
        "make a note: Murugan's number changed",
        "Can you remember that my locker is 82?",
        "Do you remember my locker? Remember that it is 82 now.",
    ],
)
def test_asking_to_remember(message):
    assert SAVE_INTENT.search(message)
    assert asks_to_save(message)


@pytest.mark.parametrize(
    "message",
    [
        "Summarise my latest email from the bank",
        "what's on my calendar tomorrow?",
        "read this page and tell me what it says",
    ],
)
def test_not_asking_to_remember(message):
    assert not SAVE_INTENT.search(message)
    assert not asks_to_save(message)


@pytest.mark.parametrize(
    "message",
    [
        "do you remember my locker code?",
        "Do you still remember where I parked",
        "what do you remember about Murugan?",
        "What else do you remember about the school app",
        "did I tell you to remember my passport number?",
        "Have I asked you to save my PAN?",
        "what did I ask you to note down yesterday?",
        "Remember when we went to Ooty?",
    ],
)
def test_a_question_about_memory_is_not_a_request_to_save(message):
    """Review 2026-10-24 (H3): these matched SAVE_INTENT and activated whatever
    the model then chose to save."""
    assert not asks_to_save(message)


@pytest.mark.parametrize(
    "message",
    [
        "forget my old address",
        "That's wrong, delete it",
        "Remove the note about the gym",
        "my dentist is not Dr. Rao any more, that's out of date",
        "I no longer work at Acme",
        "that isn't true",
        "it's incorrect",
    ],
)
def test_asking_to_forget(message):
    assert asks_to_forget(message)


@pytest.mark.parametrize(
    "message",
    [
        "what's my locker code?",
        "Don't forget I moved to Chennai",
        "never forget my anniversary is in May",
        "summarise this email",
        "",
    ],
)
def test_not_asking_to_forget(message):
    assert not asks_to_forget(message)


def test_saving_is_a_personal_tool():
    # Never offered to a model that leaves the machine.
    assert "memory_save" in PERSONAL_TOOLS


# ── memory_forget needs the owner's own forget ───────────────


@pytest.fixture
def forget_db(monkeypatch):
    from tests.unit.fakes import FakeSession, session_factory

    session = FakeSession([("My old address is 4 Lake Road.",)])
    monkeypatch.setattr("life_graph.storage.database.async_session", session_factory(session))
    return session


def _owner_says(monkeypatch, text):
    from life_graph.tools import memory_search

    monkeypatch.setattr(memory_search, "_owner_message", AsyncMock(return_value=text))


@pytest.mark.asyncio
async def test_forget_without_the_owner_asking_is_refused(monkeypatch, forget_db):
    from life_graph.core.tenant import tenant_scope
    from life_graph.tools.memory_search import memory_forget

    _owner_says(monkeypatch, "what's my address?")
    with tenant_scope("t_forget"):
        out = json.loads(await memory_forget(str(uuid.uuid4()), "wrong"))
    assert "did not ask to forget" in out["error"]
    assert forget_db.statements == []  # nothing touched


@pytest.mark.asyncio
async def test_forget_when_the_owner_asks_reports_the_id(monkeypatch, forget_db):
    from life_graph.core.tenant import tenant_scope
    from life_graph.tools.memory_search import memory_forget

    _owner_says(monkeypatch, "that address is out of date, forget it")
    mid = str(uuid.uuid4())
    with tenant_scope("t_forget"):
        out = json.loads(await memory_forget(mid, "out of date"))
    assert out == {"forgotten": True, "id": mid, "content": "My old address is 4 Lake Road."}
    assert forget_db.commits == 1


def test_a_forget_reaches_the_app_as_a_forgotten_event():
    from life_graph.api.jarvis import _app_event
    from life_graph.services.chat_stream import map_bus_event

    result = json.dumps(
        {"forgotten": True, "id": "m1", "content": "என் பழைய முகவரி"}, ensure_ascii=False
    )
    streamed = map_bus_event(
        {"depth": 0, "event": {"type": "tool_result", "name": "memory_forget", "result": result}},
        set(),
    )
    assert _app_event(streamed, {}) == {
        "type": "forgotten",
        "id": "m1",
        "content": "என் பழைய முகவரி",
    }
    refused = {"type": "tool_result", "name": "memory_forget", "result": '{"error": "no"}'}
    assert _app_event(refused, {}) is None


# ── activating a pending duplicate marks it as Jarvis's save ──


@pytest.mark.asyncio
async def test_activating_a_pending_duplicate_marks_it_saved_by_jarvis(monkeypatch):
    from life_graph.api import dependencies
    from life_graph.core.task_context import TaskContext, _task_context_var
    from life_graph.services import entities
    from life_graph.tools import memory_search

    waiting = SimpleNamespace(
        id=uuid.uuid4(), status="pending", content="I am allergic to peanuts."
    )
    store = SimpleNamespace(find_exact_duplicate=AsyncMock(return_value=waiting))
    manager = SimpleNamespace(generate_embedding=AsyncMock(return_value=None))
    activate = AsyncMock()
    monkeypatch.setattr(dependencies, "get_store", lambda: store)
    monkeypatch.setattr(dependencies, "get_memory_manager", lambda: manager)
    monkeypatch.setattr(memory_search, "_activate", activate)
    monkeypatch.setattr(entities, "known_in_text", AsyncMock(return_value=[]), raising=False)
    monkeypatch.setattr(entities, "link", AsyncMock(), raising=False)
    _owner_says(monkeypatch, "please save this: I'm allergic to peanuts")

    run = uuid.uuid4()
    token = _task_context_var.set(TaskContext(task_id=run, tenant_id="t_dup"))
    try:
        out = json.loads(await memory_search.memory_save("I am allergic to peanuts."))
    finally:
        _task_context_var.reset(token)
    activate.assert_awaited_once_with(
        "t_dup", waiting.id, {"saved_by": "jarvis", "task_id": str(run)}
    )
    assert out["id"] == str(waiting.id) and "status" not in out
