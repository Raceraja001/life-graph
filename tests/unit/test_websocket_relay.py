"""The Redis relay sends each event to its tenant's sockets once (api/websocket.py).

Two publishers share the ``events:`` prefix: ws_event_handler publishes
``events:{tenant}`` and the EventBus Redis bridge ``events:{tenant}:{type}``.
The relay read the tenant as everything after the first colon, so a bridge
channel named a tenant no socket has. It was also never started, so with
Redis up no socket got any event. Both publishers run in the API process for
every event, so the relay must send only one of the two copies.
"""

from __future__ import annotations

import asyncio
import inspect
import json
from fnmatch import fnmatchcase

import pytest

from life_graph import main
from life_graph.api import websocket as ws
from life_graph.core import events as core_events
from life_graph.core.events import Event, EventType
from life_graph.core.tenant import tenant_scope


class _Socket:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, message: dict) -> None:
        self.sent.append(message)


class _PubSub:
    def __init__(self, redis: _Redis) -> None:
        self._redis = redis
        self.queue: asyncio.Queue = asyncio.Queue()
        self.patterns: list[str] = []

    async def psubscribe(self, pattern: str) -> None:
        self.patterns.append(pattern)
        self._redis.subscribers.append(self)

    async def punsubscribe(self, pattern: str) -> None:
        self._redis.subscribers.remove(self)

    async def aclose(self) -> None:
        return None

    async def listen(self):
        while True:
            yield await self.queue.get()


class _Redis:
    """Just enough of redis.asyncio for publish + pattern subscribe, in memory."""

    def __init__(self) -> None:
        self.subscribers: list[_PubSub] = []

    async def publish(self, channel: str, data: str) -> int:
        for sub in self.subscribers:
            for pattern in sub.patterns:
                if fnmatchcase(channel, pattern):
                    sub.queue.put_nowait(
                        {"type": "pmessage", "pattern": pattern, "channel": channel, "data": data}
                    )
        return len(self.subscribers)

    def pubsub(self) -> _PubSub:
        return _PubSub(self)


@pytest.fixture
def wired(monkeypatch):
    """One socket each for acme and globex, behind an in-memory Redis."""
    manager = ws.ConnectionManager()
    monkeypatch.setattr(ws, "ws_manager", manager)
    redis = _Redis()
    monkeypatch.setattr(ws, "get_redis", lambda: redis)
    monkeypatch.setattr("life_graph.storage.redis.get_redis", lambda: redis)
    acme, globex = _Socket(), _Socket()
    manager._connections = {"acme": {acme}, "globex": {globex}}
    return redis, acme, globex


async def _drain(redis: _Redis) -> None:
    """Let the relay task handle everything published so far."""
    for _ in range(50):
        await asyncio.sleep(0)
        if all(sub.queue.empty() for sub in redis.subscribers):
            break
    await asyncio.sleep(0)


@pytest.mark.parametrize(
    ("channel", "expected"),
    [
        ("events:acme", ("acme", True)),
        (f"events:acme:{EventType.MEMORY_CREATED.value}", ("acme", False)),
        ("events:org:acme", ("org:acme", True)),  # a colon in a tenant id is kept
        (f"events:org:acme:{EventType.TASK_COMPLETED.value}", ("org:acme", False)),
        ("other:acme", (None, False)),
    ],
)
def test_the_tenant_is_read_from_both_channel_formats(channel, expected):
    assert ws._channel_tenant(channel) == expected


@pytest.mark.asyncio
async def test_one_event_reaches_its_tenants_socket_once(wired):
    """The single-process path: handler and bridge both publish; one delivery."""
    redis, acme, globex = wired
    relay = ws.start_relay()
    try:
        await asyncio.sleep(0)
        assert redis.subscribers, "the relay did not subscribe"
        event = Event(type=EventType.TASK_COMPLETED, payload={"task_id": "t1"}, source="test")
        with tenant_scope("acme"):
            await ws.ws_event_handler(event)  # events:acme
            await core_events._redis_bridge.publish(event)  # events:acme:task.completed
        await _drain(redis)
    finally:
        await ws.stop_relay(relay)

    assert [m["payload"]["task_id"] for m in acme.sent] == ["t1"]
    assert globex.sent == []
    assert relay.done()


@pytest.mark.asyncio
async def test_a_relay_message_goes_to_the_named_tenant_only(wired):
    redis, acme, globex = wired
    relay = ws.start_relay()
    try:
        await asyncio.sleep(0)
        await redis.publish("events:globex", json.dumps({"type": "x", "payload": {}}))
        await redis.publish("events:globex", "not json")
        await _drain(redis)
    finally:
        await ws.stop_relay(relay)

    assert acme.sent == []
    assert globex.sent == [{"type": "x", "payload": {}}]


@pytest.mark.asyncio
async def test_the_relay_reconnects_after_the_subscription_drops(wired, monkeypatch):
    redis, acme, _ = wired
    monkeypatch.setattr(ws, "_RECONNECT_FIRST_SECONDS", 0)
    calls = {"n": 0}
    real_pubsub = redis.pubsub

    def flaky_pubsub():
        calls["n"] += 1
        sub = real_pubsub()
        if calls["n"] == 1:

            async def broken(pattern):
                raise ConnectionError("redis went away")

            sub.psubscribe = broken
        return sub

    monkeypatch.setattr(redis, "pubsub", flaky_pubsub)
    relay = ws.start_relay()
    try:
        for _ in range(20):
            await asyncio.sleep(0)
            if redis.subscribers:
                break
        await redis.publish("events:acme", json.dumps({"type": "y"}))
        await _drain(redis)
    finally:
        await ws.stop_relay(relay)

    assert calls["n"] >= 2
    assert acme.sent == [{"type": "y"}]


def test_the_api_starts_and_stops_the_relay():
    src = inspect.getsource(main.lifespan)
    assert "start_relay()" in src
    assert "stop_relay(" in src
