"""GitHub connector (docs/specs/connector-github.md): the query mapping, the
read-only token check against a fake GitHub, private-repo exposure, and the
brief's Code section."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from life_graph.config import settings
from life_graph.connectors.base import AUTH_TOKEN, Account, ConnectorError, ReauthRequiredError
from life_graph.connectors.exposure import EXPOSURE_LOCAL_ONLY, view_items
from life_graph.connectors.locality import CLOUD, LOCAL

NOW = datetime(2026, 9, 19, 6, 0, tzinfo=UTC)


def _pr(number, title, repo="Raceraja001/life-graph", private=False, **kw):
    return {
        "number": number,
        "title": title,
        "url": f"https://github.com/{repo}/pull/{number}",
        "isDraft": kw.get("draft", False),
        "createdAt": kw.get("created", "2026-09-18T06:00:00Z"),
        "updatedAt": "2026-09-19T05:00:00Z",
        "headRefName": kw.get("branch", "feat/x"),
        "mergeable": kw.get("mergeable", "MERGEABLE"),
        "reviewDecision": kw.get("review"),
        "repository": {"nameWithOwner": repo, "isPrivate": private},
        "author": {"login": kw.get("author", "someone")},
        "commits": {
            "nodes": [
                {"commit": {"statusCheckRollup": {"state": kw["ci"]} if kw.get("ci") else None}}
            ]
        },
    }


RESPONSE = {
    "data": {
        "viewer": {"login": "Raceraja001"},
        "review": {
            "nodes": [
                _pr(36, "Contacts connector", author="teammate"),
                _pr(7, "Draft idea", draft=True),
                _pr(9, "Secret payroll change", repo="logimax/payroll", private=True),
            ]
        },
        "mine": {
            "nodes": [
                _pr(35, "Connectors", ci="FAILURE", author="Raceraja001"),
                _pr(34, "Calibration", review="APPROVED", ci="SUCCESS", author="Raceraja001"),
                _pr(33, "Waiting one", author="Raceraja001"),
                _pr(
                    40,
                    "Agent fix",
                    branch="lg/task-1234",
                    review="CHANGES_REQUESTED",
                    author="Raceraja001",
                ),
            ]
        },
        "issues": {
            "nodes": [
                {
                    "number": 12,
                    "title": "Login loop",
                    "url": "https://github.com/Race-projects/pulse/issues/12",
                    "createdAt": "2026-09-10T06:00:00Z",
                    "updatedAt": "2026-09-18T06:00:00Z",
                    "repository": {"nameWithOwner": "Race-projects/pulse", "isPrivate": False},
                    "author": {"login": "someone"},
                    "labels": {"nodes": [{"name": "bug"}]},
                },
                {},
            ]
        },
    }
}


class FakeGitHub:
    def __init__(self):
        self.scopes: str | None = None
        self.status = 200
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        headers = {"x-oauth-scopes": self.scopes} if self.scopes is not None else {}
        if self.status == 401:
            return httpx.Response(
                401,
                json={"message": "Bad credentials"},
                headers={"github-authentication-token-expiration": "2026-09-01 00:00:00 UTC"},
            )
        if request.url.path == "/user":
            return httpx.Response(200, json={"login": "Raceraja001"}, headers=headers)
        assert request.url.path == "/graphql" and request.method == "POST"
        assert "mutation" not in request.content.decode()
        return httpx.Response(200, json=RESPONSE, headers=headers)


@pytest.fixture
def fake_github(monkeypatch):
    from plugins.github import graphql

    fake = FakeGitHub()
    real = httpx.AsyncClient

    def client(**kw):
        return real(transport=httpx.MockTransport(fake.handler), **kw)

    monkeypatch.setattr(graphql.httpx, "AsyncClient", client)
    return fake


def _account(**settings_):
    return Account(
        id="acc-g",
        tenant_id="raja",
        connector="github",
        account_key="gh",
        display_name="GitHub",
        auth_method=AUTH_TOKEN,
        settings=settings_,
    )


async def test_sync_maps_the_three_searches(fake_github):
    from plugins.github import CONNECTOR

    result = await CONNECTOR.sync(_account(), {"token": "t"}, {})
    assert result.complete and result.cursor == {"login": "Raceraja001"}
    by_id = {i.external_id: i for i in result.items}
    assert set(by_id) == {
        "pr:Raceraja001/life-graph#36",
        "pr:Raceraja001/life-graph#7",
        "pr:logimax/payroll#9",
        "pr:Raceraja001/life-graph#35",
        "pr:Raceraja001/life-graph#34",
        "pr:Raceraja001/life-graph#33",
        "pr:Raceraja001/life-graph#40",
        "issue:Race-projects/pulse#12",
    }
    review = by_id["pr:Raceraja001/life-graph#36"]
    assert review.kind == "code" and review.direction == "inbound"
    assert review.flags["sub"] == "pr_review" and review.flags["author"] == "teammate"
    failing = by_id["pr:Raceraja001/life-graph#35"]
    assert failing.direction == "own" and failing.flags["ci"] == "FAILURE"
    assert by_id["pr:Raceraja001/life-graph#40"].flags["dev_agent"] is True
    assert "ci" not in by_id["pr:Raceraja001/life-graph#33"].flags
    assert by_id["issue:Race-projects/pulse#12"].flags["labels"] == ["bug"]
    assert by_id["pr:logimax/payroll#9"].flags["private"] is True
    assert fake_github.requests[0].headers["Authorization"] == "Bearer t"


async def test_token_check_refuses_write_access(fake_github):
    from plugins.github import CONNECTOR

    # A fine-grained token reports no scopes: accepted, and the login is learned.
    assert await CONNECTOR.verify_credential("token", {}, {"token": "t"}) == {
        "username": "Raceraja001"
    }
    fake_github.scopes = "read:org, read:user"
    assert await CONNECTOR.verify_credential("token", {}, {"token": "t"})
    fake_github.scopes = "repo, read:org"
    with pytest.raises(ReauthRequiredError, match="can write.*repo"):
        await CONNECTOR.verify_credential("token", {}, {"token": "t"})
    # The same check runs on every sync, in case a token is swapped later.
    with pytest.raises(ReauthRequiredError, match="can write"):
        await CONNECTOR.sync(_account(), {"token": "t"}, {})
    with pytest.raises(ValueError):
        await CONNECTOR.verify_credential("token", {}, {"token": "  "})


async def test_revoked_or_expired_token_means_reconnect(fake_github):
    from plugins.github import CONNECTOR

    fake_github.status = 401
    with pytest.raises(ReauthRequiredError, match="2026-09-01"):
        await CONNECTOR.sync(_account(), {"token": "t"}, {})


def test_enterprise_urls_and_settings():
    from plugins.github import CONNECTOR, graphql

    assert graphql.graphql_url({}) == "https://api.github.com/graphql"
    assert (
        graphql.graphql_url({"api_url": "https://ghe.test/api/v3"})
        == "https://ghe.test/api/graphql"
    )
    assert CONNECTOR.validate_settings("token", {}) == {"share_private_titles": False}
    with pytest.raises(ValueError, match="https"):
        CONNECTOR.validate_settings("token", {"api_url": "http://ghe.test"})


def test_write_scopes():
    from plugins.github import graphql

    assert graphql.write_scopes("repo, workflow, read:org") == ["repo", "workflow"]
    assert graphql.write_scopes(None) == [] and graphql.write_scopes("") == []


async def test_graphql_error_payload(monkeypatch):
    from plugins.github import graphql

    def handler(request):
        return httpx.Response(200, json={"errors": [{"message": "Resource not accessible"}]})

    real = httpx.AsyncClient
    monkeypatch.setattr(
        graphql.httpx,
        "AsyncClient",
        lambda **kw: real(transport=httpx.MockTransport(handler), **kw),
    )
    with pytest.raises(ConnectorError, match="Resource not accessible"):
        await graphql.fetch({}, "t")


# ── exposure + brief ─────────────────────────────────────────


def _row(item, account="GitHub", **kw):
    return {
        "id": item.external_id,
        "kind": "code",
        "account_name": account,
        "account_exposure": "standard",
        "account_share_private": False,
        "title": item.title,
        "direction": item.direction,
        "occurred_at": item.occurred_at,
        "flags": item.flags,
        **kw,
    }


async def _rows(fake_github, **kw):
    from plugins.github import CONNECTOR

    result = await CONNECTOR.sync(_account(), {"token": "t"}, {})
    return [_row(i, **kw) for i in result.items]


async def test_private_repos_are_counts_for_the_cloud(fake_github):
    rows = await _rows(fake_github)
    cloud = view_items(rows, CLOUD)
    assert all(c["repo"] != "logimax/payroll" for c in cloud["items"])
    assert cloud["withheld"] == {"GitHub (private repos)": 1}
    assert any(c["repo"] == "logimax/payroll" for c in view_items(rows, LOCAL)["items"])
    shared = view_items(await _rows(fake_github, account_share_private=True), CLOUD)
    payroll = next(c for c in shared["items"] if c["repo"] == "logimax/payroll")
    assert "url" not in payroll  # a private repo's link never goes to the cloud
    local_only = view_items(await _rows(fake_github, account_exposure=EXPOSURE_LOCAL_ONLY), CLOUD)
    assert local_only["items"] == [] and local_only["withheld"] == {"GitHub": 8}


async def test_brief_code_section(fake_github, monkeypatch):
    from life_graph.connectors.brief import render

    monkeypatch.setattr(settings, "user_timezone", "Asia/Kolkata")
    raw = {
        "today": [],
        "tomorrow_early": [],
        "waiting": [],
        "promises": [],
        "birthdays": [],
        "code": await _rows(fake_github),
        "people": {},
    }
    text = render(raw, CLOUD, NOW)["text"]
    assert "## Code" in text
    assert "- Review requested (1): life-graph#36 Contacts connector (teammate, 1d)" in text
    assert "Draft idea" not in text  # drafts are not waiting on anyone
    assert (
        "- Your PRs: life-graph#40 (dev agent) — changes requested · life-graph#35 — CI failing"
        " · life-graph#34 — approved, ready to merge · 1 waiting on reviewers"
    ) in text
    assert "- Assigned issues (1): pulse#12 Login loop" in text
    assert "payroll" not in text and "+1 in GitHub (private repos)" in text
    local = render(raw, LOCAL, NOW)["text"]
    assert "payroll#9 Secret payroll change" in local and "Review requested (2)" in local


def test_code_intent():
    from life_graph.connectors.chat_context import wants_code

    assert wants_code("anything waiting on me on GitHub?")
    assert wants_code("is CI green on my PRs")
    assert not wants_code("write a poem about rain")


def test_age_label_uses_created_time():
    from life_graph.connectors.brief import _age

    assert _age((NOW - timedelta(hours=30)).isoformat(), NOW) == "1d"
