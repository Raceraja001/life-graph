"""GitHub connector implementation (see ``plugins/github/__init__.py``)."""

from __future__ import annotations

from typing import Any

from life_graph.connectors.base import (
    AUTH_TOKEN,
    KIND_CODE,
    Account,
    ReauthRequiredError,
    SyncResult,
)
from plugins.github import graphql


class GitHubConnector:
    name = "github"
    display_name = "GitHub"
    item_kinds = frozenset({KIND_CODE})
    auth_methods = (AUTH_TOKEN,)
    account_fields = (
        {"name": "api_url", "label": "GitHub Enterprise API URL (blank = github.com)"},
    )

    def validate_settings(self, auth_method: str, raw: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {"share_private_titles": bool(raw.get("share_private_titles"))}
        api_url = str(raw.get("api_url") or "").strip().rstrip("/")
        if api_url:
            if not api_url.startswith("https://"):
                raise ValueError("the GitHub API URL must start with https://")
            out["api_url"] = api_url
        if raw.get("username"):
            out["username"] = str(raw["username"]).strip()[:100]
        return out

    async def verify_credential(
        self, auth_method: str, settings: dict[str, Any], secret: dict[str, Any]
    ) -> dict[str, Any]:
        """The token works and cannot write; the login becomes the account's username."""
        token = (secret or {}).get("token") or ""
        if not token.strip():
            raise ValueError("an access token is required")
        login = await graphql.verify(settings, token.strip())
        return {"username": login} if login else {}

    async def sync(
        self, account: Account, secret: dict[str, Any], cursor: dict[str, Any]
    ) -> SyncResult:
        token = (secret or {}).get("token")
        if not token:
            raise ReauthRequiredError("no GitHub token stored")
        items, login = await graphql.fetch(account.settings, token)
        return SyncResult(items=items, cursor={"login": login}, complete=True)

    async def fetch_body(
        self, account: Account, secret: dict[str, Any], external_id: str
    ) -> str | None:
        return None  # titles and status only: bodies are never fetched
