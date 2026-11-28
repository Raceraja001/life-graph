"""Phase 4b: the arena -- create a race, show it side by side, pick the winner."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from life_graph.config import settings
from life_graph.models.db import AgentTask, Approval, DevTaskGroup
from life_graph.services.dev import arena
from life_graph.services.dev import tasks as dev_tasks
from life_graph.services.dev.arena import ArenaError
from tests.unit.fakes import FakeSession, session_factory


def test_normalize_entries():
    assert arena.normalize_entries(["codex", {"driver": "claude_code", "account_id": "a1"}]) == [
        {"driver": "codex", "account_id": None},
        {"driver": "claude_code", "account_id": "a1"},
    ]
    for bad in (["codex"], ["codex", "codex"], ["a", "b", "c", "d", "e", "f"], ["x", 3], ["", "x"]):
        with pytest.raises(ArenaError) as err:
            arena.normalize_entries(bad)
        assert err.value.http_status == 422
    # The same driver on two accounts is two racers.
    assert len(arena.normalize_entries([
        {"driver": "codex", "account_id": "a1"}, {"driver": "codex", "account_id": "a2"},
    ])) == 2  # fmt: skip


class _Store(FakeSession):
    async def get(self, model, pk, **_k):
        return next((o for o in self.added if getattr(o, "id", None) == pk), None)


@pytest.fixture
def registry(monkeypatch):
    monkeypatch.setattr(
        arena.driver_registry, "get", lambda n: object() if n in ("codex", "claude_code") else None
    )


async def test_the_arena_is_off_by_default():
    assert settings.driver_arena_enabled is False
    with pytest.raises(ArenaError) as err:
        await arena.create_arena(
            session_factory(_Store()), "t1", project={"id": str(uuid.uuid4()), "name": "p"},
            instruction="do it", entries=["codex", "claude_code"], persona_name="code-fixer",
        )  # fmt: skip
    assert err.value.code == "arena_disabled" and err.value.http_status == 409


async def test_create_queues_one_pinned_task_per_racer(monkeypatch, registry):
    monkeypatch.setattr(settings, "driver_arena_enabled", True)
    calls: list = []

    async def fake_create(_sf, tenant_id, **kw):
        calls.append(kw)
        return {"id": str(uuid.uuid4())}

    async def quiet(*_a, **_k):
        return None

    async def shown(_s, tenant_id, arena_id):
        return {"id": arena_id}

    monkeypatch.setattr(dev_tasks, "create_dev_task", fake_create)
    monkeypatch.setattr(dev_tasks, "_emit_bus", quiet)
    monkeypatch.setattr(arena, "get_arena", shown)
    store = _Store()

    out = await arena.create_arena(
        session_factory(store), "t1", project={"id": str(uuid.uuid4()), "name": "p"},
        instruction="make it faster", entries=["codex", "claude_code"], persona_name="code-fixer",
        requested_by="owner",
    )  # fmt: skip

    group = store.added[0]
    assert isinstance(group, DevTaskGroup) and group.kind == "arena" and group.status == "racing"
    assert out["id"] == str(group.id)
    assert [c["properties"]["driver_pin"] for c in calls] == ["codex", "claude_code"]
    assert all(c["instruction"] == "make it faster" and c["start"] is True for c in calls)
    # The same instruction twice is not a duplicate inside a race.
    assert len({c["dedupe_scope"] for c in calls}) == 2
    assert [r["driver"] for r in group.properties["racers"]] == ["codex", "claude_code"]


async def test_create_refuses_an_unknown_driver(monkeypatch, registry):
    monkeypatch.setattr(settings, "driver_arena_enabled", True)
    with pytest.raises(ArenaError) as err:
        await arena.create_arena(
            session_factory(_Store()), "t1", project={"id": str(uuid.uuid4()), "name": "p"},
            instruction="do it", entries=["codex", "nope"], persona_name="code-fixer",
        )  # fmt: skip
    assert err.value.code == "unknown_driver"


def _racer(status="completed") -> AgentTask:
    return AgentTask(
        id=uuid.uuid4(), tenant_id="t1", agent_name="dev_task", status=status,
        properties={"kind": "dev_task"}, status_history=[], title="x",
        result={"cost_usd": 0.0, "duration_ms": 1200, "metadata": {"driver": "codex"}},
    )  # fmt: skip


def _pr(task, status="pending") -> Approval:
    return Approval(
        id=uuid.uuid4(), tenant_id="t1", kind="driver_pr", status=status, source_ref=str(task.id),
        title="Open PR: x",
        payload={"verified": True, "checks": ["tests_pass"],
                 "change": {"files": ["a.py", "b.py"], "lines": 40, "kind": "code"}},
    )  # fmt: skip


def _group(winner_ids):
    return DevTaskGroup(
        id=uuid.uuid4(), tenant_id="t1", kind="arena", status="racing",
        properties={"racers": [{"task_id": str(t.id), "driver": d, "account_id": None}
                               for t, d in winner_ids]},
    )  # fmt: skip


def test_racers_side_by_side():
    win = _racer()
    row = arena.racer_row(win, {"driver": "codex"}, [_pr(win)], 2, "awaiting_pr")
    assert row["diff"] == {"files": 2, "lines": 40, "kind": "code"}
    assert row["verified"] is True and row["rounds"] == 2 and row["duration_ms"] == 1200
    assert row["approval"]["status"] == "pending"
    assert arena.race_status("racing", [{"status": "running"}, {"status": "completed"}]) == "racing"
    assert arena.race_status("racing", [{"status": "failed"}, {"status": "completed"}]) == (
        "ready_to_pick"
    )
    assert arena.race_status("decided", [{"status": "running"}]) == "decided"


@pytest.fixture
def picked(monkeypatch):
    cancelled, events = [], []

    async def cancel(_sf, tenant_id, task_id):
        cancelled.append(task_id)

    async def bus(name, payload):
        events.append((name, payload))

    async def shown(_s, tenant_id, arena_id):
        return {"id": arena_id, "status": "decided"}

    monkeypatch.setattr(dev_tasks, "request_cancel", cancel)
    monkeypatch.setattr(dev_tasks, "_emit_bus", bus)
    monkeypatch.setattr(arena, "get_arena", shown)
    return cancelled, events


async def test_pick_cancels_and_rejects_the_others_and_leaves_the_winner_pending(picked):
    cancelled, events = picked
    win, done, running = _racer(), _racer(), _racer("running")
    win_pr, loser_pr = _pr(win), _pr(done)
    group = _group([(win, "codex"), (done, "claude_code"), (running, "gemini")])
    session = FakeSession(group, [win, done, running], [win_pr, loser_pr])

    out = await arena.pick_winner(session_factory(session), "t1", str(group.id), str(win.id))

    assert win_pr.status == "pending"  # proceeds normally: the owner approves it
    assert loser_pr.status == "rejected" and loser_pr.resolved_by == "system: arena"
    assert cancelled == [str(running.id)]
    assert group.status == "decided" and group.properties["winner_task_id"] == str(win.id)
    assert out["rejected_approval_ids"] == [str(loser_pr.id)]
    assert events[0][0] == "ARENA_DECIDED" and events[0][1]["winner_driver"] == "codex"


async def test_pick_refusals(picked):
    win, other = _racer(), _racer()
    group = _group([(win, "codex"), (other, "claude_code")])

    with pytest.raises(ArenaError) as err:
        await arena.pick_winner(
            session_factory(FakeSession(group, [win, other], [])), "t1", str(group.id), str(win.id)
        )
    assert err.value.code == "not_ready"  # nothing landed to approve

    with pytest.raises(ArenaError) as err:
        await arena.pick_winner(
            session_factory(FakeSession(group)), "t1", str(group.id), str(uuid.uuid4())
        )
    assert err.value.http_status == 422

    group.status = "decided"
    with pytest.raises(ArenaError) as err:
        await arena.pick_winner(
            session_factory(FakeSession(group)), "t1", str(group.id), str(win.id)
        )
    assert err.value.code == "decided"

    with pytest.raises(ArenaError) as err:
        await arena.pick_winner(session_factory(FakeSession(None)), "t1", "nope", str(win.id))
    assert err.value.http_status == 404


async def test_a_racer_never_auto_opens_and_runs_on_its_pin():
    racer = AgentTask(
        id=uuid.uuid4(), tenant_id="t1", agent_name="dev_task", status="running",
        properties={"kind": "dev_task", "arena_id": "a1", "driver_pin": "codex",
                    "account_pin": "acc-1"},
    )  # fmt: skip
    assert await dev_tasks._phase4b_options(FakeSession(), racer) == {
        "driver_pin": "codex", "account_pin": "acc-1", "hold_auto": True,
    }  # fmt: skip
    view = dev_tasks.serialize(racer, [])
    assert view["arena"] == {"id": "a1", "index": None, "driver": "codex", "account_id": "acc-1"}


# ── API ─────────────────────────────────────────────────────────

OWNER_KEY = "owner-key-0123456789"
SERVICE_KEY = "svc-key-9876543210"


@pytest_asyncio.fixture
async def client(monkeypatch):
    from life_graph.api import dependencies as api_deps
    from life_graph.api import drivers_automation as api
    from life_graph.api.middleware import TenantMiddleware
    from life_graph.core.tenant import get_current_tenant_id

    monkeypatch.setattr(settings, "api_key", None)
    monkeypatch.setattr(settings, "service_api_keys", f"{SERVICE_KEY},{OWNER_KEY}")
    monkeypatch.setattr(settings, "owner_api_keys", OWNER_KEY)
    seen: dict = {}

    class _Registry:
        async def get_by_id(self, _t, pid):
            return {"id": pid, "name": "p", "is_active": True} if pid != "gone" else None

    class _Personas:
        async def get_by_name(self, _t, _n):
            return {"is_active": True}

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_e):
            return False

    async def create(_sf, tenant_id, **kw):
        seen.update(kw, tenant=tenant_id)
        if kw["entries"][0] == "off":
            raise ArenaError("arena_disabled", "The arena is off")
        return {"id": "a1", "status": "racing"}

    async def get(_s, tenant_id, arena_id):
        return None if arena_id.startswith("0") else {"id": arena_id}

    async def pick(_sf, tenant_id, arena_id, task_id):
        if task_id.startswith("0"):
            raise ArenaError("not_ready", "The winner has no change to approve yet")
        return {"id": arena_id, "winner_task_id": task_id}

    monkeypatch.setattr(api_deps, "get_project_registry", lambda: _Registry())
    monkeypatch.setattr(api_deps, "get_persona_service", lambda: _Personas())
    monkeypatch.setattr(api, "async_session", lambda: _Session())
    monkeypatch.setattr(api._arena, "create_arena", create)
    monkeypatch.setattr(api._arena, "get_arena", get)
    monkeypatch.setattr(api._arena, "pick_winner", pick)
    app = FastAPI()
    app.add_middleware(TenantMiddleware)
    app.include_router(api.router, prefix="/api/v1")
    app.dependency_overrides[get_current_tenant_id] = lambda: "raja"
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield SimpleNamespace(http=c, seen=seen)


def _as(key):
    return {"Authorization": f"Bearer {key}", "X-Tenant-ID": "raja"}


async def test_arena_routes(client):
    c = client.http
    body = {"project_id": "p1", "instruction": "make it faster",
            "drivers": ["codex", {"driver": "claude_code", "account_id": "acc-1"}]}  # fmt: skip
    r = await c.post("/api/v1/kernel/drivers/arena", json=body, headers=_as(SERVICE_KEY))
    assert r.status_code == 403
    r = await c.post("/api/v1/kernel/drivers/arena", json=body, headers=_as(OWNER_KEY))
    assert r.status_code == 202 and r.json()["data"]["id"] == "a1"
    assert client.seen["entries"] == ["codex", {"driver": "claude_code", "account_id": "acc-1"}]
    assert client.seen["tenant"] == "raja"
    r = await c.post(
        "/api/v1/kernel/drivers/arena", json={**body, "drivers": ["off", "x"]},
        headers=_as(OWNER_KEY),
    )  # fmt: skip
    assert r.status_code == 409 and r.json()["detail"].startswith("arena_disabled")
    r = await c.post(
        "/api/v1/kernel/drivers/arena", json={**body, "drivers": ["codex"]}, headers=_as(OWNER_KEY)
    )
    assert r.status_code == 422
    r = await c.post(
        "/api/v1/kernel/drivers/arena", json={**body, "project_id": "gone"}, headers=_as(OWNER_KEY)
    )
    assert r.status_code == 404

    aid = "1" + str(uuid.uuid4())[1:]
    r = await c.get(f"/api/v1/kernel/drivers/arena/{aid}", headers=_as(SERVICE_KEY))
    assert r.status_code == 200
    r = await c.get(f"/api/v1/kernel/drivers/arena/0{aid[1:]}", headers=_as(SERVICE_KEY))
    assert r.status_code == 404

    win = "1" + str(uuid.uuid4())[1:]
    r = await c.post(
        f"/api/v1/kernel/drivers/arena/{aid}/pick", json={"task_id": win}, headers=_as(OWNER_KEY)
    )
    assert r.status_code == 200 and r.json()["data"]["winner_task_id"] == win
    r = await c.post(
        f"/api/v1/kernel/drivers/arena/{aid}/pick", json={"task_id": "0" + win[1:]},
        headers=_as(OWNER_KEY),
    )  # fmt: skip
    assert r.status_code == 409 and r.json()["detail"].startswith("not_ready")
    r = await c.post(
        f"/api/v1/kernel/drivers/arena/{aid}/pick", json={"task_id": win}, headers=_as(SERVICE_KEY)
    )
    assert r.status_code == 403
