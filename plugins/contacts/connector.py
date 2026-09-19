"""Contacts connector implementation (see ``plugins/contacts/__init__.py``)."""

from __future__ import annotations

from typing import Any

from life_graph.connectors.base import (
    AUTH_FILE,
    AUTH_OAUTH,
    KIND_CONTACT,
    Account,
    SyncResult,
)
from life_graph.connectors.exposure import CONTACT_FIELDS, DEFAULT_CONTACT_CLOUD_FIELDS
from plugins.contacts import google_source, vcard

CLOUD_FIELD_LABELS = {
    "name": "Names",
    "org": "Company and job title",
    "emails": "Email addresses",
    "birthday": "Birthdays (day and month)",
    "phones": "Phone numbers",
    "addresses": "Postal addresses",
    "notes": "Notes (redacted)",
}


class ContactsConnector:
    name = "contacts"
    display_name = "Contacts"
    item_kinds = frozenset({KIND_CONTACT})
    auth_methods = (AUTH_OAUTH, AUTH_FILE)
    default_interval_min = 360
    account_fields = (
        {"name": "username", "label": "Google account (for sign-in)", "methods": [AUTH_OAUTH]},
    )
    cloud_field_options = tuple(
        {
            "name": f,
            "label": CLOUD_FIELD_LABELS[f],
            "default": f in DEFAULT_CONTACT_CLOUD_FIELDS,
        }
        for f in CONTACT_FIELDS
    )

    def validate_settings(self, auth_method: str, raw: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        username = str(raw.get("username") or "").strip()
        if username:
            if "@" not in username:
                raise ValueError("the Google account must be an email address")
            out["username"] = username
        chosen = raw.get("cloud_fields")
        if chosen is None:
            chosen = list(DEFAULT_CONTACT_CLOUD_FIELDS)
        if isinstance(chosen, str):
            chosen = [c.strip() for c in chosen.split(",")]
        unknown = [c for c in chosen if c not in CONTACT_FIELDS]
        if unknown:
            raise ValueError(f"unknown contact fields: {', '.join(map(str, unknown))}")
        out["cloud_fields"] = [f for f in CONTACT_FIELDS if f in chosen]
        return out

    async def sync(
        self, account: Account, secret: dict[str, Any], cursor: dict[str, Any]
    ) -> SyncResult:
        if account.auth_method != AUTH_OAUTH:
            # A file account changes only when the user imports a new export.
            return SyncResult(cursor=cursor)
        items, deleted, new_cursor, complete = await google_source.sync(account, secret, cursor)
        return SyncResult(items=items, deleted=deleted, cursor=new_cursor, complete=complete)

    async def fetch_body(
        self, account: Account, secret: dict[str, Any], external_id: str
    ) -> str | None:
        return None

    def import_file(self, account: Account, text: str) -> SyncResult:
        return SyncResult(items=vcard.parse_vcards(text), complete=True)
