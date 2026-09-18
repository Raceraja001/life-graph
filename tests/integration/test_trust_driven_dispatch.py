"""Using the outcome record: per-project driver choice and auto-opened PRs."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from tests.integration.conftest import skip_on_db_error

TENANT = f"trust_dispatch_{uuid.uuid4().hex[:8]}"


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


async def _land(driver_name, project_id, auto_open_pr, auto_merge=False):
    from life_graph.drivers.base import DriverResult
    from life_graph.drivers.dispatcher import TaskDispatcher
    from life_graph.models.db import Approval
    from life_graph.storage.database import async_session

    task_id = str(uuid.uuid4())
    d = TaskDispatcher(session_factory=async_session)
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
    assert landing.merged == []  # merge left for a human — record isn't established yet
