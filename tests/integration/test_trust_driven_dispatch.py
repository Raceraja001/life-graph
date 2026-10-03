"""Using the outcome record: per-project driver choice and auto-opened PRs."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from tests.integration.conftest import skip_on_db_error

TENANT = f"trust_dispatch_{uuid.uuid4().hex[:8]}"


async def _make_project(scan_metadata: dict | None = None) -> uuid.UUID:
    from life_graph.models.db import Project
    from life_graph.storage.database import async_session

    project_id = uuid.uuid4()
    async with async_session() as s:
        s.add(
            Project(
                id=project_id,
                tenant_id=TENANT,
                name=f"proj-{project_id.hex[:6]}",
                path="/tmp/does-not-need-to-exist",
                scan_metadata=scan_metadata or {},
            )
        )
        await s.commit()
    return project_id


class _Driver:
    def __init__(self, name, cost):
        self.name, self._cost = name, cost

    async def available(self):
        return True

    def capabilities(self):
        return ["code_change"]

    def cost_per_task(self):
        return self._cost


@pytest.fixture
def drivers(monkeypatch):
    from life_graph.drivers.registry import driver_registry

    cheap, pricey = (
        _Driver(f"cheap-{uuid.uuid4().hex[:4]}", 0.0),
        _Driver(f"pricey-{uuid.uuid4().hex[:4]}", 1.0),
    )
    monkeypatch.setattr(driver_registry, "_drivers", {cheap.name: cheap, pricey.name: pricey})
    return cheap, pricey


async def _record(driver, project_id, merged, failed):
    from life_graph.autonomy.trust.service import TrustScoreService
    from life_graph.storage.database import async_session

    async with async_session() as s:
        svc = TrustScoreService(s)
        for _ in range(merged):
            await svc.record_success(TENANT, driver, "dev_task", str(project_id))
        for _ in range(failed):
            await svc.record_failure(TENANT, driver, "dev_task", str(project_id))
        await s.commit()


@pytest.mark.asyncio
@skip_on_db_error
async def test_track_record_counts_outcomes():
    from life_graph.services.dev_outcomes import track_record
    from life_graph.storage.database import async_session

    project = uuid.uuid4()
    await _record("drv", project, merged=2, failed=1)
    async with async_session() as s:
        rec = await track_record(s, TENANT, "drv", project)
        none = await track_record(s, TENANT, "drv", uuid.uuid4())
    assert (rec["merged"], rec["failed"], rec["established"]) == (2, 1, True)
    assert rec["merge_rate"] == pytest.approx(2 / 3)
    assert (none["total"], none["merge_rate"], none["established"]) == (0, None, False)


@pytest.mark.asyncio
@skip_on_db_error
async def test_driver_with_poor_record_is_skipped_only_on_that_project(drivers):
    from life_graph.drivers.dispatcher import TaskDispatcher
    from life_graph.storage.database import async_session

    cheap, pricey = drivers
    bad_project, other_project = uuid.uuid4(), uuid.uuid4()
    await _record(cheap.name, bad_project, merged=1, failed=3)

    d = TaskDispatcher(session_factory=async_session)
    async with async_session() as s:
        on_bad = await d._select_driver("code_change", None, TENANT, s, project_id=bad_project)
        on_other = await d._select_driver("code_change", None, TENANT, s, project_id=other_project)
    assert on_bad is pricey
    assert on_other is cheap  # the record is per project


@pytest.mark.asyncio
@skip_on_db_error
async def test_auto_persona_pin_means_choose(drivers):
    from types import SimpleNamespace

    from life_graph.drivers.dispatcher import TaskDispatcher
    from life_graph.storage.database import async_session

    cheap, _ = drivers
    persona = SimpleNamespace(driver="auto", properties={})
    d = TaskDispatcher(session_factory=async_session)
    async with async_session() as s:
        chosen = await d._select_driver(
            "code_change", "code-fixer-auto", TENANT, s, persona=persona, project_id=uuid.uuid4()
        )
    assert chosen is cheap


@pytest_asyncio.fixture
async def landing(monkeypatch):
    from types import SimpleNamespace

    from life_graph.services import github_pr

    async def fake_describe(repo_path, branch):
        return {"head_commit": "a" * 40, "base_commit": "b" * 40, "base_branch": "master"}

    monkeypatch.setattr(github_pr, "describe_landing", fake_describe)
    opened, merged = [], []

    async def fake_open(payload):
        opened.append(payload["branch"])
        return {"pr_url": "https://github.com/me/r/pull/77", "existing": False}

    async def fake_merge(payload):
        merged.append(payload.get("pr_url"))
        return {"merge_commit": "c" * 40}

    monkeypatch.setattr(github_pr, "open_pull_request", fake_open)
    monkeypatch.setattr(github_pr, "merge_pull_request", fake_merge)
    return SimpleNamespace(opened=opened, merged=merged)


async def _land(driver_name, project_id, auto_open_pr, auto_merge=False, verified=True):
    from life_graph.core.events import event_bus
    from life_graph.drivers.base import DriverResult
    from life_graph.drivers.dispatcher import TaskDispatcher
    from life_graph.models.db import Approval
    from life_graph.storage.database import async_session

    task_id = str(uuid.uuid4())
    # Wired like production (dev_tasks.py's real TaskDispatcher construction),
    # not left as the no-op default -- otherwise _emit() silently drops every
    # APPROVAL_FILED a test might want to observe.
    d = TaskDispatcher(session_factory=async_session, event_bus=event_bus)
    async with async_session() as s:
        await d._create_pr_approval(
            tenant_id=TENANT,
            task_id=task_id,
            driver_name=driver_name,
            instruction="Small fix",
            result=DriverResult(success=True, output="done"),
            branch=f"lg/task-{task_id[:8]}",
            repo_path="/mnt/h/DevTools/Projects/demo",
            checks=["build_ok_diff"],
            project_id=project_id,
            session=s,
            verified=verified,
            auto_open_pr=auto_open_pr,
            auto_merge=auto_merge,
        )
        await s.commit()
        rows = (
            (
                await s.execute(
                    select(Approval).where(
                        Approval.tenant_id == TENANT, Approval.source_ref == task_id
                    )
                )
            )
            .scalars()
            .all()
        )
    return {a.kind: a for a in rows}


@pytest.mark.asyncio
@skip_on_db_error
async def test_proven_driver_gets_pr_opened_but_merge_still_asks(landing):
    """auto_open_pr alone opens the PR; merging stays a separate opt-in
    (auto_merge, tested below) and defaults off even for a proven driver."""
    project = uuid.uuid4()
    await _record("trusted", project, merged=4, failed=0)
    approvals = await _land("trusted", project, auto_open_pr=True)
    pr, merge = approvals["driver_pr"], approvals["driver_merge"]
    assert (pr.status, pr.resolved_by) == ("approved", "auto: trusted driver")
    assert pr.payload["pr_url"].endswith("/pull/77") and pr.payload["auto_opened"]
    assert merge.status == "pending"
    assert len(landing.opened) == 1
    assert landing.merged == []


@pytest.mark.asyncio
@skip_on_db_error
@pytest.mark.parametrize(
    "merged, failed, opted_in",
    [
        (4, 0, False),  # proven, but the project did not opt in
        (2, 0, True),  # opted in, record not established yet
        (3, 2, True),  # established but merge rate 60% < 80%
    ],
)
async def test_pr_approval_stays_pending_unless_earned_and_opted_in(
    landing, merged, failed, opted_in
):
    project = uuid.uuid4()
    name = f"drv-{uuid.uuid4().hex[:6]}"
    await _record(name, project, merged=merged, failed=failed)
    approvals = await _land(name, project, auto_open_pr=opted_in)
    assert approvals["driver_pr"].status == "pending"
    assert "driver_merge" not in approvals
    assert landing.opened == []


# ── auto_merge: a second, separate opt-in from auto_open_pr ──


@pytest.mark.asyncio
@skip_on_db_error
async def test_auto_merge_fires_after_an_auto_opened_pr(landing):
    """Both flags on, trust earned: the PR opens AND the merge approval it
    files resolves immediately too — the full unattended path."""
    project = uuid.uuid4()
    await _record("trusted", project, merged=4, failed=0)
    approvals = await _land("trusted", project, auto_open_pr=True, auto_merge=True)
    pr, merge = approvals["driver_pr"], approvals["driver_merge"]
    assert (pr.status, pr.payload["auto_opened"]) == ("approved", True)
    assert (merge.status, merge.resolved_by) == ("approved", "auto: trusted driver")
    assert merge.payload["merge_commit"] == "c" * 40
    assert landing.opened == [pr.payload["branch"]]
    assert landing.merged == ["https://github.com/me/r/pull/77"]


@pytest.mark.asyncio
@skip_on_db_error
async def test_auto_merge_without_auto_open_pr_still_fires_on_manual_pr_approval(landing):
    """The other path: a human approves driver_pr normally (auto_open_pr is
    off), but the project opted into auto_merge — the merge approval that
    approving driver_pr files should still resolve itself, same trust bar."""
    from life_graph.services.approvals import ApprovalService
    from life_graph.storage.database import async_session

    project = uuid.uuid4()
    await _record("trusted", project, merged=4, failed=0)
    approvals = await _land("trusted", project, auto_open_pr=False, auto_merge=True)
    pr = approvals["driver_pr"]
    assert pr.status == "pending"  # opening still asked, as intended

    async with async_session() as s:
        result = await ApprovalService(s).resolve(TENANT, str(pr.id), "approve")
        await s.commit()
    assert result["status"] == "approved"
    assert landing.opened == [pr.payload["branch"]]
    assert landing.merged == ["https://github.com/me/r/pull/77"]  # merge fired too


@pytest.mark.asyncio
@skip_on_db_error
async def test_unverified_landing_never_auto_merges_even_with_earned_trust(landing):
    """A branch landed off an inconclusive verifier chain (verified=False)
    must never auto-open or auto-merge, no matter how trusted the driver is
    on this project — that trust bar is reserved for work actually checked."""
    project = uuid.uuid4()
    await _record("trusted", project, merged=4, failed=0)
    approvals = await _land(
        "trusted", project, auto_open_pr=True, auto_merge=True, verified=False
    )
    pr = approvals["driver_pr"]
    assert pr.status == "pending"  # not auto-opened despite earned trust
    assert pr.title.startswith("Open PR (UNVERIFIED)")
    assert "driver_merge" not in approvals
    assert landing.opened == []
    assert landing.merged == []

    # Even a human manually approving the PR step must not cascade into an
    # unattended merge.
    from life_graph.services.approvals import ApprovalService
    from life_graph.storage.database import async_session

    async with async_session() as s:
        result = await ApprovalService(s).resolve(TENANT, str(pr.id), "approve")
        await s.commit()
    assert result["status"] == "approved"
    assert landing.opened == [pr.payload["branch"]]
    assert landing.merged == []  # merge left pending — never checked, never auto-merged


@pytest.mark.asyncio
@skip_on_db_error
async def test_auto_merge_opted_in_but_trust_not_yet_earned_leaves_merge_pending(landing):
    from life_graph.services.approvals import ApprovalService
    from life_graph.storage.database import async_session

    project = uuid.uuid4()
    name = f"drv-{uuid.uuid4().hex[:6]}"
    await _record(name, project, merged=1, failed=0)  # not established (< 3)
    approvals = await _land(name, project, auto_open_pr=False, auto_merge=True)
    pr = approvals["driver_pr"]

    async with async_session() as s:
        result = await ApprovalService(s).resolve(TENANT, str(pr.id), "approve")
        await s.commit()
    assert result["status"] == "approved"  # the PR-open step itself, not the merge
    assert landing.opened == [pr.payload["branch"]]


# ── driver_deploy: a third, never-trust-gated opt-in ──


async def _merge_through(name, project_id, auto_open_pr, auto_merge):
    """Land, open-PR-approve and merge-approve a task, returning the
    (committed) approvals row keyed by kind -- including driver_deploy if
    the project's opt-in filed one."""
    from life_graph.services.approvals import ApprovalService
    from life_graph.storage.database import async_session

    approvals = await _land(name, project_id, auto_open_pr=auto_open_pr, auto_merge=auto_merge)
    async with async_session() as s:
        svc = ApprovalService(s)
        if approvals["driver_pr"].status == "pending":
            await svc.resolve(TENANT, str(approvals["driver_pr"].id), "approve")
        await s.commit()

    rows = await _approvals_for_task(approvals["driver_pr"].payload["task_id"])
    if rows.get("driver_merge", {}).get("status") == "pending":
        async with async_session() as s:
            await ApprovalService(s).resolve(TENANT, str(rows["driver_merge"]["id"]), "approve")
            await s.commit()
    return await _approvals_for_task(approvals["driver_pr"].payload["task_id"])


async def _approvals_for_task(task_id: str) -> dict:
    from life_graph.models.db import Approval
    from life_graph.storage.database import async_session

    async with async_session() as s:
        rows = (
            (await s.execute(select(Approval).where(Approval.source_ref == task_id)))
            .scalars()
            .all()
        )
    return {
        a.kind: {"id": a.id, "status": a.status, "payload": a.payload, "detail": a.detail}
        for a in rows
    }


@pytest.mark.asyncio
@skip_on_db_error
async def test_deploy_approval_filed_after_merge_when_project_opted_in(landing):
    project = await _make_project({"deploy_on_merge": True, "deploy_command": "echo deployed"})
    await _record("trusted", project, merged=4, failed=0)

    rows = await _merge_through("trusted", project, auto_open_pr=False, auto_merge=False)

    assert rows["driver_merge"]["status"] == "approved"
    assert "driver_deploy" in rows
    assert rows["driver_deploy"]["status"] == "pending"  # never auto-approved
    assert rows["driver_deploy"]["payload"]["deploy_command"] == "echo deployed"
    # The actual command must be visible in `detail` -- the only field every
    # approvals surface (dashboard, mobile) renders; `payload` alone would
    # leave a human approving blind.
    assert "echo deployed" in rows["driver_deploy"]["detail"]


@pytest.mark.asyncio
@skip_on_db_error
async def test_no_deploy_approval_when_project_did_not_opt_in(landing):
    project = await _make_project({})  # no deploy_on_merge, no deploy_command
    await _record("trusted", project, merged=4, failed=0)

    rows = await _merge_through("trusted", project, auto_open_pr=False, auto_merge=False)

    assert rows["driver_merge"]["status"] == "approved"
    assert "driver_deploy" not in rows


@pytest.mark.asyncio
@skip_on_db_error
async def test_deploy_never_auto_approved_even_with_full_auto_open_and_merge(landing):
    """Full unattended path (auto_open_pr + auto_merge, trust earned) still
    leaves driver_deploy sitting pending -- there is no auto_deploy."""
    project = await _make_project({"deploy_on_merge": True, "deploy_command": "echo deployed"})
    await _record("trusted", project, merged=4, failed=0)

    approvals = await _land("trusted", project, auto_open_pr=True, auto_merge=True)
    # auto_open_pr + auto_merge + earned trust already resolves BOTH driver_pr
    # and driver_merge unattended (covered by test_auto_merge_fires_after_an_
    # auto_opened_pr) -- the only new thing to check is what happens next.
    rows = await _approvals_for_task(approvals["driver_pr"].payload["task_id"])
    assert rows["driver_merge"]["status"] == "approved"
    assert rows["driver_deploy"]["status"] == "pending"


@pytest.mark.asyncio
@skip_on_db_error
async def test_apply_driver_deploy_runs_the_configured_command(tmp_path):
    from life_graph.models.db import Approval
    from life_graph.services.approvals import ApprovalService
    from life_graph.storage.database import async_session
    from life_graph.tools._guards import confine_to

    marker = tmp_path / "deployed.txt"
    async with async_session() as s:
        appr = Approval(
            tenant_id=TENANT,
            kind="driver_deploy",
            title="Deploy test",
            source="driver_deploy",
            source_ref=str(uuid.uuid4()),
            payload={
                "repo_path": str(tmp_path),
                "deploy_command": f"echo hi > {marker.name}",
            },
        )
        s.add(appr)
        await s.commit()
        await s.refresh(appr)
        appr_id = str(appr.id)

        with confine_to(tmp_path):
            result = await ApprovalService(s).resolve(TENANT, appr_id, "approve")
        await s.commit()

    assert result["status"] == "approved"
    assert marker.is_file()
    assert "deployed_at" in result["payload"]


@pytest.mark.asyncio
@skip_on_db_error
async def test_apply_driver_deploy_failure_leaves_it_pending(tmp_path):
    from life_graph.models.db import Approval
    from life_graph.services.approvals import ApprovalActionError, ApprovalService
    from life_graph.storage.database import async_session
    from life_graph.tools._guards import confine_to

    async with async_session() as s:
        appr = Approval(
            tenant_id=TENANT,
            kind="driver_deploy",
            title="Deploy test",
            source="driver_deploy",
            source_ref=str(uuid.uuid4()),
            payload={"repo_path": str(tmp_path), "deploy_command": "exit 1"},
        )
        s.add(appr)
        await s.commit()
        await s.refresh(appr)
        appr_id = str(appr.id)

        with confine_to(tmp_path), pytest.raises(ApprovalActionError):
            await ApprovalService(s).resolve(TENANT, appr_id, "approve")
        await s.rollback()

    async with async_session() as s:
        reloaded = await s.get(Approval, uuid.UUID(appr_id))
        assert reloaded.status == "pending"


# ── driver_plan: approving dispatches instruction + spec as a real task ──


@pytest.mark.asyncio
@skip_on_db_error
async def test_approving_driver_plan_dispatches_a_combined_task(monkeypatch):
    import life_graph.services.dev_tasks as dev_tasks_mod
    from life_graph.models.db import Approval
    from life_graph.services.approvals import ApprovalService
    from life_graph.storage.database import async_session

    project = await _make_project()
    task_id = str(uuid.uuid4())

    calls = []

    async def _fake_create_dev_task(_session_factory, tenant_id, **kwargs):
        calls.append({"tenant_id": tenant_id, **kwargs})
        return {"id": "new-task-id"}

    monkeypatch.setattr(dev_tasks_mod, "create_dev_task", _fake_create_dev_task)

    async with async_session() as s:
        appr = Approval(
            tenant_id=TENANT,
            kind="driver_plan",
            title="Review plan",
            source="driver_plan",
            source_ref=task_id,
            payload={
                "task_id": task_id,
                "driver": "local",
                "instruction": "Add a helper function",
                "spec": "**Tasks:** 1. add function",
                "project_id": str(project),
                "persona_name": "code-fixer-local",
            },
        )
        s.add(appr)
        await s.commit()
        await s.refresh(appr)
        appr_id = str(appr.id)

        result = await ApprovalService(s).resolve(TENANT, appr_id, "approve")
        await s.commit()

    assert result["status"] == "approved"
    assert result["payload"]["dispatched_task_id"] == "new-task-id"
    assert len(calls) == 1
    call = calls[0]
    assert call["persona_name"] == "code-fixer-local"
    assert call["task_type"] == "code_change"
    assert "Add a helper function" in call["instruction"]
    assert "**Tasks:** 1. add function" in call["instruction"]
    assert call["properties"]["plan_task_id"] == task_id


@pytest.mark.asyncio
@skip_on_db_error
async def test_rejecting_driver_plan_is_a_plain_noop(monkeypatch):
    import life_graph.services.dev_tasks as dev_tasks_mod
    from life_graph.models.db import Approval
    from life_graph.services.approvals import ApprovalService
    from life_graph.storage.database import async_session

    project = await _make_project()

    async def _should_not_be_called(*_a, **_k):
        raise AssertionError("create_dev_task must not run on reject")

    monkeypatch.setattr(dev_tasks_mod, "create_dev_task", _should_not_be_called)

    async with async_session() as s:
        appr = Approval(
            tenant_id=TENANT,
            kind="driver_plan",
            title="Review plan",
            source="driver_plan",
            source_ref=str(uuid.uuid4()),
            payload={
                "task_id": str(uuid.uuid4()),
                "driver": "local",
                "instruction": "Add a helper function",
                "spec": "**Tasks:** 1. add function",
                "project_id": str(project),
                "persona_name": "code-fixer-local",
            },
        )
        s.add(appr)
        await s.commit()
        await s.refresh(appr)
        appr_id = str(appr.id)

        result = await ApprovalService(s).resolve(TENANT, appr_id, "reject")
        await s.commit()

    assert result["status"] == "rejected"


@pytest.mark.asyncio
@skip_on_db_error
async def test_approving_a_multi_task_plan_fans_out_queued_in_order(monkeypatch):
    """A spec with 2+ parsed tasks becomes that many QUEUED (not started)
    child tasks, sharing a plan_group_id, numbered in order -- run_queue()
    (already running as an API lifespan task) is what actually runs them
    one at a time, so _apply_driver_plan itself only needs to queue them
    in the right order."""
    import life_graph.services.dev_tasks as dev_tasks_mod
    from life_graph.models.db import Approval
    from life_graph.services.approvals import ApprovalService
    from life_graph.storage.database import async_session

    project = await _make_project()
    calls = []

    async def _fake_create_dev_task(_session_factory, tenant_id, **kwargs):
        calls.append(kwargs)
        return {"id": f"task-{len(calls)}"}

    monkeypatch.setattr(dev_tasks_mod, "create_dev_task", _fake_create_dev_task)

    async with async_session() as s:
        appr = Approval(
            tenant_id=TENANT,
            kind="driver_plan",
            title="Review plan",
            source="driver_plan",
            source_ref=str(uuid.uuid4()),
            payload={
                "task_id": str(uuid.uuid4()),
                "driver": "local",
                "instruction": "Add a reporting feature",
                "spec": "**Tasks:** 1. Add the model 2. Add the endpoint 3. Add tests",
                "project_id": str(project),
                "persona_name": "code-fixer-local",
            },
        )
        s.add(appr)
        await s.commit()
        await s.refresh(appr)
        appr_id = str(appr.id)

        result = await ApprovalService(s).resolve(TENANT, appr_id, "approve")
        await s.commit()

    assert len(calls) == 3
    assert all(c["start"] is False for c in calls)  # queued, not started immediately
    group_ids = {c["properties"]["plan_group_id"] for c in calls}
    assert len(group_ids) == 1  # all three share one group
    assert [c["properties"]["plan_task_index"] for c in calls] == [1, 2, 3]
    assert all(c["properties"]["plan_task_count"] == 3 for c in calls)
    assert "Add the model" in calls[0]["instruction"]
    assert "Add the endpoint" in calls[1]["instruction"]
    assert "Add tests" in calls[2]["instruction"]
    # Full spec stays attached to each task as context, not just its own item.
    assert "Add the endpoint" in calls[0]["instruction"]  # task 1 sees the whole plan too

    assert result["status"] == "approved"
    assert result["payload"]["dispatched_task_ids"] == ["task-1", "task-2", "task-3"]
    assert result["payload"]["plan_group_id"] in group_ids


@pytest.mark.asyncio
@skip_on_db_error
async def test_single_parsed_task_falls_back_to_one_combined_dispatch(monkeypatch):
    import life_graph.services.dev_tasks as dev_tasks_mod
    from life_graph.models.db import Approval
    from life_graph.services.approvals import ApprovalService
    from life_graph.storage.database import async_session

    project = await _make_project()
    calls = []

    async def _fake_create_dev_task(_session_factory, tenant_id, **kwargs):
        calls.append(kwargs)
        return {"id": "only-task"}

    monkeypatch.setattr(dev_tasks_mod, "create_dev_task", _fake_create_dev_task)

    async with async_session() as s:
        appr = Approval(
            tenant_id=TENANT,
            kind="driver_plan",
            title="Review plan",
            source="driver_plan",
            source_ref=str(uuid.uuid4()),
            payload={
                "task_id": str(uuid.uuid4()),
                "driver": "local",
                "instruction": "Fix the typo",
                "spec": "**Tasks:** 1. Fix the typo in README",
                "project_id": str(project),
                "persona_name": "code-fixer-local",
            },
        )
        s.add(appr)
        await s.commit()
        await s.refresh(appr)
        appr_id = str(appr.id)

        result = await ApprovalService(s).resolve(TENANT, appr_id, "approve")
        await s.commit()

    assert len(calls) == 1
    assert calls[0].get("start", True) is True  # started immediately, not queued
    assert result["payload"]["dispatched_task_id"] == "only-task"
    assert "dispatched_task_ids" not in result["payload"]


# ── APPROVAL_FILED: every producer actually notifies, auto-resolved ones don't ──


@pytest.fixture
def _captured_approval_events():
    from life_graph.core.events import Event, EventType, event_bus

    captured: list[Event] = []

    async def _capture(event: Event) -> None:
        captured.append(event)

    event_bus.subscribe(EventType.APPROVAL_FILED, _capture)
    try:
        yield captured
    finally:
        event_bus.unsubscribe(EventType.APPROVAL_FILED, _capture)


@pytest.mark.asyncio
@skip_on_db_error
async def test_manual_flow_emits_approval_filed_for_every_stage(landing, _captured_approval_events):
    """driver_pr (via landing), driver_merge (via approving driver_pr), and
    driver_deploy (via approving driver_merge) each file a pending approval
    along this fully-manual path -- each one must actually notify."""
    project = await _make_project({"deploy_on_merge": True, "deploy_command": "echo deployed"})
    await _record("trusted", project, merged=4, failed=0)

    await _merge_through("trusted", project, auto_open_pr=False, auto_merge=False)

    kinds = [e.payload["kind"] for e in _captured_approval_events]
    assert kinds == ["driver_pr", "driver_merge", "driver_deploy"]
    for e in _captured_approval_events:
        assert e.payload["tenant_id"] == TENANT
        assert e.payload["title"]
        assert e.payload["detail"]


@pytest.mark.asyncio
@skip_on_db_error
async def test_fully_auto_resolved_approvals_never_notify_but_deploy_still_does(
    landing, _captured_approval_events
):
    """Full unattended path (auto_open_pr + auto_merge, trust earned):
    driver_pr and driver_merge both auto-resolve and must NOT trigger a
    false "approval needed" alert for something already approved --
    driver_deploy is never trust-gated, so it must still notify."""
    project = await _make_project({"deploy_on_merge": True, "deploy_command": "echo deployed"})
    await _record("trusted", project, merged=4, failed=0)

    await _land("trusted", project, auto_open_pr=True, auto_merge=True)

    kinds = [e.payload["kind"] for e in _captured_approval_events]
    assert kinds == ["driver_deploy"]
