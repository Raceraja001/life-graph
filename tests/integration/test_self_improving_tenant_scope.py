"""Self-improving: suites and eval runs stay in their tenant; optimizing is the owner's.

Two gaps found while fixing #364:

* ``POST /eval-suites/{id}/cases`` and ``.../cases/bulk`` and
  ``GET /eval-runs/{id}`` and ``.../failures`` never checked the tenant. Another
  tenant could add cases to your suite, which changes what the optimizer
  learns from, and read your runs' inputs and outputs. Now another tenant's id
  gets 404, the same as an id that does not exist.
* ``POST /optimize/{suite_id}`` was open to any service key, although it
  deploys its best candidate prompt when that clears the gate. Now it is
  owner only and writes one ``prompt_change`` audit row.

Over real HTTP and Postgres, with an owner key and a plain service key
configured. The optimizer itself is stubbed: it needs an LLM.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from life_graph.config import settings
from life_graph.main import app
from tests.integration.conftest import skip_on_db_error

OWNER_KEY = "it-sitenant-owner-key-0123456789"
SERVICE_KEY = "it-sitenant-svc-key-9876543210"


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setattr(settings, "api_key", None)
    monkeypatch.setattr(settings, "service_api_keys", f"{SERVICE_KEY},{OWNER_KEY}")
    monkeypatch.setattr(settings, "owner_api_keys", OWNER_KEY)
    monkeypatch.setattr(settings, "approvals_require_owner", False)


@pytest.fixture
def mine() -> str:
    return f"si_mine_{uuid.uuid4().hex[:10]}"


@pytest.fixture
def theirs() -> str:
    return f"si_theirs_{uuid.uuid4().hex[:10]}"


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _as(key: str, tenant: str) -> dict:
    return {"Authorization": f"Bearer {key}", "X-Tenant-ID": tenant}


async def _suite(client: AsyncClient, tenant: str) -> str:
    resp = await client.post(
        "/api/v1/self-improving/eval-suites",
        headers=_as(OWNER_KEY, tenant),
        json={"name": "tenant suite", "task_type": "tenant_check"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _case_count(suite_id: str) -> int:
    from life_graph.self_improving.models import EvalCase
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return await s.scalar(
            select(func.count()).select_from(EvalCase).where(EvalCase.suite_id == suite_id)
        )


CASE = {"input_text": "2+2?", "expected_output": "4"}
SECRET_OUTPUT = "private-output-of-my-run"


@skip_on_db_error
async def test_another_tenant_cannot_add_cases_to_my_suite(client, mine, theirs):
    suite_id = await _suite(client, mine)
    base = f"/api/v1/self-improving/eval-suites/{suite_id}/cases"

    one = await client.post(base, headers=_as(OWNER_KEY, theirs), json=CASE)
    assert one.status_code == 404, one.text
    bulk = await client.post(f"{base}/bulk", headers=_as(OWNER_KEY, theirs), json={"cases": [CASE]})
    assert bulk.status_code == 404, bulk.text
    assert await _case_count(suite_id) == 0

    ok = await client.post(base, headers=_as(OWNER_KEY, mine), json=CASE)
    assert ok.status_code == 201, ok.text
    ok_bulk = await client.post(
        f"{base}/bulk", headers=_as(OWNER_KEY, mine), json={"cases": [CASE, CASE]}
    )
    assert ok_bulk.status_code == 201, ok_bulk.text
    assert await _case_count(suite_id) == 3


async def _failed_run(client: AsyncClient, tenant: str) -> uuid.UUID:
    from life_graph.self_improving.models import EvalResult, EvalRun
    from life_graph.storage.database import async_session

    suite_id = await _suite(client, tenant)
    case = await client.post(
        f"/api/v1/self-improving/eval-suites/{suite_id}/cases",
        headers=_as(OWNER_KEY, tenant),
        json=CASE,
    )
    assert case.status_code == 201, case.text
    run_id = uuid.uuid4()
    async with async_session() as s:
        s.add(
            EvalRun(
                id=run_id,
                suite_id=uuid.UUID(suite_id),
                prompt_version_id="default",
                status="completed",
            )
        )
        await s.flush()
        s.add(
            EvalResult(
                run_id=run_id,
                case_id=uuid.UUID(case.json()["data"]["id"]),
                status="fail",
                actual_output=SECRET_OUTPUT,
                failure_type="wrong_answer",
            )
        )
        await s.commit()
    return run_id


@skip_on_db_error
async def test_another_tenant_cannot_read_my_eval_run(client, mine, theirs):
    run_id = await _failed_run(client, mine)
    for path in (f"/eval-runs/{run_id}", f"/eval-runs/{run_id}/failures"):
        url = f"/api/v1/self-improving{path}"
        other = await client.get(url, headers=_as(OWNER_KEY, theirs))
        assert other.status_code == 404, (path, other.text)
        assert SECRET_OUTPUT not in other.text  # nothing of the run leaks

        own = await client.get(url, headers=_as(OWNER_KEY, mine))
        assert own.status_code == 200, (path, own.text)

    failures = await client.get(
        f"/api/v1/self-improving/eval-runs/{run_id}/failures", headers=_as(OWNER_KEY, mine)
    )
    assert [f["count"] for f in failures.json()["data"]] == [1]


class _StubOptimizer:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.run_id = uuid.uuid4()

    async def optimize(self, tenant_id, suite_id):
        self.calls.append((tenant_id, suite_id))
        return {"status": "no_improvement", "optimization_run_id": self.run_id}


@pytest.fixture
def optimizer():
    from life_graph.runtime import get_optimizer_service

    stub = _StubOptimizer()
    app.dependency_overrides[get_optimizer_service] = lambda: stub
    yield stub
    app.dependency_overrides.pop(get_optimizer_service, None)


async def _prompt_rows(tenant: str) -> list:
    from life_graph.autonomy.models import AuditLogEntry
    from life_graph.storage.database import async_session

    async with async_session() as s:
        result = await s.execute(
            select(AuditLogEntry).where(
                AuditLogEntry.tenant_id == tenant, AuditLogEntry.action_type == "prompt_change"
            )
        )
        return list(result.scalars().all())


@skip_on_db_error
async def test_only_the_owner_runs_an_optimization(client, mine, optimizer):
    suite_id = await _suite(client, mine)
    url = f"/api/v1/self-improving/optimize/{suite_id}"

    refused = await client.post(url, headers=_as(SERVICE_KEY, mine))
    assert refused.status_code == 403, refused.text
    assert optimizer.calls == []
    assert await _prompt_rows(mine) == []

    ok = await client.post(url, headers=_as(OWNER_KEY, mine))
    assert ok.status_code == 202, ok.text
    assert optimizer.calls == [(mine, uuid.UUID(suite_id))]

    rows = await _prompt_rows(mine)
    assert len(rows) == 1
    row = rows[0]
    assert (row.actor_type, row.actor_id) == ("operator", "owner")
    assert row.action_name == "prompt_optimize"
    details = row.classification_reasoning
    assert details["suite_id"] == suite_id
    assert details["status"] == "no_improvement"
    assert details["optimization_run_id"] == str(optimizer.run_id)
