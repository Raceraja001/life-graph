"""Email connector implementation (see ``plugins/mail/__init__.py``)."""

from __future__ import annotations

from typing import Any

from life_graph.connectors.base import (
    AUTH_APP_PASSWORD,
    AUTH_OAUTH,
    KIND_EMAIL,
    Account,
    SyncResult,
)
from plugins.mail import gmail_source, imap_source


class EmailConnector:
    name = "email"
    display_name = "Email"
    item_kinds = frozenset({KIND_EMAIL})
    auth_methods = (AUTH_APP_PASSWORD, AUTH_OAUTH)
    account_fields = (
        {
            "name": "username",
            "label": "Email address",
            "methods": [AUTH_APP_PASSWORD, AUTH_OAUTH],
            "required": True,
        },
        {
            "name": "host",
            "label": "IMAP server (default imap.gmail.com)",
            "methods": [AUTH_APP_PASSWORD],
        },
        {
            "name": "my_addresses",
            "label": "Other addresses of yours (aliases)",
            "methods": [AUTH_APP_PASSWORD, AUTH_OAUTH],
            "list": True,
        },
    )

    def validate_settings(self, auth_method: str, raw: dict[str, Any]) -> dict[str, Any]:
        username = str(raw.get("username") or "").strip()
        if "@" not in username:
            raise ValueError("an email address is required")
        aliases = raw.get("my_addresses") or []
        if isinstance(aliases, str):
            aliases = aliases.replace(";", ",").split(",")
        mine = [username.lower(), *[str(a).strip().lower() for a in aliases if str(a).strip()]]
        out: dict[str, Any] = {"username": username, "my_addresses": list(dict.fromkeys(mine))}
        if auth_method == AUTH_APP_PASSWORD:
            # Gmail and Google Workspace both use imap.gmail.com; any other
            # provider's server is entered explicitly.
            out["host"] = str(raw.get("host") or "").strip() or "imap.gmail.com"
            out["port"] = int(raw.get("port") or 993)
            if raw.get("tls_insecure") is True:
                # Test servers with self-signed certificates only.
                out["tls_insecure"] = True
        return out

    async def sync(
        self, account: Account, secret: dict[str, Any], cursor: dict[str, Any]
    ) -> SyncResult:
        if account.auth_method == AUTH_OAUTH:
            items, deleted, new_cursor = await gmail_source.sync(account, secret, cursor)
            return SyncResult(items=items, deleted=deleted, cursor=new_cursor)
        items, imap_cursor = await imap_source.sync(account, secret, cursor)
        return SyncResult(items=items, cursor={"imap": imap_cursor})

    async def fetch_body(
        self, account: Account, secret: dict[str, Any], external_id: str
    ) -> str | None:
        if account.auth_method == AUTH_OAUTH:
            return await gmail_source.fetch_body(account, secret, external_id)
        return await imap_source.fetch_body(account, secret, external_id)
