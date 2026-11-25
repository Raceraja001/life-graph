"""A spoken turn in a temporary chat is temporary too (Stage 0 finding 6, M1.6).

/jarvis/voice runs its turn through jarvis._answer, not chat_turn's
_turn_input, and _answer never set ``temporary``: the lead did not pin the
turn to the local model and the memory tools were not removed.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from life_graph.api import dependencies, jarvis


@pytest.fixture
def spawned(monkeypatch):
    seen: list[dict] = []
    task_id = str(uuid.uuid4())

    class PM:
        async def spawn(self, **kw):
            seen.append(kw)
            return {"task_id": task_id}

    async def settled(tenant_id, tid):
        return SimpleNamespace(
            id=uuid.UUID(task_id), status="completed", session_id=None, result={"response": "ok"}
        )

    async def nothing(*_a, **_k):
        return []

    async def no_history(*_a, **_k):
        return []

    monkeypatch.setattr(dependencies, "get_process_manager", lambda: PM())
    monkeypatch.setattr(jarvis, "_settled", settled)
    monkeypatch.setattr(jarvis, "_saved_in", nothing)
    monkeypatch.setattr(jarvis, "_reminded_in", nothing)
    monkeypatch.setattr("life_graph.services.chat_turn.load_chat_history", no_history)
    return seen


def _temporary(answer: bool):
    async def is_temporary(tenant_id, session_id):
        return answer

    return is_temporary


@pytest.mark.asyncio
async def test_a_spoken_turn_in_a_temporary_chat_is_marked_temporary(spawned, monkeypatch):
    monkeypatch.setattr("life_graph.services.chat_turn.session_is_temporary", _temporary(True))
    await jarvis._answer("t1", "what's on today", uuid.uuid4())
    assert spawned[-1]["input_data"]["temporary"] is True


@pytest.mark.asyncio
async def test_a_spoken_turn_in_a_kept_chat_is_not(spawned, monkeypatch):
    monkeypatch.setattr("life_graph.services.chat_turn.session_is_temporary", _temporary(False))
    await jarvis._answer("t1", "what's on today", uuid.uuid4())
    assert "temporary" not in spawned[-1]["input_data"]
