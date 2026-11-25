"""Making a prompt live is the owner's alone (Stage 0 report §7).

``/self-improving/prompt-versions/{id}/activate``, ``.../rollback`` and
``/self-improving/optimization-runs/{id}/review`` had no owner gate: any
service key could create a prompt version and make it the live prompt for a
task. Now each is ``owner_only`` (403 for a plain service key), writes one
``prompt_change`` audit_log row naming the server-derived caller, and the
review records ``reviewed_by`` from the server, not the old fixed "user".

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

OWNER_KEY = "it-selfimp-owner-key-0123456789"
SERVICE_KEY = "it-selfimp-svc-key-9876543210"


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setattr(settings, "api_key", None)
    monkeypatch.setattr(settings, "service_api_keys", f"{SERVICE_KEY},{OWNER_KEY}")
    monkeypatch.setattr(settings, "owner_api_keys", OWNER_KEY)
    monkeypatch.setattr(settings, "approvals_require_owner", False)


@pytest.fixture
def tenant() -> str:
    return f"selfimp_gate_{uuid.uuid4().hex[:10]}"


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _as(key: str, tenant: str) -> dict:
    return {"Authorization": f"Bearer {key}", "X-Tenant-ID": tenant}


async def _version(client: AsyncClient, tenant: str, task_type: str) -> str:
    # Creating a version stays open: a stored version is not live.
    resp = await client.post(
        "/api/v1/self-improving/prompt-versions",
        headers=_as(SERVICE_KEY, tenant),
        json={"task_type": task_type, "prompt_text": "Do the task: {input}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _active(tenant: str, task_type: str):
    from life_graph.runtime import get_prompt_version_service

    return await get_prompt_version_service().get_active(tenant, task_type)


async def _audit_rows(tenant: str) -> list:
    from life_graph.autonomy.models import AuditLogEntry
    from life_graph.storage.database import async_session

    async with async_session() as s:
        result = await s.execute(
            select(AuditLogEntry).where(
                AuditLogEntry.tenant_id == tenant, AuditLogEntry.action_type == "prompt_change"
            )
        )
        return list(result.scalars().all())


@pytest.mark.parametrize("action", ["activate", "rollback"])
@skip_on_db_error
async def test_only_the_owner_makes_a_prompt_version_live(client, tenant, action):
    task_type = f"gate_{action}"
    version_id = await _version(client, tenant, task_type)
    url = f"/api/v1/self-improving/prompt-versions/{version_id}/{action}"

    refused = await client.post(url, headers=_as(SERVICE_KEY, tenant))
    assert refused.status_code == 403, refused.text
    assert await _active(tenant, task_type) is None
    assert await _audit_rows(tenant) == []

    ok = await client.post(url, headers=_as(OWNER_KEY, tenant))
    assert ok.status_code == 200, ok.text
    assert str((await _active(tenant, task_type)).id) == version_id

    rows = await _audit_rows(tenant)
    assert len(rows) == 1
    row = rows[0]
    assert (row.actor_type, row.actor_id) == ("operator", "owner")
    assert row.action_name == f"prompt_{action}"
    assert row.classification_reasoning["version_id"] == version_id
    assert row.classification_reasoning["task_type"] == task_type


async def _needs_review_run(client: AsyncClient, tenant: str) -> uuid.UUID:
    from life_graph.self_improving.models import OptimizationRun
    from life_graph.storage.database import async_session

    suite = await client.post(
        "/api/v1/self-improving/eval-suites",
        headers=_as(OWNER_KEY, tenant),
        json={"name": "gate suite", "task_type": "gate_review"},
    )
    assert suite.status_code == 201, suite.text
    run_id = uuid.uuid4()
    async with async_session() as s:
        s.add(
            OptimizationRun(
                id=run_id,
                tenant_id=tenant,
                suite_id=uuid.UUID(suite.json()["data"]["id"]),
                task_type="gate_review",
                trigger_eval_run_id="gate-test",
                status="needs_review",
            )
        )
        await s.commit()
    return run_id


@skip_on_db_error
async def test_only_the_owner_reviews_an_optimization_run(client, tenant):
    from life_graph.self_improving.models import OptimizationRun
    from life_graph.storage.database import async_session

    run_id = await _needs_review_run(client, tenant)
    url = f"/api/v1/self-improving/optimization-runs/{run_id}/review"

    refused = await client.post(url, headers=_as(SERVICE_KEY, tenant), json={"decision": "reject"})
    assert refused.status_code == 403, refused.text
    async with async_session() as s:
        assert (await s.get(OptimizationRun, run_id)).status == "needs_review"

    ok = await client.post(url, headers=_as(OWNER_KEY, tenant), json={"decision": "reject"})
    assert ok.status_code == 200, ok.text
    async with async_session() as s:
        run = await s.get(OptimizationRun, run_id)
    assert run.status == "rejected"
    assert run.reviewed_by == "owner"  # the server's view, not a fixed "user"

    rows = await _audit_rows(tenant)
    assert len(rows) == 1
    assert (rows[0].actor_type, rows[0].actor_id) == ("operator", "owner")
    assert rows[0].action_name == "prompt_review_reject"
    assert rows[0].classification_reasoning["optimization_run_id"] == str(run_id)


@skip_on_db_error
async def test_any_caller_may_still_return_a_task_to_its_built_in_prompt(client, tenant):
    resp = await client.post(
        "/api/v1/self-improving/prompt-versions/deactivate?task_type=gate_deactivate",
        headers=_as(SERVICE_KEY, tenant),
    )
    assert resp.status_code == 200, resp.text
