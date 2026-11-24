"""POST /kernel/drivers/dispatch is off by default (audit L5).

It runs a whole driver pipeline inside the request, outside the dev runner's
lock, concurrency limits and budget check. Nothing in the repo, the UI or the
phone app calls it, so it answers 404 unless drivers_dispatch_endpoint is on.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from life_graph.api import drivers as drivers_api
from life_graph.config import Settings, settings

BODY = {"instruction": "say hello", "task_type": "general"}


class _Session:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def commit(self):
        return None


@pytest.fixture
def calls(monkeypatch):
    seen: list[dict] = []

    class FakeDispatcher:
        def __init__(self, **kwargs):
            pass

        async def dispatch_task(self, **kwargs):
            seen.append(kwargs)
            return SimpleNamespace(
                success=True,
                output="hi",
                cost_usd=0.0,
                duration_ms=1,
                error=None,
                metadata={"driver": "fake"},
            )

    import life_graph.drivers.dispatcher as dispatcher_mod

    monkeypatch.setattr(dispatcher_mod, "TaskDispatcher", FakeDispatcher)
    monkeypatch.setattr(drivers_api, "async_session", _Session)
    monkeypatch.setattr(drivers_api, "get_current_tenant_id", lambda: "t1")
    return seen


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(drivers_api.router)
    return TestClient(app)


def test_off_by_default():
    assert Settings.model_fields["drivers_dispatch_endpoint"].default is False


def test_dispatch_is_404_and_runs_nothing_when_off(client, calls, monkeypatch):
    monkeypatch.setattr(settings, "drivers_dispatch_endpoint", False)
    resp = client.post("/kernel/drivers/dispatch", json=BODY)
    assert resp.status_code == 404
    assert calls == []


def test_dispatch_runs_when_switched_on(client, calls, monkeypatch):
    monkeypatch.setattr(settings, "drivers_dispatch_endpoint", True)
    resp = client.post("/kernel/drivers/dispatch", json=BODY)
    assert resp.status_code == 201
    assert len(calls) == 1 and calls[0]["tenant_id"] == "t1"


def test_dispatch_failure_hides_raw_error(client, calls, monkeypatch, caplog):
    """A dispatch crash returns a fixed message; the detail goes to the log (audit M3)."""
    secret = "connect to postgres://admin:hunter2@10.0.0.5 failed"

    class BoomDispatcher:
        def __init__(self, **kwargs):
            pass

        async def dispatch_task(self, **kwargs):
            raise RuntimeError(secret)

    import life_graph.drivers.dispatcher as dispatcher_mod

    monkeypatch.setattr(dispatcher_mod, "TaskDispatcher", BoomDispatcher)
    monkeypatch.setattr(settings, "drivers_dispatch_endpoint", True)
    with caplog.at_level("ERROR", logger=drivers_api.__name__):
        resp = client.post("/kernel/drivers/dispatch", json=BODY)
    assert resp.status_code == 500
    assert "hunter2" not in resp.text
    assert resp.json()["detail"] == "Dispatch failed."
    assert secret in caplog.text
