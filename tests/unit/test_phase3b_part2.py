"""Phase 3b part 2 outside the dispatch loop: the subscription budget in the
account hook, billing per account kind, parking/resuming dev tasks (incl.
after a restart), kept worktrees, continue_task and its single approval path,
and the run-health policy fields.

docs/specs/agent-drivers.md, "Phase 3b part 2". No database: FakeSession.
"""

from __future__ import annotations

import subprocess
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from life_graph.config import settings
from life_graph.drivers import accounts_hook
from life_graph.drivers.base import ContextPacket, DriverResult
from life_graph.drivers.claude_code import ClaudeCodeDriver
from life_graph.drivers.dispatcher import TaskDispatcher
from life_graph.models.agent_accounts import AgentAccountLimit
from life_graph.models.db import AgentTask, Approval
from life_graph.services.agent_accounts import budget, homes
from life_graph.services.dev import autonomy_policy as ap
from life_graph.services.dev import continuation as cont
from life_graph.services.dev import task_events
from life_graph.services.dev import tasks as dev_tasks
from tests.unit.fakes import FakeSession, session_factory
from tests.unit.test_agent_accounts import NOW, _acct, _Factory


@pytest.fixture(autouse=True)
def _quiet_events(monkeypatch):
    seen: list = []
    monkeypatch.setattr(
        task_events, "emit", lambda *a, **k: seen.append({"kind": a[2], "content": a[3], **k})
    )

    async def _flush(*_a, **_k):
        return None

    monkeypatch.setattr(task_events, "flush", _flush)

    async def _bus(name, payload):
        seen.append({"bus": name, **payload})

    monkeypatch.setattr(dev_tasks, "_emit_bus", _bus)
    return seen


@pytest.fixture
def accounts_on(monkeypatch):
    monkeypatch.setattr(settings, "driver_accounts_enabled", True)
    yield
    accounts_hook.configure(None)


@pytest.fixture
def home_root(tmp_path, monkeypatch):
    root = tmp_path / "homes"
    monkeypatch.setattr(settings, "driver_accounts_home_root", str(root))
    return root


def _limit(account, used, *, window="five_hour", resets=NOW + timedelta(hours=2), observed=NOW):
    return AgentAccountLimit(
        tenant_id="t1",
        account_id=account.id,
        window=window,
        used_percent=used,
        resets_at=resets,
        observed_at=observed,
        source="run",
    )


# ── Subscription budget (D4) ─────────────────────────────────


def test_budget_readings_ignore_reset_and_stale_windows():
    a = _acct("a")
    readings = budget.fullest(
        [a],
        [
            _limit(a, 99, resets=NOW - timedelta(minutes=1)),  # window already reset
            _limit(a, 95, window="primary", resets=None, observed=NOW - timedelta(hours=6)),
            _limit(a, 40, window="seven_day"),
        ],
        NOW,
    )
    assert readings[a.id].window == "seven_day" and readings[a.id].used_percent == 40
    assert budget.over_share(readings, 0.3) and not budget.over_share(readings, 0.9)
    assert budget.over_share(readings, 1.0) == {}


async def test_unattended_run_skips_an_account_over_its_share(accounts_on, home_root):
    a, b = _acct("a", priority=1), _acct("b", priority=2)
    b.home_dir = str(homes.ensure_home("t1", "codex", b.id))
    accounts_hook.configure(_Factory([a, b], [_limit(a, 93), _limit(b, 20)]))
    lease = await accounts_hook.acquire("codex", "t1", unattended=True, now=NOW)
    assert lease.active and lease.name == "b"
    info = lease.metadata()["budget"]
    assert info["skipped"][0]["account"] == "a" and info["used_percent"] == 20.0
    assert "a five_hour 93%" in info["reason"]


async def test_every_account_over_its_share_refuses_until_the_reset(accounts_on):
    a = _acct("a")
    accounts_hook.configure(_Factory([a], [_limit(a, 91)]))
    lease = await accounts_hook.acquire("codex", "t1", unattended=True, now=NOW)
    md = lease.refusal.metadata
    assert md["exit_status"] == "subscription_budget"
    assert md["failure"]["kind"] == "rate_limited"
    assert md["failure"]["resets_at"] == "2026-11-27T11:00:00Z"
    assert md["account_pool"] == {"state": "over_budget", "retry_at": "2026-11-27T11:00:00Z"}


async def test_attended_runs_and_share_1_are_not_budgeted(accounts_on, home_root, monkeypatch):
    a = _acct("a")
    a.home_dir = str(homes.ensure_home("t1", "codex", a.id))
    accounts_hook.configure(_Factory([a], [_limit(a, 99)]))
    lease = await accounts_hook.acquire("codex", "t1", now=NOW)
    assert lease.active and lease.budget is None
    monkeypatch.setattr(settings, "driver_accounts_subscription_max_share", 1.0)
    accounts_hook.configure(_Factory([a], [_limit(a, 99)]))
    lease = await accounts_hook.acquire("codex", "t1", unattended=True, now=NOW)
    assert lease.active


async def test_a_pinned_account_over_its_share_refuses_unattended(accounts_on):
    a = _acct("a")
    accounts_hook.configure(_Factory(a, [_limit(a, 95)]))
    lease = await accounts_hook.acquire("codex", "t1", account_id=a.id, unattended=True, now=NOW)
    assert lease.refusal.metadata["exit_status"] == "subscription_budget"


async def test_preview_reports_kind_and_decision(accounts_on, monkeypatch):
    a, k = _acct("a", priority=1), _acct("k", priority=2, kind="api_key")
    accounts_hook.configure(_Factory([a, k], [_limit(a, 95)]))
    preview = await accounts_hook.preview("codex", "t1", unattended=True, now=NOW)
    assert preview["state"] == "selected" and preview["kind"] == "api_key"
    monkeypatch.setattr(settings, "driver_accounts_enabled", False)
    assert await accounts_hook.preview("codex", "t1") is None


def test_billing_follows_the_account_kind():
    assert accounts_hook.billing_of("subscription", "api") == "subscription"
    assert accounts_hook.billing_of("api_key", "subscription") == "api"
    assert accounts_hook.billing_of("vertex", "subscription") == "api"
    assert accounts_hook.billing_of(None, "subscription") == "subscription"


class _Env:
    def apply(self, env):
        return env

    def names(self):
        return ["ANTHROPIC_API_KEY"]


@pytest.mark.parametrize(
    ("kind", "billing"), [("api_key", "api"), ("subscription", "subscription")]
)
async def test_claude_run_metadata_billing_follows_the_account(
    monkeypatch, tmp_path, kind, billing
):
    driver = ClaudeCodeDriver(binary="claude")
    stream = (
        b'{"type":"result","subtype":"success","is_error":false,"result":"ok",'
        b'"session_id":"0199c0de-0000-7000-8000-00000000c0de","total_cost_usd":0.2}\n'
    )

    async def _exec(*_a, **_k):
        return 0, stream, b""

    monkeypatch.setattr(driver, "_exec_cli", _exec)
    packet = ContextPacket(task_id=uuid.uuid4(), tenant_id="t1", task_type="code", instruction="x")
    lease = accounts_hook.AccountLease(
        driver="claude_code", tenant_id="t1", account_id=uuid.uuid4(), name="n", kind=kind,
        env=_Env(),
    )  # fmt: skip
    result = await driver._run_cli(
        packet, tmp_path, 30, "x", None, lease,
        host_mode=True, host_shell_denied=True, start=0.0, resume_id=None,
    )  # fmt: skip
    assert result.success and result.metadata["billing"] == billing
    no_account = accounts_hook.AccountLease(driver="claude_code")
    plain = await driver._run_cli(
        packet, tmp_path, 30, "x", None, no_account,
        host_mode=True, host_shell_denied=True, start=0.0, resume_id=None,
    )  # fmt: skip
    assert "billing" not in plain.metadata  # accounts off: metadata as before


# ── Run-health policy fields ─────────────────────────────────


def test_run_health_policy_defaults_off_and_bounded():
    assert ap.NEUTRAL.max_nudges == 0 and ap.NEUTRAL.max_stall_retries == 0
    assert ap.NEUTRAL.wait_for_reset is False
    eff = ap.merge({"max_nudges": 2, "max_stall_retries": 1, "wait_for_reset": True}, None)
    assert (eff.max_nudges, eff.max_stall_retries, eff.wait_for_reset) == (2, 1, True)
    # A project may override each one; null = the global value.
    eff = ap.merge({"max_nudges": 2, "wait_for_reset": True}, {"wait_for_reset": False})
    assert eff.max_nudges == 2 and eff.wait_for_reset is False
    with pytest.raises(ValueError):
        ap.GlobalAutonomyPolicy.model_validate({"max_nudges": ap.MAX_RUN_HEALTH_ROUNDS + 1})
    assert ap.limits()["bounds"]["max_stall_retries"] == {"min": 0, "max": 3}
    assert ap.describe(eff)["wait_for_reset"] is False


# ── Parking ──────────────────────────────────────────────────


def _task(status="parked", **props):
    return AgentTask(
        id=uuid.uuid4(),
        tenant_id="t1",
        agent_name="dev_task",
        project_id=uuid.uuid4(),
        instructions="fix x",
        status=status,
        task_type="code_change",
        assigned_agent="code-fixer",
        properties={"kind": "dev_task", "run_mode": "queue", **props},
        status_history=[],
        result={},
    )


@pytest.fixture
def unpaused(monkeypatch):
    async def _no(_t):
        return False

    monkeypatch.setattr(dev_tasks, "autonomy_stopped", _no)


async def _run_task(monkeypatch, task, result):
    async def _dispatch(self, **kw):
        return result

    monkeypatch.setattr(TaskDispatcher, "dispatch_task", _dispatch)
    session = FakeSession(objects={(AgentTask, task.id): task})
    await dev_tasks._run(
        session_factory(session), "t1", str(task.id), "fix x", str(task.project_id),
        "code-fixer", "code_change",
    )  # fmt: skip
    return session


def _parked_result():
    return DriverResult(
        success=False,
        error="every codex account is cooling down",
        metadata={"park": {"resume_at": "2026-11-27T12:01:00Z", "reason": "cooling"}},
    )


async def test_a_rate_limited_run_with_a_park_is_parked_not_failed(monkeypatch, _quiet_events):
    task = _task(status="queued")
    await _run_task(monkeypatch, task, _parked_result())
    assert task.status == "parked" and task.completed_at is None
    assert task.properties["park"]["resume_at"] == "2026-11-27T12:01:00Z"
    assert task.properties["park"]["count"] == 1 and task.properties["parks"] == 1
    assert any(e.get("bus") == "TASK_PARKED" for e in _quiet_events)


async def test_without_a_park_the_run_fails_as_before(monkeypatch):
    task = _task(status="queued")
    await _run_task(monkeypatch, task, DriverResult(success=False, error="rate limited"))
    assert task.status == "failed" and "park" not in task.properties


async def test_parks_are_bounded(monkeypatch):
    task = _task(status="queued", parks=dev_tasks.MAX_PARKS_PER_TASK)
    await _run_task(monkeypatch, task, _parked_result())
    assert task.status == "failed" and "not parking again" in task.error


async def test_release_parked_requeues_due_tasks_only(unpaused, _quiet_events):
    due = _task(park={"resume_at": "2026-11-27T08:59:00Z"})
    later = _task(park={"resume_at": "2026-11-27T10:00:00Z"})
    # The rows are all the state there is: a runner that just restarted reads
    # exactly these, so a park survives a restart.
    session = FakeSession([due, later])
    released = await dev_tasks.release_parked(session_factory(session), now=NOW)
    assert released == [str(due.id)]
    assert due.status == "queued" and "park" not in due.properties
    assert due.properties["unparked"]["resume_at"] == "2026-11-27T08:59:00Z"
    assert later.status == "parked" and session.commits == 1
    assert any(e.get("bus") == "TASK_UNPARKED" for e in _quiet_events)


async def test_a_paused_tenant_stays_parked(monkeypatch):
    async def _yes(_t):
        return True

    monkeypatch.setattr(dev_tasks, "autonomy_stopped", _yes)
    task = _task(park={"resume_at": "2026-11-27T08:00:00Z"})
    assert await dev_tasks.release_parked(session_factory(FakeSession([task])), now=NOW) == []
    assert task.status == "parked"


async def test_resume_now_and_not_parked(monkeypatch):
    import life_graph.services.dev.runner as runner_mod

    woke: list = []

    async def _notify(**_k):
        woke.append(1)

    monkeypatch.setattr(runner_mod, "notify_runner", _notify)
    task = _task(park={"resume_at": "2099-01-01T00:00:00Z"})
    state = await dev_tasks.resume_parked(session_factory(FakeSession(task)), "t1", str(task.id))
    assert state["resumed"] and task.status == "queued" and task.properties["start_now"]
    assert woke == [1]
    again = await dev_tasks.resume_parked(session_factory(FakeSession(task)), "t1", str(task.id))
    assert again == {"id": str(task.id), "status": "queued", "resumed": False}
    missing = await dev_tasks.resume_parked(session_factory(FakeSession(None)), "t1", str(task.id))
    assert missing is None


async def test_a_parked_task_can_be_cancelled_and_stage_says_parked():
    task = _task(park={"resume_at": "2099-01-01T00:00:00Z"})
    assert dev_tasks._stage(task, []) == "parked"
    assert dev_tasks.serialize(task, [])["park"]["resume_at"] == "2099-01-01T00:00:00Z"
    state = await dev_tasks._request_cancel(
        session_factory(FakeSession(task)), "t1", str(task.id), task.id
    )
    assert state["status"] == "cancelled" and "park" not in task.properties


async def test_runner_housekeeping_releases_parked_tasks(monkeypatch):
    from life_graph.services.dev.runner import DevTaskRunner

    calls: list = []

    async def _release(sf, **_k):
        calls.append("release")
        return []

    async def _sweep(sf, **_k):
        calls.append("sweep")
        return 0

    monkeypatch.setattr(dev_tasks, "release_parked", _release)
    monkeypatch.setattr(dev_tasks, "sweep_kept_worktrees", _sweep)
    r = DevTaskRunner(None, claim=None, run_task=None, listen=False)
    await r.housekeep(now=1000.0)
    await r.housekeep(now=1010.0)  # the sweep waits SWEEP_SECONDS
    assert calls == ["release", "sweep", "release"]


# ── Kept worktrees and continue_task ─────────────────────────


def _git_worktree(tmp_path: Path) -> tuple[Path, Path]:
    origin = tmp_path / "origin"
    origin.mkdir()
    run = lambda *a, cwd=origin: subprocess.run(  # noqa: E731
        ["git", *a], cwd=cwd, check=True, capture_output=True
    )
    run("init", "-q")
    (origin / "a.txt").write_text("a\n")
    run("add", "-A")
    run("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
    wt = tmp_path / "wt"
    run("worktree", "add", "--detach", "-q", str(wt))
    return origin, wt


@pytest.fixture
def continue_on(monkeypatch):
    monkeypatch.setattr(settings, "driver_continue_enabled", True)

    async def _no(_t):
        return False

    monkeypatch.setattr(cont, "autonomy_stopped", _no)

    async def _notify(**_k):
        return None

    monkeypatch.setattr(cont, "notify_runner", _notify)
    resumable = SimpleNamespace(name="codex", supports_resume=True)
    monkeypatch.setattr(
        cont.driver_registry, "get", lambda name: resumable if name == "codex" else None
    )


def _finished(tmp_path, **record):
    origin, wt = _git_worktree(tmp_path)
    rec = {
        "worktree": str(wt), "origin": str(origin), "driver": "codex",
        "session_id": "0199c0de-0000-7000-8000-00000000c0de", "account_id": None,
        "branch": "lg/task-abc", "rounds": 0, **record,
    }  # fmt: skip
    return _task(status="completed", continuation=rec)


async def _continue(task, approvals=None, feedback="also handle None"):
    session = FakeSession(task, approvals or [])
    return await cont.continue_task(
        session_factory(session), "t1", str(task.id), feedback, "request_changes"
    )


async def test_continue_task_queues_the_task_with_its_request(tmp_path, continue_on, _quiet_events):
    task = _finished(tmp_path)
    data = await _continue(task)
    assert data["status"] == "queued" and task.status == "queued"
    req = task.properties["continue_request"]
    assert req["feedback"] == "also handle None" and req["reason"] == "request_changes"
    assert task.properties["start_now"] and task.properties["interactive"]
    assert any(e.get("bus") == "TASK_CONTINUED" for e in _quiet_events)


@pytest.mark.parametrize(
    ("setup", "code"),
    [
        ("disabled", "continue_disabled"),
        ("missing", "not_found"),
        ("running", "busy"),
        ("parked", "busy"),
        ("cancelled", "not_continuable"),
        ("no_session", "no_session"),
        ("no_workdir", "no_workdir"),
        ("merged", "not_continuable"),
        ("bad_driver", "resume_unsupported"),
        ("empty_feedback", "no_feedback"),
    ],
)
async def test_continue_task_refusals(tmp_path, continue_on, monkeypatch, setup, code):
    task = _finished(tmp_path)
    approvals: list = []
    feedback = "more"
    if setup == "disabled":
        monkeypatch.setattr(settings, "driver_continue_enabled", False)
    elif setup == "missing":
        task = None
    elif setup in ("running", "parked", "cancelled"):
        task.status = setup
    elif setup == "no_session":
        task.properties["continuation"]["session_id"] = None
    elif setup == "no_workdir":
        task.properties["continuation"]["worktree"] = str(tmp_path / "gone")
    elif setup == "merged":
        approvals = [
            Approval(tenant_id="t1", kind="driver_pr", status="approved", source_ref=str(task.id),
                     payload={"outcome": "merged"}, created_at=NOW)
        ]  # fmt: skip
    elif setup == "bad_driver":
        task.properties["continuation"]["driver"] = "local"
    elif setup == "empty_feedback":
        feedback = "   "
    with pytest.raises(cont.ContinueError) as err:
        if task is None:
            await cont.continue_task(
                session_factory(FakeSession(None)), "t1", str(uuid.uuid4()), feedback
            )
        else:
            await _continue(task, approvals, feedback)
    assert err.value.code == code
    if task is not None and setup not in ("running", "parked", "cancelled"):
        assert task.status == "completed"  # nothing changed


async def test_sweep_keeps_open_prs_and_young_worktrees(tmp_path, monkeypatch):
    import life_graph.drivers.dispatcher as disp_mod

    removed: list = []

    async def _discard(worktree, origin):
        removed.append(str(worktree))

    monkeypatch.setattr(disp_mod, "_discard_worktree", _discard)
    monkeypatch.setattr(settings, "driver_continue_enabled", True)
    old = "2026-11-27T08:00:00Z"
    expired = _task(status="completed", continuation={"worktree": "/w1", "origin": "/o",
                                                       "keep_until": old})  # fmt: skip
    young = _task(status="completed", continuation={"worktree": "/w2", "origin": "/o",
                                                     "keep_until": "2026-11-28T08:00:00Z"})  # fmt: skip
    open_pr = _task(status="completed", continuation={"worktree": "/w3", "origin": "/o",
                                                       "keep_until": old})  # fmt: skip
    pr = Approval(tenant_id="t1", kind="driver_pr", status="approved", source_ref=str(open_pr.id),
                  payload={"pr_url": "https://github.com/o/r/pull/1"}, created_at=NOW)  # fmt: skip
    session = FakeSession([expired, young, open_pr], [pr])
    n = await dev_tasks.sweep_kept_worktrees(session_factory(session), now=NOW)
    assert n == 1 and removed == ["/w1"] and "continuation" not in expired.properties
    assert "continuation" in young.properties and "continuation" in open_pr.properties
    # Turned off: every kept worktree goes.
    monkeypatch.setattr(settings, "driver_continue_enabled", False)
    session = FakeSession([young], [])
    assert await dev_tasks.sweep_kept_worktrees(session_factory(session), now=NOW) == 1


# ── continue_dispatch (the dispatcher half) ──────────────────


class _ResumeDriver:
    name = "codex"
    supports_resume = True

    def __init__(self):
        self.resumes: list = []

    def cost_per_task(self):
        return 0.0

    async def resume(self, packet, workdir, session_id, prompt, timeout=300, *, account_id=None):
        self.resumes.append({"session": session_id, "prompt": prompt, "workdir": workdir,
                             "account": account_id})  # fmt: skip
        (Path(workdir) / "b.txt").write_text("b\n")
        return DriverResult(success=True, output="added b", metadata={"session_id": session_id})


@pytest.fixture
def continue_dispatcher(monkeypatch):
    import life_graph.drivers.continue_run as cr

    d = TaskDispatcher(session_factory=lambda: None, reviewer=object())
    seen: dict = {"steps": [], "landed": 0, "kept": []}
    driver = _ResumeDriver()
    monkeypatch.setattr(cr.driver_registry, "get", lambda name: driver if name == "codex" else None)

    async def _noop(*_a, **_k):
        return None

    async def _prepare(run, **_k):
        run.packet = ContextPacket(
            task_id=uuid.UUID(run.task_id), tenant_id=run.tenant_id, task_type=run.task_type,
            instruction=run.instruction, project_context={},
        )  # fmt: skip
        run.verify_chain = []

    async def _land(run):
        seen["landed"] += 1
        seen["continuation"] = (run.continuation_round, run.base_commit)

    async def _keep(run, updates):
        seen["kept"].append(updates)
        return True

    for name in ("_check_wip_limits", "_emit", "_finish_dispatch", "_persist_checkpoint"):
        monkeypatch.setattr(d, name, _noop)
    monkeypatch.setattr(d, "_prepare_packet", _prepare)
    monkeypatch.setattr(d, "_land_verified_work", _land)
    monkeypatch.setattr(d, "_persist_task_props", _keep)
    monkeypatch.setattr(d, "_budget_preview", _noop)
    return d, driver, seen


async def test_continue_dispatch_resumes_in_the_kept_worktree(
    tmp_path, monkeypatch, continue_dispatcher
):
    d, driver, seen = continue_dispatcher
    monkeypatch.setattr(settings, "driver_continue_enabled", True)
    task = _finished(tmp_path, base_commit="abc123", rounds=1, account_id="acct-1")
    saved = task.properties["continuation"]
    result = await d.continue_dispatch(
        tenant_id="t1", task_id=str(task.id), instruction="fix x", task_type="code_change",
        project_id=None, persona_name=None, session=None, saved=saved,
        feedback="handle None too", reason="pr_feedback",
    )  # fmt: skip
    assert result.success and result.metadata["continuation"] == 2
    (call,) = driver.resumes
    assert call["session"] == saved["session_id"] and call["account"] == "acct-1"
    assert Path(call["workdir"]) == Path(saved["worktree"]) and "handle None too" in call["prompt"]
    assert seen["landed"] == 1 and seen["continuation"] == (2, "abc123")
    # Kept again for the next round of feedback.
    assert seen["kept"][-1]["continuation"]["rounds"] == 2
    assert Path(saved["worktree"]).is_dir()


@pytest.mark.parametrize("missing", ["session_id", "worktree", "driver"])
async def test_continue_dispatch_refuses_without_session_workdir_or_driver(
    tmp_path, continue_dispatcher, missing
):
    d, driver, _seen = continue_dispatcher
    saved = dict(_finished(tmp_path).properties["continuation"])
    saved[missing] = None if missing != "driver" else "local"
    result = await d.continue_dispatch(
        tenant_id="t1", task_id=str(uuid.uuid4()), instruction="x", task_type="code_change",
        project_id=None, persona_name=None, session=None, saved=saved, feedback="f",
    )  # fmt: skip
    expected = {"session_id": "no_session", "worktree": "no_workdir",
                "driver": "resume_unsupported"}[missing]  # fmt: skip
    assert not result.success and result.metadata["exit_status"] == expected
    assert driver.resumes == []


async def test_a_dispatch_keeps_its_worktree_only_when_continue_is_on(tmp_path, monkeypatch):
    from life_graph.drivers.dispatcher import _DispatchRun

    origin, wt = _git_worktree(tmp_path)
    d = TaskDispatcher(session_factory=lambda: None, reviewer=object())
    stored: list = []

    async def _props(run, updates):
        stored.append(updates)
        return True

    monkeypatch.setattr(d, "_persist_task_props", _props)
    run = _DispatchRun(
        tenant_id="t1", task_id=str(uuid.uuid4()), instruction="x", task_type="code",
        persona_name=None, session=None, cost_cap_usd=2.0, interactive=False,
        spec_first=False, acceptance_tests=None,
    )  # fmt: skip
    run.worktree, run.worktree_origin = wt, str(origin)
    run.session_ref = {"driver": "codex", "session_id": "s-00000001", "account_id": None}
    monkeypatch.setattr(settings, "driver_continue_enabled", False)
    assert await d._retain_for_continuation(run) is False and stored == []
    monkeypatch.setattr(settings, "driver_continue_enabled", True)
    monkeypatch.setattr(settings, "driver_continue_keep_hours", 6)
    assert await d._retain_for_continuation(run) is True
    record = stored[0]["continuation"]
    assert record["worktree"] == str(wt) and record["session_id"] == "s-00000001"
    kept = datetime.fromisoformat(record["kept_at"].replace("Z", "+00:00"))
    until = datetime.fromisoformat(record["keep_until"].replace("Z", "+00:00"))
    assert until - kept == timedelta(hours=6)
    run.session_ref = None  # no session to resume -> nothing to keep
    assert await d._retain_for_continuation(run) is False


# ── The single approval path for a continuation ──────────────


class _NestedSession(FakeSession):
    def begin_nested(self):
        session = self

        class _Ctx:
            async def __aenter__(self):
                return session

            async def __aexit__(self, *_e):
                return False

        return _Ctx()


async def test_continuation_updates_a_pending_pr_approval_in_place():
    d = TaskDispatcher(session_factory=lambda: None, reviewer=object())
    pending = Approval(tenant_id="t1", kind="driver_pr", status="pending", source_ref="t",
                       title="Open PR: x", payload={"head_commit": "old"}, created_at=NOW)  # fmt: skip
    session = _NestedSession([pending])
    payload: dict = {"head_commit": "new"}
    appr = await d._store_pr_approval(
        session, tenant_id="t1", task_id="t", title=("Open PR", "x"), detail="d",
        payload=payload, verified=True, continuation={"round": 1, "base_commit": "b"},
    )  # fmt: skip
    assert appr is pending and session.added == []
    assert pending.payload["head_commit"] == "new" and pending.payload["continuation"]["round"] == 1


async def test_continuation_after_the_pr_opened_files_an_update_and_supersedes_the_merge():
    d = TaskDispatcher(session_factory=lambda: None, reviewer=object())
    url = "https://github.com/o/r/pull/7"
    opened = Approval(id=uuid.uuid4(), tenant_id="t1", kind="driver_pr", status="approved",
                      source_ref="t", payload={"pr_url": url}, created_at=NOW)  # fmt: skip
    merge = Approval(tenant_id="t1", kind="driver_merge", status="pending", source_ref="t",
                     payload={"pr_url": url}, created_at=NOW + timedelta(minutes=1))  # fmt: skip
    session = _NestedSession([opened, merge])
    payload: dict = {}
    appr = await d._store_pr_approval(
        session, tenant_id="t1", task_id="t", title=("Open PR", "x"), detail="d",
        payload=payload, verified=True, continuation={"round": 2, "base_commit": "b"},
    )  # fmt: skip
    assert session.added == [appr] and appr.title == "Update PR: x"
    assert appr.payload["continuation"] == {
        "round": 2, "previous_approval": str(opened.id), "pr_url": url,
    }  # fmt: skip
    assert url in appr.detail
    assert merge.status == "rejected" and merge.resolved_by == "system: continued"
    assert opened.status == "approved"


def test_stage_reads_the_newest_approval_of_a_kind():
    task = _task(status="completed")
    old = SimpleNamespace(kind="driver_pr", status="approved", payload={}, created_at=NOW)
    new = SimpleNamespace(
        kind="driver_pr", status="pending", payload={}, created_at=NOW + timedelta(hours=1)
    )
    assert dev_tasks._stage(task, [new, old]) == "awaiting_pr"


def test_serialize_exposes_ladder_second_opinion_and_review_panel():
    task = _task()
    task.result = {
        "output": "ok",
        "metadata": {
            "ladder": {"start_reason": "floor: protected path", "escalations": []},
            "second_opinion_status": "objected",
            "second_opinion_concern": "SQL injection",
        },
    }
    task.properties = {
        **(task.properties or {}),
        "review_panel": {"mode": "shadow", "verdict": "approve"},
    }
    out = dev_tasks.serialize(task, [])
    assert out["ladder"]["start_reason"] == "floor: protected path"
    assert out["second_opinion_status"] == "objected"
    assert out["second_opinion_reason"] == "SQL injection"
    assert out["review_panel"]["verdict"] == "approve"
    bare = _task()
    bare.result = None
    plain = dev_tasks.serialize(bare, [])
    assert (
        plain["ladder"] is None
        and plain["second_opinion_status"] is None
        and plain["review_panel"] is None
    )
