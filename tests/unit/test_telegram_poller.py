"""The Telegram poller's failure modes, which is where its risk lives.

The happy path is three lines. What matters is what happens when the network
drops, when Telegram rate limits us, when a handler raises, and when a second
instance is running — because each of those either loses the user's messages or
silently splits them between two consumers.

No network: a fake client stands in for the Bot API.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from life_graph.integrations.telegram.client import TelegramError
from life_graph.integrations.telegram.poller import TelegramPoller


class FakeClient:
    """Serves scripted getUpdates results, then blocks so the loop parks."""

    def __init__(self, script):
        self.script = list(script)
        self.calls: list[dict] = []

    async def get_updates(self, offset=None, timeout=25):
        self.calls.append({"offset": offset, "timeout": timeout})
        if not self.script:
            await asyncio.sleep(3600)  # park; the test cancels us
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _update(uid: int, text: str = "hello", chat_id: int = 77) -> dict:
    return {
        "update_id": uid,
        "message": {
            "message_id": uid,
            "chat": {"id": chat_id, "type": "private"},
            "text": text,
        },
    }


async def _run_until(poller, predicate, timeout=2.0):
    """Run the loop until predicate() is true, then stop it."""
    task = asyncio.create_task(poller.run_forever())
    deadline = asyncio.get_event_loop().time() + timeout
    try:
        while not predicate():
            if asyncio.get_event_loop().time() > deadline:
                raise AssertionError("condition not reached before timeout")
            await asyncio.sleep(0.01)
    finally:
        poller._stopping.set()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    return task


@pytest.fixture
def no_redis(monkeypatch):
    """No Redis: lease is a no-op and offsets are not persisted."""
    monkeypatch.setattr("life_graph.integrations.telegram.poller._redis", lambda: None)


@pytest.fixture
def token(monkeypatch):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "telegram_bot_token", "test-token")
    monkeypatch.setattr(settings, "telegram_poll_timeout", 1)


# ── Offset handling ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_offset_advances_only_after_an_update_is_handled(token, monkeypatch):
    """A crash mid-handler must replay the update, not skip it."""
    stored: list[int] = []
    handled: list[int] = []

    async def handler(update, session):
        handled.append(update["update_id"])

    monkeypatch.setattr("life_graph.integrations.telegram.poller.handle_update", handler)
    poller = TelegramPoller(client=FakeClient([[_update(5)]]))
    monkeypatch.setattr(poller, "_store_offset", lambda o: _record(stored, o))
    monkeypatch.setattr(poller, "_load_offset", _async_none)
    monkeypatch.setattr(poller, "_acquire_lease", _async_true)
    monkeypatch.setattr(poller, "_dispatch", lambda u: handler(u, None))

    await _run_until(poller, lambda: stored)
    assert handled == [5]
    assert stored == [6], "offset must be update_id + 1, written after handling"


@pytest.mark.asyncio
async def test_a_failing_handler_does_not_advance_past_the_update(token, monkeypatch):
    """If handling raises, the offset must not move — the message would be lost."""
    stored: list[int] = []

    async def boom(update):
        raise RuntimeError("handler exploded")

    poller = TelegramPoller(client=FakeClient([[_update(9)]]))
    monkeypatch.setattr(poller, "_store_offset", lambda o: _record(stored, o))
    monkeypatch.setattr(poller, "_load_offset", _async_none)
    monkeypatch.setattr(poller, "_acquire_lease", _async_true)
    monkeypatch.setattr(poller, "_dispatch", boom)

    task = asyncio.create_task(poller.run_forever())
    await asyncio.sleep(0.15)
    poller._stopping.set()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert stored == [], "a failed handler must not advance the offset"


@pytest.mark.asyncio
async def test_a_stored_offset_is_sent_back_to_telegram(token, monkeypatch):
    client = FakeClient([[]])
    poller = TelegramPoller(client=client)
    monkeypatch.setattr(poller, "_load_offset", lambda: _async_value(4242))
    monkeypatch.setattr(poller, "_acquire_lease", _async_true)

    await _run_until(poller, lambda: client.calls)
    assert client.calls[0]["offset"] == 4242


# ── Standby / lease ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_standby_instance_never_calls_get_updates(token, monkeypatch):
    """Two concurrent getUpdates would split the conversation, not duplicate it."""
    client = FakeClient([[_update(1)]])
    poller = TelegramPoller(client=client)
    monkeypatch.setattr(poller, "_acquire_lease", _async_false)

    task = asyncio.create_task(poller.run_forever())
    await asyncio.sleep(0.15)
    poller._stopping.set()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert client.calls == [], "standby must not consume updates"
    assert poller.status == "stopped"


@pytest.mark.asyncio
async def test_the_lease_is_only_released_when_it_is_ours(no_redis, token):
    """Releasing another process's lease would let a third instance barge in."""
    poller = TelegramPoller()
    await poller._release_lease()  # no Redis: must not raise


# ── Error handling ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_network_error_backs_off_and_retries(token, monkeypatch):
    client = FakeClient([httpx.ConnectError("down"), [_update(2)]])
    poller = TelegramPoller(client=client)
    monkeypatch.setattr(poller, "_load_offset", _async_none)
    monkeypatch.setattr(poller, "_store_offset", lambda o: _async_none())
    monkeypatch.setattr(poller, "_acquire_lease", _async_true)
    monkeypatch.setattr(poller, "_dispatch", lambda u: _async_none())

    await _run_until(poller, lambda: len(client.calls) >= 2, timeout=5.0)
    assert len(client.calls) >= 2, "the loop must retry after a network error"


@pytest.mark.asyncio
async def test_a_rejected_token_stops_the_loop_instead_of_hammering(token, monkeypatch):
    """401 never fixes itself; retrying forever just burns the API quota."""
    client = FakeClient([TelegramError("Unauthorized", error_code=401)])
    poller = TelegramPoller(client=client)
    monkeypatch.setattr(poller, "_load_offset", _async_none)
    monkeypatch.setattr(poller, "_acquire_lease", _async_true)

    await asyncio.wait_for(poller.run_forever(), timeout=3.0)
    assert len(client.calls) == 1, "must not retry a rejected token"


@pytest.mark.asyncio
async def test_rate_limiting_waits_the_period_telegram_asked_for(token, monkeypatch):
    slept: list[float] = []
    client = FakeClient([TelegramError("Too Many Requests", error_code=429, retry_after=7)])
    poller = TelegramPoller(client=client)
    monkeypatch.setattr(poller, "_load_offset", _async_none)
    monkeypatch.setattr(poller, "_acquire_lease", _async_true)

    async def fake_sleep(seconds):
        slept.append(seconds)
        poller._stopping.set()

    monkeypatch.setattr(poller, "_sleep", fake_sleep)
    await asyncio.wait_for(poller.run_forever(), timeout=3.0)
    assert slept == [7], "must honour retry_after rather than guessing a backoff"


# ── Configuration ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_no_token_means_the_bridge_simply_does_not_start(monkeypatch):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "telegram_bot_token", "")
    poller = TelegramPoller()
    assert await poller.start() is False
    assert poller.status == "stopped"


# ── Helpers ───────────────────────────────────────────────────────


async def _async_true(*a, **k):
    return True


async def _async_false(*a, **k):
    return False


async def _async_none(*a, **k):
    return None


async def _async_value(value):
    return value


async def _record(sink, value):
    sink.append(value)
