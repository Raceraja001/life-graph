"""A message the phone resends (WorkManager cancelled the first send after the
PC received it) carries the same client_id, and Jarvis answers it once: a
finished turn is replayed, a running one waited for, a failed one run again.
The endpoints with a real device token: tests/integration/test_jarvis_idempotent_send.py.
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from tests.unit.fakes import FakeSession, session_factory, sql

CID = "msg_0123456789-ab"
CONV = uuid.uuid4()


def _task(status, response="It is 31 degrees.", **kw):
    return SimpleNamespace(
        id=uuid.uuid4(),
        status=status,
        session_id=CONV,
        input={"message": "how hot is it?", "client_id": CID},
        result={"response": response, "route": {"kind": "personal"}} if response else {},
        **kw,
    )


@pytest.fixture
def wired(monkeypatch):
    """Jarvis with no database or model: nothing is captured or started unless a
    test expects it, and polling does not sleep."""
    from life_graph.api import dependencies, jarvis

    calls = SimpleNamespace(captured=[], started=[], prior=None, polled=[])

    async def turn_for(tenant_id, client_id):
        assert (tenant_id, client_id) == ("t_idem", CID)
        return calls.prior

    async def capture(tenant_id, text, kind, conversation_id, *, trust_tier=None, client_id=None):
        calls.captured.append((text, kind, client_id))

    async def start_chat(body, conversation_id):
        calls.started.append((body.client_id, conversation_id))

        async def gen():
            yield 'data: {"type": "assistant_delta", "text": "fresh"}\n\n'
            yield 'data: {"type": "done"}\n\n'

        return SimpleNamespace(body_iterator=gen(), headers={})

    async def get_task(tenant_id, task_id):
        return calls.polled.pop(0) if len(calls.polled) > 1 else calls.polled[0]

    monkeypatch.setattr(jarvis, "_turn_for", turn_for)
    monkeypatch.setattr(jarvis, "_capture", capture)
    monkeypatch.setattr(jarvis, "_start_chat", start_chat)
    monkeypatch.setattr(jarvis, "_POLL_SECONDS", 0)
    saved = [{"id": "m1", "content": "I like filter coffee.", "pending": False}]
    reminded = [{"id": "r1", "text": "Pay TNEB", "at": "2026-10-26T09:00:00+05:30"}]
    monkeypatch.setattr(jarvis, "_saved_in", AsyncMock(return_value=saved))
    monkeypatch.setattr(jarvis, "_reminded_in", AsyncMock(return_value=reminded))
    pm = SimpleNamespace(get_task=AsyncMock(side_effect=get_task))
    monkeypatch.setattr(dependencies, "get_process_manager", lambda: pm)
    return calls


async def _chat(**body) -> list:
    from life_graph.api import jarvis
    from life_graph.core.tenant import tenant_scope

    out = []
    with tenant_scope("t_idem"):
        resp = await jarvis.chat(jarvis.ChatRequest(message="how hot is it?", **body))
        async for chunk in resp.body_iterator:
            for frame in chunk.split("\n\n"):
                if frame.startswith(":"):
                    out.append("heartbeat")
                elif frame.startswith("data: "):
                    out.append(json.loads(frame[6:]))
    return out


_REPLAY = [
    {"type": "saved", "id": "m1", "content": "I like filter coffee.", "pending": False},
    {"type": "reminded", "id": "r1", "text": "Pay TNEB", "at": "2026-10-26T09:00:00+05:30"},
    {"type": "token", "content": "It is 31 degrees."},
    {"type": "done", "conversation_id": str(CONV), "route": "personal"},
]


# ── The contract ─────────────────────────────────────────────────────


@pytest.mark.parametrize("cid", ["abcdefgh", "A" * 64, "msg_01-XY_zz"])
def test_a_client_id_is_8_to_64_letters_digits_dash_underscore(cid):
    from life_graph.api.jarvis import ChatRequest

    assert ChatRequest(message="hi", client_id=cid).client_id == cid
    assert ChatRequest(message="hi").client_id is None


@pytest.mark.parametrize("cid", ["", "short", "A" * 65, "has space1", "dot.ted.id", "abcdefgh\n"])
def test_anything_else_is_refused(cid):
    from pydantic import ValidationError

    from life_graph.api.jarvis import ChatRequest

    with pytest.raises(ValidationError):
        ChatRequest(message="hi", client_id=cid)


@pytest.mark.parametrize("cid", ["", "short", "A" * 65, "no/slash1", "abcdefgh\n"])
@pytest.mark.asyncio
async def test_voice_refuses_a_bad_client_id_with_422(cid):
    from life_graph.api import jarvis
    from life_graph.core.tenant import tenant_scope

    with tenant_scope("t_idem"), pytest.raises(HTTPException) as err:
        await jarvis.voice(audio=SimpleNamespace(), conversation_id=None, client_id=cid)
    assert err.value.status_code == 422


@pytest.mark.asyncio
async def test_a_turn_is_found_by_tenant_client_id_and_the_last_day(monkeypatch):
    from life_graph.api import jarvis
    from life_graph.core.tenant import tenant_scope

    session = FakeSession(None)
    monkeypatch.setattr(jarvis, "async_session", session_factory(session))
    with tenant_scope("t_idem"):
        assert await jarvis._turn_for("t_idem", CID) is None
    text = sql(session.statements[0])
    assert "agent_tasks.tenant_id = 't_idem'" in text
    assert "agent_tasks.agent_name = 'jarvis'" in text
    assert "agent_tasks.parent_task_id IS NULL" in text
    assert "agent_tasks.created_at >= " in text
    assert f"(agent_tasks.input ->> 'client_id') = '{CID}'" in text
    assert "ORDER BY agent_tasks.created_at DESC" in text and "LIMIT 1" in text


# ── Chat ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_new_message_is_captured_and_run_with_its_client_id(wired):
    out = await _chat(client_id=CID)
    assert wired.captured == [("how hot is it?", "text", CID)]
    assert wired.started == [(CID, None)]
    assert out == [
        {"type": "token", "content": "fresh"},
        {"type": "done", "conversation_id": None, "route": None, "task_id": None},
    ]


@pytest.mark.asyncio
async def test_a_resent_finished_message_is_replayed_not_asked_again(wired):
    wired.prior = _task("completed")
    out = await _chat(client_id=CID)
    assert out == _REPLAY
    assert wired.captured == [] and wired.started == []


@pytest.mark.asyncio
async def test_a_resent_running_message_is_waited_for_then_replayed(wired, monkeypatch):
    from life_graph.api import kernel

    monkeypatch.setattr(kernel, "CHAT_STREAM_HEARTBEAT_SECONDS", 0)
    wired.prior = _task("running", response=None)
    wired.polled = [_task("running", response=None), _task("completed")]
    out = await _chat(client_id=CID)
    assert "heartbeat" in out  # the stream stays open while it waits
    assert [e for e in out if e != "heartbeat"] == _REPLAY
    assert wired.captured == [] and wired.started == []


@pytest.mark.asyncio
async def test_a_resent_failed_message_runs_again_without_a_second_capture(wired):
    wired.prior = _task("failed", response=None)
    out = await _chat(client_id=CID)
    # Again, in the conversation the failed turn opened; its words were captured then.
    assert wired.started == [(CID, CONV)] and wired.captured == []
    assert out[0] == {"type": "token", "content": "fresh"}


@pytest.mark.asyncio
async def test_a_turn_that_fails_while_waited_for_runs_again(wired):
    wired.prior = _task("running", response=None)
    wired.polled = [_task("timeout", response=None)]
    out = await _chat(client_id=CID)
    assert wired.started == [(CID, CONV)] and wired.captured == []
    assert out[0] == {"type": "token", "content": "fresh"}


@pytest.mark.asyncio
async def test_a_turn_still_running_when_the_wait_runs_out_is_an_error(wired, monkeypatch):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "telegram_ask_timeout_seconds", 0)
    wired.prior = _task("running", response=None)
    wired.polled = [_task("running", response=None)]
    out = await _chat(client_id=CID)
    assert out == [{"type": "error", "message": "Jarvis could not finish (running)."}]
    assert wired.started == [] and wired.captured == []


@pytest.mark.asyncio
async def test_without_a_client_id_nothing_is_looked_up(wired, monkeypatch):
    from life_graph.api import jarvis

    monkeypatch.setattr(jarvis, "_turn_for", AsyncMock(side_effect=AssertionError))
    await _chat()
    assert wired.captured == [("how hot is it?", "text", None)] and wired.started == [(None, None)]


@pytest.mark.asyncio
async def test_the_kernel_stores_the_client_id_in_the_task_input(monkeypatch):
    from life_graph.api import kernel
    from life_graph.core.tenant import tenant_scope

    pm = SimpleNamespace(spawn=AsyncMock(return_value={"task_id": "t-1"}))
    personas = SimpleNamespace(get_by_name=AsyncMock(return_value={"name": "jarvis"}))
    monkeypatch.setattr(kernel, "_load_chat_history", AsyncMock(return_value=[]))
    with tenant_scope("t_idem"):
        resp = await kernel.chat_stream(
            kernel.ChatStreamRequest(message="hi", session_id=CONV, client_id=CID),
            pm=pm,
            personas=personas,
        )
        it = resp.body_iterator
        await it.__anext__()
        await it.aclose()
    assert pm.spawn.call_args.kwargs["input_data"] == {
        "message": "hi",
        "history": [],
        "client_id": CID,
    }


@pytest.mark.asyncio
async def test_the_capture_carries_the_client_id(monkeypatch):
    from life_graph.api import jarvis
    from life_graph.services import capture

    seen = {}

    class _Capture:
        def __init__(self, session, bus):
            pass

        async def ingest(self, **kw):
            seen.update(kw)

    monkeypatch.setattr(capture, "CaptureService", _Capture)
    monkeypatch.setattr(jarvis, "async_session", session_factory(FakeSession()))
    await jarvis._capture("t_idem", "how hot is it?", "text", CONV, client_id=CID)
    assert seen["properties"] == {"input": "text", "conversation_id": str(CONV), "client_id": CID}


# ── Voice ────────────────────────────────────────────────────────────


@pytest.fixture
def voice_wired(wired, monkeypatch):
    from life_graph.api import jarvis
    from life_graph.services import assistant_chat

    wired.answered = []

    async def answer(tenant_id, question, conversation_id, *, client_id=None):
        wired.answered.append((question, conversation_id, client_id))
        return {"reply": "Fresh.", "conversation_id": str(CONV), "route": "personal"}

    monkeypatch.setattr(jarvis, "_answer", answer)
    monkeypatch.setattr(jarvis, "_transcribe", AsyncMock(return_value="how hot is it now?"))
    monkeypatch.setattr(assistant_chat, "speak", AsyncMock(return_value=b"mp3"))
    return wired


async def _voice():
    from life_graph.api import jarvis
    from life_graph.core.tenant import tenant_scope

    with tenant_scope("t_idem"):
        return (await jarvis.voice(audio=SimpleNamespace(), conversation_id=None, client_id=CID))[
            "data"
        ]


@pytest.mark.asyncio
async def test_a_resent_voice_message_returns_the_stored_reply_spoken_again(voice_wired):
    from life_graph.api import jarvis

    voice_wired.prior = _task("completed")
    data = await _voice()
    assert data["heard"] == "how hot is it?" and data["reply"] == "It is 31 degrees."
    assert data["conversation_id"] == str(CONV) and data["route"] == "personal"
    assert data["saved"][0]["id"] == "m1" and data["reminded"][0]["id"] == "r1"
    assert data["audio_base64"] == "bXAz"
    jarvis._transcribe.assert_not_called()
    assert voice_wired.answered == [] and voice_wired.captured == []


@pytest.mark.asyncio
async def test_a_resent_running_voice_message_is_waited_for(voice_wired):
    voice_wired.prior = _task("queued", response=None)
    voice_wired.polled = [_task("running", response=None), _task("completed")]
    data = await _voice()
    assert data["reply"] == "It is 31 degrees." and voice_wired.answered == []


@pytest.mark.asyncio
async def test_a_resent_failed_voice_message_runs_again_on_the_same_words(voice_wired):
    from life_graph.api import jarvis

    voice_wired.prior = _task("failed", response=None)
    data = await _voice()
    assert voice_wired.answered == [("how hot is it?", CONV, CID)]
    assert voice_wired.captured == [] and data["reply"] == "Fresh."
    jarvis._transcribe.assert_not_called()


@pytest.mark.asyncio
async def test_a_new_voice_message_is_transcribed_captured_and_run_with_its_id(voice_wired):
    data = await _voice()
    assert voice_wired.captured == [("how hot is it now?", "voice", CID)]
    assert voice_wired.answered == [("how hot is it now?", None, CID)]
    assert data["heard"] == "how hot is it now?"


@pytest.mark.asyncio
async def test_answer_stores_the_client_id_in_the_task_input(monkeypatch):
    from life_graph.api import dependencies, jarvis, kernel

    done = _task("completed")
    pm = SimpleNamespace(
        spawn=AsyncMock(return_value={"task_id": str(done.id)}),
        get_task=AsyncMock(return_value=done),
    )
    monkeypatch.setattr(dependencies, "get_process_manager", lambda: pm)
    monkeypatch.setattr(kernel, "_load_chat_history", AsyncMock(return_value=[]))
    monkeypatch.setattr(jarvis, "_saved_in", AsyncMock(return_value=[]))
    monkeypatch.setattr(jarvis, "_reminded_in", AsyncMock(return_value=[]))
    turn = await jarvis._answer("t_idem", "how hot is it?", CONV, client_id=CID)
    assert pm.spawn.call_args.kwargs["input_data"]["client_id"] == CID
    assert turn["reply"] == "It is 31 degrees." and turn["conversation_id"] == str(CONV)
