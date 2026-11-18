"""The dev-task runner against a real database (work order Stage 3).

- every start goes through the runner (a process without it only queues);
- start_now work is claimed ahead of older unattended work;
- a cancel stops a running task and records ``cancelled``;
- the lease heartbeat is an atomic merge (never clobbers checkpoints);
- a verified run interrupted before landing is landed from its kept
  worktree with no second agent run — and re-run if the worktree changed;
- landed work whose PR approval was lost gets exactly one approval.
"""

from __future__ import annotations

import asyncio
import hashlib
import subprocess
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select

from tests.integration.conftest import skip_on_db_error

TENANT = f"dev_runner_{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture
async def project(monkeypatch):
    from life_graph.api.dependencies import get_persona_service, get_project_registry
    from life_graph.config import settings

    monkeypatch.setattr(settings, "tool_fs_roots", str(Path.cwd()))
    await get_persona_service().seed_builtins(TENANT)
    return await get_project_registry().register(
        TENANT, {"name": f"proj-{uuid.uuid4().hex[:6]}", "path": str(Path.cwd())}
    )


@pytest.fixture
def no_local_runner():
    from life_graph.services.dev import runner as runner_mod

    previous = runner_mod.local_runner()
    runner_mod.set_local_runner(None)
    yield
    runner_mod.set_local_runner(previous)


async def _row(task_id):
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return await s.get(AgentTask, uuid.UUID(task_id))


def _runner(**kw):
    from life_graph.services.dev.runner import DevTaskRunner
    from life_graph.storage.database import async_session

    return DevTaskRunner(async_session, listen=False, **kw)


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_start_only_queues_when_this_process_is_not_the_runner(project, no_local_runner):
    """The old bug: an immediate start ran in whichever API process got the
    request, lock or not. Now it is queued for the runner."""
    from life_graph.services.dev import tasks as dev_tasks
    from life_graph.storage.database import async_session

    data = await dev_tasks.create_dev_task(
        async_session, TENANT, instruction=f"Fix {uuid.uuid4().hex}", project=project,
        persona_name="code-fixer",
    )  # fmt: skip
    await asyncio.sleep(0.2)
    row = await _row(data["id"])
    assert row.status == "queued"
    assert row.properties["run_mode"] == "queue"
    assert row.properties["start_now"] is True
    assert row.properties["interactive"] is True


@pytest.mark.asyncio
@skip_on_db_error
async def test_start_now_is_claimed_before_older_unattended_work(project, no_local_runner):
    from life_graph.services.dev import tasks as dev_tasks
    from life_graph.storage.database import async_session

    nightly = await dev_tasks.create_dev_task(
        async_session, TENANT, instruction=f"Nightly {uuid.uuid4().hex}", project=project,
        persona_name="code-fixer-local", start=False, properties={"origin": "nightly"},
    )  # fmt: skip
    started = await dev_tasks.create_dev_task(
        async_session, TENANT, instruction=f"Now {uuid.uuid4().hex}", project=project,
        persona_name="code-fixer",
    )  # fmt: skip
    claimed = []
    while True:
        task = await dev_tasks.claim_next_queued(async_session, runner_id="t")
        if task is None:
            break
        claimed.append(str(task.id))
    assert started["id"] in claimed
    if nightly["id"] in claimed:  # the GPU router may make it wait; then it isn't claimed
        assert claimed.index(started["id"]) < claimed.index(nightly["id"])
    row = await _row(started["id"])
    assert row.properties["lease"]["runner"] == "t"


@pytest.mark.asyncio
@skip_on_db_error
async def test_cancel_stops_a_running_task_and_records_it(project, monkeypatch, no_local_runner):
    from life_graph.drivers.dispatcher import TaskDispatcher
    from life_graph.services.dev import tasks as dev_tasks
    from life_graph.storage.database import async_session

    entered, killed = asyncio.Event(), asyncio.Event()

    async def slow_dispatch(self, **kw):
        entered.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            killed.set()  # where a driver kills its process group / container
            raise

    monkeypatch.setattr(TaskDispatcher, "dispatch_task", slow_dispatch)
    data = await dev_tasks.create_dev_task(
        async_session, TENANT, instruction=f"Slow {uuid.uuid4().hex}", project=project,
        persona_name="code-fixer",
    )  # fmt: skip
    runner = _runner()
    await runner.fill()
    assert data["id"] in runner.running
    await asyncio.wait_for(entered.wait(), 5)

    state = await dev_tasks.request_cancel(async_session, TENANT, data["id"])
    assert state["cancel"] == "requested"
    assert await runner.check_cancels() == [data["id"]]
    await asyncio.wait_for(killed.wait(), 5)
    for _ in range(50):
        if not runner.running:
            break
        await asyncio.sleep(0.05)
    row = await _row(data["id"])
    assert row.status == "cancelled"
    assert row.status_history[-1]["note"] == "cancelled while running"


@pytest.mark.asyncio
@skip_on_db_error
async def test_cancel_of_a_queued_task_is_immediate_and_tenant_checked(project, no_local_runner):
    from life_graph.services.dev import tasks as dev_tasks
    from life_graph.storage.database import async_session

    data = await dev_tasks.create_dev_task(
        async_session, TENANT, instruction=f"Later {uuid.uuid4().hex}", project=project,
        persona_name="code-fixer-local", start=False,
    )  # fmt: skip
    assert await dev_tasks.request_cancel(async_session, "someone-else", data["id"]) is None
    state = await dev_tasks.request_cancel(async_session, TENANT, data["id"])
    assert state == {"id": data["id"], "status": "cancelled", "cancel": "done"}
    again = await dev_tasks.request_cancel(async_session, TENANT, data["id"])
    assert again["cancel"] == "not_cancellable"


@pytest.mark.asyncio
@skip_on_db_error
async def test_heartbeat_merges_the_lease_without_clobbering_checkpoints(project):
    from life_graph.models.db import AgentTask
    from life_graph.services.dev import tasks as dev_tasks
    from life_graph.storage.database import async_session

    data = await dev_tasks.create_dev_task(
        async_session, TENANT, instruction=f"Beat {uuid.uuid4().hex}", project=project,
        persona_name="code-fixer-local", start=False,
    )  # fmt: skip
    async with async_session() as s:
        row = await s.get(AgentTask, uuid.UUID(data["id"]))
        row.status = "running"
        row.properties = {
            **row.properties,
            "checkpoints": {"keep": True},
            "lease": {"claimed_at": "x"},
        }
        await s.commit()
    runner = _runner(runner_id="beat-runner")
    runner._running[data["id"]] = asyncio.get_running_loop().create_future()
    try:
        await runner.heartbeat()
    finally:
        runner._running.clear()
    row = await _row(data["id"])
    assert row.properties["checkpoints"] == {"keep": True}
    assert row.properties["lease"]["runner"] == "beat-runner"
    assert row.properties["lease"]["claimed_at"] == "x"
    assert row.properties["lease"]["heartbeat_at"]


# ── Land-only resume ──────────────────────────────────────────


def _git(cwd, *args):
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout  # fmt: skip


@pytest.fixture
def verified_worktree(tmp_path):
    """An origin repo and a worktree off it holding a verified (uncommitted) change."""
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(origin, "init", "-q")
    (origin / "app.py").write_text("x = 1\n")
    _git(origin, "add", ".")
    _git(origin, "commit", "-qm", "init")
    wt = tmp_path / "wt"
    _git(origin, "worktree", "add", "-q", "--detach", str(wt))
    (wt / "app.py").write_text("x = 2\n")
    return origin, wt


async def _resume_point(wt, origin):
    from life_graph.drivers.workdir import diff_against_head

    diff = await diff_against_head(wt)
    return {
        "worktree": str(wt),
        "worktree_origin": str(origin),
        "diff_sha256": hashlib.sha256(diff.encode()).hexdigest(),
        "driver": "claude_code",
        "verify_chain": [],
        "output": "Set x to 2.",
        "files_changed": ["app.py"],
    }


async def _resume(project, task_id, saved):
    from life_graph.core.events import event_bus
    from life_graph.drivers.dispatcher import TaskDispatcher
    from life_graph.storage.database import async_session

    async with async_session() as session:
        result = await TaskDispatcher(
            session_factory=async_session, event_bus=event_bus
        ).resume_landing(
            tenant_id=TENANT, task_id=task_id, instruction="Set x to 2",
            task_type="code_change", project_id=project["id"], persona_name="code-fixer",
            session=session, saved=saved,
        )  # fmt: skip
        await session.commit()
    return result


async def _approvals(task_id):
    from life_graph.models.db import Approval
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return (
            (await s.execute(select(Approval).where(Approval.source_ref == task_id)))
            .scalars()
            .all()
        )


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_verified_worktree_is_landed_without_another_agent_run(
    project, verified_worktree, monkeypatch
):
    from life_graph.drivers.dispatcher import TaskDispatcher

    async def no_agent(*a, **k):
        raise AssertionError("a resume must not run the agent")

    monkeypatch.setattr(TaskDispatcher, "_run_driver", no_agent)
    origin, wt = verified_worktree
    task_id = str(uuid.uuid4())
    result = await _resume(project, task_id, await _resume_point(wt, origin))

    assert result is not None and result.success
    branch = result.metadata["landed_branch"]
    assert branch.startswith("lg/task-")
    assert "x = 2" in _git(origin, "show", f"{branch}:app.py")
    assert [a.kind for a in await _approvals(task_id)] == ["driver_pr"]
    assert not wt.exists()  # cleaned up after landing


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_worktree_changed_since_verification_is_not_landed(project, verified_worktree):
    origin, wt = verified_worktree
    saved = await _resume_point(wt, origin)
    (wt / "app.py").write_text("x = 3  # changed after it was verified\n")
    task_id = str(uuid.uuid4())

    assert await _resume(project, task_id, saved) is None
    assert await _approvals(task_id) == []
    assert "lg/task-" not in _git(origin, "branch", "--list")


@pytest.mark.asyncio
@skip_on_db_error
async def test_landed_work_gets_exactly_one_approval(project, verified_worktree):
    origin, wt = verified_worktree
    task_id = str(uuid.uuid4())
    saved = {**await _resume_point(wt, origin), "landed_branch": f"lg/task-{task_id[:8]}"}
    _git(wt, "checkout", "-q", "-b", saved["landed_branch"])
    _git(wt, "commit", "-qam", "landed before the crash")

    first = await _resume(project, task_id, saved)
    second = await _resume(project, task_id, saved)
    assert first.success and second.success
    assert second.metadata["resumed"] == "already_landed"
    assert [a.kind for a in await _approvals(task_id)] == ["driver_pr"]


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_moved_head_is_not_landed_and_the_worktree_is_cleaned(project, verified_worktree):
    """Review 2026-11-18: the diff hash alone could match over extra commits."""
    origin, wt = verified_worktree
    saved = await _resume_point(wt, origin)
    saved["head"] = _git(wt, "rev-parse", "HEAD").strip()
    _git(wt, "stash", "-q")
    (wt / "other.py").write_text("y = 1\n")
    _git(wt, "add", "other.py")
    _git(wt, "commit", "-qm", "a commit nobody verified")
    _git(wt, "stash", "pop", "-q")
    task_id = str(uuid.uuid4())

    assert await _resume(project, task_id, saved) is None
    assert await _approvals(task_id) == []
    assert not wt.exists()  # not kept around forever


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_task_waits_while_its_project_is_at_the_wip_limit(project, no_local_runner):
    """Found by scripts/runtime_reliability.py (2026-11-18): the runner claimed a
    third task for a project already running two, and the dispatcher failed it
    ("Project WIP limit reached"). It must wait in the queue instead."""
    from life_graph.api.dependencies import get_project_registry
    from life_graph.drivers.dispatch_stats import MAX_WIP_PER_PROJECT
    from life_graph.services.dev import tasks as dev_tasks
    from life_graph.storage.database import async_session

    from life_graph.api.dependencies import get_persona_service

    # A tenant and project of their own: other tests leave rows "running" in
    # the shared ones, and the tenant limit would block this one too.
    tenant = f"wip_{uuid.uuid4().hex[:6]}"
    await get_persona_service().seed_builtins(tenant)
    project = await get_project_registry().register(
        tenant, {"name": f"wip-{uuid.uuid4().hex[:6]}", "path": str(Path.cwd())}
    )
    ids = []
    for i in range(MAX_WIP_PER_PROJECT + 1):
        d = await dev_tasks.create_dev_task(
            async_session, tenant, instruction=f"WIP {i} {uuid.uuid4().hex}", project=project,
            persona_name="code-fixer",
        )  # fmt: skip
        ids.append(d["id"])
    claimed = []
    while True:
        task = await dev_tasks.claim_next_queued(async_session, runner_id="wip")
        if task is None:
            break
        claimed.append(str(task.id))
    ours = [i for i in ids if i in claimed]
    assert len(ours) == MAX_WIP_PER_PROJECT
    waiting = next(i for i in ids if i not in claimed)
    assert (await _row(waiting)).status == "queued"


@pytest.mark.asyncio
@skip_on_db_error
async def test_tasks_of_a_full_project_never_starve_another_project(no_local_runner):
    """More blocked tasks than the claim's scan window must not hide a task
    that could run: full projects are excluded in the query itself."""
    from life_graph.api.dependencies import get_persona_service, get_project_registry
    from life_graph.drivers.dispatch_stats import MAX_WIP_PER_PROJECT
    from life_graph.models.db import AgentTask
    from life_graph.services.dev import tasks as dev_tasks
    from life_graph.storage.database import async_session

    tenant = f"starve_{uuid.uuid4().hex[:6]}"
    await get_persona_service().seed_builtins(tenant)
    reg = get_project_registry()
    full = await reg.register(tenant, {"name": f"full-{uuid.uuid4().hex[:4]}", "path": str(Path.cwd())})
    other = await reg.register(tenant, {"name": f"other-{uuid.uuid4().hex[:4]}", "path": str(Path.cwd())})
    async with async_session() as s:
        for _ in range(MAX_WIP_PER_PROJECT):  # the full project is already at its limit
            s.add(AgentTask(id=uuid.uuid4(), tenant_id=tenant, agent_name="dev_task", title="busy",
                            status="running", project_id=uuid.UUID(full["id"]),
                            properties={"kind": "dev_task"}))  # fmt: skip
        await s.commit()
    for i in range(dev_tasks._QUEUE_SCAN_LIMIT + 5):
        await dev_tasks.create_dev_task(
            async_session, tenant, instruction=f"blocked {i} {uuid.uuid4().hex}", project=full,
            persona_name="code-fixer",
        )  # fmt: skip
    wanted = await dev_tasks.create_dev_task(
        async_session, tenant, instruction=f"runnable {uuid.uuid4().hex}", project=other,
        persona_name="code-fixer",
    )  # fmt: skip
    claimed = []
    while (task := await dev_tasks.claim_next_queued(async_session, runner_id="starve")) is not None:
        claimed.append(str(task.id))
    assert wanted["id"] in claimed
