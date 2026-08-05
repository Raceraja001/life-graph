"""Unit tests for the in-process chat session bus."""

from __future__ import annotations

import asyncio

import pytest

from life_graph.services.chat_stream import ChatStreamBus


@pytest.mark.asyncio
async def test_publish_reaches_subscriber():
    bus = ChatStreamBus()
    got = []

    async def consume():
        async for ev in bus.subscribe("k1"):
            got.append(ev)

    task = asyncio.create_task(consume())
    await asyncio.sleep(0)  # let subscribe register
    bus.publish("k1", {"type": "token", "content": "hi"})
    bus.close("k1")
    await asyncio.wait_for(task, timeout=1)
    assert got == [{"type": "token", "content": "hi"}]


@pytest.mark.asyncio
async def test_buffer_replays_events_published_before_subscribe():
    bus = ChatStreamBus()
    bus.publish("k2", {"type": "token", "content": "a"})
    bus.publish("k2", {"type": "token", "content": "b"})
    got = []

    async def consume():
        async for ev in bus.subscribe("k2"):
            got.append(ev)

    task = asyncio.create_task(consume())
    await asyncio.sleep(0)
    bus.close("k2")
    await asyncio.wait_for(task, timeout=1)
    assert [e["content"] for e in got] == ["a", "b"]


@pytest.mark.asyncio
async def test_two_subscribers_both_receive():
    bus = ChatStreamBus()
    a, b = [], []

    async def consume(sink):
        async for ev in bus.subscribe("k3"):
            sink.append(ev)

    ta = asyncio.create_task(consume(a))
    tb = asyncio.create_task(consume(b))
    await asyncio.sleep(0)
    bus.publish("k3", {"type": "done"})
    bus.close("k3")
    await asyncio.wait_for(asyncio.gather(ta, tb), timeout=1)
    assert a == b == [{"type": "done"}]


def test_publish_with_no_subscriber_is_noop_but_buffered():
    bus = ChatStreamBus()
    bus.publish("k4", {"type": "token", "content": "x"})  # must not raise
    assert bus.buffer_len("k4") == 1


@pytest.mark.asyncio
async def test_subscribe_after_close_and_drain_terminates():
    """Late subscriber to an already closed+drained stream must terminate promptly."""
    bus = ChatStreamBus()
    # Publish, close, and fully consume with the first subscriber.
    bus.publish("k5", {"type": "token", "content": "first"})
    bus.close("k5")
    got1 = []

    async def consume1():
        async for ev in bus.subscribe("k5"):
            got1.append(ev)

    task1 = asyncio.create_task(consume1())
    await asyncio.wait_for(task1, timeout=1)  # First subscriber fully drains stream

    # Now subscribe again to the same, already-closed key.
    # This must NOT hang; it should terminate promptly, even though
    # the buffer was cleaned up after the first subscriber exited.
    got2 = []

    async def consume2():
        async for ev in bus.subscribe("k5"):
            got2.append(ev)

    task2 = asyncio.create_task(consume2())
    await asyncio.wait_for(task2, timeout=1)  # Must not hang
    # Second subscriber receives only _END (buffer was cleaned up).
    assert got2 == []
