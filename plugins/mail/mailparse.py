"""Message parsing shared by the IMAP and Gmail API sources."""

from __future__ import annotations

import email
import email.policy
import html
import re
from datetime import UTC, datetime
from email.header import decode_header, make_header
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from typing import TYPE_CHECKING, Any

from life_graph.connectors.base import DIR_INBOUND, DIR_SENT, KIND_EMAIL, Item

if TYPE_CHECKING:
    from email.message import Message

MAX_TEXT = 8000

_AUTOMATED_SENDER = re.compile(
    r"(?i)^(no[-_.]?reply|do[-_.]?not[-_.]?reply|notifications?|mailer[-_.]?daemon|"
    r"postmaster|bounce[s]?|alerts?|updates?|news(?:letter)?|marketing|info)@"
)


def decode(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except Exception:
        return str(value).strip()


def msgid(value: str | None) -> str | None:
    if not value:
        return None
    m = re.search(r"<([^>]+)>", value)
    return (m.group(1) if m else value.strip()).lower() or None


def thread_key(headers: dict[str, str]) -> str | None:
    """The thread root: first References id, else In-Reply-To, else own Message-ID."""
    refs = re.findall(r"<([^>]+)>", headers.get("references", ""))
    if refs:
        return refs[0].lower()
    return msgid(headers.get("in-reply-to")) or msgid(headers.get("message-id"))


def is_automated(headers: dict[str, str], sender_addr: str) -> bool:
    auto_sub = headers.get("auto-submitted", "").strip().lower()
    precedence = headers.get("precedence", "").strip().lower()
    return bool(
        headers.get("list-id")
        or headers.get("list-unsubscribe")
        or (auto_sub and auto_sub != "no")
        or precedence in ("bulk", "list", "junk")
        or _AUTOMATED_SENDER.match(sender_addr or "")
    )


def html_to_text(markup: str) -> str:
    markup = re.sub(r"(?is)<(script|style|head)[^>]*>.*?</\1>", " ", markup)
    markup = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</tr>", "\n", markup)
    text = html.unescape(re.sub(r"<[^>]+>", " ", markup))
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def text_of(msg: Message) -> str:
    """Readable text of a parsed message: text/plain parts, else HTML stripped."""
    plain: list[str] = []
    htmls: list[str] = []
    for part in msg.walk() if msg.is_multipart() else [msg]:
        if part.is_multipart() or part.get_content_disposition() == "attachment":
            continue
        ctype = part.get_content_type()
        if ctype not in ("text/plain", "text/html"):
            continue
        try:
            payload = part.get_payload(decode=True) or b""
            text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        except Exception:
            continue
        (plain if ctype == "text/plain" else htmls).append(text)
    body = "\n".join(plain).strip() or html_to_text("\n".join(htmls))
    return body[:MAX_TEXT]


def parse_bytes(raw: bytes) -> Message:
    return email.message_from_bytes(raw, policy=email.policy.compat32)


def header_map(msg: Message) -> dict[str, str]:
    return {k.lower(): str(v) for k, v in msg.items()}


def to_item(
    headers: dict[str, str],
    *,
    external_id: str,
    sent: bool,
    my_addresses: set[str],
    fallback_date: datetime | None = None,
    text: str | None = None,
    extra_flags: dict[str, Any] | None = None,
    thread: str | None = None,
) -> Item:
    name, addr = parseaddr(decode(headers.get("from")))
    addr = addr.lower()
    recipients = [a.lower() for _, a in getaddresses([headers.get("to", "")]) if a]
    try:
        when = parsedate_to_datetime(headers.get("date", "")).astimezone(UTC)
    except (TypeError, ValueError, IndexError):
        when = fallback_date or datetime.now(UTC)
    automated = is_automated(headers, addr)
    sent = sent or addr in my_addresses
    copied = [a.lower() for _, a in getaddresses([headers.get("cc", "")]) if a]
    # Everyone on the message except the user: how meeting prep finds the
    # history with a person by exact address.
    people = [a for a in dict.fromkeys([addr, *recipients, *copied]) if a and a not in my_addresses]
    return Item(
        kind=KIND_EMAIL,
        external_id=external_id,
        direction=DIR_SENT if sent else DIR_INBOUND,
        occurred_at=when,
        title=decode(headers.get("subject")) or "(no subject)",
        thread_key=thread or thread_key(headers),
        sender_name=name or None,
        sender_addr=addr or None,
        to_me=(not sent) and any(r in my_addresses for r in recipients),
        emails=people[:50],
        flags={"automated": automated, **(extra_flags or {})},
        summary_source=text,
    )
