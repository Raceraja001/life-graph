"""A thin async wrapper over the Telegram Bot API.

Deliberately not ``python-telegram-bot``: that library brings its own event
loop, job queue and update dispatcher, all of which this repo already has. The
Bot API is plain HTTPS with JSON bodies, so ``httpx`` — already a core
dependency — is enough.

Every method returns data or raises. Callers decide what a failure means: the
poller retries with backoff, the notification channel returns ``False``.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from life_graph.config import settings

logger = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org"

# Telegram truncates at 4096 UTF-16 code units. Chunk below that so a long
# recall answer arrives as several readable messages rather than one rejection.
MAX_MESSAGE_CHARS = 4000


class TelegramError(RuntimeError):
    """The Bot API returned ``ok: false``.

    ``retry_after`` is set when Telegram asked us to slow down (HTTP 429),
    which the poller honours instead of applying its own backoff.
    """

    def __init__(
        self, description: str, *, error_code: int | None = None, retry_after: int | None = None
    ):
        super().__init__(description)
        self.description = description
        self.error_code = error_code
        self.retry_after = retry_after


class TelegramClient:
    """Bot API calls for one bot token.

    The token is a credential: it is never logged, and it travels in the URL
    path because that is the only place the Bot API accepts it.
    """

    def __init__(self, token: str | None = None, *, client: httpx.AsyncClient | None = None):
        self._token = token if token is not None else settings.telegram_bot_token
        self._client = client
        self._owns_client = client is None

    @property
    def configured(self) -> bool:
        """False when no bot token is set — the bridge is then simply off."""
        return bool(self._token)

    async def __aenter__(self) -> TelegramClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0))
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    # ── Calls ─────────────────────────────────────────────────

    async def get_me(self) -> dict[str, Any]:
        """Identify the bot. Used by /status to prove the token works."""
        return await self._call("getMe", {})

    async def get_updates(self, offset: int | None = None, timeout: int = 25) -> list[dict]:
        """Long-poll for updates.

        ``allowed_updates`` is pinned to messages: subscribing to everything
        would have Telegram queue edits, reactions and poll answers we do not
        handle, and the offset would advance past them as if they were read.
        """
        payload: dict[str, Any] = {
            "timeout": timeout,
            "allowed_updates": ["message"],
        }
        if offset is not None:
            payload["offset"] = offset
        result = await self._call("getUpdates", payload, read_timeout=timeout + 15)
        return result if isinstance(result, list) else []

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        *,
        parse_mode: str | None = None,
        disable_notification: bool = False,
    ) -> list[dict]:
        """Send ``text``, split across messages when it exceeds the API limit.

        Returns one result per message actually sent.
        """
        sent = []
        for chunk in _chunk(text, MAX_MESSAGE_CHARS):
            payload: dict[str, Any] = {
                "chat_id": chat_id,
                "text": chunk,
                "disable_notification": disable_notification,
                # Link previews turn a recalled URL into an unsolicited fetch of
                # that page by Telegram's servers. Off by default.
                "link_preview_options": {"is_disabled": True},
            }
            if parse_mode:
                payload["parse_mode"] = parse_mode
            sent.append(await self._call("sendMessage", payload))
        return sent

    async def get_file_path(self, file_id: str) -> str:
        """Resolve a file id to a download path (for voice notes and photos)."""
        result = await self._call("getFile", {"file_id": file_id})
        return result["file_path"]

    async def download_file(self, file_path: str, *, max_bytes: int) -> bytes:
        """Fetch a file previously resolved by :meth:`get_file_path`.

        ``max_bytes`` is enforced while streaming rather than after the fact:
        the ``file_size`` a message advertises is Telegram's word, and the
        bytes land in memory before anything else looks at them. Streaming
        means a file that lies about its size costs one chunk, not all of it.

        Note the different host path — downloads live under ``/file/bot<token>/``
        rather than the method endpoint, so this cannot go through ``_call``.
        """
        if not self._token:
            raise TelegramError("Telegram bot token is not configured")
        if self._client is None:
            raise RuntimeError("TelegramClient used outside its async context manager")

        url = f"{API_BASE}/file/bot{self._token}/{file_path}"
        chunks: list[bytes] = []
        total = 0
        async with self._client.stream("GET", url) as response:
            if response.status_code != 200:
                raise TelegramError(
                    f"file download failed ({response.status_code})",
                    error_code=response.status_code,
                )
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    raise TelegramError(f"file exceeds {max_bytes} bytes")
                chunks.append(chunk)
        return b"".join(chunks)

    # ── Internals ─────────────────────────────────────────────

    async def _call(
        self, method: str, payload: dict[str, Any], *, read_timeout: float | None = None
    ) -> Any:
        if not self._token:
            raise TelegramError("Telegram bot token is not configured")
        if self._client is None:
            raise RuntimeError("TelegramClient used outside its async context manager")

        url = f"{API_BASE}/bot{self._token}/{method}"
        kwargs: dict[str, Any] = {"json": payload}
        if read_timeout is not None:
            kwargs["timeout"] = httpx.Timeout(read_timeout, connect=10.0)

        response = await self._client.post(url, **kwargs)

        # 429 carries the wait time in the body, not the standard header, and it
        # is not an error to shout about — it is Telegram pacing us.
        try:
            body = response.json()
        except ValueError:
            response.raise_for_status()
            raise TelegramError(f"{method}: non-JSON response") from None

        if not body.get("ok"):
            params = body.get("parameters") or {}
            raise TelegramError(
                body.get("description", "unknown error"),
                error_code=body.get("error_code"),
                retry_after=params.get("retry_after"),
            )
        return body.get("result")


def _chunk(text: str, size: int) -> list[str]:
    """Split on line boundaries where possible, so a message never cuts a word.

    Falls back to a hard cut only for a single line longer than the limit.
    """
    text = text or ""
    if len(text) <= size:
        return [text] if text else []

    chunks: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        while len(line) > size:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:size])
            line = line[size:]
        if len(current) + len(line) > size:
            chunks.append(current)
            current = line
        else:
            current += line
    if current:
        chunks.append(current)
    return chunks
