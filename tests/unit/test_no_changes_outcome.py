"""The "no changes needed" outcome (2026-11-28): a code run that finished normally, changed
nothing and said there was nothing to change ends as status ``completed``, stage
``no_changes`` -- not failed -- and the breaker and the morning digest treat it
as such. A run that errored, or that changed nothing without saying why, still
fails exactly as before (docs/specs/agent-drivers.md, Step 4c).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from life_graph.drivers.base import DriverResult
from life_graph.drivers.dispatcher import (
    NO_CHANGES_OUTCOME,
    TaskDispatcher,
    is_no_changes,
    states_no_change_needed,
)
from life_graph.services.dev import autonomy_policy as ap
from life_graph.services.dev.automation.breaker import Breaker, schedule_key
from life_graph.services.dev.automation.digest import build
from life_graph.services.dev.automation.settings import BreakerSettings
from life_graph.services.dev.automation.status import (
    failure_reason,
    finished,
    item_status_for,
    no_changes,
)
from life_graph.services.dev.tasks import _stage, final_status
from life_graph.services.night_shift import lines
from tests.unit.automation_fakes import FakeNotifier, MemStore, T, at
from tests.unit.test_run_health import _Driver, _ok, _run, disp  # noqa: F401 - fixture

HEALTHY = (
    "Ran ruff, mypy and the unit tests: all clean. "
    "There is nothing in the source to fix, so no changes are needed."
)


# ── The statement classifier ─────────────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        HEALTHY,
        "No changes needed.",
        "No code changes were required: the bug is already fixed on master.",
        "Nothing to fix -- lint, typecheck and tests are green.",
        "Checked everything; nothing needs fixing.",
        "This is already implemented in life_graph/x.py.",
    ],
)
def test_explicit_no_change_statements_qualify(text):
    assert states_no_change_needed(text)


@pytest.mark.parametrize(
    "text",
    [
        "",
        None,
        "all done!",  # task ade60cc6's kind of claim: success with an empty diff
        "Added task_diff.",
        "All tests pass.",
        "Done, nothing needed.",  # not explicit about changes
        "No changes needed? Should I also bump the deps?",  # a question
        "I fixed the import; no further changes are needed.",  # claims an edit
        "- Updated x.py\nNo other changes are needed.",
        "I can't edit files here, so no changes are needed from me.",  # refusal
        "Permission denied writing x.py; nothing to change.",
    ],
)
def test_claims_questions_and_refusals_do_not(text):
    assert not states_no_change_needed(text)


# ── Step 4c: the dispatcher's empty-diff path ────────────────


@pytest.fixture
def step4c(disp, monkeypatch):  # noqa: F811 - the imported fixture
    d, rec = disp

    async def _nothing(run):
        run.files_changed = []

    async def _noop(run):
        return None

    monkeypatch.setattr(d, "_observe_files_changed", _nothing)
    monkeypatch.setattr(d, "_check_worktree_link", _noop)
    monkeypatch.setattr(d, "_persist_checkpoint", _noop)
    return d, rec


def _empty_run(result, policy=ap.NEUTRAL):
    run = _run(policy)
    run.worktree = run.workdir = "/tmp/wt"
    run.result = result
    return run


async def test_a_clean_run_saying_nothing_to_fix_is_no_changes(step4c):
    d, _rec = step4c
    run = _empty_run(_ok(HEALTHY, num_turns=7), ap.merge({"max_nudges": 2}, None))
    await d._check_files_changed(run)
    assert is_no_changes(run.result)
    assert run.result.error is None and run.result.success is False
    assert run.result.output == HEALTHY  # the agent's message is the summary
    assert run.result.metadata["outcome"] == NO_CHANGES_OUTCOME
    assert run.result.metadata["stop_reason"] == "no_change_needed"
    assert run.result.metadata["num_turns"] == 7
    assert run.driver.calls == []  # a run that concluded is not nudged
    assert final_status(run.result) == "completed"


async def test_a_clean_run_that_does_not_say_why_still_fails(step4c):
    d, _rec = step4c
    run = _empty_run(_ok("all done!"))
    await d._check_files_changed(run)
    assert not is_no_changes(run.result)
    assert "changed no files" in run.result.error
    assert run.result.metadata["stop_reason"] == "no_change"
    assert final_status(run.result) == "failed"


@pytest.mark.parametrize(
    "result",
    [
        # A timeout, a crash, an auth/rate-limit failure, a refusal: the driver
        # itself failed, whatever its last words were.
        DriverResult(success=False, output=HEALTHY, error="Timed out after 900s"),
        DriverResult(success=False, output=HEALTHY, error="claude exited 1"),
        DriverResult(
            success=False,
            output=HEALTHY,
            error="rate limited",
            metadata={"exit_status": "rate_limited"},
        ),
        DriverResult(
            success=False, output="", error="refused", metadata={"exit_status": "refused_unscoped"}
        ),
    ],
)
async def test_a_failed_run_with_no_diff_stays_failed(step4c, result):
    d, _rec = step4c
    run = _empty_run(result)
    await d._check_files_changed(run)
    assert run.result is result  # untouched
    assert not is_no_changes(run.result)
    assert final_status(run.result) == "failed"


async def test_plan_only_output_is_still_nudged_first(step4c):
    """A plan or a question with a nudge budget gets "carry it out now" (as before);
    it becomes "no changes needed" only when the agent then says so."""
    d, rec = step4c
    run = _empty_run(_ok("Plan:\n1. run ruff\n2. run tests"), ap.merge({"max_nudges": 1}, None))
    run.driver = _Driver(_ok(HEALTHY))
    run.session_ref = {"driver": "codex", "session_id": "sess-0001", "account_id": None}
    await d._check_files_changed(run)
    assert len(run.driver.calls) == 1 and run.nudges == 1
    assert is_no_changes(run.result) and run.result.output == HEALTHY


async def test_plan_only_output_after_the_nudges_still_fails(step4c):
    d, _rec = step4c
    run = _empty_run(_ok("Should I proceed?"), ap.merge({"max_nudges": 1}, None))
    run.driver = _Driver(_ok("Shall I continue?"))
    run.session_ref = {"driver": "codex", "session_id": "sess-0001", "account_id": None}
    await d._check_files_changed(run)
    assert run.nudges == 1
    assert not is_no_changes(run.result) and "changed no files" in run.result.error


async def test_no_changes_skips_driver_stats_and_says_so_in_the_event(monkeypatch):
    d = TaskDispatcher(session_factory=lambda: None, reviewer=object())
    events, stats = [], []

    async def _emit(event_type, payload):
        events.append(payload)

    async def _stats(*a, **_k):
        stats.append(a)

    monkeypatch.setattr(d, "_emit", _emit)
    monkeypatch.setattr(d, "_record_stats", _stats)
    run = _empty_run(
        DriverResult(success=False, output=HEALTHY, metadata={"outcome": NO_CHANGES_OUTCOME})
    )
    run.tracker = None
    await d._finish_dispatch(run)
    assert stats == []  # neither landed nor failed: the driver's trust is untouched
    assert events[0]["outcome"] == NO_CHANGES_OUTCOME and events[0]["success"] is False


# ── The task row and its stage ───────────────────────────────


def _task(status, metadata):
    return SimpleNamespace(status=status, result={"output": HEALTHY, "metadata": metadata})


def test_stage_is_no_changes_only_for_a_completed_no_change_row():
    assert _stage(_task("completed", {"outcome": "no_changes"}), []) == "no_changes"
    assert _stage(_task("failed", {"outcome": "no_changes"}), []) == "failed"
    assert _stage(_task("completed", {}), []) == "completed"


def test_final_status_mapping():
    assert final_status(DriverResult(success=True)) == "completed"
    assert final_status(DriverResult(success=False, error="x")) == "failed"
    # An error always wins over the outcome tag: never a pass for a real failure.
    tagged = DriverResult(success=False, error="boom", metadata={"outcome": "no_changes"})
    assert final_status(tagged) == "failed"
    assert final_status(DriverResult(success=False, metadata={"park": {"resume_at": "x"}})) == (
        "parked"
    )


# ── Automation: breaker, backlog item, chains ────────────────

VIEW = {
    "id": "t-nc",
    "status": "completed",
    "stage": "no_changes",
    "error": None,
    "output": HEALTHY,
}


def test_status_helpers_treat_no_changes_as_finished_not_failed():
    assert no_changes(VIEW) and finished(VIEW)
    assert failure_reason(VIEW) is None
    status, reason = item_status_for(VIEW)
    assert status == "skipped"  # nothing done, nothing failed: restartable, no "merged" comment
    assert reason.startswith("no changes needed: Ran ruff")


async def test_breaker_counts_no_changes_as_a_success():
    key = schedule_key("j1")
    store = MemStore()
    b = Breaker(store, FakeNotifier(), T, BreakerSettings(), at("2026-11-28T08:00"))
    for n in range(2):
        await b.observe(key, "Health check", {"id": f"f{n}", "status": "failed", "error": "boom"})
    assert store.breakers[(T, key)].consecutive_failures == 2
    await b.observe(key, "Health check", VIEW)
    assert store.breakers[(T, key)].consecutive_failures == 0
    # Three no-change nights in a row never trip it.
    for n in range(3):
        await b.observe(key, "Health check", {**VIEW, "id": f"nc{n}"})
    state = store.breakers[(T, key)]
    assert state.consecutive_failures == 0 and not state.tripped


# ── Morning digest / night-shift report ──────────────────────


def _rep(**kw):
    return {"since": "2026-11-27T08:00:00+00:00", "merged": [], "waiting": [], "failed": [],
            "no_changes": [], "queued": 0, **kw}  # fmt: skip


def test_digest_lists_no_change_runs_on_their_own_line_not_as_failed():
    rep = _rep(
        no_changes=[{"title": "Nightly health check", "reason": "nothing to fix", "pr_url": None}],
        failed=[{"title": "Fix x", "reason": "Timed out", "pr_url": None}],
    )
    out = lines(rep)
    assert out == [
        "0 merged, 0 waiting for you, 1 failed, 0 queued, 1 checked with no changes needed",
        "failed: Fix x — Timed out",
        "no changes needed: Nightly health check — nothing to fix",
    ]
    digest = build(rep, out, since=at("2026-11-27T08:00"), to=at("2026-11-28T08:00"))
    assert digest["failed"] == 1 and digest["noChanges"] == 1 and not digest["quiet"]


def test_a_report_without_the_key_still_formats():
    rep = _rep()
    del rep["no_changes"]
    assert lines(rep) == []


async def test_report_puts_a_no_change_run_under_no_changes(monkeypatch):
    from life_graph.services import night_shift
    from life_graph.services.dev import tasks as dev_tasks

    task = {
        "id": "t-nc", "title": "Nightly health check", "status": "completed",
        "stage": "no_changes", "error": None, "output": HEALTHY, "pr_url": None,
        "completed_at": "2026-11-28T02:10:00+00:00", "approvals": [],
    }  # fmt: skip

    async def _list(_session, _tenant, limit=300):
        return [task]

    monkeypatch.setattr(dev_tasks, "list_dev_tasks", _list)
    rep = await night_shift.report(object(), T, since=at("2026-11-27T08:00"))
    assert rep["failed"] == [] and rep["waiting"] == []
    (row,) = rep["no_changes"]
    assert row["stage"] == "no_changes" and row["reason"].startswith("Ran ruff, mypy")


def test_the_row_and_the_dispatcher_agree_on_the_tag():
    from life_graph.services import night_shift
    from life_graph.services.dev.automation.status import NO_CHANGES_STAGE
    from life_graph.services.dev.tasks import NO_CHANGES

    assert NO_CHANGES == NO_CHANGES_OUTCOME == NO_CHANGES_STAGE == night_shift.NO_CHANGES
