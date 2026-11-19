"""The Telegram bot token never reaches the logs (audit M22).

The token travels in the Bot API URL path. A non-JSON error page (a 502 from
a proxy) made the client call ``raise_for_status()``, whose ``HTTPStatusError``
message embeds the full URL — token included — and the poller and the
notification channel both log that message. The ARQ worker, where the poller
runs, also never configured logging, so no mask could be applied there.
"""

from __future__ import annotations

import logging

import httpx
import pytest

from life_graph.core.logging import SecretMaskFilter, setup_logging
from life_graph.integrations.telegram.client import TelegramClient, TelegramError
from life_graph.watchers.channels.telegram_channel import TelegramChannel

TOKEN = "1234567890:AAH" + "x9Y8z7W6v5U4t3S2r1Q0p" + "-_abcdefghijk"


def _bad_gateway(request: httpx.Request) -> httpx.Response:
    return httpx.Response(502, content=b"<html>502 Bad Gateway</html>")


def _client() -> TelegramClient:
    http = httpx.AsyncClient(transport=httpx.MockTransport(_bad_gateway))
    return TelegramClient(token=TOKEN, client=http)


async def test_a_non_json_error_raises_a_url_free_telegram_error():
    with pytest.raises(TelegramError) as exc:
        await _client().send_message(5, "hi")
    assert TOKEN not in str(exc.value)
    assert "502" in str(exc.value)
    # Not a token-rejection code: the poller must back off, not stop.
    assert exc.value.error_code not in (401, 404)


async def test_send_voice_non_json_error_is_url_free():
    with pytest.raises(TelegramError) as exc:
        await _client().send_voice(5, b"abc")
    assert TOKEN not in str(exc.value)


async def test_the_channel_logs_a_502_without_the_token(caplog):
    channel = TelegramChannel(client_factory=_client)

    async def _resolve(config, tenant_id):
        return [5]

    channel._resolve_chats = _resolve  # type: ignore[method-assign]
    with caplog.at_level(logging.DEBUG):
        assert await channel.send({}, "t1", "critical", "Disk full") is False
    ours = [r for r in caplog.records if r.name.startswith("life_graph")]
    assert ours, "the failure should be logged"
    # Our own log lines carry no token even before any filter runs.
    assert all(TOKEN not in r.getMessage() for r in ours)
    assert all(TOKEN not in (r.exc_text or "") for r in ours)
    # httpx logs every request URL at INFO, token included (when its level
    # allows). setup_logging quiets httpx to WARNING, and the mask catches
    # such a line if it ever gets out.
    assert all(TOKEN not in _format(r) for r in caplog.records)


def _format(record: logging.LogRecord) -> str:
    handler = logging.StreamHandler()
    handler.addFilter(SecretMaskFilter())
    handler.setFormatter(logging.Formatter("%(message)s"))
    assert handler.filter(record)
    return handler.format(record)


def test_mask_filter_hides_a_bot_token_in_message_and_args():
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    record = logging.LogRecord(
        "x", logging.WARNING, __file__, 1, "network error — %s", (url,), None
    )
    out = _format(record)
    assert TOKEN not in out
    assert "api.telegram.org/bot" in out  # still diagnosable


def test_mask_filter_hides_a_bot_token_in_a_traceback():
    try:
        raise RuntimeError(
            f"Server error for url 'https://api.telegram.org/bot{TOKEN}/sendMessage'"
        )
    except RuntimeError:
        import sys

        exc_info = sys.exc_info()
    record = logging.LogRecord("x", logging.ERROR, __file__, 1, "boom", None, exc_info)
    out = _format(record)
    assert TOKEN not in out
    assert "RuntimeError" in out


def test_mask_filter_leaves_ordinary_text_alone():
    record = logging.LogRecord(
        "x", logging.INFO, __file__, 1, "chat %s bound at %s", (42, "12:30"), None
    )
    assert _format(record) == "chat 42 bound at 12:30"


@pytest.fixture
def _restore_logging():
    root = logging.getLogger()
    arq = logging.getLogger("arq")
    quieted = ["uvicorn.access", "sqlalchemy.engine", "httpx", "httpcore"]
    saved = (root.handlers[:], root.level, arq.handlers[:], arq.propagate)
    levels = {name: logging.getLogger(name).level for name in quieted}
    yield
    root.handlers[:] = saved[0]
    root.setLevel(saved[1])
    arq.handlers[:] = saved[2]
    arq.propagate = saved[3]
    for name, level in levels.items():
        logging.getLogger(name).setLevel(level)


@pytest.mark.usefixtures("_restore_logging")
def test_setup_logging_installs_the_mask():
    setup_logging()
    handlers = logging.getLogger().handlers
    assert handlers
    assert all(any(isinstance(f, SecretMaskFilter) for f in h.filters) for h in handlers)


@pytest.mark.usefixtures("_restore_logging")
def test_worker_configures_masked_logging_without_doubling_arq_lines():
    from life_graph.workers.settings import configure_worker_logging

    arq = logging.getLogger("arq")
    arq_handler = logging.StreamHandler()
    arq.handlers[:] = [arq_handler]  # what arq's dictConfig sets up
    arq.propagate = True

    configure_worker_logging()

    root_handlers = logging.getLogger().handlers
    assert root_handlers
    assert all(any(isinstance(f, SecretMaskFilter) for f in h.filters) for h in root_handlers)
    # arq keeps its own handler and format; it no longer also propagates to
    # the root handler (which would print every arq line twice).
    assert arq.handlers == [arq_handler]
    assert any(isinstance(f, SecretMaskFilter) for f in arq_handler.filters)
    assert arq.propagate is False
    # httpx logs request URLs (token included) at INFO; keep it quiet.
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING

    # Idempotent: a second call does not stack filters.
    configure_worker_logging()
    assert sum(isinstance(f, SecretMaskFilter) for f in arq_handler.filters) == 1
