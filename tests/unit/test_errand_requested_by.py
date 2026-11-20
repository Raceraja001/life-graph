"""A paused errand's card says who asked for it, so that caller can't approve it.

``api/jarvis.py`` refuses an Approve from the caller named in the card's
``requested_by`` (api/approval_identity.refuse_self_approval, PR #301), but
the errand tool never wrote that field. Now AuthMiddleware records the
server's view of the caller (core/task_context.set_requester), work spawned
by the request inherits it, and the errand card carries it.
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from life_graph.api import middleware
from life_graph.config import settings
from life_graph.core import task_context
from life_graph.services import browser_errand as be
from life_graph.tools import errand

SERVICE_KEY = "mcp-key-9876543210"
SERVICE_LABEL = f"service-key:{hashlib.sha256(SERVICE_KEY.encode()).hexdigest()[:8]}"
NOW = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)


def _step() -> be.StepResult:
    return be.StepResult(
        index=0,
        kind="click",
        action_type="browser_click",
        target_origin="https://bank.example",
        decision="deny",
        reasons=("no_owner_mandate",),
        status=be.DENIED,
    )


def test_the_card_carries_who_asked():
    row = errand.approval_notification(
        "t1", goal="g", errand_id="e1", step=_step(), now=NOW, requested_by=SERVICE_LABEL
    )
    assert row.extra_metadata["requested_by"] == SERVICE_LABEL


def test_a_card_nobody_asked_for_has_no_requested_by():
    row = errand.approval_notification("t1", goal="g", errand_id="e1", step=_step(), now=NOW)
    assert "requested_by" not in row.extra_metadata


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(settings, "api_key", None)
    monkeypatch.setattr(settings, "service_api_keys", SERVICE_KEY)
    monkeypatch.setattr(settings, "owner_api_keys", "")
    monkeypatch.setattr(settings, "environment", "production")

    async def who(request):  # noqa: ANN001
        # The way a kernel task is started from a request: a background task.
        spawned = await asyncio.create_task(asyncio.sleep(0, result=task_context.get_requester()))
        return JSONResponse({"now": task_context.get_requester(), "spawned": spawned})

    a = Starlette(routes=[Route("/api/v1/who", who), Route("/health", who)])
    a.add_middleware(middleware.AuthMiddleware)
    return TestClient(a)


def test_an_authenticated_request_records_its_caller_for_spawned_work(app):
    resp = app.get("/api/v1/who", headers={"Authorization": f"Bearer {SERVICE_KEY}"})
    assert resp.status_code == 200
    assert resp.json() == {"now": SERVICE_LABEL, "spawned": SERVICE_LABEL}


def test_an_exempt_path_records_no_caller(app):
    assert app.get("/health").json() == {"now": None, "spawned": None}


def test_outside_a_request_there_is_no_requester():
    assert task_context.get_requester() is None
