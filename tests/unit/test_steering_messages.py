"""Steering messages (2026-11-28) and the team-rung dispatcher hook.

docs/specs/agent-drivers.md, "Steering messages (2026-11-28)" and "Team
upgrades (2026-11-28)" -> "Dispatcher hook". Fakes only: no database, no real
driver, no network (one test runs git in a temp repo).
"""

from __future__ import annotations

import shutil
import subprocess
import uuid
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

import life_graph.drivers.dispatcher as disp_mod
import life_graph.drivers.review_stages as rs_mod
from life_graph.config import settings
from life_graph.core.budget import BudgetDecision
from life_graph.drivers import steering
from life_graph.drivers.base import ContextPacket, DriverResult
from life_graph.drivers.dispatcher import TaskDispatcher
from life_graph.models.db import AgentTask
from life_graph.services.dev import task_events, task_messages, team_rungs
from tests.unit.fakes import FakeSession, session_factory

# ── The store ─────────────────────────────────────────────────


def _task(status="running", tenant="t1", kind="dev_task", **props) -> AgentTask:
    return AgentTask(
        id=uuid.uuid4(), tenant_id=tenant, agent_name="dev_task", status=status,
        properties={"kind": kind, **props}, status_history=[], title="t",
        instructions="Do it.", task_type="code_change",
    )  # fmt: skip


def _sf(task: AgentTask):
    return session_factory(FakeSession(objects={(AgentTask, task.id): task}))


@pytest.fixture
def events(monkeypatch):
    seen: list[dict] = []

    def _emit(tenant_id, task_id, kind, content="", *, data=None, source="runner"):
        seen.append({"kind": kind, "content": content, "data": data or {}, "source": source})

    monkeypatch.setattr(task_events, "emit", _emit)
    return seen


async def test_a_message_is_trimmed_redacted_and_queued(events):
    task = _task()
    sf = _sf(task)
    secret = "sk-ant-api03-" + "a" * 40
    out = await task_messages.queue_message(sf, "t1", str(task.id), f"  also fix y.py {secret}  ")
    assert out["queued"] == 1
    stored = task.properties["steer_messages"][0]
    assert stored["text"].startswith("also fix y.py") and secret not in stored["text"]
    assert "[REDACTED]" in stored["text"] and stored["delivered_at"] is None
    assert events[-1]["kind"] == "steer" and events[-1]["data"]["state"] == "queued"
    listed = await task_messages.list_messages(sf, "t1", str(task.id))
    assert listed == [
        {"id": stored["id"], "text": stored["text"], "at": stored["at"], "delivered_at": None}
    ]


async def test_messages_are_refused_when_they_cannot_be_delivered(events):
    task = _task()
    sf = _sf(task)
    for bad, code in (("   ", "empty"), ("x" * 4001, "too_long")):
        with pytest.raises(task_messages.MessageError) as err:
            await task_messages.queue_message(sf, "t1", str(task.id), bad)
        assert err.value.code == code and err.value.http_status == 422
    assert (await task_messages.queue_message(sf, "t1", str(task.id), "x" * 4000))["queued"] == 1
    for n in range(2, 11):
        assert (await task_messages.queue_message(sf, "t1", str(task.id), f"m{n}"))["queued"] == n
    with pytest.raises(task_messages.MessageError) as err:
        await task_messages.queue_message(sf, "t1", str(task.id), "one too many")
    assert err.value.code == "too_many" and err.value.http_status == 409
    # Delivered ones no longer count against the limit.
    first = task.properties["steer_messages"][0]["id"]
    assert await task_messages.settle(sf, "t1", str(task.id), [first], via="turn")
    assert (await task_messages.queue_message(sf, "t1", str(task.id), "now fits"))["queued"] == 10

    for status in ("completed", "failed", "cancelled", "parked"):
        done = _task(status=status)
        with pytest.raises(task_messages.MessageError) as err:
            await task_messages.queue_message(_sf(done), "t1", str(done.id), "hi")
        assert err.value.code == "not_running" and err.value.http_status == 409
    queued = _task(status="queued")
    assert (await task_messages.queue_message(_sf(queued), "t1", str(queued.id), "hi"))["queued"]

    for other in (_task(tenant="t2"), _task(kind="errand")):
        with pytest.raises(task_messages.MessageError) as err:
            await task_messages.queue_message(_sf(other), "t1", str(other.id), "hi")
        assert err.value.code == "not_found" and err.value.http_status == 404
        assert await task_messages.list_messages(_sf(other), "t1", str(other.id)) is None
    with pytest.raises(task_messages.MessageError):
        await task_messages.queue_message(sf, "t1", "not-a-uuid", "hi")


async def test_settle_marks_delivered_or_notes_why_not(events):
    task = _task()
    sf = _sf(task)
    a = (await task_messages.queue_message(sf, "t1", str(task.id), "a"))["id"]
    b = (await task_messages.queue_message(sf, "t1", str(task.id), "b"))["id"]
    await task_messages.settle(sf, "t1", str(task.id), [b], via="turn", reason="kill switch")
    await task_messages.settle(sf, "t1", str(task.id), [a], via="instruction")
    by_id = {m["id"]: m for m in await task_messages.list_messages(sf, "t1", str(task.id))}
    assert by_id[a]["delivered_at"] and by_id[a]["via"] == "instruction"
    assert by_id[b]["delivered_at"] is None and by_id[b]["undelivered_reason"] == "kill switch"
    assert [m["id"] for m in await task_messages.read_pending(sf, "t1", str(task.id))] == [b]
    # Never raises: no row, no database.
    assert await task_messages.read_pending(lambda: None, "t1", str(task.id)) == []
    assert await task_messages.settle(lambda: None, "t1", str(task.id), [a], via="turn") is False


# ── API ───────────────────────────────────────────────────────

OWNER_KEY = "owner-key-0123456789"
SERVICE_KEY = "svc-key-9876543210"


@pytest_asyncio.fixture
async def client(monkeypatch, events):
    from life_graph.api import drivers_automation as api
    from life_graph.api.middleware import TenantMiddleware
    from life_graph.core.tenant import get_current_tenant_id

    monkeypatch.setattr(settings, "api_key", None)
    monkeypatch.setattr(settings, "service_api_keys", f"{SERVICE_KEY},{OWNER_KEY}")
    monkeypatch.setattr(settings, "owner_api_keys", OWNER_KEY)
    task = _task(tenant="raja")
    monkeypatch.setattr(api, "async_session", _sf(task))
    app = FastAPI()
    app.add_middleware(TenantMiddleware)
    app.include_router(api.router, prefix="/api/v1")
    app.dependency_overrides[get_current_tenant_id] = lambda: "raja"
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield SimpleNamespace(http=c, task=task)


def _as(key):
    return {"Authorization": f"Bearer {key}", "X-Tenant-ID": "raja"}


async def test_the_message_routes(client):
    c, task = client.http, client.task
    url = f"/api/v1/kernel/drivers/tasks/{task.id}/messages"
    r = await c.post(url, json={"text": "use the helper"}, headers=_as(SERVICE_KEY))
    assert r.status_code == 403  # owner only
    r = await c.post(url, json={"text": "  use the helper "}, headers=_as(OWNER_KEY))
    assert r.status_code == 200 and r.json()["data"]["queued"] == 1
    r = await c.post(url, json={"text": " "}, headers=_as(OWNER_KEY))
    assert r.status_code == 422 and r.json()["detail"].startswith("empty: ")
    r = await c.post(url, json={"text": "x", "extra": 1}, headers=_as(OWNER_KEY))
    assert r.status_code == 422
    r = await c.get(url, headers=_as(SERVICE_KEY))  # a tenant read
    assert r.status_code == 200
    (msg,) = r.json()["data"]["messages"]
    assert set(msg) == {"id", "text", "at", "delivered_at"}
    assert msg["text"] == "use the helper" and msg["delivered_at"] is None
    task.status = "completed"
    r = await c.post(url, json={"text": "too late"}, headers=_as(OWNER_KEY))
    assert r.status_code == 409 and r.json()["detail"].startswith("not_running: ")
    r = await c.get(f"/api/v1/kernel/drivers/tasks/{uuid.uuid4()}/messages", headers=_as(OWNER_KEY))
    assert r.status_code == 404
    r = await c.post(
        "/api/v1/kernel/drivers/tasks/nope/messages", json={"text": "x"}, headers=_as(OWNER_KEY)
    )
    assert r.status_code == 400


# ── Delivery inside a dispatch ────────────────────────────────


class _Store:
    """An in-memory stand-in for task_messages' row reads and writes."""

    def __init__(self) -> None:
        self.messages: list[dict] = []

    def add(self, text: str) -> str:
        mid = str(uuid.uuid4())
        self.messages.append({"id": mid, "text": text, "at": "now", "delivered_at": None})
        return mid

    async def read_pending(self, _sf, _tenant, _task):
        return [dict(m) for m in self.messages if not m["delivered_at"]]

    async def settle(self, _sf, _tenant, _task, ids, *, via, reason=None):
        for m in self.messages:
            if m["id"] in ids and not m["delivered_at"]:
                if reason is None:
                    m["delivered_at"], m["via"] = "later", via
                else:
                    m["undelivered_reason"] = reason
        return True

    def pending(self) -> list[dict]:
        return [m for m in self.messages if not m["delivered_at"]]


class _Driver:
    """Scripted results; ``on_call`` runs as the owner would, mid-run."""

    name = "codex"
    supports_resume = True

    def __init__(self, *results: DriverResult, on_call=None) -> None:
        self.results = list(results)
        self.calls: list[dict] = []
        self.on_call = on_call
        self.log: list[str] | None = None

    def cost_per_task(self) -> float:
        return 0.0

    def _next(self, kind: str) -> DriverResult:
        if self.log is not None:
            self.log.append(kind)
        if self.on_call:
            self.on_call(len(self.calls))
        return self.results.pop(0) if len(self.results) > 1 else self.results[0]

    async def dispatch(self, packet, workdir, timeout=300):
        self.calls.append({"kind": "dispatch", "instruction": packet.instruction})
        return self._next("dispatch")

    async def resume(self, packet, workdir, session_id, prompt, timeout=300, *, account_id=None):
        self.calls.append({"kind": "resume", "session": session_id, "prompt": prompt})
        return self._next("resume")


def _ok(output="done"):
    return DriverResult(success=True, output=output, metadata={"session_id": "sess-1"})


def _failed(error="crashed"):
    return DriverResult(success=False, error=error, metadata={"exit_status": "error"})


async def _noop(*_a, **_k):
    return None


@pytest.fixture
def wired(monkeypatch, events):
    """A dispatcher whose packet, driver choice, budget, kill switch and
    message store are fakes; ``log`` records driver calls and verification."""
    store = _Store()
    state = {"paused": False, "budget_denied": False, "verified": []}
    monkeypatch.setattr(task_messages, "read_pending", store.read_pending)
    monkeypatch.setattr(task_messages, "settle", store.settle)
    monkeypatch.setattr(settings, "driver_steer_max_turns", 2)

    async def _packet(*_a, **kw):
        return ContextPacket(
            task_id=uuid.uuid4(), tenant_id="t1", task_type="code",
            instruction=kw["instruction"], project_context={},
        )  # fmt: skip

    async def _stopped(_t):
        return state["paused"]

    async def _authorize(*_a, **_k):
        if state["budget_denied"]:
            return BudgetDecision(False, False, "monthly cap reached", 10.0, 10.0, 0.0)
        return BudgetDecision(True, False, "ok", 0.0, 10.0, 10.0)

    def make(driver: _Driver) -> TaskDispatcher:
        disp = TaskDispatcher(session_factory=lambda: FakeSession(), event_bus=None)
        log: list[str] = []
        driver.log = log

        async def _pick(*_a, **_k):
            return driver

        async def _verify(run):
            log.append("verify")
            state["verified"].append(run.result.output)

        monkeypatch.setattr(disp._context_builder, "build_packet", _packet)
        monkeypatch.setattr(disp, "_select_driver", _pick)
        monkeypatch.setattr(disp, "_emit", _noop)
        monkeypatch.setattr(disp, "_record_stats", _noop)
        monkeypatch.setattr(disp, "_verify_result", _verify)
        state["log"] = log
        return disp

    monkeypatch.setattr(disp_mod.governor, "authorize", _authorize)
    monkeypatch.setattr(disp_mod.governor, "record", _noop)
    monkeypatch.setattr(rs_mod, "autonomy_stopped", _stopped)
    return SimpleNamespace(store=store, state=state, make=make, events=events)


async def _dispatch(disp: TaskDispatcher, instruction="fix x.py"):
    return await disp.dispatch_task(
        tenant_id="t1", task_id=str(uuid.uuid4()), instruction=instruction,
        verify_chain=["ruff"],
    )  # fmt: skip


def _steer_states(events) -> list[str]:
    return [e["data"].get("state") for e in events if e["kind"] == "steer"]


async def test_a_message_sent_mid_run_gets_one_turn_before_verification(wired):
    driver = _Driver(
        _ok("first pass"), _ok("steered"),
        on_call=lambda n: wired.store.add("also handle None") if n == 1 else None,
    )  # fmt: skip
    result = await _dispatch(wired.make(driver))
    assert wired.state["log"] == ["dispatch", "resume", "verify"]
    assert driver.calls[1]["session"] == "sess-1"
    assert "The owner sent these messages" in driver.calls[1]["prompt"]
    assert "1. also handle None" in driver.calls[1]["prompt"]
    assert wired.state["verified"] == ["steered"] and result.output == "steered"
    assert wired.store.pending() == [] and wired.store.messages[0]["via"] == "turn"
    assert _steer_states(wired.events) == ["delivering", "delivered"]


async def test_no_message_means_no_extra_turn(wired):
    driver = _Driver(_ok())
    await _dispatch(wired.make(driver))
    assert wired.state["log"] == ["dispatch", "verify"]
    assert _steer_states(wired.events) == []


async def test_steering_turns_are_bounded(wired):
    # The owner sends one more message during every call.
    driver = _Driver(_ok(), on_call=lambda n: wired.store.add(f"message {n}"))
    await _dispatch(wired.make(driver))
    assert wired.state["log"] == ["dispatch", "resume", "resume", "verify"]
    (left,) = wired.store.pending()
    assert left["undelivered_reason"] == "the steering turn limit (2) was reached"
    assert _steer_states(wired.events)[-1] == "skipped"


async def test_zero_turns_disables_steering(wired, monkeypatch):
    monkeypatch.setattr(settings, "driver_steer_max_turns", 0)
    driver = _Driver(_ok(), on_call=lambda n: wired.store.add("hi") if n == 1 else None)
    await _dispatch(wired.make(driver))
    assert wired.state["log"] == ["dispatch", "verify"]
    assert len(wired.store.pending()) == 1


async def test_a_failed_steering_turn_keeps_the_pre_steer_result(wired):
    driver = _Driver(
        _ok("first pass"), _failed("stalled"),
        on_call=lambda n: wired.store.add("rename it") if n == 1 else None,
    )  # fmt: skip
    result = await _dispatch(wired.make(driver))
    assert wired.state["log"] == ["dispatch", "resume", "verify"]
    assert result.success and result.output == "first pass"
    assert wired.state["verified"] == ["first pass"]
    (left,) = wired.store.pending()
    assert left["undelivered_reason"].startswith("the steering turn failed: stalled")
    assert _steer_states(wired.events) == ["delivering", "failed", "fallback"]


async def test_a_failed_run_delivers_nothing(wired):
    driver = _Driver(_failed(), on_call=lambda n: wired.store.add("hi"))
    result = await _dispatch(wired.make(driver))
    assert not result.success and wired.state["log"] == ["dispatch"]  # no verification either
    (left,) = wired.store.pending()
    assert left["undelivered_reason"] == "the run did not succeed"


@pytest.mark.parametrize("gate", ["paused", "budget_denied"])
async def test_the_kill_switch_and_the_budget_refuse_a_steering_turn(wired, gate):
    driver = _Driver(_ok(), on_call=lambda n: wired.store.add("hi") if n == 1 else None)
    disp = wired.make(driver)

    def flip(n):
        wired.store.add("hi")
        wired.state[gate] = True  # flipped while the run was going

    driver.on_call = flip
    await _dispatch(disp)
    assert wired.state["log"] == ["dispatch", "verify"]
    (left,) = wired.store.pending()
    reason = left["undelivered_reason"]
    assert ("kill switch" in reason) if gate == "paused" else reason.startswith("budget:")
    assert _steer_states(wired.events) == ["skipped"]


async def test_messages_sent_while_queued_ride_in_the_instruction(wired):
    wired.store.add("target Python 3.12")
    driver = _Driver(_ok())
    await _dispatch(wired.make(driver), instruction="fix x.py")
    assert wired.state["log"] == ["dispatch", "verify"]  # no extra turn
    sent = driver.calls[0]["instruction"]
    assert task_messages.CLAIM_START in sent and "1. target Python 3.12" in sent
    assert sent.index("fix x.py") < sent.index(task_messages.CLAIM_START)
    assert wired.store.messages[0]["via"] == "instruction"
    assert _steer_states(wired.events) == ["delivered"]


async def test_a_driver_without_resume_gets_the_messages_as_a_redispatch(wired):
    driver = _Driver(
        _ok("first"), _ok("second"),
        on_call=lambda n: wired.store.add("one more thing") if n == 1 else None,
    )  # fmt: skip
    driver.supports_resume = False
    await _dispatch(wired.make(driver))
    assert wired.state["log"] == ["dispatch", "dispatch", "verify"]
    again = driver.calls[1]["instruction"]
    assert again.startswith("The owner sent these messages") and "fix x.py" in again
    assert wired.store.pending() == []


async def test_continue_folds_waiting_messages_into_the_follow_up(wired):
    wired.store.add("and update the docs")
    disp = wired.make(_Driver(_ok()))
    run = SimpleNamespace(tenant_id="t1", task_id=str(uuid.uuid4()), start_messages=[],
                          start_messages_via="instruction", autonomy={},
                          result=_ok())  # fmt: skip
    block = await disp._take_start_messages(run, into="continue")
    assert "1. and update the docs" in block and run.start_messages_via == "continue"
    await disp._settle_start_messages(run)
    assert wired.store.messages[0]["via"] == "continue" and run.start_messages == []


# ── A failed turn's worktree is put back ──────────────────────


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
async def test_restore_puts_the_worktree_back(tmp_path, monkeypatch):
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("-c", "user.email=a@b", "-c", "user.name=a", "commit", "-q", "--allow-empty", "-m", "0")
    (tmp_path / "a.py").write_text("before\n")
    monkeypatch.setattr(steering, "worktree_intact", lambda *_a: True)
    run = SimpleNamespace(worktree=tmp_path, worktree_origin=str(tmp_path))
    tree = await steering.snapshot_tree(run)
    assert tree
    (tmp_path / "a.py").write_text("half-edited\n")
    (tmp_path / "junk.py").write_text("new\n")
    assert await steering.restore_tree(run, tree)
    assert (tmp_path / "a.py").read_text() == "before\n"
    assert not (tmp_path / "junk.py").exists()
    monkeypatch.setattr(steering, "worktree_intact", lambda *_a: False)
    assert await steering.snapshot_tree(run) is None  # never git in a tampered tree
    assert await steering.restore_tree(run, tree) is False


# ── Team upgrades: the dispatcher hook ────────────────────────


async def test_the_dispatcher_calls_the_team_rung_hook_before_the_floor(wired, monkeypatch):
    order: list[str] = []
    seen: list = []
    real = team_rungs.apply_team_rung

    async def hook(run):
        order.append("team_rung")
        seen.append(run)
        await real(run)

    disp = wired.make(_Driver(_ok()))
    real_floor = disp._apply_start_floor

    async def floor(run):
        order.append("floor")
        await real_floor(run)

    monkeypatch.setattr(team_rungs, "apply_team_rung", hook)
    monkeypatch.setattr(disp, "_apply_start_floor", floor)
    await _dispatch(disp)
    assert order == ["team_rung", "floor"]
    # A task that is not a rung-pinned team worker is left as it was.
    (run,) = seen
    assert run.driver_pin is None and run.reached_top is False
    assert run.packet.persona_model is None
