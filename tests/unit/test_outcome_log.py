"""The dev-task outcome log (2026-11-28): one row per dispatch, on every terminal path.

docs/specs/agent-drivers.md, "Escalation ladder, starting floor, outcome log
(2026-11-28)". Written beside ``record_outcome`` (the trust recorder, kept),
read by the floor, the top-rung cap and ``GET /kernel/drivers/outcomes``.
"""

from __future__ import annotations

import subprocess
import sys
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import life_graph.drivers.dispatcher as disp_mod
import life_graph.drivers.ladder_steps as ls_mod
from life_graph.core.budget import BudgetDecision
from life_graph.core.tenant import tenant_scope
from life_graph.drivers.base import DriverResult
from life_graph.drivers.dispatcher import DispatchError, TaskDispatcher, _DispatchRun
from life_graph.models.dev_outcomes import DevOutcomeLog
from life_graph.services.dev import outcome_log
from life_graph.services.dev.verifiers import VerifierResult
from tests.unit.fakes import FakeResult, FakeSession, sql
from tests.unit.test_dispatcher_spec_first import _FakeSession, _wire

ROOT = Path(__file__).resolve().parents[2]


class _Driver:
    name = "local"
    billing = "local"

    def __init__(self, result=None):
        self._result = result or DriverResult(success=True, output="did it", cost_usd=0.0)

    async def available(self):
        return True

    def cost_per_task(self):
        return 0.0

    async def dispatch(self, packet, workdir, timeout=300):
        return self._result


class _Registry:
    def __init__(self, *drivers):
        self._d = {d.name: d for d in drivers}

    def get(self, name):
        return self._d.get(name)


@pytest.fixture
def logged(monkeypatch):
    """A wired dispatcher whose outcome rows are captured, not written."""
    driver = _Driver()
    disp = TaskDispatcher(session_factory=lambda: _FakeSession(), event_bus=None)
    _wire(disp, monkeypatch, driver)
    rows: list[dict] = []

    async def _write(row):
        rows.append(row)

    async def _no(*_a, **_k):
        return False

    monkeypatch.setattr(disp, "_write_outcome", _write)
    monkeypatch.setattr(disp, "_recent_failure", _no)
    monkeypatch.setattr(ls_mod, "autonomy_stopped", _no)
    monkeypatch.setattr(ls_mod, "driver_registry", _Registry(driver))
    return disp, driver, rows


async def test_a_finished_dispatch_writes_one_row(logged):
    disp, _, rows = logged
    task_id = str(uuid.uuid4())
    await disp.dispatch_task(
        tenant_id="t1", task_id=task_id, instruction="Add a helper", verify_chain=[]
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["tenant_id"] == "t1" and row["task_id"] == task_id
    assert row["outcome"] == "succeeded" and row["verification"] == "passed"
    assert row["start_driver"] == row["final_driver"] == "local"
    assert row["start_tier"] == "cheap"  # the default ladder's bottom rung
    assert row["start_reason"] == "selection"
    # The default reviewer is off: skipped, and recorded as such.
    assert row["review_verdict"] == "skipped"
    assert row["reviews"] == [{"reviewer": "second_opinion", "verdict": "skipped"}]
    assert row["shadow_tier"] == "cheap" and row["escalations"] == []
    assert row["instruction_sha"] == outcome_log.instruction_fingerprint("add  a HELPER")


async def test_a_budget_denial_is_logged(logged, monkeypatch):
    disp, _, rows = logged

    async def _deny(*_a, **_k):
        return BudgetDecision(False, False, "monthly cap", 10.0, 10.0, 0.0)

    monkeypatch.setattr(disp_mod.governor, "authorize", _deny)
    monkeypatch.setattr(disp_mod, "runs_on_local_model", lambda *_a: False)
    result = await disp.dispatch_task(
        tenant_id="t1", task_id=str(uuid.uuid4()), instruction="x", verify_chain=[]
    )
    assert result.metadata["budget_throttled"]
    assert [r["outcome"] for r in rows] == ["budget_denied"]


async def test_a_refused_or_crashed_dispatch_is_logged(logged, monkeypatch):
    disp, _, rows = logged

    async def _full(*_a, **_k):
        raise DispatchError("WIP limit reached")

    monkeypatch.setattr(disp, "_check_wip_limits", _full)
    with pytest.raises(DispatchError):
        await disp.dispatch_task(
            tenant_id="t1", task_id=str(uuid.uuid4()), instruction="x", verify_chain=[]
        )
    assert len(rows) == 1
    assert rows[0]["outcome"] == "error" and rows[0]["error"] == "WIP limit reached"
    assert rows[0]["start_driver"] is None  # not counted by the top-rung cap


async def test_failed_verification_logs_needs_human_and_the_rounds(logged, monkeypatch):
    disp, _, rows = logged
    fail = VerifierResult("tests_pass", False, {"stdout": "1 failed"})

    async def _chain(*_a, **_k):
        return [fail]

    async def _no_fix(*_a, **_k):
        return {}

    async def _noop(*_a, **_k):
        return None

    monkeypatch.setattr(disp_mod.verifier_chain, "run_chain", _chain)
    monkeypatch.setattr(disp_mod, "mechanical_autofix", _no_fix)
    monkeypatch.setattr(disp, "_create_approval_entry", _noop)
    monkeypatch.setattr(disp, "_record_verification", _noop)
    await disp.dispatch_task(
        tenant_id="t1", task_id=str(uuid.uuid4()), instruction="x", verify_chain=["tests_pass"]
    )
    (row,) = rows
    assert row["outcome"] == "needs_human" and row["verification"] == "failed"
    assert row["rounds_used"] == 1  # the bounce
    # The bounce climbed the default ladder: qwen3:14b -> qwen3-coder:30b.
    assert row["escalations"][0]["to"] == "local:ollama_chat/qwen3-coder:30b"
    # Only local is registered here, so qwen3-coder:30b is the top rung -- and
    # a local top rung is not capped (there is no subscription to protect).
    assert row["final_tier"] == "best" and row["reached_top"] is True


# ── Pure pieces ──────────────────────────────────────────────


def _run(**kw) -> _DispatchRun:
    run = _DispatchRun(
        tenant_id="t1", task_id=str(uuid.uuid4()), instruction="x", task_type="code",
        persona_name=None, session=None, cost_cap_usd=2.0, interactive=False,
        spec_first=False, acceptance_tests=None,
    )  # fmt: skip
    for k, v in kw.items():
        setattr(run, k, v)
    return run


@pytest.mark.parametrize(
    ("result", "error", "outcome"),
    [
        (DriverResult(success=True, metadata={"landed_branch": "lg/task-1"}), None, "landed"),
        (DriverResult(success=True), None, "succeeded"),
        (DriverResult(success=False, metadata={"outcome": "no_changes"}), None, "no_changes"),
        (DriverResult(success=False, error="x", metadata={"park": {"a": 1}}), None, "parked"),
        (
            DriverResult(success=False, error="x", metadata={"needs_human": True}),
            None,
            "needs_human",
        ),
        (DriverResult(success=False, error="x"), None, "failed"),
        (None, RuntimeError("boom"), "error"),
    ],
)
def test_final_outcome(result, error, outcome):
    assert ls_mod._final_outcome(_run(result=result), error) == outcome


@dataclass
class _V:
    ran: bool
    approved: bool
    concern: str | None = None


def test_review_verdicts():
    from life_graph.services.dev.second_opinion import ReviewVerdict

    def entry(verdict):
        return ls_mod._review_entry("second_opinion", verdict)

    assert ls_mod._reviews(_run()) == ([], "skipped")
    assert ls_mod._reviews(_run(second_opinion=entry(_V(True, True))))[1] == "approved"
    assert entry(_V(True, False, "SQL")) == {
        "reviewer": "second_opinion", "verdict": "objected", "concern": "SQL",
    }  # fmt: skip
    # Legacy ran/approved pairs and the status-based verdict agree.
    assert entry(_V(False, False))["verdict"] == "not_reviewed"
    assert entry(_V(False, True))["verdict"] == "skipped"
    assert entry(ReviewVerdict.not_reviewed("timeout"))["verdict"] == "not_reviewed"
    assert entry(ReviewVerdict.skipped())["verdict"] == "skipped"
    down = _run(second_opinion=entry(ReviewVerdict.not_reviewed("timeout")))
    assert ls_mod._reviews(down)[1] == "not_reviewed"
    staged = _run(
        second_opinion=None,
        review_results=[
            {"index": 0, "name": "security", "verdict": "unavailable"},
            {"index": 1, "name": "style", "verdict": "objection", "concern": "naming"},
        ],
    )
    reviews, overall = ls_mod._reviews(staged)
    assert overall == "objected"
    assert reviews == [
        {"reviewer": "stage:security", "verdict": "not_reviewed"},
        {"reviewer": "stage:style", "verdict": "objected", "concern": "naming"},
    ]


async def test_second_opinion_verdict_is_captured(monkeypatch):
    class _Reviewer:
        async def review(self, *_a):
            return _V(True, True)

    async def _diff(_w):
        return "diff"

    async def _noop(*_a, **_k):
        return None

    d = TaskDispatcher(session_factory=lambda: None, reviewer=_Reviewer())
    monkeypatch.setattr(d, "_emit", _noop)
    monkeypatch.setattr(disp_mod, "diff_against_head", _diff)
    run = _run(driver=_Driver(), result=DriverResult(success=True))
    await d._second_opinion_review(run)
    assert run.second_opinion == {"reviewer": "second_opinion", "verdict": "approved"}
    assert ls_mod._reviews(run)[1] == "approved"


def test_summarize_counts():
    rows = [
        {"outcome": "landed", "final": {"tier": "best"}, "escalations": [{"to": "claude_code"}],
         "reached_top": True, "review_verdict": "approved",
         "shadow": {"tier": "best"}},
        {"outcome": "failed", "final": {"tier": None}, "escalations": [{"to": None}],
         "reached_top": False, "review_verdict": "not_reviewed", "shadow": {"tier": "cheap"}},
    ]  # fmt: skip
    assert outcome_log.summarize(rows) == {
        "total": 2,
        "outcomes": {"landed": 1, "failed": 1},
        "final_tiers": {"best": 1, "off_ladder": 1},
        "escalated": 1,
        "reached_top": 1,
        "not_reviewed": 1,
        "review_skipped": 0,
        "shadow_agrees": 1,
        "shadow_compared": 1,
    }


# ── The service against a fake session ──────────────────────


class _NestedSession(FakeSession):
    def begin_nested(self):
        @asynccontextmanager
        async def _cm():
            yield None

        return _cm()


async def test_write_numbers_attempts_per_task():
    session = FakeSession(FakeResult([2]))
    ok = await outcome_log.write(
        lambda: session,
        {"tenant_id": "t1", "task_id": "abc", "project_id": "not-a-uuid", "outcome": "failed"},
    )
    assert ok and session.commits == 1
    (row,) = session.added
    assert isinstance(row, DevOutcomeLog) and row.attempt == 3 and row.project_id is None
    assert "'t1'" in sql(session.statements[0])


async def test_write_never_raises():
    def _broken():
        raise RuntimeError("db down")

    assert await outcome_log.write(_broken, {"tenant_id": "t1", "task_id": "x"}) is False
    assert await outcome_log.top_tier_usage(_broken, "t1") is None
    assert await outcome_log.recent_failure(_broken, "t1", None, "sha", days=14) is False


async def test_recent_failure_and_top_usage_queries():
    found = FakeSession(FakeResult([uuid.uuid4()]))
    pid = uuid.uuid4()
    assert await outcome_log.recent_failure(lambda: found, "t1", pid, "abc", days=14)
    text = sql(found.statements[0])
    assert (
        "'t1'" in text and "'abc'" in text and "'needs_human'" in text and "'pr_rejected'" in text
    )
    counted = FakeSession(FakeResult([(5, 1)]))
    assert await outcome_log.top_tier_usage(lambda: counted, "t1") == (1, 5)
    assert "start_driver IS NOT NULL" in sql(counted.statements[0])


async def test_owner_decision_updates_the_latest_row():
    session = _NestedSession()
    await outcome_log.record_owner_decision(session, "t1", "task-1", "merged")
    text = sql(session.statements[0])
    assert text.startswith("UPDATE dev_outcome_log") and "'merged'" in text and "'task-1'" in text


async def test_record_outcome_logs_the_owner_decision(monkeypatch):
    import life_graph.autonomy.trust.service as trust_mod
    from life_graph.services.dev import outcomes

    seen = []

    class _Trust:
        def __init__(self, _s):
            pass

        async def record_success(self, *a):
            seen.append(("success", a))

    async def _decision(session, tenant, task_id, decision, panel=None):
        seen.append(("logged", tenant, task_id, decision))

    monkeypatch.setattr(trust_mod, "TrustScoreService", _Trust)
    monkeypatch.setattr(outcome_log, "record_owner_decision", _decision)
    appr = SimpleNamespace(tenant_id="t1", payload={"task_id": "not-a-uuid", "driver": "local"})
    assert await outcomes.record_outcome(FakeSession(), appr, "merged", source="test")
    assert ("logged", "t1", "not-a-uuid", "merged") in seen
    assert seen[0][0] == "success"  # the trust record is unchanged and first


# ── API ──────────────────────────────────────────────────────


@pytest.fixture
def route(monkeypatch):
    from life_graph.api import drivers

    seen: dict = {}

    @asynccontextmanager
    async def fake_session():
        yield "session"

    async def _list(session, tenant_id, *, days, project_id, limit):
        seen.update(session=session, tenant=tenant_id, days=days, project=project_id, limit=limit)
        return {"days": days, "project_id": project_id, "summary": {"total": 0}, "outcomes": []}

    monkeypatch.setattr(outcome_log, "list_outcomes", _list)
    monkeypatch.setattr(drivers, "async_session", fake_session)
    return seen


async def test_outcomes_route(route):
    from life_graph.api.drivers import get_driver_outcomes

    pid = str(uuid.uuid4())
    with tenant_scope("acme"):
        response = await get_driver_outcomes(days=7, project_id=pid, limit=50)
    data = response["data"]
    assert route == {"session": "session", "tenant": "acme", "days": 7, "project": pid, "limit": 50}
    assert data["outcomes"] == [] and data["summary"] == {"total": 0}
    assert set(data["ladder"]) == {
        "enabled", "rungs", "top_share", "top_daily_min", "allow_metered", "floor_enabled",
    }  # fmt: skip


async def test_outcomes_route_400_for_a_bad_project(route):
    from life_graph.api.drivers import get_driver_outcomes

    with tenant_scope("acme"), pytest.raises(HTTPException) as err:
        await get_driver_outcomes(days=7, project_id="nope", limit=50)
    assert err.value.status_code == 400 and route == {}


def test_outcomes_route_is_registered():
    from life_graph.api.drivers import router

    assert "/kernel/drivers/outcomes" in {r.path for r in router.routes}


# ── Migration ────────────────────────────────────────────────


def test_migration_068_renders_and_matches_the_model():
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "067:068", "--sql"],
        cwd=ROOT, capture_output=True, text=True, timeout=120, check=False,
    )  # fmt: skip
    assert proc.returncode == 0, proc.stderr[-2000:]
    ddl = proc.stdout
    assert "CREATE TABLE dev_outcome_log" in ddl
    body = ddl.split("CREATE TABLE dev_outcome_log (", 1)[1].split(");", 1)[0]
    rendered = {line.strip().split()[0] for line in body.splitlines() if line.strip()} - {"PRIMARY"}
    assert rendered == set(DevOutcomeLog.__table__.columns.keys())
    for index in DevOutcomeLog.__table__.indexes:
        assert f"CREATE INDEX {index.name} ON dev_outcome_log" in ddl
    assert "version_num='068'" in ddl


def test_row_for_a_run_with_no_driver_or_packet():
    d = TaskDispatcher(session_factory=lambda: None, reviewer=object())
    run = _run(result=DriverResult(success=True))
    row = d._outcome_row(run, None)
    assert row["final_driver"] is None and row["outcome"] == "succeeded"


# ── The second-opinion call site: four statuses (fail-closed, step 1) ─


@pytest.mark.parametrize(
    ("make", "lands", "dissent_event", "status"),
    [
        ("approve", True, False, "approved"),
        ("skipped", True, False, "skipped"),
        ("objected", False, True, "objected"),
        ("not_reviewed", False, False, "not_reviewed"),
    ],
)
async def test_second_opinion_statuses_at_the_call_site(
    monkeypatch, make, lands, dissent_event, status
):
    from life_graph.core.events import EventType
    from life_graph.services.dev.second_opinion import ReviewVerdict

    verdict = {
        "approve": ReviewVerdict.approve,
        "skipped": ReviewVerdict.skipped,
        "objected": lambda: ReviewVerdict.objected("SQL injection"),
        "not_reviewed": lambda: ReviewVerdict.not_reviewed("timeout"),
    }[make]()

    class _Reviewer:
        async def review(self, *_a):
            return verdict

    events, approvals = [], []

    async def _emit(event_type, payload):
        events.append(event_type)

    async def _dissent(tenant_id, task_id, driver_name, concern, session):
        approvals.append(concern)

    async def _diff(_w):
        return "diff"

    d = TaskDispatcher(session_factory=lambda: None, reviewer=_Reviewer())
    monkeypatch.setattr(d, "_emit", _emit)
    monkeypatch.setattr(d, "_create_dissent_approval_entry", _dissent)
    monkeypatch.setattr(disp_mod, "diff_against_head", _diff)
    run = _run(driver=_Driver(), result=DriverResult(success=True, output="done"))
    await d._second_opinion_review(run)

    assert run.result.success is lands
    assert (EventType.SECOND_OPINION_DISSENT in events) is dissent_event
    assert run.second_opinion["verdict"] == status
    assert d._outcome_row(run, None)["properties"]["second_opinion"] == status
    if lands:
        assert approvals == []
    elif status == "not_reviewed":
        assert approvals == ["Second opinion did not run: timeout"]
        assert run.result.error == "Second opinion did not run: timeout"
        assert run.result.metadata == {
            "needs_human": True,
            "second_opinion_status": "not_reviewed",
            "second_opinion_reason": "timeout",
        }
    else:
        assert approvals == ["SQL injection"]
        assert run.result.metadata["second_opinion_concern"] == "SQL injection"


async def test_owner_decision_stores_the_panel_verdict():
    session = _NestedSession()
    panel = {"verdict": "objection", "members": [], "risky": ["auth"], "gated": False}
    await outcome_log.record_owner_decision(session, "t1", "task-1", "merged", panel=panel)
    compiled = session.statements[0].compile()
    assert "properties" in str(compiled)
    assert {"review_panel": panel} in compiled.params.values()
