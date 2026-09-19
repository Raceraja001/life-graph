"""GitHub GraphQL: one query for what is waiting on the user, and its mapping.

Three searches in one request: pull requests where the user's review is
requested, the user's own open pull requests (with CI rollup and review
decision), and open issues assigned to them. Only titles and status are asked
for — never bodies, comments, diffs or code. The result is the complete open
set, so anything closed or merged since the last sync disappears.

Read-only by construction: GraphQL queries only (no mutations), and the
credential is a read-only token (``verify`` refuses a classic token that can
write).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from life_graph.connectors.base import (
    DIR_INBOUND,
    DIR_OWN,
    KIND_CODE,
    ConnectorError,
    Item,
    ReauthRequiredError,
)

API = "https://api.github.com"
PER_SEARCH = 50
DEV_AGENT_BRANCH = "lg/task-"

# Classic-token scopes that allow no writing. Anything else is refused.
READ_ONLY_SCOPES = frozenset({"read:org", "read:user", "user:email", "read:project"})
READ_ONLY_SCOPES |= frozenset({"read:discussion", "read:packages", "read:gpg_key"})
READ_ONLY_SCOPES |= frozenset({"read:public_key", "read:ssh_signing_key", "read:enterprise"})
READ_ONLY_SCOPES |= frozenset({"read:audit_log", "notifications"})

SEARCHES = {
    "pr_review": "is:open is:pr review-requested:@me archived:false",
    "pr_mine": "is:open is:pr author:@me archived:false",
    "issue": "is:open is:issue assignee:@me archived:false",
}

QUERY = """
query($review: String!, $mine: String!, $issues: String!, $n: Int!) {
  viewer { login }
  review: search(query: $review, type: ISSUE, first: $n) { nodes { ...pr } }
  mine: search(query: $mine, type: ISSUE, first: $n) { nodes { ...pr } }
  issues: search(query: $issues, type: ISSUE, first: $n) {
    nodes {
      ... on Issue {
        number title url createdAt updatedAt
        repository { nameWithOwner isPrivate }
        author { login }
        labels(first: 5) { nodes { name } }
      }
    }
  }
}
fragment pr on PullRequest {
  number title url isDraft createdAt updatedAt headRefName mergeable reviewDecision
  repository { nameWithOwner isPrivate }
  author { login }
  commits(last: 1) { nodes { commit { statusCheckRollup { state } } } }
}
"""


def api_base(settings: dict[str, Any]) -> str:
    return (settings.get("api_url") or API).rstrip("/")


def graphql_url(settings: dict[str, Any]) -> str:
    base = api_base(settings)
    # GitHub Enterprise Server serves REST at /api/v3 and GraphQL at /api/graphql.
    if base.endswith("/api/v3"):
        return base[: -len("/v3")] + "/graphql"
    return base + "/graphql"


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def write_scopes(scopes_header: str | None) -> list[str]:
    """Scopes on a classic token that allow writing (empty for fine-grained tokens)."""
    scopes = [s.strip() for s in (scopes_header or "").split(",") if s.strip()]
    return [s for s in scopes if s not in READ_ONLY_SCOPES]


def _check(resp: httpx.Response) -> None:
    if resp.status_code == 401:
        expiry = resp.headers.get("github-authentication-token-expiration")
        hint = f" (token expiry: {expiry})" if expiry else ""
        raise ReauthRequiredError(f"GitHub refused the token{hint}; create a new one")
    if resp.status_code == 403 and resp.headers.get("x-ratelimit-remaining") == "0":
        raise ConnectorError("GitHub rate limit reached; will retry later")
    if resp.status_code >= 400:
        raise ConnectorError(f"GitHub error {resp.status_code}: {resp.text[:200]}")
    refused = write_scopes(resp.headers.get("x-oauth-scopes"))
    if refused:
        raise ReauthRequiredError(
            "this token can write to GitHub (scopes: "
            + ", ".join(refused)
            + "); use a read-only fine-grained token instead"
        )


async def verify(settings: dict[str, Any], token: str) -> str:
    """Check a token (it works, it cannot write); returns the login."""
    async with httpx.AsyncClient(timeout=20, headers=_headers(token)) as http:
        try:
            resp = await http.get(f"{api_base(settings)}/user")
        except httpx.HTTPError as exc:
            raise ConnectorError(f"could not reach GitHub: {type(exc).__name__}") from exc
    _check(resp)
    return resp.json().get("login") or ""


def _when(value: str | None) -> datetime:
    try:
        return datetime.fromisoformat((value or "").replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(UTC)


def _ci(node: dict[str, Any]) -> str | None:
    commits = ((node.get("commits") or {}).get("nodes")) or []
    rollup = ((commits[0].get("commit") or {}).get("statusCheckRollup")) if commits else None
    return (rollup or {}).get("state")


def node_item(sub: str, node: dict[str, Any]) -> Item | None:
    """One search result → an Item (None for an empty or foreign node)."""
    repo = node.get("repository") or {}
    name = repo.get("nameWithOwner")
    number = node.get("number")
    if not name or not number:
        return None
    is_pr = sub != "issue"
    flags: dict[str, Any] = {
        "sub": sub,
        "repo": name,
        "number": number,
        "private": bool(repo.get("isPrivate")),
        "author": (node.get("author") or {}).get("login"),
        "url": node.get("url"),
        "created": node.get("createdAt"),
    }
    if is_pr:
        flags["draft"] = bool(node.get("isDraft"))
        flags["review"] = node.get("reviewDecision")  # APPROVED / CHANGES_REQUESTED / …
        flags["mergeable"] = node.get("mergeable")  # MERGEABLE / CONFLICTING / UNKNOWN
        flags["ci"] = _ci(node)  # SUCCESS / FAILURE / ERROR / PENDING / EXPECTED
        flags["dev_agent"] = (node.get("headRefName") or "").startswith(DEV_AGENT_BRANCH)
    else:
        flags["labels"] = [
            lb["name"] for lb in ((node.get("labels") or {}).get("nodes") or []) if lb.get("name")
        ]
    return Item(
        kind=KIND_CODE,
        external_id=f"{'pr' if is_pr else 'issue'}:{name}#{number}",
        direction=DIR_OWN if sub == "pr_mine" else DIR_INBOUND,
        occurred_at=_when(node.get("updatedAt")),
        title=node.get("title") or "(no title)",
        flags={k: v for k, v in flags.items() if v not in (None, [], "")},
    )


async def fetch(settings: dict[str, Any], token: str) -> tuple[list[Item], str | None]:
    """Everything open and waiting on the user: (items, login)."""
    variables = {
        "review": SEARCHES["pr_review"],
        "mine": SEARCHES["pr_mine"],
        "issues": SEARCHES["issue"],
        "n": PER_SEARCH,
    }
    async with httpx.AsyncClient(timeout=45, headers=_headers(token)) as http:
        try:
            resp = await http.post(
                graphql_url(settings), json={"query": QUERY, "variables": variables}
            )
        except httpx.HTTPError as exc:
            raise ConnectorError(f"could not reach GitHub: {type(exc).__name__}") from exc
    _check(resp)
    payload = resp.json()
    data = payload.get("data")
    if not data:
        errors = "; ".join(e.get("message", "") for e in payload.get("errors") or [])
        raise ConnectorError(f"GitHub query failed: {errors[:300] or 'no data'}")
    items: dict[str, Item] = {}
    for sub, key in (("pr_review", "review"), ("pr_mine", "mine"), ("issue", "issues")):
        for node in (data.get(key) or {}).get("nodes") or []:
            item = node_item(sub, node or {})
            if item is not None:
                items.setdefault(item.external_id, item)
    return list(items.values()), (data.get("viewer") or {}).get("login")
