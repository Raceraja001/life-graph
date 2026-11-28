"""/kernel/agent-accounts without a database: owner gates, write-only secret, shapes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from life_graph.api import agent_accounts as api
from life_graph.models.agent_accounts import AgentAccount, AgentAccountLimit
from life_graph.services.agent_accounts import service

NOW = datetime(2026, 11, 27, 9, 0, tzinfo=UTC)


def _row(**kw) -> AgentAccount:
    return AgentAccount(
        id=kw.pop("id", uuid.uuid4()),
        tenant_id="t1",
        driver=kw.pop("driver", "codex"),
        name=kw.pop("name", "Codex · personal"),
        kind=kw.pop("kind", "subscription"),
        enabled=True,
        priority=100,
        properties={},
        home_dir="/private/home/dir",
        created_at=NOW,
        updated_at=NOW,
        **kw,
    )


class _Session:
    commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def commit(self):
        _Session.commits += 1


@pytest.fixture
def owner(monkeypatch):
    """Who the caller is: flip ``owner['is']`` to test the 403s."""
    state = {"is": True}

    def owner_only(request, what):
        if not state["is"]:
            raise HTTPException(403, f"{what} needs the owner")

    monkeypatch.setattr(api, "owner_only", owner_only)
    monkeypatch.setattr(api, "async_session", _Session)
    monkeypatch.setattr(api, "get_current_tenant_id", lambda: "t1")
    return state


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(api.router)
    return TestClient(app)


def test_create_takes_no_secret_and_returns_none(client, owner, monkeypatch):
    seen = {}

    async def create_account(session, tenant, **kw):
        seen.update(kw, tenant=tenant)
        return _row(kind=kw["kind"], name=kw["name"])

    monkeypatch.setattr(service, "create_account", create_account)
    body = {"driver": "codex", "name": "Codex · work", "kind": "api_key", "identity": "a@b.co"}
    resp = client.post("/kernel/agent-accounts", json=body)
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["kind"] == "api_key" and data["has_secret"] is False
    assert "home_dir" not in data and "/private/home/dir" not in resp.text
    assert seen["tenant"] == "t1" and seen["identity_value"] == "a@b.co"

    # A secret in the create body is refused outright, not silently dropped.
    leaky = client.post("/kernel/agent-accounts", json={**body, "api_key": "sk-x"})
    assert leaky.status_code == 422


def test_writes_are_owner_only(client, owner, monkeypatch):
    owner["is"] = False
    rid = str(uuid.uuid4())
    calls = [
        (
            "post",
            "/kernel/agent-accounts",
            {"driver": "codex", "name": "x", "kind": "subscription"},
        ),
        ("patch", f"/kernel/agent-accounts/{rid}", {"name": "y"}),
        ("delete", f"/kernel/agent-accounts/{rid}", None),
        ("put", f"/kernel/agent-accounts/{rid}/secret", {"value": "sk-x"}),
        ("delete", f"/kernel/agent-accounts/{rid}/secret", None),
        ("put", "/kernel/agent-accounts/pool/codex", {"order": [rid]}),
        ("post", f"/kernel/agent-accounts/{rid}/enable", None),
        ("post", f"/kernel/agent-accounts/{rid}/disable", None),
        ("post", f"/kernel/agent-accounts/{rid}/cooldown/reset", None),
        ("get", f"/kernel/agent-accounts/{rid}/home", None),
    ]
    for method, path, body in calls:
        resp = client.request(method, path, json=body)
        assert resp.status_code == 403, (method, path, resp.status_code)


def test_secret_is_write_only(client, owner, monkeypatch):
    row = _row(kind="api_key")

    async def set_secret(session, tenant, account_id, value):
        assert value == "sk-live-key-123"
        row.secret_ref, row.secret_set_at = uuid.uuid4(), NOW
        return row

    monkeypatch.setattr(service, "set_secret", set_secret)
    resp = client.put(f"/kernel/agent-accounts/{row.id}/secret", json={"value": "sk-live-key-123"})
    assert resp.status_code == 200
    assert resp.json()["data"]["has_secret"] is True
    assert "sk-live-key-123" not in resp.text and str(row.secret_ref) not in resp.text


def test_reads_carry_no_paths_and_errors_map(client, owner, monkeypatch):
    row = _row()

    async def list_accounts(session, tenant, driver=None):
        return [row]

    async def get_account(session, tenant, account_id):
        if account_id != str(row.id):
            raise service.AccountNotFoundError("account not found")
        return row

    monkeypatch.setattr(service, "list_accounts", list_accounts)
    monkeypatch.setattr(service, "get_account", get_account)
    owner["is"] = False  # reads need only the tenant
    listed = client.get("/kernel/agent-accounts?driver=codex")
    assert listed.status_code == 200 and "/private/home/dir" not in listed.text
    assert client.get(f"/kernel/agent-accounts/{uuid.uuid4()}").status_code == 404
    assert client.get("/kernel/agent-accounts?driver=aider").status_code == 422

    owner["is"] = True
    home = client.get(f"/kernel/agent-accounts/{row.id}/home").json()["data"]
    assert home["home_dir"] == "/private/home/dir"
    from life_graph.services.agent_accounts import homes

    assert home["home_root"] == str(homes.root()) and Path(home["home_root"]).is_absolute()
    assert home["env"] == {"CODEX_HOME": "/private/home/dir"}
    assert home["login_command"] == ["codex", "login"]


def test_conflict_and_validation_errors(client, owner, monkeypatch):
    async def conflict(session, tenant, **kw):
        raise service.AccountConflictError("another codex account already has this name")

    monkeypatch.setattr(service, "create_account", conflict)
    body = {"driver": "codex", "name": "x", "kind": "subscription"}
    assert client.post("/kernel/agent-accounts", json=body).status_code == 409

    from life_graph.services.agent_accounts.catalog import AccountError

    async def bad(session, tenant, **kw):
        raise AccountError("codex supports ['subscription', 'api_key'], not 'vertex'")

    monkeypatch.setattr(service, "create_account", bad)
    resp = client.post("/kernel/agent-accounts", json={**body, "kind": "vertex"})
    assert resp.status_code == 400 and "vertex" in resp.text


def test_limits_shape_and_refresh_rules(client, owner, monkeypatch):
    row = _row(driver="claude_code")
    win = AgentAccountLimit(
        tenant_id="t1",
        account_id=row.id,
        window="five_hour",
        used_percent=44.0,
        window_minutes=None,
        resets_at=NOW,
        status="allowed",
        source="run",
        observed_at=NOW,
    )

    async def get_account(session, tenant, account_id):
        return row

    async def get_limits(session, tenant, account_id):
        return [win]

    monkeypatch.setattr(service, "get_account", get_account)
    monkeypatch.setattr(service, "get_limits", get_limits)
    data = client.get(f"/kernel/agent-accounts/{row.id}/limits").json()["data"]
    assert data["windows"][0] == {
        "window": "five_hour",
        "used_percent": 44.0,
        "window_minutes": None,
        "resets_at": "2026-11-27T09:00:00Z",
        "status": "allowed",
        "source": "run",
        "observed_at": "2026-11-27T09:00:00Z",
    }
    # Claude is never polled (U4): refresh says so instead of probing.
    refreshed = client.get(f"/kernel/agent-accounts/{row.id}/limits?refresh=true").json()["data"]
    assert refreshed["refresh"]["kind"] == "unavailable"
    owner["is"] = False
    assert client.get(f"/kernel/agent-accounts/{row.id}/limits?refresh=true").status_code == 403


def test_codex_refresh_is_off_by_default(client, owner, monkeypatch):
    row = _row()

    async def get_account(session, tenant, account_id):
        return row

    async def get_limits(session, tenant, account_id):
        return []

    monkeypatch.setattr(service, "get_account", get_account)
    monkeypatch.setattr(service, "get_limits", get_limits)
    data = client.get(f"/kernel/agent-accounts/{row.id}/limits?refresh=true").json()["data"]
    assert "probe_enabled is off" in data["refresh"]["reason"]
