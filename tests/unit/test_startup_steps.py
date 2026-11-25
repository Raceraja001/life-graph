"""The extended-domain startup runs the same steps, in the same order (audit M15).

``main._start_extended_domains`` was one 260-line function ("moved out of
lifespan unchanged", 2026-10-29). It is now a tuple of per-domain steps run in
order. These tests pin that the split changed nothing a probe can see: the
recorded step names, their order, the conditional steps, and that one failing
step never stops the rest.
"""

from __future__ import annotations

import ast
import builtins
import inspect
import textwrap
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from life_graph import main

# The startup_step names of the pre-split function, in source order, taken
# from master@18b9e4e by the same AST walk as _names_in() below.
BEFORE_THE_SPLIT = [
    "durable_authorization",
    "agent_tools",
    "mcp_bridge",
    "connectors",
    "webhook_handler",
    "webhook_arq_pool",
    "seed_personas",
    "seed_ambient_jobs",
    "seed_ambient_autonomy",
    "scheduler_outcomes",
    "judgment_engine",
    "push_delivery",
    "telegram_delivery",
    "approval_notifications",
    "findings_bridge",
    "autonomous_action_bridges",
    "agent_drivers",
    "adopted_models",
    # Added 2026-11-25 (audit M2), not in the pre-split function: abandoned
    # kernel tasks are failed at startup (kernel/recovery.py).
    "kernel_tasks_recovery",
    "dev_task_runner_lock",
    "dev_tasks_recovery",
    "dev_task_runtime_sweep",
    "dev_outcome_recorder",
    "trajectory_recorder",
    "dev_task_queue",
]


def _names_in(fn) -> list[str]:
    """``startup_step(report, "<name>")`` names in *fn*, in source order."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    calls = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "startup_step"
    ]
    calls.sort(key=lambda c: (c.lineno, c.col_offset))
    return [c.args[1].value for c in calls]


def test_the_steps_record_the_same_names_in_the_same_order():
    names = [name for step in main._EXTENDED_STARTUP for name in _names_in(step)]
    assert names == BEFORE_THE_SPLIT


def test_start_extended_domains_only_runs_the_steps():
    """No step hides in the runner itself: it just walks the tuple."""
    assert _names_in(main._start_extended_domains) == []


@pytest.fixture
def blocked_imports(monkeypatch):
    """Every step body starts by importing what it wires. Refusing those
    imports makes each body fail at once -- no database, Redis, MCP server or
    tool registry is touched -- so what is left to watch is the sequence."""
    real_import = builtins.__import__

    def _import(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and name.split(".")[0] in ("life_graph", "arq", "sqlalchemy"):
            raise ImportError(f"blocked in test: {name}")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _import)


@pytest.fixture
def recorded(monkeypatch):
    order: list[str] = []
    real = main.startup_step

    @contextmanager
    def _recording(report, name):
        order.append(name)
        with real(report, name):
            yield

    monkeypatch.setattr(main, "startup_step", _recording)
    return order


@pytest.mark.asyncio
@pytest.mark.parametrize("optional_on", [True, False])
async def test_every_step_runs_in_order_and_a_failure_stops_none(
    monkeypatch, recorded, blocked_imports, optional_on
):
    monkeypatch.setattr(main.settings, "durable_authorization", optional_on)
    monkeypatch.setattr(main.settings, "connectors_enabled", optional_on)
    app = SimpleNamespace(state=SimpleNamespace())
    report = main.StartupReport()

    await main._start_extended_domains(app, report)

    # webhook_arq_pool runs inside webhook_handler, only once the handler is
    # up; here the handler's import failed first, as it would in production.
    expected = [n for n in BEFORE_THE_SPLIT if n != "webhook_arq_pool"]
    if not optional_on:
        expected = [n for n in expected if n not in ("durable_authorization", "connectors")]
    assert recorded == expected
    # Every step recorded and none raised. The sweep imports nothing unless
    # this process holds the runner lock, so it alone succeeds here.
    assert sorted(report.as_dict()) == sorted(expected)
    assert report.failed == sorted(n for n in expected if n != "dev_task_runtime_sweep")
    assert app.state.dev_task_runner_lock is None
    assert app.state.dev_task_queue is None
