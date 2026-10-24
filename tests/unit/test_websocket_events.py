"""/ws sends each event to its own tenant's sockets only (api/websocket.py).

An event with no tenant context — every background job's — used to be
broadcast to every connected socket, so one tenant could watch another's.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from life_graph.api import websocket as ws
from life_graph.core.events import Event, EventType
from life_graph.core.tenant import tenant_scope


class _Socket:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def accept(self) -> None:
        return None

    async def send_json(self, message: dict) -> None:
        self.sent.append(message)


@pytest.fixture
def sockets(monkeypatch):
    """One socket each for tenants acme and globex; Redis absent, so local delivery."""
    manager = ws.ConnectionManager()
    monkeypatch.setattr(ws, "ws_manager", manager)
    monkeypatch.setattr(ws, "get_redis", lambda: None)
    acme, globex = _Socket(), _Socket()
    manager._connections = {"acme": {acme}, "globex": {globex}}
    return acme, globex


def _event(payload: dict) -> Event:
    return Event(type=EventType.TASK_COMPLETED, payload=payload, source="worker")


@pytest.mark.asyncio
async def test_an_event_goes_to_the_tenant_its_payload_names(sockets):
    acme, globex = sockets

    await ws.ws_event_handler(_event({"tenant_id": "acme", "task_id": "t1"}))

    assert [m["payload"]["task_id"] for m in acme.sent] == ["t1"]
    assert globex.sent == []


@pytest.mark.asyncio
async def test_the_tenant_context_is_used_when_the_payload_names_none(sockets):
    acme, globex = sockets

    with tenant_scope("globex"):
        await ws.ws_event_handler(_event({"task_id": "t2"}))

    assert acme.sent == []
    assert len(globex.sent) == 1


@pytest.mark.asyncio
async def test_an_event_with_no_tenant_reaches_nobody(sockets):
    """The leak: background jobs emit with no tenant context."""
    acme, globex = sockets

    await ws.ws_event_handler(_event({"task_id": "t3"}))

    assert acme.sent == []
    assert globex.sent == []


@pytest.mark.asyncio
async def test_a_payload_and_context_that_disagree_reach_nobody(sockets):
    acme, globex = sockets

    with tenant_scope("globex"):
        await ws.ws_event_handler(_event({"tenant_id": "acme"}))

    assert acme.sent == []
    assert globex.sent == []


@pytest.mark.asyncio
async def test_only_allowlisted_types_go_to_everyone(sockets, monkeypatch):
    acme, globex = sockets
    monkeypatch.setattr(ws, "GLOBAL_EVENT_TYPES", frozenset({EventType.TASK_COMPLETED.value}))

    await ws.ws_event_handler(_event({}))

    assert len(acme.sent) == 1
    assert len(globex.sent) == 1


def test_no_event_type_is_global_today():
    assert frozenset() == ws.GLOBAL_EVENT_TYPES


@pytest.mark.asyncio
async def test_with_redis_it_publishes_on_the_tenants_channel(sockets, monkeypatch):
    redis = AsyncMock()
    monkeypatch.setattr(ws, "get_redis", lambda: redis)

    await ws.ws_event_handler(_event({"tenant_id": "acme"}))

    assert redis.publish.await_args.args[0] == "events:acme"
