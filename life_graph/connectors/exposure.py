"""What each audience may see of a connector item (docs/specs/connectors.md, Story 2).

Every connector result passes through ``view_items`` before any caller sees it.
Plugins return raw ``Item`` rows; only this module decides which fields reach
which audience:

=========================================  =====  ==========================
Field                                      LOCAL  CLOUD / off-machine
=========================================  =====  ==========================
event time, title, location, attendees      yes    yes (redacted)
event description, notes, meeting links     yes    never
mail sender, subject, date, flags           yes    yes (redacted)
mail local summary                          yes    yes (redacted)
mail body, attachments                      yes*   never
=========================================  =====  ==========================

(*) fetched live on request, never stored.

Accounts with ``exposure = local_only`` show a cloud audience counts only.
Mail the local classifier labels ``sensitive`` (banking, one-time codes,
medical, legal) shows only its sender.
"""

from __future__ import annotations

import re
from typing import Any

from life_graph.connectors.base import KIND_EMAIL, KIND_EVENT
from life_graph.connectors.locality import CLOUD, LOCAL

EXPOSURE_STANDARD = "standard"
EXPOSURE_LOCAL_ONLY = "local_only"
EXPOSURES = (EXPOSURE_STANDARD, EXPOSURE_LOCAL_ONLY)

MASK = "[redacted]"

# Order matters: the more specific patterns run first so a card number is not
# half-eaten by the generic long-number rule.
_REDACTIONS: list[tuple[re.Pattern[str], str]] = [
    # "OTP is 482913", "verification code: 5521", "code 1234 to sign in"
    (
        re.compile(
            r"(?i)\b(otp|one[- ]time (?:password|code|pin)|verification code|security code|"
            r"login code|passcode|pin|code)\b(\s*(?:is|:|=|-)?\s*)(\d[\d\s-]{2,9}\d)"
        ),
        r"\1\2" + MASK,
    ),
    (re.compile(r"(?i)\b(password|passwd|pwd)\b(\s*(?:is|:|=)\s*)\S+"), r"\1\2" + MASK),
    # Card numbers: 13-19 digits, optionally grouped by spaces or dashes.
    (re.compile(r"\b(?:\d[ -]?){12,18}\d\b"), MASK),
    # Aadhaar: 12 digits in 4-4-4 groups.
    (re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b"), MASK),
    # PAN: ABCDE1234F
    (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), MASK),
    # IFSC: HDFC0001234
    (re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"), MASK),
    # Bank account numbers and other long identifiers (9-18 digits).
    (re.compile(r"\b\d{9,18}\b"), MASK),
    # Masked account references still identify the account: "a/c XX1234".
    (
        re.compile(
            r"(?i)\b(a/?c|acct|account)(\s*(?:no\.?|number|ending(?: in)?)?\s*(?:is\s*)?[:#]?\s*)"
            r"[X*]*\d{3,}\b"
        ),
        r"\1\2" + MASK,
    ),
]


def redact(text: str | None) -> str | None:
    """Mask one-time codes, passwords and account-like numbers in cloud-bound text."""
    if not text:
        return text
    for pattern, repl in _REDACTIONS:
        text = pattern.sub(repl, text)
    return text


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _event_view(item: dict[str, Any], audience: str) -> dict[str, Any]:
    local = audience == LOCAL
    clean = (lambda s: s) if local else redact
    view = {
        "id": item["id"],
        "kind": KIND_EVENT,
        "account": item["account_name"],
        "title": clean(item.get("title")) or "(no title)",
        "starts_at": _iso(item.get("starts_at")),
        "ends_at": _iso(item.get("ends_at")),
        "all_day": bool((item.get("flags") or {}).get("all_day")),
        "location": clean(item.get("location")),
        "attendees": list(item.get("attendees") or []),
        "direction": item.get("direction"),
    }
    if local:
        view["description"] = item.get("local_detail")
    return view


def _email_view(item: dict[str, Any], audience: str) -> dict[str, Any]:
    local = audience == LOCAL
    flags = dict(item.get("flags") or {})
    view: dict[str, Any] = {
        "id": item["id"],
        "kind": KIND_EMAIL,
        "account": item["account_name"],
        "direction": item.get("direction"),
        "date": _iso(item.get("occurred_at")),
        "sender_name": item.get("sender_name"),
        "sender_addr": item.get("sender_addr"),
        "needs_reply": bool(flags.get("needs_reply")),
        "suspicious": bool(flags.get("suspicious")),
        "category": item.get("category"),
    }
    if not local and item.get("category") == "sensitive":
        view["subject"] = "(sensitive email)"
        view["summary"] = None
        return view
    view["subject"] = item.get("title") if local else redact(item.get("title"))
    view["summary"] = item.get("summary") if local else redact(item.get("summary"))
    if flags.get("commitment"):
        # The user's own promise, from mail they sent.
        view["commitment"] = flags["commitment"] if local else redact(flags["commitment"])
        view["commitment_due"] = flags.get("commitment_due")
    return view


def view_items(items: list[dict[str, Any]], audience: str) -> dict[str, Any]:
    """Render items for ``audience``.

    Returns ``{"items": [...], "withheld": {account: count}}``: items from
    ``local_only`` accounts are counted, not shown, for a cloud audience.
    """
    shown: list[dict[str, Any]] = []
    withheld: dict[str, int] = {}
    for item in items:
        if audience != LOCAL and item.get("account_exposure") == EXPOSURE_LOCAL_ONLY:
            withheld[item["account_name"]] = withheld.get(item["account_name"], 0) + 1
            continue
        if item["kind"] == KIND_EVENT:
            shown.append(_event_view(item, audience))
        elif item["kind"] == KIND_EMAIL:
            shown.append(_email_view(item, audience))
    return {"items": shown, "withheld": withheld}


def body_for(audience: str, body: str | None) -> str | None:
    """A mail body is only ever released to a local audience."""
    return body if audience == LOCAL else None


def audience_or_cloud(value: str | None) -> str:
    """Normalise an audience string; anything unrecognised is CLOUD."""
    return LOCAL if value == LOCAL else CLOUD
