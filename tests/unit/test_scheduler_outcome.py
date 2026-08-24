"""A schedule's auto-disable has to see the job's real outcome.

``fire_job`` recorded ``"completed"`` the moment ``spawn()`` returned. But
spawn only ENQUEUES — the AgentTask it creates is ``status="queued"`` and has
not run. So:

* ``last_run_status`` said completed for a job that had never once succeeded;
* ``consecutive_failures`` only incremented when spawn itself raised, i.e.
  when the task could not be enqueued at all;
* the documented "auto-disable after 3 consecutive failures" therefore could
  not fire for a broken job — only for an unreachable queue. A schedule
  firing a permanently failing task would fire forever, spending budget each
  time.

Firing now records ``"dispatched"``, and the real outcome arrives on
TASK_COMPLETED / TASK_FAILED / TASK_TIMEOUT.
"""

import ast
import pathlib

from life_graph.core.events import EventType

SCHEDULER_PY = (
    pathlib.Path(__file__).resolve().parents[2] / "life_graph" / "kernel" / "scheduler.py"
)


def _fn(name: str) -> ast.AsyncFunctionDef:
    tree = ast.parse(SCHEDULER_PY.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"scheduler.py has no {name}()")


def _record_run_statuses() -> set[str]:
    """Status literals fire_job passes to _record_run."""
    found: set[str] = set()
    for node in ast.walk(_fn("fire_job")):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "_record_run"
        ):
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    found.add(arg.value)
    return found


def test_firing_does_not_claim_success():
    """Regression: enqueueing is not completing."""
    statuses = _record_run_statuses()
    assert statuses, "no _record_run calls found in fire_job"
    assert "completed" not in statuses, (
        "fire_job records 'completed' when spawn() has only queued the task; "
        "a job that fails every run would report success forever and never "
        "accumulate consecutive_failures"
    )
    assert "dispatched" in statuses


def test_firing_still_records_an_enqueue_failure():
    """A queue that refuses the job is a real failure and must still count."""
    assert "failed" in _record_run_statuses()


def test_scheduler_subscribes_to_every_terminal_task_event():
    """Missing one leaves those runs stuck on 'dispatched' forever."""
    subscribed = set()
    for node in ast.walk(_fn("subscribe")):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "subscribe"
            and node.args
            and isinstance(node.args[0], ast.Attribute)
        ):
            subscribed.add(node.args[0].attr)
    for required in ("TASK_COMPLETED", "TASK_FAILED", "TASK_TIMEOUT"):
        assert required in subscribed, f"scheduler never hears about {required}"
        assert hasattr(EventType, required)


def test_settling_does_not_double_count_the_run():
    """fire_job already counted it; settling is the same run finishing."""
    src = ast.unparse(_fn("_on_task_settled"))
    assert "count_run=False" in src, (
        "without this the settle path increments run_count a second time and "
        "re-advances next_run_at, skipping a scheduled fire"
    )


def test_dispatched_does_not_reset_a_failure_streak():
    """Two failures then a fire must not put the counter back to zero."""
    # ast.unparse normalises string literals to single quotes, so match on
    # the bare word rather than on a quoting style.
    src = ast.unparse(_fn("_record_run"))
    assert "dispatched" in src, (
        "_record_run must special-case 'dispatched'; treating it as success "
        "resets consecutive_failures on every fire, so a streak never builds "
        "and auto-disable never triggers"
    )


def test_the_threshold_still_comes_from_settings():
    src = SCHEDULER_PY.read_text()
    assert "settings.kernel_max_consecutive_failures" in src
