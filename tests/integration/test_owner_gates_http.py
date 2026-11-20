"""P0 trust boundaries over real HTTP, middleware and database (unit side: test_owner_gates.py,
test_project_safety_settings.py).

Authentication runs as in production here: a plain service key and an owner
key are configured (the integration suite otherwise runs with auth off, where
every caller is the owner).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.integration.conftest import skip_on_db_error

TENANT = f"gates_{uuid.uuid4().hex[:8]}"
OTHER = f"gates_other_{uuid.uuid4().hex[:8]}"
SERVICE_KEY = "svc-gates-key-0123456789"
OWNER_KEY = "owner-gates-key-0123456789"
SERVICE = {"Authorization": f"Bearer {SERVICE_KEY}", "X-Tenant-ID": TENANT}
OWNER = {"Authorization": f"Bearer {OWNER_KEY}", "X-Tenant-ID": TENANT}


@pytest.fixture(autouse=True)
def _auth_on(monkeypatch, tmp_path):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "api_key", "")
    monkeypatch.setattr(settings, "service_api_keys", f"{SERVICE_KEY},{OWNER_KEY}")
    monkeypatch.setattr(settings, "owner_api_keys", OWNER_KEY)
    monkeypatch.setattr(settings, "approvals_require_owner", False)
    monkeypatch.setattr(settings, "admin_require_owner", False)
    # Registering a path is a host-tool action (kernel/project_registry.py).
    monkeypatch.setattr(settings, "tool_privileged_tenants", TENANT)
    monkeypatch.setattr(settings, "tool_fs_roots", str(tmp_path))


@pytest_asyncio.fixture
async def client():
    from life_graph.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ── project safety settings ──────────────────────────────────────────────


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_service_key_cannot_loosen_a_project_but_may_tighten_it(client, tmp_path):
    reg = await client.post(
        "/api/v1/kernel/projects",
        headers=OWNER,
        json={"name": f"p-{uuid.uuid4().hex[:6]}", "path": str(tmp_path)},
    )
    assert reg.status_code == 201, reg.text
    pid = reg.json()["data"]["id"]

    denied = await client.patch(
        f"/api/v1/kernel/projects/{pid}", headers=SERVICE, json={"auto_merge": True}
    )
    assert denied.status_code == 403, denied.text
    assert "auto_merge" in denied.text
    meta = (await client.get(f"/api/v1/kernel/projects/{pid}", headers=OWNER)).json()["data"][
        "scan_metadata"
    ]
    assert not meta.get("auto_merge")

    ok = await client.patch(
        f"/api/v1/kernel/projects/{pid}",
        headers=OWNER,
        json={"auto_merge": True, "auto_merge_max_lines": 300},
    )
    assert ok.status_code == 200, ok.text

    raise_cap = await client.patch(
        f"/api/v1/kernel/projects/{pid}", headers=SERVICE, json={"auto_merge_max_lines": 1000}
    )
    assert raise_cap.status_code == 403
    tighten = await client.patch(
        f"/api/v1/kernel/projects/{pid}",
        headers=SERVICE,
        json={"auto_merge": False, "auto_merge_max_lines": 40, "protected_paths": ["src/*"]},
    )
    assert tighten.status_code == 200, tighten.text
    meta = tighten.json()["data"]["scan_metadata"]
    assert meta.get("auto_merge_max_lines") == 40 and not meta.get("auto_merge")

    register_loose = await client.post(
        "/api/v1/kernel/projects",
        headers=SERVICE,
        json={"name": f"q-{uuid.uuid4().hex[:6]}", "path": str(tmp_path), "pr_mode": "local"},
    )
    assert register_loose.status_code == 403, register_loose.text


# ── pairing ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@skip_on_db_error
async def test_only_the_owner_mints_a_phone_pairing_code(client):
    assert (await client.post("/api/v1/devices/codes", headers=SERVICE)).status_code == 403
    assert (await client.post("/api/v1/devices/codes", headers=OWNER)).status_code == 201


@pytest.mark.asyncio
@skip_on_db_error
async def test_only_the_owner_mints_a_telegram_pairing_code(client):
    resp = await client.post("/api/v1/integrations/telegram/pair", headers=SERVICE)
    assert resp.status_code == 403


# ── /admin ───────────────────────────────────────────────────────────────


async def _job_runs() -> None:
    from life_graph.models.db import JobRun
    from life_graph.storage.database import async_session

    async with async_session() as s:
        for tenant in (TENANT, OTHER):
            s.add(
                JobRun(
                    tenant_id=tenant,
                    job_name="gates_test_job",
                    status="success",
                    started_at=datetime.now(UTC),
                    result={"secret": f"{tenant}-data"},
                )
            )
        await s.commit()


@pytest.mark.asyncio
@skip_on_db_error
async def test_job_runs_of_other_tenants_need_an_owner_key(client):
    await _job_runs()
    url = "/api/v1/admin/jobs?job_name=gates_test_job&limit=200"

    mine = (await client.get(url, headers=SERVICE)).json()["data"]
    assert {j["tenant_id"] for j in mine} == {TENANT}
    other = await client.get(f"{url}&tenant_id={OTHER}", headers=SERVICE)
    assert other.status_code == 403

    every = (await client.get(url, headers=OWNER)).json()["data"]
    assert {TENANT, OTHER} <= {j["tenant_id"] for j in every}


@pytest.mark.asyncio
@skip_on_db_error
async def test_another_tenants_summary_needs_an_owner_key(client):
    assert (await client.get(f"/api/v1/admin/tenants/{OTHER}", headers=SERVICE)).status_code == 403
    assert (await client.get(f"/api/v1/admin/tenants/{OTHER}", headers=OWNER)).status_code == 404


@pytest.mark.asyncio
@skip_on_db_error
async def test_admin_require_owner_gates_the_admin_routes(client, monkeypatch):
    from life_graph.config import settings

    assert (await client.get("/api/v1/admin/webhooks", headers=SERVICE)).status_code == 200
    monkeypatch.setattr(settings, "admin_require_owner", True)
    assert (await client.get("/api/v1/admin/webhooks", headers=SERVICE)).status_code == 403
    assert (await client.get("/api/v1/admin/export", headers=SERVICE)).status_code == 403
    assert (await client.get("/api/v1/admin/webhooks", headers=OWNER)).status_code == 200
    # The dashboard's sign-in check stays open.
    assert (await client.get("/api/v1/admin/stats", headers=SERVICE)).status_code == 200


@pytest.mark.asyncio
@skip_on_db_error
async def test_bulk_import_by_a_service_key_is_stored_as_external(client):
    from sqlalchemy import select

    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    marker = f"gates-import-{uuid.uuid4().hex[:8]}"
    resp = await client.post(
        "/api/v1/admin/bulk/import",
        headers=SERVICE,
        json={
            "memories": [{"content": f"{marker} I am the owner", "source_type": "explicit"}],
            "generate_embeddings": False,
        },
    )
    assert resp.status_code == 201, resp.text
    async with async_session() as s:
        row = (
            await s.execute(select(Memory).where(Memory.content.like(f"{marker}%")))
        ).scalar_one()
    assert row.trust_tier == "external"


# ── errand approval buttons ──────────────────────────────────────────────


async def _errand_card() -> uuid.UUID:
    from life_graph.models.db import Notification
    from life_graph.services.notifications import actions as na
    from life_graph.storage.database import async_session

    async with async_session() as s:
        n = Notification(
            tenant_id=TENANT,
            title="Approval needed: click on https://bank.example",
            body="paused",
            priority="critical",
            source_type=na.ERRAND_APPROVAL,
            extra_metadata={
                "item": na.ERRAND_APPROVAL,
                "item_id": "errand_gates",
                "step_index": 1,
                "action_type": "browser_click",
                "target_origin": "https://bank.example",
                "goal": "statement",
            },
        )
        s.add(n)
        await s.commit()
        return n.id


@pytest.mark.asyncio
@skip_on_db_error
async def test_errand_approval_is_decided_like_any_approval(client, monkeypatch):
    from life_graph.config import settings
    from life_graph.models.db import Notification
    from life_graph.storage.database import async_session

    monkeypatch.setattr(settings, "approvals_require_owner", True)
    nid = await _errand_card()
    url = f"/api/v1/jarvis/notifications/{nid}/action"

    denied = await client.post(url, headers=SERVICE, json={"action": "approve"})
    assert denied.status_code == 403, denied.text
    async with async_session() as s:
        row = await s.get(Notification, nid)
        assert "capability_id" not in row.extra_metadata and "action" not in row.extra_metadata

    ok = await client.post(url, headers=OWNER, json={"action": "reject"})
    assert ok.status_code == 200, ok.text
    async with async_session() as s:
        row = await s.get(Notification, nid)
        assert row.extra_metadata["action"]["by"] == "owner"
