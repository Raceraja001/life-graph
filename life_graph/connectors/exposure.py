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
contact name, org, emails, birthday         yes    per account (default yes)
contact phones, postal addresses, notes     yes    per account (default no)
contact birth year, relations               yes    never
code item (PR, issue), public repo          yes    yes (title redacted)
code item, private repo                     yes    count, unless the account
                                                   shares private titles
code item URL, private repo                 yes    never
=========================================  =====  ==========================

(*) fetched live on request, never stored.

Contacts: the account setting ``cloud_fields`` lists the field groups a cloud
audience may see (``CONTACT_FIELDS``). Without ``name`` a contact is counted,
not shown.

Accounts with ``exposure = local_only`` show a cloud audience counts only.
Mail the local classifier labels ``sensitive`` (banking, one-time codes,
medical, legal) shows only its sender.
"""

from __future__ import annotations

import json
import re
from typing import Any

from life_graph.connectors.base import KIND_CODE, KIND_CONTACT, KIND_EMAIL, KIND_EVENT
from life_graph.connectors.locality import CLOUD, LOCAL

EXPOSURE_STANDARD = "standard"
EXPOSURE_LOCAL_ONLY = "local_only"
EXPOSURES = (EXPOSURE_STANDARD, EXPOSURE_LOCAL_ONLY)

# Contact field groups a cloud audience may be allowed to see, and the default.
CONTACT_FIELDS = ("name", "org", "emails", "birthday", "phones", "addresses", "notes")
DEFAULT_CONTACT_CLOUD_FIELDS = ("name", "org", "emails", "birthday")

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


def _event_view(
    item: dict[str, Any], audience: str, people: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    local = audience == LOCAL
    clean = (lambda s: s) if local else redact
    attendees = [
        (person_name(people.get(a.lower()), audience) or a) if "@" in a else a
        for a in item.get("attendees") or []
    ]
    view = {
        "id": item["id"],
        "kind": KIND_EVENT,
        "account": item["account_name"],
        "title": clean(item.get("title")) or "(no title)",
        "starts_at": _iso(item.get("starts_at")),
        "ends_at": _iso(item.get("ends_at")),
        "all_day": bool((item.get("flags") or {}).get("all_day")),
        "location": clean(item.get("location")),
        "attendees": attendees,
        "direction": item.get("direction"),
    }
    if local:
        view["description"] = item.get("local_detail")
    return view


def _email_view(
    item: dict[str, Any], audience: str, people: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    local = audience == LOCAL
    flags = dict(item.get("flags") or {})
    sender_name = item.get("sender_name")
    if not sender_name and not flags.get("suspicious"):
        # Never lend a contact's name to a suspicious (possibly spoofed) sender.
        sender_name = person_name(people.get(item.get("sender_addr") or ""), audience)
    view: dict[str, Any] = {
        "id": item["id"],
        "kind": KIND_EMAIL,
        "account": item["account_name"],
        "direction": item.get("direction"),
        "date": _iso(item.get("occurred_at")),
        "sender_name": sender_name,
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


def contact_cloud_fields(item: dict[str, Any]) -> frozenset[str]:
    """The field groups a cloud audience may see of this contact's account."""
    if item.get("account_exposure") == EXPOSURE_LOCAL_ONLY:
        return frozenset()
    chosen = item.get("account_cloud_fields")
    if chosen is None:
        chosen = DEFAULT_CONTACT_CLOUD_FIELDS
    return frozenset(f for f in chosen if f in CONTACT_FIELDS)


def _contact_private(item: dict[str, Any]) -> dict[str, Any]:
    try:
        private = json.loads(item.get("local_detail") or "{}")
    except ValueError:
        private = {}
    return private if isinstance(private, dict) else {}


def _contact_view(item: dict[str, Any], audience: str) -> dict[str, Any] | None:
    """None when a cloud audience may not see this contact at all."""
    local = audience == LOCAL
    allowed = frozenset(CONTACT_FIELDS) if local else contact_cloud_fields(item)
    if "name" not in allowed:
        return None
    flags = item.get("flags") or {}
    private = _contact_private(item)
    view: dict[str, Any] = {
        "id": item["id"],
        "kind": KIND_CONTACT,
        "account": item["account_name"],
        "name": item.get("title") or "(no name)",
        "saved": item.get("direction") == "own",
    }
    if "org" in allowed:
        view["org"] = flags.get("org")
        view["job_title"] = flags.get("job_title")
    if "emails" in allowed:
        view["emails"] = list(item.get("emails") or [])
    if "birthday" in allowed and flags.get("birthday"):
        view["birthday"] = flags["birthday"]  # MM-DD
    if "phones" in allowed:
        view["phones"] = private.get("phones") or []
    if "addresses" in allowed:
        view["addresses"] = private.get("addresses") or []
    if "notes" in allowed and private.get("notes"):
        view["notes"] = private["notes"] if local else redact(private["notes"])
    if local:
        view["birth_year"] = private.get("birth_year")
        view["relations"] = private.get("relations") or []
    return {k: v for k, v in view.items() if v not in (None, "", [])}


def person_name(contact: dict[str, Any] | None, audience: str) -> str | None:
    """A contact's name for use inside another item's view, if ``audience`` may see it."""
    if not contact:
        return None
    if audience == LOCAL or "name" in contact_cloud_fields(contact):
        return contact.get("title") or None
    return None


def person_line(contact: dict[str, Any] | None, audience: str) -> str | None:
    """'Name — Org, Title' for a contact, within what ``audience`` may see."""
    name = person_name(contact, audience)
    if not name or contact is None:
        return None
    flags = contact.get("flags") or {}
    allowed = frozenset(CONTACT_FIELDS) if audience == LOCAL else contact_cloud_fields(contact)
    work = ", ".join(p for p in (flags.get("org"), flags.get("job_title")) if p)
    if work and "org" in allowed:
        return f"{name} — {work}"
    return name


PRIVATE_REPOS = "private repos"


def _code_view(item: dict[str, Any], audience: str) -> dict[str, Any] | None:
    """A pull request or issue. None when a cloud audience may not see it."""
    local = audience == LOCAL
    flags = item.get("flags") or {}
    private = bool(flags.get("private"))
    if not local and private and not item.get("account_share_private"):
        return None
    view: dict[str, Any] = {
        "id": item["id"],
        "kind": KIND_CODE,
        "account": item["account_name"],
        "sub": flags.get("sub"),  # pr_review | pr_mine | issue
        "repo": flags.get("repo"),
        "number": flags.get("number"),
        "title": item.get("title") if local else redact(item.get("title")),
        "author": flags.get("author"),
        "created": flags.get("created"),
        "updated": _iso(item.get("occurred_at")),
        "draft": flags.get("draft"),
        "ci": flags.get("ci"),
        "review": flags.get("review"),
        "mergeable": flags.get("mergeable"),
        "labels": flags.get("labels"),
        "dev_agent": flags.get("dev_agent"),
        "private": private,
    }
    if local or not private:
        view["url"] = flags.get("url")
    return {k: v for k, v in view.items() if v not in (None, [], "")}


def view_items(
    items: list[dict[str, Any]],
    audience: str,
    people: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Render items for ``audience``.

    Returns ``{"items": [...], "withheld": {account: count}}``: items from
    ``local_only`` accounts are counted, not shown, for a cloud audience, as
    are contacts whose account does not share names. ``people`` (address →
    contact row, from ``store.people_by_address``) puts names on bare
    addresses, each within what ``audience`` may see of that contact.
    """
    people = people or {}
    shown: list[dict[str, Any]] = []
    withheld: dict[str, int] = {}

    def hold(item: dict[str, Any], label: str | None = None) -> None:
        key = label or item["account_name"]
        withheld[key] = withheld.get(key, 0) + 1

    for item in items:
        if audience != LOCAL and item.get("account_exposure") == EXPOSURE_LOCAL_ONLY:
            hold(item)
            continue
        if item["kind"] == KIND_EVENT:
            shown.append(_event_view(item, audience, people))
        elif item["kind"] == KIND_EMAIL:
            shown.append(_email_view(item, audience, people))
        elif item["kind"] == KIND_CONTACT:
            view = _contact_view(item, audience)
            if view is None:
                hold(item)
            else:
                shown.append(view)
        elif item["kind"] == KIND_CODE:
            view = _code_view(item, audience)
            if view is None:
                hold(item, f"{item['account_name']} ({PRIVATE_REPOS})")
            else:
                shown.append(view)
    return {"items": shown, "withheld": withheld}


def body_for(audience: str, body: str | None) -> str | None:
    """A mail body is only ever released to a local audience."""
    return body if audience == LOCAL else None


def audience_or_cloud(value: str | None) -> str:
    """Normalise an audience string; anything unrecognised is CLOUD."""
    return LOCAL if value == LOCAL else CLOUD
