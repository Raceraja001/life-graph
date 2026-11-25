"""Safety-rule and trust-override writes leave an audit_log row (Stage 0 report §7).

``AuditService.log_rule_change`` and ``log_trust_override`` existed but nothing
called them, so creating, changing or deleting a safety rule, seeding the
defaults, or overriding a trust score left no trace in ``audit_log``. Each of
those routes now writes exactly one row naming who did it — the server's view
of the caller (``resolver``), never the body — with ``actor_type`` operator.
The audit write is best effort, as for the kill switch: if it fails, the
change still stands.

Over real HTTP and Postgres, with an owner key and a plain service key
configured (the integration suite otherwise runs with auth off).
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from life_graph.config import settings
from life_graph.main import app
from tests.integration.conftest import skip_on_db_error

OWNER_KEY = "it-audit-owner-key-0123456789"
SERVICE_KEY = "it-audit-svc-key-9876543210"


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setattr(settings, "api_key", None)
    monkeypatch.setattr(settings, "service_api_keys", f"{SERVICE_KEY},{OWNER_KEY}")
    monkeypatch.setattr(settings, "owner_api_keys", OWNER_KEY)
    monkeypatch.setattr(settings, "approvals_require_owner", False)


@pytest.fixture
def tenant() -> str:
    return f"audit_rows_{uuid.uuid4().hex[:10]}"


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _as(key: str, tenant: str) -> dict:
    return {"Authorization": f"Bearer {key}", "X-Tenant-ID": tenant}


async def _rows(tenant: str, action_type: str) -> list:
    from life_graph.autonomy.models import AuditLogEntry
    from life_graph.storage.database import async_session

    async with async_session() as s:
        result = await s.execute(
            select(AuditLogEntry).where(
                AuditLogEntry.tenant_id == tenant, AuditLogEntry.action_type == action_type
            )
        )
        return list(result.scalars().all())


async def _create_rule(client: AsyncClient, tenant: str) -> str:
    resp = await client.post(
        "/api/v1/autonomy/safety/rules",
        headers=_as(OWNER_KEY, tenant),
        json={
            "action_name": f"audit_test_{uuid.uuid4().hex[:6]}",
            "action_pattern": "audit_test*",
            "risk_level": "moderate",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


def _by_owner(row) -> None:
    assert row.actor_type == "operator"
    assert row.actor_id == "owner"


@skip_on_db_error
async def test_creating_a_rule_writes_one_audit_row(client, tenant):
    rule_id = await _create_rule(client, tenant)

    rows = await _rows(tenant, "rule_change")
    assert len(rows) == 1
    row = rows[0]
    _by_owner(row)
    assert row.action_name == "rule_create"
    assert row.result == "success"
    details = row.classification_reasoning
    assert details["rule_id"] == rule_id
    assert details["old_value"] is None
    assert details["new_value"]["risk_level"] == "moderate"


@skip_on_db_error
async def test_updating_a_rule_writes_one_audit_row_with_before_and_after(client, tenant):
    rule_id = await _create_rule(client, tenant)
    resp = await client.patch(
        f"/api/v1/autonomy/safety/rules/{rule_id}",
        headers=_as(OWNER_KEY, tenant),
        json={"risk_level": "safe"},
    )
    assert resp.status_code == 200, resp.text

    rows = [r for r in await _rows(tenant, "rule_change") if r.action_name == "rule_update"]
    assert len(rows) == 1
    _by_owner(rows[0])
    details = rows[0].classification_reasoning
    assert details["rule_id"] == rule_id
    assert details["old_value"]["risk_level"] == "moderate"
    assert details["new_value"]["risk_level"] == "safe"


@skip_on_db_error
async def test_deleting_a_rule_writes_one_audit_row(client, tenant):
    rule_id = await _create_rule(client, tenant)
    resp = await client.delete(
        f"/api/v1/autonomy/safety/rules/{rule_id}", headers=_as(OWNER_KEY, tenant)
    )
    assert resp.status_code == 200, resp.text

    rows = [r for r in await _rows(tenant, "rule_change") if r.action_name == "rule_delete"]
    assert len(rows) == 1
    _by_owner(rows[0])
    details = rows[0].classification_reasoning
    assert details["rule_id"] == rule_id
    assert details["old_value"]["risk_level"] == "moderate"


@skip_on_db_error
async def test_seeding_the_defaults_writes_one_audit_row(client, tenant):
    resp = await client.post("/api/v1/autonomy/safety/seed", headers=_as(OWNER_KEY, tenant))
    assert resp.status_code == 201, resp.text
    seeded = {r["action_name"] for r in resp.json()["data"]}
    assert seeded

    rows = await _rows(tenant, "rule_change")
    assert len(rows) == 1
    _by_owner(rows[0])
    assert rows[0].action_name == "rule_seed"
    created = rows[0].classification_reasoning["new_value"]["created"]
    assert {c["action_name"] for c in created} == seeded


@skip_on_db_error
async def test_a_refused_rule_write_writes_no_audit_row(client, tenant):
    resp = await client.post(
        "/api/v1/autonomy/safety/rules",
        headers=_as(SERVICE_KEY, tenant),
        json={"action_name": "x", "action_pattern": "x*", "risk_level": "safe"},
    )
    assert resp.status_code == 403, resp.text
    assert await _rows(tenant, "rule_change") == []


@skip_on_db_error
async def test_overriding_trust_writes_one_audit_row_with_old_and_new_score(client, tenant):
    agent = f"agent-{uuid.uuid4().hex[:8]}"
    body = {"agent_id": agent, "action_type": "fix_lint", "score": 0.9, "reason": "first"}
    first = await client.post(
        "/api/v1/autonomy/trust/override", headers=_as(OWNER_KEY, tenant), json=body
    )
    assert first.status_code == 200, first.text

    rows = await _rows(tenant, "trust_override")
    assert len(rows) == 1
    row = rows[0]
    _by_owner(row)  # the owner who overrode, not the agent the score is about
    assert row.agent_id == agent
    assert row.result == "success"
    details = row.classification_reasoning
    assert details["old_score"] is None  # no score yet; the override created it
    assert details["new_score"] == 0.9
    assert details["action_type"] == "fix_lint"

    second = await client.post(
        "/api/v1/autonomy/trust/override",
        headers=_as(OWNER_KEY, tenant),
        json={**body, "score": 0.4, "reason": "second"},
    )
    assert second.status_code == 200, second.text
    rows = sorted(await _rows(tenant, "trust_override"), key=lambda r: r.created_at)
    assert len(rows) == 2
    assert rows[1].classification_reasoning["old_score"] == 0.9
    assert rows[1].classification_reasoning["new_score"] == 0.4


@skip_on_db_error
async def test_a_failed_audit_write_does_not_undo_the_change(client, tenant, monkeypatch):
    from life_graph.autonomy.safety import router as safety_router
    from life_graph.autonomy.trust import router as trust_router

    class _Broken:
        async def log_rule_change(self, **_kw):
            raise RuntimeError("audit store down")

        async def log_trust_override(self, **_kw):
            raise RuntimeError("audit store down")

    monkeypatch.setattr(safety_router, "get_audit_service", lambda: _Broken())
    monkeypatch.setattr(trust_router, "get_audit_service", lambda: _Broken())

    rule_id = await _create_rule(client, tenant)
    got = await client.get(
        f"/api/v1/autonomy/safety/rules/{rule_id}", headers=_as(OWNER_KEY, tenant)
    )
    assert got.status_code == 200, got.text

    agent = f"agent-{uuid.uuid4().hex[:8]}"
    ok = await client.post(
        "/api/v1/autonomy/trust/override",
        headers=_as(OWNER_KEY, tenant),
        json={"agent_id": agent, "action_type": "fix_lint", "score": 0.7, "reason": "x"},
    )
    assert ok.status_code == 200, ok.text
    scores = await client.get(
        f"/api/v1/autonomy/trust/scores?agent_id={agent}", headers=_as(OWNER_KEY, tenant)
    )
    assert [float(s["manual_override"]) for s in scores.json()["data"]] == [0.7]
