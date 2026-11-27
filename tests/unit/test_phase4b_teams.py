"""Phase 4b: parallel plans -- scopes, scheduling, max_parallel, integration, failure."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from life_graph.config import settings
from life_graph.drivers.plan_spec import parse_task_files, plan_only_prefix
from life_graph.models.db import AgentTask, Approval, DevTaskGroup
from life_graph.services.dev import tasks as dev_tasks
from life_graph.services.dev import teams
from life_graph.services.dev.team_scope import (
    overlap_dependencies,
    parallel_waves,
    paths_overlap,
    scopes_overlap,
)
from tests.unit.fakes import FakeSession, session_factory, sql

# ── Scopes ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("a", "b", "overlap"),
    [
        ("a.py", "a.py", True),
        ("./src//a.py", "src/a.py", True),
        ("src", "src/ui/x.ts", True),
        ("src/ui", "src/api", False),
        ("src/**", "src/deep/x.py", True),
        ("src/*.py", "src/a.py", True),
        ("src/*.py", "src/sub/a.py", False),
        ("src/ui/**", "src", True),
        ("src/ui/**", "src/api/**", False),
        ("tests/unit/test_?.py", "tests/unit/test_a.py", True),
        ("life_graph/api/x.py", "tests/unit/test_x.py", False),
        (".", "anything.py", True),
    ],
)
def test_paths_overlap(a, b, overlap):
    assert paths_overlap(a, b) is overlap
    assert paths_overlap(b, a) is overlap


def test_an_undeclared_scope_overlaps_everything():
    assert scopes_overlap([], ["a.py"]) is True
    assert scopes_overlap(["a.py"], ["b.py"]) is False


def test_overlapping_tasks_depend_on_the_earlier_ones():
    scopes = [["a.py"], ["b.py"], ["a.py", "c.py"], [], ["d/**"]]
    # The undeclared one (3) waits for everything before it, and what follows it
    # waits for it.
    assert overlap_dependencies(scopes) == [[], [], [0], [0, 1, 2], [3]]
    assert parallel_waves(scopes) == [[0, 1], [2], [3], [4]]
    assert parallel_waves([["a"], ["b"], ["a"], ["c/**"]]) == [[0, 1, 3], [2]]


def test_plan_tasks_declare_files():
    assert parse_task_files("Add parser (AC-1) Files: life_graph/x.py, tests/unit/test_x.py") == [
        "life_graph/x.py",
        "tests/unit/test_x.py",
    ]
    assert parse_task_files("UI **Files:** `src/ui/**`, src/app.ts.") == ["src/ui/**", "src/app.ts"]
    assert parse_task_files("Scope: docs/") == ["docs/"]
    assert parse_task_files("No scope here") == []


def test_the_plan_prompt_asks_for_files_only_when_parallel_plans_are_on():
    assert "Files:" not in plan_only_prefix(False)
    assert "Files:" in plan_only_prefix(True)


def test_team_mode_is_off_by_default(monkeypatch):
    items = ["one Files: a.py", "two Files: b.py"]
    assert settings.driver_team_max_parallel == 1
    assert teams.team_mode(items) is False  # default: sequential, unchanged
    monkeypatch.setattr(settings, "driver_team_max_parallel", 3)
    assert teams.team_mode(items) is True
    assert teams.team_mode(["one", "two"]) is False  # nothing declared: as before
    assert teams.team_mode(["only Files: a.py"]) is False


# ── Fan-out from the plan approval ──────────────────────────────


class _Store(FakeSession):
    """A session that also finds what was added (session.get by id)."""

    async def get(self, model, pk, **_k):
        return next((o for o in self.added if getattr(o, "id", None) == pk), None)


SPEC = (
    "**Requirements:**\nAC-1: a works — test: tests/unit/test_a.py::test_a\n"
    "AC-2: b works — test: tests/unit/test_b.py::test_b\n"
    "**Design:** two modules.\n"
    "**Tasks:**\n1. Add a (AC-1) Files: a.py\n2. Add b (AC-2) Files: b.py\n"
    "3. Wire a into b Files: a.py, b.py\n"
)


@pytest.fixture
def created(monkeypatch):
    calls: list[dict] = []

    async def fake_create(_sf, tenant_id, **kw):
        calls.append({"tenant_id": tenant_id, **kw})
        return {"id": str(uuid.uuid4())}

    async def quiet(*_a, **_k):
        return None

    monkeypatch.setattr(dev_tasks, "create_dev_task", fake_create)
    monkeypatch.setattr(dev_tasks, "_emit_bus", quiet)
    return calls


async def _approve_plan(monkeypatch, store):
    from life_graph.services import approvals as approvals_mod
    from life_graph.services.approvals import ApprovalService

    project = SimpleNamespace(id=uuid.uuid4(), name="p")

    async def scoped(*_a, **_k):
        return project

    monkeypatch.setattr(approvals_mod, "get_scoped", scoped)
    monkeypatch.setattr("life_graph.storage.database.async_session", session_factory(store))
    appr = SimpleNamespace(
        payload={"project_id": str(project.id), "instruction": "Build a and b",
                 "spec": SPEC, "persona_name": "code-fixer", "task_id": "plan-1"},
        resolution_note="looks right",
    )  # fmt: skip
    await ApprovalService(None)._apply_driver_plan("t1", appr, True)
    return appr


async def test_default_max_parallel_keeps_todays_sequential_fan_out(monkeypatch, created):
    appr = await _approve_plan(monkeypatch, _Store())

    assert len(created) == 3
    assert [c["properties"]["plan_task_index"] for c in created] == [1, 2, 3]
    assert all("team_role" not in c["properties"] for c in created)
    assert all(c.get("depends_on") is None for c in created)
    assert "team" not in appr.payload
    assert appr.resolution_note.startswith("looks right | Queued 3 tasks")


async def test_a_plan_with_scopes_becomes_a_team(monkeypatch, created):
    monkeypatch.setattr(settings, "driver_team_max_parallel", 2)
    store = _Store()
    appr = await _approve_plan(monkeypatch, store)

    workers, integ = created[:3], created[3]
    ids = appr.payload["dispatched_task_ids"]
    assert len(ids) == 4 and appr.payload["team"]["integration_task_id"] == ids[3]
    # 1 and 2 are disjoint: no dependencies. 3 touches both: waits for both.
    assert workers[0].get("depends_on") is None and workers[1].get("depends_on") is None
    assert workers[2]["depends_on"] == ids[:2]
    assert workers[2]["properties"]["seed_from"] == ids[:2]
    for w in workers:
        p = w["properties"]
        assert p["team_role"] == "worker" and p["origin"] == "team_worker"
        assert p["team_max_parallel"] == 2 and w["start"] is False
    assert workers[0]["properties"]["acceptance_tests"] == ["tests/unit/test_a.py::test_a"]
    # The integration task waits for every worker, starts from all of them and
    # checks every criterion; it is the plan's only approval.
    assert integ["depends_on"] == ids[:3]
    assert integ["properties"]["team_role"] == "integration"
    assert integ["properties"]["seed_from"] == ids[:3]
    assert len(integ["properties"]["acceptance_tests"]) == 2
    group = next(o for o in store.added if isinstance(o, DevTaskGroup))
    assert group.kind == "team" and group.status == "running"
    assert group.properties["worker_ids"] == ids[:3]
    assert group.properties["waves"] == [[0, 1], [2]]
    assert "team of 3 parallel tasks + 1 integration task" in appr.resolution_note


# ── The claim: max_parallel, unattended slot ────────────────────


def _queued(**props) -> AgentTask:
    return AgentTask(
        id=uuid.uuid4(), tenant_id="t1", agent_name="dev_task", status="queued",
        properties={"kind": "dev_task", "run_mode": "queue", **props}, status_history=[],
        assigned_agent="code-fixer", project_id=uuid.uuid4(), title="x",
    )  # fmt: skip


@pytest.fixture
def unpaused(monkeypatch):
    async def no(_t):
        return False

    monkeypatch.setattr(dev_tasks, "autonomy_stopped", no)


def _worker(group="g1", max_parallel=2):
    return _queued(
        team_role="worker", plan_group_id=group, team_max_parallel=max_parallel,
        plan_task_index=2,
    )  # fmt: skip


async def test_the_claim_bounds_a_team_by_max_parallel(unpaused):
    worker, other = _worker(max_parallel=2), _queued(interactive=False)
    session = FakeSession([], [worker, other], [("g1", 2)])

    claimed = await dev_tasks.claim_next_queued(session_factory(session))

    assert claimed is other  # the team already runs its 2
    assert worker.status == "queued"
    assert "team_role" in sql(session.statements[2])


async def test_the_claim_starts_a_team_worker_below_its_limit_beside_other_unattended_work(
    unpaused,
):
    worker = _worker(max_parallel=3)
    session = FakeSession([], [worker], [("g1", 2)])

    claimed = await dev_tasks.claim_next_queued(session_factory(session), allow_unattended=False)

    assert claimed is worker and worker.status == "running"


async def test_plain_unattended_work_still_waits_for_the_one_unattended_slot(unpaused):
    other = _queued(interactive=False)
    claimed = await dev_tasks.claim_next_queued(
        session_factory(FakeSession([], [other])), allow_unattended=False
    )
    assert claimed is None


async def test_team_tasks_skip_the_sequential_plan_gate():
    worker = _worker()
    assert await dev_tasks._plan_gate(FakeSession(), worker) == ("ready", None, "")


# ── What a team task runs with ─────────────────────────────────


async def test_a_worker_hands_off_and_starts_from_its_dependencies():
    dep = _queued()
    dep.status = "completed"
    handoff = {"task_id": str(dep.id), "branch": "lg/task-abcd1234", "base_commit": "a" * 40,
               "head_commit": "b" * 40}  # fmt: skip
    dep.result = {"metadata": {"handoff": handoff}}
    worker = _queued(team_role="worker", seed_from=[str(dep.id)])

    opts = await dev_tasks._phase4b_options(FakeSession([dep]), worker)

    assert opts == {"handoff": "branch", "seed": {"handoffs": [handoff], "commit": True}}


async def test_the_integration_task_keeps_the_seeds_uncommitted_and_names_missing_ones():
    gone = str(uuid.uuid4())
    integ = _queued(team_role="integration", seed_from=[gone])
    opts = await dev_tasks._phase4b_options(FakeSession([]), integ)
    assert "handoff" not in opts
    assert opts["seed"]["commit"] is False
    assert opts["seed"]["handoffs"] == [{"task_id": gone, "branch": "(none)"}]


async def test_a_plain_task_runs_with_no_phase4b_options():
    session = FakeSession()
    assert await dev_tasks._phase4b_options(session, _queued()) == {}
    assert session.statements == []


# ── Team state ──────────────────────────────────────────────────


def test_decide():
    assert teams.decide("running", [("w1", "completed"), ("w2", "failed")], None) == (
        "failed", "worker w2 failed",
    )  # fmt: skip
    assert teams.decide("running", [("w1", "running")], ("queued", "queued")) == ("running", None)
    assert teams.decide("running", [("w1", "completed")], ("running", "running"))[0] == (
        "integrating"
    )
    assert teams.decide("integrating", [("w1", "completed")], ("completed", "awaiting_pr"))[0] == (
        "awaiting_approval"
    )
    assert teams.decide("integrating", [], ("failed", "failed"))[0] == "failed"


async def test_a_failing_worker_cancels_the_rest_of_its_team(monkeypatch):
    group = DevTaskGroup(
        id=uuid.uuid4(), tenant_id="t1", kind="team", status="running", properties={},
        source_ref="plan-1",
    )  # fmt: skip
    failed = _queued(team_role="worker", plan_group_id=str(group.id))
    failed.status = "failed"
    running = _queued(team_role="worker", plan_group_id=str(group.id))
    running.status = "running"
    integ = _queued(team_role="integration", plan_group_id=str(group.id))
    cancelled, events = [], []

    async def fake_cancel(_sf, tenant_id, task_id):
        cancelled.append((tenant_id, task_id))

    async def bus(name, payload):
        events.append(name)

    async def notify(change):
        events.append("notified")

    monkeypatch.setattr(dev_tasks, "request_cancel", fake_cancel)
    monkeypatch.setattr(dev_tasks, "_emit_bus", bus)
    monkeypatch.setattr(teams, "_notify_failed", notify)
    session = FakeSession([group], [failed, running, integ], [])

    changes = await teams.reconcile(session_factory(session))

    assert group.status == "failed"
    assert group.properties["reason"].startswith(f"worker {str(failed.id)[:8]} failed")
    assert sorted(cancelled) == sorted([("t1", str(running.id)), ("t1", str(integ.id))])
    assert changes[0]["status"] == "failed"
    assert events == ["TEAM_FAILED", "notified"]
    assert "tenant_id" in sql(session.statements[1])


async def test_the_team_waits_on_its_one_approval(monkeypatch):
    group = DevTaskGroup(
        id=uuid.uuid4(), tenant_id="t1", kind="team", status="integrating", properties={}
    )
    worker = _queued(team_role="worker", plan_group_id=str(group.id))
    worker.status = "completed"
    integ = _queued(team_role="integration", plan_group_id=str(group.id))
    integ.status = "completed"
    pending = Approval(
        id=uuid.uuid4(), tenant_id="t1", kind="driver_pr", status="pending",
        source_ref=str(integ.id), payload={}, title="Open PR",
    )  # fmt: skip
    events = []

    async def bus(name, payload):
        events.append(name)

    monkeypatch.setattr(dev_tasks, "_emit_bus", bus)
    await teams.reconcile(session_factory(FakeSession([group], [worker, integ], [pending])))
    assert group.status == "awaiting_approval"
    assert events == ["TEAM_AWAITING_APPROVAL"]


async def test_the_plan_view_shows_the_team(monkeypatch):
    group = DevTaskGroup(
        id=uuid.uuid4(), tenant_id="t1", kind="team", status="running",
        properties={"max_parallel": 2, "waves": [[0, 1]]},
    )  # fmt: skip
    w1 = _queued(team_role="worker", plan_group_id=str(group.id), plan_task_index=1,
                 team_files=["a.py"])  # fmt: skip
    w1.properties.update({"depends_on": [], "deps_pending": None})
    integ = _queued(team_role="integration", plan_group_id=str(group.id), plan_task_index=2)
    session = FakeSession(objects={(DevTaskGroup, group.id): group})

    view = await teams.team_view(session, "t1", [w1, integ], {})

    assert view["status"] == "running" and view["max_parallel"] == 2
    assert view["workers"][0]["files"] == ["a.py"]
    assert view["integration"]["task_id"] == str(integ.id)
    assert await teams.team_view(session, "t1", [_queued()], {}) is None
    # Another tenant's group is not shown.
    assert (await teams.team_view(session, "t2", [w1], {}))["status"] is None
