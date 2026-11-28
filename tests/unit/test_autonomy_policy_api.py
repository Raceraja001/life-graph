"""Autonomy policy API (/autonomy/policy) and the per-task review/risk routes.

In-process (httpx ASGITransport) with an in-memory session: no database.
Writes are owner-only; reads are tenant-scoped.
"""

from __future__ import annotations

import re
import uuid

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from life_graph import main
from life_graph.api import drivers as drivers_api
from life_graph.api.middleware import TenantMiddleware
from life_graph.autonomy.router import router as autonomy_router
from life_graph.config import settings
from life_graph.core.errors import DomainError
from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.db import AutonomyPolicy
from life_graph.storage.database import get_session
from tests.unit.fakes import FakeResult

OWNER_KEY = "owner-key-0123456789"
SERVICE_KEY = "svc-key-9876543210"
PROJECT = str(uuid.uuid4())


class _Store:
    """An in-memory autonomy_policies table, reached through SQL statements."""

    def __init__(self, tenant="raja"):
        self.tenant = tenant
        self.rows: dict[tuple[str, str], AutonomyPolicy] = {}
        self.projects = {(tenant, PROJECT)}
        self.names = {PROJECT: "race-app"}
        self.commits = 0

    def session(self):
        return _StoreSession(self)


class _StoreSession:
    def __init__(self, store: _Store):
        self.store = store

    @staticmethod
    def _sql(stmt) -> str:
        return str(stmt.compile(compile_kwargs={"literal_binds": True}))

    async def execute(self, stmt, *_a, **_k):
        sql = self._sql(stmt)
        tenant = re.search(r"tenant_id = '([^']+)'", sql)
        tenant = tenant.group(1) if tenant else None
        if sql.startswith("DELETE FROM autonomy_policies"):
            scope = re.search(r"scope = '([^']+)'", sql).group(1)
            gone = self.store.rows.pop((tenant, scope), None)
            return FakeResult([], rowcount=1 if gone else 0)
        if "count(" in sql:
            return FakeResult([0])
        if "FROM projects" in sql:
            ids = re.search(r"projects.id IN \(([^)]*)\)", sql)
            if ids:  # the names for GET /autonomy/policy's projects[]
                wanted = {str(uuid.UUID(v)) for v in re.findall(r"'([^']+)'", ids.group(1))}
                return FakeResult(
                    [
                        (pid, self.store.names.get(pid, "name"), True)
                        for (t, pid) in self.store.projects
                        if t == tenant and pid in wanted
                    ]
                )
            pid = re.search(r"projects.id = '([^']+)'", sql)
            key = str(uuid.UUID(pid.group(1))) if pid else None
            ok = pid and (tenant, key) in self.store.projects
            return FakeResult([(key, self.store.names.get(key, "name"))] if ok else [])
        if "FROM autonomy_policies" in sql:
            rows = [r for (t, _s), r in self.store.rows.items() if t == tenant]
            one = re.search(r"autonomy_policies.scope = '([^']+)'", sql)
            if one:
                rows = [r for r in rows if r.scope == one.group(1)]
            return FakeResult(rows)
        raise AssertionError(f"unexpected statement: {sql}")

    def add(self, obj):
        self.store.rows[(obj.tenant_id, obj.scope)] = obj

    async def commit(self):
        self.store.commits += 1


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setattr(settings, "api_key", None)
    monkeypatch.setattr(settings, "service_api_keys", f"{SERVICE_KEY},{OWNER_KEY}")
    monkeypatch.setattr(settings, "owner_api_keys", OWNER_KEY)


@pytest.fixture
def store():
    return _Store()


@pytest_asyncio.fixture
async def client(store):
    app = FastAPI()
    # The app's own error envelope (main.py), as served.
    app.add_exception_handler(StarletteHTTPException, main.http_exception_handler)
    app.add_exception_handler(DomainError, main.domain_error_handler)
    app.add_exception_handler(RequestValidationError, main.validation_exception_handler)
    app.add_middleware(TenantMiddleware)
    app.include_router(autonomy_router, prefix="/api/v1")
    app.include_router(drivers_api.router, prefix="/api/v1")

    async def _session():
        yield store.session()

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_current_tenant_id] = lambda: "raja"
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _as(key):
    return {"Authorization": f"Bearer {key}", "X-Tenant-ID": "raja"}


GLOBAL = {
    "conditions": {
        "max_changed_lines": 80,
        "max_files": 4,
        "paths_allowed": ["docs/*", "tests/*"],
        "paths_forbidden": ["*.env"],
        "require_verification_passed": True,
        "require_no_reviewer_objection": True,
        "risk_tolerance": "warnings",
    },
    "daily_auto_approval_cap": 5,
    "review_stages": [
        {"name": "security", "reviewer": "model:gemini/gemini-2.5-flash", "focus": "secrets"},
        {"name": "owner", "reviewer": "human", "focus": ""},
    ],
    "verify_fix_rounds": 2,
    "review_fix_rounds": 1,
}


async def test_get_with_no_policy_is_empty(client):
    r = await client.get("/api/v1/autonomy/policy", headers=_as(SERVICE_KEY))
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["global"] is None and data["projects"] == []
    assert data["auto_approvals_today"] == 0
    assert data["limits"]["max_fix_rounds"] == 3 and data["limits"]["max_review_stages"] == 4


async def test_put_global_needs_the_owner(client, store):
    r = await client.put("/api/v1/autonomy/policy", json=GLOBAL, headers=_as(SERVICE_KEY))
    assert r.status_code == 403 and "needs the owner" in r.json()["detail"]
    assert store.rows == {}


async def test_owner_puts_and_reads_the_global_policy(client, store):
    r = await client.put("/api/v1/autonomy/policy", json=GLOBAL, headers=_as(OWNER_KEY))
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    # Stored with every field; the run-health ones (Phase 3b part 2) default off.
    assert data["global"]["policy"] == {
        **GLOBAL,
        "max_nudges": 0,
        "max_stall_retries": 0,
        "wait_for_reset": False,
    }
    assert data["global"]["updated_by"] == "owner"  # the server's, not the body's
    assert store.rows[("raja", "global")].policy == {
        **GLOBAL,
        "max_nudges": 0,
        "max_stall_retries": 0,
        "wait_for_reset": False,
    }

    r = await client.get("/api/v1/autonomy/policy", headers=_as(SERVICE_KEY))
    assert r.json()["data"]["global"]["policy"]["daily_auto_approval_cap"] == 5


@pytest.mark.parametrize(
    "body",
    [
        {"verify_fix_rounds": 9},
        {"review_stages": [{"name": f"s{i}", "reviewer": "human"} for i in range(5)]},
        {"review_stages": [{"name": "x", "reviewer": "codex"}]},
        {"conditions": {"risk_tolerance": "yolo"}},
        {"daily_auto_approval_cap": -2},
    ],
)
async def test_invalid_policy_is_422(client, body):
    r = await client.put("/api/v1/autonomy/policy", json=body, headers=_as(OWNER_KEY))
    assert r.status_code == 422
    err = r.json()
    # The app-wide envelope (main.py), not FastAPI's bare list.
    assert err["error"]["code"] == "VALIDATION_ERROR"
    assert err["error"]["details"] and err["detail"] == err["error"]["message"]


async def test_limits_name_every_bound_and_the_reviewer_format(client):
    r = await client.get("/api/v1/autonomy/policy", headers=_as(SERVICE_KEY))
    limits = r.json()["data"]["limits"]
    # The original flat shape stays.
    assert limits["max_globs"] == 50
    assert limits["reviewers"] == ["human", "pr_agent", "model:<model id>"]
    assert limits["reviewer_format"] == {
        "kinds": ["human", "pr_agent", "model"],
        "model_prefix": "model:",
        "max_length": 120,
    }
    assert limits["risk_tolerances"] == ["any", "warnings", "none"]
    b = limits["bounds"]
    assert b["conditions.max_changed_lines"] == {"min": 0, "max": 100_000}
    assert b["conditions.max_files"] == {"min": 0, "max": 10_000}
    assert b["conditions.paths_allowed"] == {"max_items": 50, "item_max_length": 200}
    assert b["daily_auto_approval_cap"] == {"min": 0, "max": 1000}
    assert b["review_stages"] == {"max_items": 4}
    assert b["review_stages[].name"] == {"min_length": 1, "max_length": 60}
    assert b["review_stages[].focus"] == {"max_length": 2000}
    assert b["verify_fix_rounds"] == b["review_fix_rounds"] == {"min": 0, "max": 3}


def _stage(**kw):
    return {"name": "s", "reviewer": "human", "focus": "", **kw}


@pytest.mark.parametrize(
    ("at_limit", "over"),
    [
        ({"conditions": {"max_changed_lines": 100_000}}, {"conditions": {"max_changed_lines": 100_001}}),
        ({"conditions": {"max_files": 10_000}}, {"conditions": {"max_files": 10_001}}),
        ({"conditions": {"paths_allowed": [f"a{i}" for i in range(50)]}},
         {"conditions": {"paths_allowed": [f"a{i}" for i in range(51)]}}),
        ({"conditions": {"paths_forbidden": ["x" * 200]}},
         {"conditions": {"paths_forbidden": ["x" * 201]}}),
        ({"daily_auto_approval_cap": 1000}, {"daily_auto_approval_cap": 1001}),
        ({"review_stages": [_stage(name="n" * 60)]}, {"review_stages": [_stage(name="n" * 61)]}),
        ({"review_stages": [_stage(focus="f" * 2000)]},
         {"review_stages": [_stage(focus="f" * 2001)]}),
        ({"review_stages": [_stage(reviewer="model:" + "m" * 114)]},
         {"review_stages": [_stage(reviewer="model:" + "m" * 115)]}),
        ({"review_fix_rounds": 3}, {"review_fix_rounds": 4}),
    ],
)  # fmt: skip
async def test_limits_are_the_bounds_the_models_enforce(client, at_limit, over):
    r = await client.put("/api/v1/autonomy/policy", json=at_limit, headers=_as(OWNER_KEY))
    assert r.status_code == 200, r.text
    r = await client.put("/api/v1/autonomy/policy", json=over, headers=_as(OWNER_KEY))
    assert r.status_code == 422


async def test_a_known_project_without_an_override_is_200(client):
    await client.put("/api/v1/autonomy/policy", json=GLOBAL, headers=_as(OWNER_KEY))
    r = await client.get(f"/api/v1/autonomy/policy/projects/{PROJECT}", headers=_as(SERVICE_KEY))
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["override"] is None and data["policy"] is None
    assert data["has_override"] is False and data["name"] == "race-app"
    assert data["effective"]["sources"] == ["global"]
    assert data["effective"]["daily_auto_approval_cap"] == 5


async def test_a_project_row_for_a_gone_project_is_listed_inactive(client, store):
    gone = str(uuid.uuid4())
    store.rows[("raja", gone)] = AutonomyPolicy(tenant_id="raja", scope=gone, policy={})
    r = await client.get("/api/v1/autonomy/policy", headers=_as(SERVICE_KEY))
    (row,) = r.json()["data"]["projects"]
    assert row["project_id"] == gone and row["name"] is None and row["active"] is False


async def test_project_policy_roundtrip_and_effective(client, store):
    await client.put("/api/v1/autonomy/policy", json=GLOBAL, headers=_as(OWNER_KEY))
    body = {"conditions": {"max_files": 2}, "verify_fix_rounds": 0, "review_stages": None}
    r = await client.put(
        f"/api/v1/autonomy/policy/projects/{PROJECT}", json=body, headers=_as(SERVICE_KEY)
    )
    assert r.status_code == 403
    r = await client.put(
        f"/api/v1/autonomy/policy/projects/{PROJECT}", json=body, headers=_as(OWNER_KEY)
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["project_id"] == PROJECT
    assert data["policy"]["policy"]["conditions"]["max_files"] == 2
    eff = data["effective"]
    assert eff["sources"] == ["global", "project"]
    assert [c["source"] for c in eff["conditions"]] == ["global", "project"]
    assert eff["verify_fix_rounds"] == 0 and eff["review_fix_rounds"] == 1
    assert [s["name"] for s in eff["review_stages"]] == ["security", "owner"]
    assert eff["human_stage"] is True and eff["daily_auto_approval_cap"] == 5

    assert data["name"] == "race-app" and data["has_override"] is True
    assert data["override"] == data["policy"]

    r = await client.get("/api/v1/autonomy/policy", headers=_as(SERVICE_KEY))
    (row,) = r.json()["data"]["projects"]
    assert row["project_id"] == PROJECT and row["name"] == "race-app"
    assert row["active"] is True and row["override"] is True
    assert row["policy"]["conditions"]["max_files"] == 2

    r = await client.delete(f"/api/v1/autonomy/policy/projects/{PROJECT}", headers=_as(OWNER_KEY))
    assert r.json()["data"] == {"project_id": PROJECT, "removed": True}
    assert ("raja", PROJECT) not in store.rows


async def test_project_policy_rejects_a_cap_and_unknown_projects(client):
    r = await client.put(
        f"/api/v1/autonomy/policy/projects/{PROJECT}",
        json={"daily_auto_approval_cap": 1},
        headers=_as(OWNER_KEY),
    )
    assert r.status_code == 422
    other = str(uuid.uuid4())
    for method in ("get", "delete"):
        r = await getattr(client, method)(
            f"/api/v1/autonomy/policy/projects/{other}", headers=_as(OWNER_KEY)
        )
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "PROJECT_NOT_FOUND"
        assert r.json()["detail"] == "Project not found"
    r = await client.put(
        f"/api/v1/autonomy/policy/projects/{other}", json={}, headers=_as(OWNER_KEY)
    )
    assert r.status_code == 404 and r.json()["error"]["code"] == "PROJECT_NOT_FOUND"
    r = await client.get("/api/v1/autonomy/policy/projects/not-a-uuid", headers=_as(OWNER_KEY))
    assert r.status_code == 404 and r.json()["error"]["code"] == "PROJECT_NOT_FOUND"


async def test_delete_global_is_owner_only(client, store):
    await client.put("/api/v1/autonomy/policy", json={}, headers=_as(OWNER_KEY))
    r = await client.delete("/api/v1/autonomy/policy", headers=_as(SERVICE_KEY))
    assert r.status_code == 403 and ("raja", "global") in store.rows
    r = await client.delete("/api/v1/autonomy/policy", headers=_as(OWNER_KEY))
    assert r.json()["data"] == {"removed": True} and store.rows == {}


async def test_reads_are_tenant_scoped(client, store):
    store.rows[("other", "global")] = AutonomyPolicy(
        tenant_id="other", scope="global", policy={"daily_auto_approval_cap": 0}
    )
    r = await client.get("/api/v1/autonomy/policy", headers=_as(SERVICE_KEY))
    assert r.json()["data"]["global"] is None


# ── per-task review stages and risk report ───────────────────


class _NoSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        return False


def _task(monkeypatch, data):
    async def _get(_session, tenant_id, task_id):
        assert tenant_id == "raja"
        return data

    monkeypatch.setattr(drivers_api, "async_session", lambda: _NoSession())
    monkeypatch.setattr(drivers_api._dev_tasks, "get_dev_task", _get)


STAGES = [
    {"index": 0, "name": "sec", "reviewer": "model:m", "verdict": "objection", "fix_round": 0,
     "concern": "x", "focus": "", "note": None, "at": "2026-11-27T00:00:00+00:00"},
    {"index": 0, "name": "sec", "reviewer": "model:m", "verdict": "no_objection", "fix_round": 1,
     "concern": None, "focus": "", "note": None, "at": "2026-11-27T00:01:00+00:00"},
]  # fmt: skip


async def test_task_review_stages(client, monkeypatch):
    tid = str(uuid.uuid4())
    _task(monkeypatch, {"id": tid, "review_stages": STAGES})
    r = await client.get(
        f"/api/v1/kernel/drivers/tasks/{tid}/review-stages", headers=_as(SERVICE_KEY)
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["results"] == STAGES
    assert data["latest"] == [
        {"index": 0, "name": "sec", "reviewer": "model:m", "verdict": "no_objection",
         "fix_round": 1}
    ]  # fmt: skip


async def test_task_risk(client, monkeypatch):
    tid = str(uuid.uuid4())
    report = {"version": 1, "complete": True, "block": 1, "warn": 0, "files": 1, "findings": [
        {"severity": "block", "rule": "high_entropy_string", "file": "a.py", "line": 3,
         "detail": "32-char string, 4.6 bits/char"}], "truncated": False,
        "generated_at": "2026-11-27T00:00:00+00:00"}  # fmt: skip
    _task(monkeypatch, {"id": tid, "risk_report": report})
    r = await client.get(f"/api/v1/kernel/drivers/tasks/{tid}/risk", headers=_as(SERVICE_KEY))
    assert r.status_code == 200 and r.json()["data"] == {"task_id": tid, **report}


@pytest.mark.parametrize("data", [None, {"id": "x"}])
@pytest.mark.parametrize("route", ["review-stages", "risk"])
async def test_task_routes_404(client, monkeypatch, data, route):
    tid = str(uuid.uuid4())
    _task(monkeypatch, data)
    r = await client.get(f"/api/v1/kernel/drivers/tasks/{tid}/{route}", headers=_as(SERVICE_KEY))
    assert r.status_code == 404
    r = await client.get(f"/api/v1/kernel/drivers/tasks/nope/{route}", headers=_as(SERVICE_KEY))
    assert r.status_code == 404


async def test_get_dev_task_returns_stages_and_risk():
    from datetime import UTC, datetime

    from life_graph.models.db import AgentTask
    from life_graph.services.dev import tasks as dev_tasks
    from tests.unit.fakes import FakeSession

    pk = uuid.uuid4()
    task = AgentTask(
        id=pk,
        tenant_id="raja",
        title="t",
        instructions="i",
        task_type="code",
        status="completed",
        properties={"kind": dev_tasks.KIND, "review_stages": STAGES, "risk_report": {"block": 0}},
        created_at=datetime.now(UTC),
    )
    session = FakeSession(None, objects={(AgentTask, pk): task})
    data = await dev_tasks.get_dev_task(session, "raja", str(pk))
    assert data["review_stages"] == STAGES and data["risk_report"] == {"block": 0}
    assert await dev_tasks.get_dev_task(session, "other", str(pk)) is None
