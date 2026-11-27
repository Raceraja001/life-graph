"""Phase 4b: dev-task dependencies -- hold, start, cancel, cycles, restart."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from life_graph.models.db import AgentTask, Approval
from life_graph.services.dev import dependencies as deps
from life_graph.services.dev import tasks as dev_tasks
from life_graph.services.dev.dependencies import DependencyError
from tests.unit.fakes import FakeSession, session_factory, sql

NOW = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)


def task(status="queued", *, depends_on=None, tenant="t1", props=None, result=None) -> AgentTask:
    p = {"kind": "dev_task", **(props or {})}
    if depends_on is not None:
        p.update(deps.hold_properties([str(d) for d in depends_on]))
    return AgentTask(
        id=uuid.uuid4(), tenant_id=tenant, agent_name="dev_task", status=status,
        properties=p, result=result or {}, status_history=[], title="x",
        assigned_agent="code-fixer",
    )  # fmt: skip


def pr_approval(t: AgentTask, status="pending") -> Approval:
    return Approval(
        id=uuid.uuid4(), tenant_id=t.tenant_id, kind="driver_pr", status=status,
        source_ref=str(t.id), payload={}, title="Open PR",
    )  # fmt: skip


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    emitted: list = []

    async def _bus(name, payload):
        emitted.append((name, payload))

    monkeypatch.setattr(dev_tasks, "_emit_bus", _bus)
    monkeypatch.setattr(
        dev_tasks.task_events, "emit", lambda *a, **k: emitted.append(("task", a[2], a[3]))
    )
    return emitted


async def open_gate(*_a, **_k):
    return []


# ── Pure rules ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("status", "stage", "verdict"),
    [
        ("completed", "awaiting_pr", "done"),
        ("completed", "pr_open", "done"),
        ("completed", "merged", "done"),
        ("completed", "landed", "done"),  # a team worker's branch hand-off
        ("queued", "queued", "wait"),
        ("running", "running", "wait"),
        ("parked", "parked", "wait"),
        ("failed", "failed", "broken"),
        ("failed", "needs_review", "broken"),
        ("cancelled", "cancelled", "broken"),
        ("completed", "pr_rejected", "broken"),
        ("completed", "closed", "broken"),
        (None, None, "broken"),  # the row is gone
    ],
)
def test_dependency_state(status, stage, verdict):
    assert deps.dependency_state(status, stage) == verdict


def test_evaluate_waits_until_every_dependency_finished():
    a, b = "a", "b"
    assert deps.evaluate([a, b], {a: ("completed", "awaiting_pr"), b: ("running", "running")}) == (
        "wait", None, [b],
    )  # fmt: skip
    assert deps.evaluate([a, b], {a: ("completed", "landed"), b: ("completed", "merged")})[0] == (
        "ready"
    )
    assert deps.evaluate([a, b], {a: ("failed", "failed"), b: ("running", "running")})[:2] == (
        "broken", a,
    )  # fmt: skip
    assert deps.evaluate([a], {})[:2] == ("broken", a)


def test_find_cycle():
    graph = {"a": ["b"], "b": ["c"], "c": ["a"]}
    assert deps.find_cycle(graph, ["a"]) == ["a", "b", "c", "a"]
    assert deps.find_cycle({"a": ["b"], "b": []}, ["a"]) is None
    assert deps.find_cycle({}, ["n"], new_id="n") == ["n", "n"]
    assert deps.find_cycle({"a": ["n"]}, ["a"], new_id="n") == ["a", "n"]


def test_normalize_refuses_bad_ids_and_too_many():
    one = uuid.uuid4()
    assert deps.normalize([str(one), str(one).upper()]) == [str(one)]
    with pytest.raises(DependencyError) as err:
        deps.normalize(["nope"])
    assert err.value.code == "invalid"
    with pytest.raises(DependencyError):
        deps.normalize([uuid.uuid4() for _ in range(deps.MAX_DEPENDENCIES + 1)])


# ── Validation at creation (422) ───────────────────────────────


async def test_unknown_dependencies_are_refused():
    session = FakeSession([])
    with pytest.raises(DependencyError) as err:
        await deps.validate_dependencies(session, "t1", [str(uuid.uuid4())])
    assert err.value.code == "unknown"
    stmt = sql(session.statements[0])
    assert "tenant_id" in stmt  # another tenant's id reads as unknown


async def test_a_cycle_among_existing_tasks_is_refused():
    a, b = task(), task()
    a.properties["depends_on"] = [str(b.id)]
    b.properties["depends_on"] = [str(a.id)]
    session = FakeSession([a], [b], [])
    with pytest.raises(DependencyError) as err:
        await deps.validate_dependencies(session, "t1", [str(a.id)])
    assert err.value.code == "cyclic"


async def test_valid_dependencies_pass():
    a = task("running")
    assert await deps.validate_dependencies(FakeSession([a], []), "t1", [str(a.id)]) == [str(a.id)]
    assert await deps.validate_dependencies(FakeSession(), "t1", None) == []


async def test_create_dev_task_holds_a_task_with_dependencies(monkeypatch):
    dep = task("running")
    session = FakeSession([dep], [], None, None)
    data = await dev_tasks.create_dev_task(
        session_factory(session), "t1", instruction="do the second part",
        project={"id": str(uuid.uuid4()), "name": "p"}, persona_name="code-fixer",
        start=False, depends_on=[str(dep.id)],
    )  # fmt: skip
    created = session.added[0]
    assert created.status == "queued"
    assert created.properties["deps_pending"] is True
    assert created.properties["depends_on"] == [str(dep.id)]
    assert data["depends_on"] == [str(dep.id)]
    assert data["dependency_wait"]["waiting_on"] == [str(dep.id)]


async def test_create_dev_task_refuses_an_unknown_dependency_and_creates_nothing():
    session = FakeSession([])
    with pytest.raises(DependencyError):
        await dev_tasks.create_dev_task(
            session_factory(session), "t1", instruction="do it",
            project={"id": str(uuid.uuid4()), "name": "p"}, persona_name="code-fixer",
            depends_on=[str(uuid.uuid4())],
        )  # fmt: skip
    assert session.added == []


async def test_the_claim_skips_held_tasks(monkeypatch):
    async def not_paused(_t):
        return False

    monkeypatch.setattr(dev_tasks, "autonomy_stopped", not_paused)
    session = FakeSession([], [])
    assert await dev_tasks.claim_next_queued(session_factory(session)) is None
    candidates = sql(session.statements[1])
    assert "deps_pending" in candidates


# ── The runner's release pass ──────────────────────────────────


async def test_a_held_task_starts_once_its_dependencies_finished(quiet):
    dep = task("completed")
    held = task(depends_on=[dep.id])
    session = FakeSession([held], [dep], [pr_approval(dep)])

    out = await deps.release_dependencies(session_factory(session), now=NOW, gate=open_gate)

    assert out == {"released": [str(held.id)], "cancelled": []}
    assert "deps_pending" not in held.properties
    assert held.properties["dependencies_met_at"] == NOW.isoformat()
    assert held.status == "queued"
    assert ("TASK_DEPENDENCIES_MET", {"tenant_id": "t1", "task_id": str(held.id)}) in quiet
    # Every query is tenant-scoped.
    assert all("tenant_id" in sql(s) for s in session.statements[1:])


async def test_a_held_task_keeps_waiting_while_a_dependency_runs():
    dep = task("running")
    held = task(depends_on=[dep.id])
    session = FakeSession([held], [dep], [])

    out = await deps.release_dependencies(session_factory(session), now=NOW, gate=open_gate)

    assert out == {"released": [], "cancelled": []}
    assert held.properties["deps_pending"] is True
    assert held.properties["dependency_wait"]["waiting_on"] == [str(dep.id)]


async def test_a_failed_dependency_cancels_the_dependent_with_the_reason(quiet):
    dep = task("failed")
    held = task(depends_on=[dep.id])
    session = FakeSession([held], [dep], [])

    out = await deps.release_dependencies(session_factory(session), now=NOW, gate=open_gate)

    assert out["cancelled"] == [str(held.id)]
    assert held.status == "cancelled"
    assert held.error == f"Dependency {dep.id} failed (failed)"
    assert held.properties["dependency_failed"] == {"task_id": str(dep.id), "stage": "failed"}
    assert held.completed_at == NOW
    assert any(e[0] == "TASK_DEPENDENCY_FAILED" for e in quiet)


async def test_a_dependency_whose_row_is_gone_cancels_the_dependent():
    held = task(depends_on=[uuid.uuid4()])
    out = await deps.release_dependencies(
        session_factory(FakeSession([held], [], [])), now=NOW, gate=open_gate
    )
    assert out["cancelled"] == [str(held.id)]
    assert "(gone)" in held.error


async def test_the_gate_holds_a_ready_task_and_says_why():
    dep = task("completed")
    held = task(depends_on=[dep.id])
    seen = {}

    async def closed(tenant_id, *, driver=None, account_id=None):
        seen.update(tenant=tenant_id, driver=driver)
        return ["Autonomy is paused (kill switch)."]

    out = await deps.release_dependencies(
        session_factory(FakeSession([held], [dep], [pr_approval(dep)])), now=NOW, gate=closed
    )

    assert out["released"] == []
    assert held.properties["deps_pending"] is True
    assert held.properties["dependency_wait"]["blocked"] == "Autonomy is paused (kill switch)."
    assert seen["tenant"] == "t1"


async def test_release_is_restart_safe_the_rows_are_the_state():
    """A second pass (a new runner after a restart) decides from the rows alone."""
    dep = task("running")
    held = task(depends_on=[dep.id])
    first = await deps.release_dependencies(
        session_factory(FakeSession([held], [dep], [])), now=NOW, gate=open_gate
    )
    assert first["released"] == []
    dep.status = "completed"
    dep.result = {"metadata": {"landed_branch": "lg/task-abcd1234"}}  # handed off
    again = await deps.release_dependencies(
        session_factory(FakeSession([held], [dep], [])), now=NOW, gate=open_gate
    )
    assert again["released"] == [str(held.id)]


async def test_nothing_held_is_one_query():
    session = FakeSession([])
    assert await deps.release_dependencies(session_factory(session), gate=open_gate) == {
        "released": [],
        "cancelled": [],
    }
    assert len(session.statements) == 1


def test_a_task_shows_what_it_waits_for():
    dep = uuid.uuid4()
    held = task(depends_on=[dep])
    view = dev_tasks.serialize(held, [])
    assert view["depends_on"] == [str(dep)]
    assert view["dependency_wait"]["waiting_on"] == [str(dep)]
    held.properties.pop("deps_pending")
    assert dev_tasks.serialize(held, [])["dependency_wait"] is None


# ── API ─────────────────────────────────────────────────────────


async def test_the_api_passes_depends_on_and_maps_refusals_to_422(monkeypatch):
    from fastapi import HTTPException

    from life_graph.api import dependencies as api_deps
    from life_graph.api import drivers

    seen: dict = {}

    class _Registry:
        async def get_by_id(self, _t, _p):
            return {"id": str(uuid.uuid4()), "name": "p", "is_active": True}

    class _Personas:
        async def get_by_name(self, _t, _n):
            return {"driver": "claude_code", "is_active": True}

    async def fake_create(_factory, _tenant, **kw):
        seen.update(kw)
        if kw.get("depends_on") == ["bad"]:
            raise DependencyError("unknown", "Unknown dev task(s): bad")
        return {"id": "t1"}

    monkeypatch.setattr(api_deps, "get_project_registry", lambda: _Registry())
    monkeypatch.setattr(api_deps, "get_persona_service", lambda: _Personas())
    monkeypatch.setattr(dev_tasks, "create_dev_task", fake_create)
    request = SimpleNamespace(headers={}, state=SimpleNamespace())
    monkeypatch.setattr("life_graph.api.approval_identity.resolver", lambda _r: "owner")
    monkeypatch.setattr(drivers, "get_current_tenant_id", lambda: "t1")

    dep = str(uuid.uuid4())
    body = drivers.DevTaskCreate(instruction="fix the thing", project_id="p", depends_on=[dep])
    await drivers.create_dev_task(body, request)
    assert seen["depends_on"] == [dep]

    body = drivers.DevTaskCreate(instruction="fix the thing", project_id="p", depends_on=["bad"])
    with pytest.raises(HTTPException) as err:
        await drivers.create_dev_task(body, request)
    assert err.value.status_code == 422
    assert err.value.detail.startswith("unknown:")
