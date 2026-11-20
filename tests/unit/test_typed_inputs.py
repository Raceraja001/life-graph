"""API inputs are typed and bounded (audit M10).

- POST /internal/sync/analytics took a bare dict: any importance, any size,
  written straight to *active* memories. It now takes AnalyticsBatch.
- Its key was compared with ``!=`` against a default of "" — an empty header
  matched an unconfigured key. It now refuses when no key is configured and
  compares in constant time.
- Agent-task status and priority were free strings, and timeout/max_retries
  unbounded; the PATCH handler's service setattr'd any key it was given.
- CorrectionCreate.kind was a free string.
"""

from __future__ import annotations

import time
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from pydantic import ValidationError

from life_graph.api import middleware
from life_graph.config import settings
from life_graph.main import app
from life_graph.models.schemas import (
    ANALYTICS_MAX_ITEMS,
    AgentTaskCreate,
    AgentTaskUpdate,
    AnalyticsBatch,
    AnalyticsItem,
    CorrectionCreate,
)

TENANT = "typed-inputs"
KEY = "k-typed-inputs-test"


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setitem(middleware._tenant_status_cache, TENANT, (time.monotonic() + 3600, None))
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", headers={"X-Tenant-ID": TENANT}
    ) as http:
        yield http
    app.dependency_overrides.clear()


@pytest.fixture
def sync_svc():
    from life_graph.api.dependencies import get_sync_service

    svc = MagicMock()
    svc.receive_analytics = AsyncMock(side_effect=AssertionError("must not be reached"))
    app.dependency_overrides[get_sync_service] = lambda: svc
    return svc


# ── analytics payload ──────────────────────────────────────


def test_analytics_item_bounds():
    AnalyticsItem(content="ok", importance=1.0)
    with pytest.raises(ValidationError):
        AnalyticsItem(content="x", importance=5)
    with pytest.raises(ValidationError):
        AnalyticsItem(content="x", importance=-0.1)
    with pytest.raises(ValidationError):
        AnalyticsItem(content="")
    with pytest.raises(ValidationError):
        AnalyticsItem(content="x", tags=["t" * 65])
    with pytest.raises(ValidationError):
        AnalyticsItem(content="x", properties={"blob": "y" * 20_000})
    with pytest.raises(ValidationError):
        AnalyticsBatch(items=[{"content": "x"}] * (ANALYTICS_MAX_ITEMS + 1))


def test_analytics_keeps_the_old_field_names_and_defaults():
    """The dict the endpoint used to read: content, source, importance, properties, tags."""
    batch = AnalyticsBatch.model_validate(
        {"items": [{"content": "yield up", "tags": ["farm"], "extra": "ignored"}], "batch": 7}
    )
    item = batch.items[0]
    assert (item.source, item.importance, item.properties) == ("uzhavu", 0.5, {})
    assert AnalyticsBatch.model_validate({}).items == []


async def test_analytics_route_rejects_out_of_range_importance(client, monkeypatch, sync_svc):
    monkeypatch.setattr(settings, "internal_api_key", KEY)
    response = await client.post(
        "/api/v1/internal/sync/analytics",
        json={"items": [{"content": "x", "importance": 5}]},
        headers={"X-Internal-API-Key": KEY},
    )

    assert response.status_code == 422, response.text
    sync_svc.receive_analytics.assert_not_called()


# ── internal key ───────────────────────────────────────────


async def test_unconfigured_internal_key_refuses_an_empty_header(client, monkeypatch, sync_svc):
    monkeypatch.setattr(settings, "internal_api_key", "")
    response = await client.post(
        "/api/v1/internal/sync/analytics", json={"items": []}, headers={"X-Internal-API-Key": ""}
    )

    assert response.status_code == 403, response.text
    sync_svc.receive_analytics.assert_not_called()


async def test_wrong_internal_key_is_refused(client, monkeypatch, sync_svc):
    monkeypatch.setattr(settings, "internal_api_key", KEY)
    response = await client.post(
        "/api/v1/internal/sync/analytics",
        json={"items": []},
        headers={"X-Internal-API-Key": KEY + "x"},
    )

    assert response.status_code == 403


async def test_right_internal_key_reaches_the_service(client, monkeypatch, sync_svc):
    from life_graph.models.db import CrossSystemSync

    monkeypatch.setattr(settings, "internal_api_key", KEY)
    now = __import__("datetime").datetime.now(__import__("datetime").UTC)
    record = CrossSystemSync(
        id=uuid.uuid4(),
        tenant_id=TENANT,
        direction="inbound",
        sync_type="analytics",
        target_system="uzhavu",
        status="completed",
        records_sent=1,
        records_synced=1,
        records_failed=0,
        retry_count=0,
        created_at=now,
    )
    sync_svc.receive_analytics = AsyncMock(return_value=record)
    response = await client.post(
        "/api/v1/internal/sync/analytics",
        json={"items": [{"content": "x", "importance": 0.4}]},
        headers={"X-Internal-API-Key": KEY},
    )

    assert response.status_code == 200, response.text
    _tenant, batch = sync_svc.receive_analytics.await_args.args
    assert isinstance(batch, AnalyticsBatch)
    assert batch.items[0].importance == 0.4


# ── agent tasks ────────────────────────────────────────────


def test_agent_task_status_and_priority_are_closed_sets():
    AgentTaskUpdate(status="running", priority="high")
    with pytest.raises(ValidationError):
        AgentTaskUpdate(status="banana")
    with pytest.raises(ValidationError):
        AgentTaskUpdate(priority="urgent")
    with pytest.raises(ValidationError):
        AgentTaskCreate(agent_name="a", priority="urgent")


def test_agent_task_timeout_and_retries_are_bounded_like_the_kernel():
    AgentTaskCreate(agent_name="a", timeout_seconds=3600, max_retries=5)
    with pytest.raises(ValidationError):
        AgentTaskCreate(agent_name="a", timeout_seconds=3601)
    with pytest.raises(ValidationError):
        AgentTaskCreate(agent_name="a", max_retries=6)


async def test_patch_agent_task_with_unknown_status_is_422(client):
    from life_graph.api.dependencies import get_delegation_engine

    engine = MagicMock()
    engine.update_task = AsyncMock(side_effect=AssertionError("must not be reached"))
    app.dependency_overrides[get_delegation_engine] = lambda: engine

    response = await client.patch(f"/api/v1/agent-tasks/{uuid.uuid4()}", json={"status": "banana"})

    assert response.status_code == 422, response.text
    engine.update_task.assert_not_called()


async def test_update_task_writes_only_allowlisted_fields():
    from life_graph.services.delegation import DelegationEngine

    task = SimpleNamespace(
        tenant_id=TENANT,
        status="queued",
        status_history=[],
        started_at=None,
        completed_at=None,
        title="old",
        cost_usd=0.0,
    )
    session = MagicMock()
    session.get = AsyncMock(return_value=task)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    class _Ctx:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *exc):
            return False

    engine = DelegationEngine(session_factory=lambda: _Ctx())
    await engine.update_task(
        TENANT,
        uuid.uuid4(),
        {"title": "new", "tenant_id": "someone-else", "cost_usd": 99.0},
    )

    assert task.title == "new"
    assert task.tenant_id == TENANT
    assert task.cost_usd == 0.0


# ── corrections ────────────────────────────────────────────


def test_correction_kind_is_a_closed_set():
    for kind in ("edit", "override", "reject", "approve"):
        CorrectionCreate(kind=kind)
    with pytest.raises(ValidationError):
        CorrectionCreate(kind="banana")
