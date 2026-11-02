"""The simulated owner's own pieces (scripts/sim_owner_night.py)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import httpx
import pytest

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "sim_owner_night.py"
_spec = importlib.util.spec_from_file_location("sim_owner_night", _PATH)
sim = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sim)


def _stream(*events: dict) -> bytes:
    return b"".join(f"data: {json.dumps(e)}\n\n".encode() for e in events) + b": ping\n\n"


@pytest.mark.asyncio
async def test_a_reply_is_rebuilt_from_its_tokens():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        seen["tenant"] = request.headers["X-Tenant-ID"]
        return httpx.Response(
            200,
            content=_stream(
                {"type": "token", "content": "Nila is "},
                {"type": "token", "content": "6."},
                {"type": "done", "conversation_id": None},
            ),
        )

    j = sim.Jarvis("http://api", "sim-x", "k")
    j.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    reply, err = await j.say("How old is Nila?", temporary=True)

    assert (reply, err) == ("Nila is 6.", None)
    assert seen["body"] == {"message": "How old is Nila?", "temporary": True}
    assert seen["tenant"] == "sim-x"


@pytest.mark.asyncio
async def test_an_error_event_or_status_is_reported():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/chat") and request.headers.get("X-Tenant-ID") == "bad":
            return httpx.Response(404, json={"detail": "Unknown persona: 'jarvis'"})
        return httpx.Response(200, content=_stream({"type": "error", "message": "model down"}))

    for tenant, expected in (("bad", "HTTP 404"), ("ok", "model down")):
        j = sim.Jarvis("http://api", tenant, "k")
        j.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        assert (await j.say("hi"))[1] == expected


def test_the_owner_keeps_what_is_not_hedged():
    assert sim.HEDGED.search("The owner is considering selling on Amazon.")
    assert sim.HEDGED.search("The owner might move to Pune.")
    assert not sim.HEDGED.search("Nila is 6 and in class 1.")
