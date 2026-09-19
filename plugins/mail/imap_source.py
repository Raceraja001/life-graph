"""IMAP source (app password). Read-only by construction.

Every folder is opened with ``EXAMINE`` (``select(readonly=True)``) and every
fetch uses ``BODY.PEEK``, so the server never sets ``\\Seen``; there is no
STORE, COPY, MOVE, EXPUNGE or APPEND anywhere in this module.

Incremental by folder: the cursor keeps ``uidvalidity`` and the highest UID
seen. The first sync of a folder (or after UIDVALIDITY changes) reads the
newest ``MAX_NEW_PER_FOLDER`` messages of the retention window.
"""

from __future__ import annotations

import asyncio
import contextlib
import imaplib
import logging
import re
import ssl
from datetime import UTC, datetime, timedelta
from typing import Any

from life_graph.config import settings
from life_graph.connectors.base import Account, ConnectorError, Item, ReauthRequiredError
from plugins.mail import mailparse

logger = logging.getLogger(__name__)

MAX_NEW_PER_FOLDER = 500
HEADER_FIELDS = (
    "FROM TO CC DATE SUBJECT MESSAGE-ID IN-REPLY-TO REFERENCES LIST-ID LIST-UNSUBSCRIBE "
    "AUTO-SUBMITTED PRECEDENCE"
)
BODY_PEEK_BYTES = 65536

# Commands this module may send. Anything else is a programming error: the
# guard below makes a write command impossible to issue by accident.
_ALLOWED = {"LOGIN", "AUTHENTICATE", "CAPABILITY", "LIST", "EXAMINE", "UID", "LOGOUT", "NOOP"}
_ALLOWED_UID = {"SEARCH", "FETCH"}


class ReadOnlyIMAP(imaplib.IMAP4_SSL):
    """IMAP4_SSL that refuses every command that could change the mailbox."""

    def _command(self, name, *args):  # noqa: D401 - imaplib internal hook
        if name not in _ALLOWED:
            raise ConnectorError(f"refusing IMAP command {name} (connector is read-only)")
        if name == "UID" and (not args or str(args[0]).upper() not in _ALLOWED_UID):
            raise ConnectorError("refusing IMAP UID sub-command (connector is read-only)")
        return super()._command(name, *args)


def _connect(account: Account, secret: dict[str, Any]) -> ReadOnlyIMAP:
    host = account.settings.get("host") or "imap.gmail.com"
    port = int(account.settings.get("port") or 993)
    user = account.settings.get("username")
    password = secret.get("password")
    if not user or not password:
        raise ReauthRequiredError("username or app password missing")
    # imaplib's default context does not verify the server certificate; a
    # mailbox password must never go to an unverified server. ``tls_insecure``
    # exists only for a local test server with a self-signed certificate.
    ctx = ssl.create_default_context()
    if account.settings.get("tls_insecure"):
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    try:
        conn = ReadOnlyIMAP(host, port, ssl_context=ctx, timeout=45)
    except (OSError, ssl.SSLError) as exc:
        raise ConnectorError(f"could not connect to {host}:{port}: {type(exc).__name__}") from exc
    try:
        conn.login(user, password)
    except imaplib.IMAP4.error as exc:
        msg = str(exc)
        raise ReauthRequiredError(
            "the mail server refused the app password"
            + (" (web login required / app passwords disabled?)" if "WEBALERT" in msg else "")
        ) from exc
    return conn


_LIST_RE = re.compile(r'\((?P<flags>[^)]*)\) (?P<delim>"[^"]*"|NIL) (?P<name>.+)')


def _folders(conn: imaplib.IMAP4) -> dict[str, str]:
    """{"inbox": name, "sent": name} using SPECIAL-USE flags where available."""
    found = {"inbox": "INBOX"}
    status, lines = conn.list()
    if status != "OK":
        return found
    for raw in lines or []:
        line = raw.decode(errors="replace") if isinstance(raw, bytes) else str(raw)
        m = _LIST_RE.match(line)
        if not m:
            continue
        name = m.group("name").strip()
        if (
            "\\Sent" in m.group("flags")
            or "sent" not in found
            and name.strip('"').lower() in ("sent", "sent items", "sent mail")
        ):
            found["sent"] = name
    return found


def _examine(conn: imaplib.IMAP4, folder: str) -> int | None:
    status, _ = conn.select(folder, readonly=True)
    if status != "OK":
        return None
    resp = conn.response("UIDVALIDITY")[1]
    try:
        return int(resp[0]) if resp and resp[0] else None
    except (TypeError, ValueError):
        return None


def _uid_search(conn: imaplib.IMAP4, *criteria: str) -> list[int]:
    status, data = conn.uid("SEARCH", *criteria)
    if status != "OK" or not data or not data[0]:
        return []
    return sorted(int(x) for x in data[0].split())


def _fetch(
    conn: imaplib.IMAP4, uids: list[int], with_body: bool
) -> dict[int, tuple[bytes, bytes | None]]:
    """{uid: (header bytes, body bytes or None)} using BODY.PEEK only."""
    out: dict[int, tuple[bytes, bytes | None]] = {}
    if not uids:
        return out
    spec = f"(UID BODY.PEEK[HEADER.FIELDS ({HEADER_FIELDS})]"
    spec += f" BODY.PEEK[]<0.{BODY_PEEK_BYTES}>)" if with_body else ")"
    for start in range(0, len(uids), 100):
        chunk = ",".join(str(u) for u in uids[start : start + 100])
        status, data = conn.uid("FETCH", chunk, spec)
        if status != "OK":
            continue
        current: dict[str, Any] = {}
        for part in data or []:
            if not isinstance(part, tuple):
                if current.get("uid") is not None:
                    out[current["uid"]] = (current.get("hdr", b""), current.get("body"))
                    current = {}
                continue
            meta = part[0].decode(errors="replace")
            m = re.search(r"UID (\d+)", meta)
            if m:
                if current.get("uid") is not None and int(m.group(1)) != current["uid"]:
                    out[current["uid"]] = (current.get("hdr", b""), current.get("body"))
                    current = {}
                current["uid"] = int(m.group(1))
            if "HEADER.FIELDS" in meta:
                current["hdr"] = part[1]
            elif "BODY[]" in meta:
                current["body"] = part[1]
        if current.get("uid") is not None:
            out[current["uid"]] = (current.get("hdr", b""), current.get("body"))
    return out


def _sync_blocking(
    account: Account, secret: dict[str, Any], cursor: dict[str, Any], body_budget: int
) -> tuple[list[Item], dict[str, Any]]:
    my = set(a.lower() for a in account.settings.get("my_addresses") or [])
    since = (datetime.now(UTC) - timedelta(days=settings.connector_email_retention_days)).strftime(
        "%d-%b-%Y"
    )
    items: list[Item] = []
    new_cursor: dict[str, Any] = dict(cursor)
    conn = _connect(account, secret)
    try:
        folders = _folders(conn)
        for role, folder in folders.items():
            validity = _examine(conn, folder)
            if validity is None:
                continue
            state = cursor.get(role) or {}
            if state.get("uidvalidity") == validity and state.get("last_uid"):
                uids = [
                    u
                    for u in _uid_search(conn, "UID", f"{state['last_uid'] + 1}:*")
                    if u > state["last_uid"]
                ]
            else:
                uids = _uid_search(conn, "SINCE", since)
            uids = uids[-MAX_NEW_PER_FOLDER:]
            # Bodies for the newest few only (they feed the summariser now);
            # the rest are summarised later via fetch_body.
            with_body = set(uids[-body_budget:]) if body_budget > 0 else set()
            fetched = _fetch(conn, [u for u in uids if u not in with_body], with_body=False)
            fetched.update(_fetch(conn, sorted(with_body), with_body=True))
            body_budget -= len(with_body)
            for uid in uids:
                hdr_raw, body_raw = fetched.get(uid, (b"", None))
                if not hdr_raw:
                    continue
                headers = mailparse.header_map(mailparse.parse_bytes(hdr_raw))
                ext = mailparse.msgid(headers.get("message-id")) or f"{role}:{validity}:{uid}"
                text = mailparse.text_of(mailparse.parse_bytes(body_raw)) if body_raw else None
                items.append(
                    mailparse.to_item(
                        headers, external_id=ext, sent=(role == "sent"), my_addresses=my, text=text
                    )
                )
            if uids or state.get("uidvalidity") != validity:
                new_cursor[role] = {
                    "uidvalidity": validity,
                    "last_uid": max(uids) if uids else state.get("last_uid", 0),
                }
    finally:
        with contextlib.suppress(Exception):
            conn.logout()
    return items, new_cursor


def _body_blocking(account: Account, secret: dict[str, Any], external_id: str) -> str | None:
    conn = _connect(account, secret)
    try:
        for folder in _folders(conn).values():
            if _examine(conn, folder) is None:
                continue
            safe = external_id.replace('"', "")
            uids = _uid_search(conn, "HEADER", "Message-ID", f'"{safe}"')
            if uids:
                fetched = _fetch(conn, uids[-1:], with_body=True)
                raw = next(iter(fetched.values()), (b"", None))[1]
                return mailparse.text_of(mailparse.parse_bytes(raw)) if raw else None
        return None
    finally:
        with contextlib.suppress(Exception):
            conn.logout()


async def sync(
    account: Account, secret: dict[str, Any], cursor: dict[str, Any]
) -> tuple[list[Item], dict[str, Any]]:
    budget = settings.connector_summaries_per_sync
    return await asyncio.to_thread(
        _sync_blocking, account, secret, cursor.get("imap") or {}, budget
    )


async def fetch_body(account: Account, secret: dict[str, Any], external_id: str) -> str | None:
    return await asyncio.to_thread(_body_blocking, account, secret, external_id)
