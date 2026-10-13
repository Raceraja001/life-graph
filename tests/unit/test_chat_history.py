"""Turning stored tasks back into a conversation.

Every chat turn used to be a single-message run, so a persona could not answer
"what did I just say?" — the UI showed a thread the model had never seen. These
cover the rebuild: what counts as a turn, what order it comes back in, and what
is deliberately left out.
"""

import uuid
from types import SimpleNamespace

import pytest

from life_graph.api import kernel


def task(asked, answered, *, status="completed", parent=None):
    """An agent_tasks row, as the loader reads it."""
    return SimpleNamespace(
        input={"message": asked} if asked is not None else {},
        result={"response": answered} if answered is not None else {},
        status=status,
        parent_task_id=parent,
    )


@pytest.fixture
def rows(monkeypatch):
    """Stub the query so these stay unit tests, and capture what was asked for."""
    captured = {}

    def install(returned):
        class _Result:
            def scalars(self):
                return self

            def all(self):
                return returned

        class _Session:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def execute(self, stmt):
                captured["stmt"] = stmt
                return _Result()

        monkeypatch.setattr(kernel, "async_session", lambda: _Session(), raising=False)
        import life_graph.storage.database as db

        monkeypatch.setattr(db, "async_session", lambda: _Session())
        return captured

    return install


async def test_a_turn_becomes_a_user_message_and_a_reply(rows):
    rows([task("what is the capital", "Chennai")])

    history = await kernel._load_chat_history("raja", uuid.uuid4())

    assert history == [
        {"role": "user", "content": "what is the capital"},
        {"role": "assistant", "content": "Chennai"},
    ]


async def test_oldest_turn_comes_first(rows):
    # The query orders newest-first so that the LIMIT keeps recent turns; the
    # loader has to flip that back, or the model reads the conversation
    # backwards.
    rows([task("second", "2"), task("first", "1")])

    history = await kernel._load_chat_history("raja", uuid.uuid4())

    assert [m["content"] for m in history] == ["first", "1", "second", "2"]


async def test_a_turn_that_produced_no_reply_is_dropped(rows):
    # A cancelled or timed-out turn left an empty response. Feeding that back as
    # an assistant message teaches the model that saying nothing is a valid
    # reply.
    rows([task("answered", "yes"), task("abandoned", "")])

    history = await kernel._load_chat_history("raja", uuid.uuid4())

    assert history == [
        {"role": "user", "content": "answered"},
        {"role": "assistant", "content": "yes"},
    ]


async def test_a_row_with_no_message_is_dropped(rows):
    rows([task(None, "a reply to nothing")])

    assert await kernel._load_chat_history("raja", uuid.uuid4()) == []


async def test_an_empty_conversation_is_empty(rows):
    rows([])

    assert await kernel._load_chat_history("raja", uuid.uuid4()) == []


async def test_history_is_bounded(rows):
    # A local model's context window is finite: an unbounded thread would start
    # silently pushing the system prompt out of it.
    assert kernel.CHAT_HISTORY_TURNS > 0
    rows([task(f"q{i}", f"a{i}") for i in range(kernel.CHAT_HISTORY_TURNS)])

    history = await kernel._load_chat_history("raja", uuid.uuid4())

    assert len(history) == kernel.CHAT_HISTORY_TURNS * 2
