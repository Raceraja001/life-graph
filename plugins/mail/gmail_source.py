"""Gmail API source (OAuth, ``gmail.readonly``). Read-only twice over: the scope
cannot modify mail, and this module only issues GET requests.

First sync lists the retention window (newest ``MAX_INITIAL`` messages) and
records the mailbox ``historyId``; later syncs replay ``history.list`` from it
(messageAdded / messageDeleted). An expired history id falls back to a full
listing.
"""

from __future__ import annotations

import asyncio
import base64
import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from life_graph.config import settings
from life_graph.connectors.base import Account, ConnectorError, Item, ReauthRequiredError
from plugins.mail import mailparse

logger = logging.getLogger(__name__)

API = "https://gmail.googleapis.com/gmail/v1/users/me"
MAX_INITIAL = 500
CONCURRENCY = 8
META_HEADERS = [
    "From",
    "To",
    "Cc",
    "Date",
    "Subject",
    "Message-ID",
    "In-Reply-To",
    "References",
    "List-Id",
    "List-Unsubscribe",
    "Auto-Submitted",
    "Precedence",
]


class _Client:
    def __init__(self, token: str) -> None:
        self.http = httpx.AsyncClient(timeout=45, headers={"Authorization": f"Bearer {token}"})

    async def get(self, path: str, params: Any = None) -> httpx.Response:
        try:
            resp = await self.http.get(f"{API}{path}", params=params)
        except httpx.HTTPError as exc:
            raise ConnectorError(f"could not reach Gmail: {type(exc).__name__}") from exc
        if resp.status_code in (401, 403):
            raise ReauthRequiredError(f"Gmail refused access (HTTP {resp.status_code}); reconnect")
        return resp

    async def aclose(self) -> None:
        await self.http.aclose()


def _headers(payload: dict[str, Any]) -> dict[str, str]:
    return {h["name"].lower(): h["value"] for h in payload.get("headers", [])}


def _decode(data: str | None) -> str:
    if not data:
        return ""
    try:
        return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")
    except Exception:
        return ""


def body_text(payload: dict[str, Any]) -> str:
    plain: list[str] = []
    htmls: list[str] = []

    def walk(part: dict[str, Any]) -> None:
        mime = part.get("mimeType", "")
        if part.get("filename"):
            return
        if mime == "text/plain":
            plain.append(_decode(part.get("body", {}).get("data")))
        elif mime == "text/html":
            htmls.append(_decode(part.get("body", {}).get("data")))
        for sub in part.get("parts", []) or []:
            walk(sub)

    walk(payload)
    text = "\n".join(plain).strip() or mailparse.html_to_text("\n".join(htmls))
    return text[: mailparse.MAX_TEXT]


def _item(msg: dict[str, Any], my: set[str], text: str | None) -> Item:
    headers = _headers(msg.get("payload", {}))
    labels = set(msg.get("labelIds") or [])
    fallback = datetime.fromtimestamp(int(msg.get("internalDate", "0")) / 1000, tz=UTC)
    return mailparse.to_item(
        headers,
        external_id=msg["id"],
        sent="SENT" in labels,
        my_addresses=my,
        fallback_date=fallback,
        text=text,
        thread=msg.get("threadId"),
        extra_flags={"labels": sorted(labels & {"INBOX", "SENT", "IMPORTANT", "STARRED"})},
    )


async def _get_messages(
    client: _Client, ids: list[str], my: set[str], body_budget: int
) -> list[Item]:
    sem = asyncio.Semaphore(CONCURRENCY)
    full_ids = set(ids[:body_budget]) if body_budget > 0 else set()

    async def one(mid: str) -> Item | None:
        async with sem:
            if mid in full_ids:
                resp = await client.get(f"/messages/{mid}", {"format": "full"})
            else:
                resp = await client.get(
                    f"/messages/{mid}",
                    [("format", "metadata"), *[("metadataHeaders", h) for h in META_HEADERS]],
                )
            if resp.status_code == 404:
                return None
            if resp.status_code >= 400:
                raise ConnectorError(f"Gmail message fetch failed ({resp.status_code})")
            msg = resp.json()
            if set(msg.get("labelIds") or []) & {"SPAM", "TRASH", "CHAT", "DRAFT"}:
                return None
            text = body_text(msg.get("payload", {})) if mid in full_ids else None
            return _item(msg, my, text)

    results = await asyncio.gather(*(one(m) for m in ids))
    return [r for r in results if r is not None]


async def _full_listing(client: _Client) -> list[str]:
    days = settings.connector_email_retention_days
    ids: list[str] = []
    page = None
    while len(ids) < MAX_INITIAL:
        params = {"q": f"newer_than:{days}d -in:chats -in:spam -in:trash", "maxResults": "500"}
        if page:
            params["pageToken"] = page
        resp = await client.get("/messages", params)
        if resp.status_code >= 400:
            raise ConnectorError(f"Gmail listing failed ({resp.status_code})")
        data = resp.json()
        ids.extend(m["id"] for m in data.get("messages", []))
        page = data.get("nextPageToken")
        if not page:
            break
    return ids[:MAX_INITIAL]  # newest first


async def sync(
    account: Account, secret: dict[str, Any], cursor: dict[str, Any]
) -> tuple[list[Item], list[str], dict[str, Any]]:
    token = secret.get("access_token")
    if not token:
        raise ReauthRequiredError("no Google access token")
    my = set(a.lower() for a in account.settings.get("my_addresses") or [])
    state = cursor.get("gmail") or {}
    client = _Client(token)
    try:
        profile = await client.get("/profile")
        if profile.status_code >= 400:
            raise ConnectorError(f"Gmail profile failed ({profile.status_code})")
        history_now = profile.json().get("historyId")
        added: list[str] = []
        deleted: list[str] = []
        full = not state.get("history_id")
        if not full:
            page = None
            while True:
                params = [
                    ("startHistoryId", state["history_id"]),
                    ("historyTypes", "messageAdded"),
                    ("historyTypes", "messageDeleted"),
                    ("maxResults", "500"),
                ]
                if page:
                    params.append(("pageToken", page))
                resp = await client.get("/history", params)
                if resp.status_code == 404:  # history id too old
                    full = True
                    break
                if resp.status_code >= 400:
                    raise ConnectorError(f"Gmail history failed ({resp.status_code})")
                data = resp.json()
                for h in data.get("history", []):
                    added.extend(m["message"]["id"] for m in h.get("messagesAdded", []))
                    deleted.extend(m["message"]["id"] for m in h.get("messagesDeleted", []))
                page = data.get("nextPageToken")
                if not page:
                    break
        if full:
            added, deleted = await _full_listing(client), []
        added = list(dict.fromkeys(a for a in added if a not in set(deleted)))
        items = await _get_messages(client, added, my, settings.connector_summaries_per_sync)
    finally:
        await client.aclose()
    return items, deleted, {"gmail": {"history_id": history_now}}


async def fetch_body(account: Account, secret: dict[str, Any], external_id: str) -> str | None:
    token = secret.get("access_token")
    if not token:
        raise ReauthRequiredError("no Google access token")
    client = _Client(token)
    try:
        resp = await client.get(f"/messages/{external_id}", {"format": "full"})
        if resp.status_code >= 400:
            return None
        return body_text(resp.json().get("payload", {}))
    finally:
        await client.aclose()
