"""What ``/status`` and ``/health`` can honestly say about the poller.

The poller runs in the ARQ worker; this code runs in the API process. There is
no object to inspect, so every answer is derived from what the poller published
to Redis. These tests pin the derivation, and in particular the two cases where
the honest answer is "I don't know" — because reporting ``stopped`` when Redis
is simply unreachable would send someone to debug a poller that is running
perfectly well.

Also covers the streaming size ceiling on file downloads: a message's
``file_size`` is Telegram's claim about the file, so the limit has to hold while
the bytes arrive rather than after they are all in memory.
"""

from __future__ import annotations

import httpx
import pytest

from life_graph.api import integrations_telegram as tg_api
from life_graph.integrations.telegram.client import TelegramClient, TelegramError
from life_graph.integrations.telegram.poller import (
    HEARTBEAT_KEY,
    LAST_UPDATE_KEY,
    LEASE_KEY,
)


class FakeRedis:
    def __init__(self, values: dict | None = None, *, fail: bool = False):
        self.values = values or {}
        self.fail = fail

    async def get(self, key):
        if self.fail:
            raise ConnectionError("redis is down")
        return self.values.get(key)


@pytest.fixture
def token(monkeypatch):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "telegram_bot_token", "test-token")


def _with_redis(monkeypatch, redis):
    import life_graph.storage.redis as redis_mod

    monkeypatch.setattr(redis_mod, "get_redis", lambda: redis)


# ── poller_state ─────────────────────────────────────────────────


class TestPollerState:
    async def test_no_token_reads_as_disabled(self, monkeypatch):
        from life_graph.config import settings

        monkeypatch.setattr(settings, "telegram_bot_token", "")
        state = await tg_api.poller_state()
        assert state["poller"] == "disabled"

    async def test_a_held_lease_reads_as_leading(self, token, monkeypatch):
        _with_redis(
            monkeypatch,
            FakeRedis(
                {
                    LEASE_KEY: "1234:abcd",
                    HEARTBEAT_KEY: "2026-08-26T18:41:03+00:00",
                    LAST_UPDATE_KEY: "2026-08-26T18:40:11+00:00",
                }
            ),
        )
        state = await tg_api.poller_state()
        assert state["poller"] == "leading"
        assert state["last_poll_at"] == "2026-08-26T18:41:03+00:00"
        assert state["last_update_at"] == "2026-08-26T18:40:11+00:00"

    async def test_no_lease_reads_as_stopped(self, token, monkeypatch):
        _with_redis(monkeypatch, FakeRedis({}))
        assert (await tg_api.poller_state())["poller"] == "stopped"

    async def test_bytes_from_redis_are_decoded(self, token, monkeypatch):
        # Whether the client decodes responses is a connection setting, so the
        # endpoint must not assume it — an un-decoded b'...' would be rendered
        # into JSON as the repr of a bytes object.
        _with_redis(
            monkeypatch,
            FakeRedis({LEASE_KEY: b"held", HEARTBEAT_KEY: b"2026-08-26T18:41:03+00:00"}),
        )
        state = await tg_api.poller_state()
        assert state["last_poll_at"] == "2026-08-26T18:41:03+00:00"

    async def test_no_redis_reads_as_unknown_not_stopped(self, token, monkeypatch):
        _with_redis(monkeypatch, None)
        state = await tg_api.poller_state()
        assert state["poller"] == "unknown", "no Redis means no observation, not a verdict"

    async def test_a_redis_failure_reads_as_unknown(self, token, monkeypatch):
        _with_redis(monkeypatch, FakeRedis(fail=True))
        assert (await tg_api.poller_state())["poller"] == "unknown"

    async def test_a_lease_without_a_heartbeat_still_reports_no_poll_time(self, token, monkeypatch):
        # The heartbeat expires with the lease TTL; a leader that stopped
        # turning shows a lease and no recent stamp, which is the signal.
        _with_redis(monkeypatch, FakeRedis({LEASE_KEY: "held"}))
        state = await tg_api.poller_state()
        assert state["poller"] == "leading"
        assert state["last_poll_at"] is None


# ── download ceiling ─────────────────────────────────────────────


class TestDownloadCeiling:
    async def _client(self, handler) -> TelegramClient:
        transport = httpx.MockTransport(handler)
        http = httpx.AsyncClient(transport=transport)
        return TelegramClient(token="t", client=http)

    async def test_a_file_within_the_limit_downloads(self):
        def handler(request):
            return httpx.Response(200, content=b"abcdef")

        client = await self._client(handler)
        assert await client.download_file("photos/1.jpg", max_bytes=100) == b"abcdef"

    async def test_a_file_over_the_limit_is_refused_mid_stream(self):
        # The response is far larger than the cap; the point is that the call
        # raises rather than returning a buffer bigger than the caller allowed.
        def handler(request):
            return httpx.Response(200, content=b"x" * 10_000)

        client = await self._client(handler)
        with pytest.raises(TelegramError):
            await client.download_file("photos/1.jpg", max_bytes=100)

    async def test_an_http_error_becomes_a_telegram_error(self):
        def handler(request):
            return httpx.Response(404, content=b"nope")

        client = await self._client(handler)
        with pytest.raises(TelegramError):
            await client.download_file("photos/gone.jpg", max_bytes=100)

    async def test_the_token_never_appears_in_the_error(self):
        # The token travels in the URL path because the Bot API accepts it
        # nowhere else, which puts it one careless f-string away from the logs.
        secret = "123456:AAHsecrettokenvalue"

        def handler(request):
            return httpx.Response(403, content=b"forbidden")

        transport = httpx.MockTransport(handler)
        client = TelegramClient(token=secret, client=httpx.AsyncClient(transport=transport))
        with pytest.raises(TelegramError) as exc:
            await client.download_file("photos/1.jpg", max_bytes=100)
        assert secret not in str(exc.value)
