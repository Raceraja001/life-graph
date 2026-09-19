"""Google Tasks connector implementation (see ``plugins/tasks/__init__.py``)."""

from __future__ import annotations

from typing import Any

from life_graph.connectors.base import AUTH_OAUTH, KIND_TASK, Account, SyncResult
from plugins.tasks import google_source


class TasksConnector:
    name = "tasks"
    display_name = "Google Tasks"
    item_kinds = frozenset({KIND_TASK})
    auth_methods = (AUTH_OAUTH,)
    account_fields = (
        {"name": "username", "label": "Google account (for sign-in)", "methods": [AUTH_OAUTH]},
    )

    def validate_settings(self, auth_method: str, raw: dict[str, Any]) -> dict[str, Any]:
        username = str(raw.get("username") or "").strip()
        if username and "@" not in username:
            raise ValueError("the Google account must be an email address")
        return {"username": username} if username else {}

    async def sync(
        self, account: Account, secret: dict[str, Any], cursor: dict[str, Any]
    ) -> SyncResult:
        items, deleted, new_cursor, complete = await google_source.sync(account, secret, cursor)
        return SyncResult(items=items, deleted=deleted, cursor=new_cursor, complete=complete)

    async def fetch_body(
        self, account: Account, secret: dict[str, Any], external_id: str
    ) -> str | None:
        return None
