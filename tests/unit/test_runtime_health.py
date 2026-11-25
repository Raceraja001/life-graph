"""Runtime health (services/dev/runtime_health.py) and its alert job.

Counts and issue codes only, never task data; each issue alerts the owner at
most once per 6-hour window.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from life_graph.config import settings
from life_graph.services.dev import runtime_health as rh
from life_graph.services.dev import sandbox, task_runtime
from life_graph.services.dev.sandbox import SandboxResult
from life_graph.workers import runtime_health as job

NOW = datetime(2026, 11, 19, 10, 0, 0, tzinfo=UTC)


def _report(runner=None, tasks=None, containers=None):
    r = rh.Report(checked_at=NOW.isoformat())
    r.runner = {"enabled": True, "mode": "worker", "lock_holders": 1, **(runner or {})}
    r.tasks = {
        "running": 0,
        "stale_leases": 0,
        "queued": 0,
        "oldest_start_now_wait_seconds": None,
        "failed_24h": 0,
        **(tasks or {}),
    }
    r.containers = {
        "available": True,
        "total": 0,
        "agents_running": 0,
        "orphan_containers": 0,
        "orphan_networks": 0,
        "agent_usage": [],
        **(containers or {}),
    }
    rh.evaluate(r)
    return r


def _codes(r):
    return [i.code for i in r.issues]


def test_a_healthy_runtime_has_no_issues():
    r = _report()
    assert r.status == "ok" and r.issues == []


@pytest.mark.parametrize(
    ("kw", "code", "status"),
    [
        ({"runner": {"lock_holders": 0}}, "runner_down", "critical"),
        ({"tasks": {"stale_leases": 2}}, "stale_leases", "critical"),
        ({"tasks": {"oldest_start_now_wait_seconds": 3600}}, "queue_stuck", "warning"),
        ({"tasks": {"failed_24h": 7}}, "failures", "warning"),
        ({"containers": {"orphan_containers": 1}}, "orphans", "warning"),
        ({"containers": {"orphan_networks": 1}}, "orphans", "warning"),
        (
            {"containers": {"agent_usage": [{"memory_percent": 95.0}]}},
            "memory_pressure",
            "warning",
        ),
    ],
)
def test_each_problem_becomes_one_issue(kw, code, status):
    r = _report(**kw)
    assert _codes(r) == [code]
    assert r.status == status


def test_a_disabled_runner_is_not_down():
    assert "runner_down" not in _codes(_report(runner={"enabled": False, "lock_holders": 0}))


def test_docker_unavailable_matters_only_when_tasks_use_containers(monkeypatch):
    monkeypatch.setattr(settings, "driver_claude_sandbox", "task")
    r = _report(containers={"available": False, "reason": "docker check failed: x"})
    assert _codes(r) == ["docker_unavailable"]
    monkeypatch.setattr(settings, "driver_claude_sandbox", "none")
    assert _codes(_report(containers={"available": False, "reason": "x"})) == []


def test_the_fenced_docker_driver_mode_is_a_critical_issue(monkeypatch):
    # D25: every claude_code task fails in this mode, so it must not be quiet.
    monkeypatch.setattr(settings, "driver_claude_sandbox", "docker")
    r = _report()
    assert _codes(r) == ["driver_sandbox_fenced"]
    assert r.status == "critical"
    assert "task" in r.issues[0].detail
    # Containers are not in use then, so a missing daemon is not also raised.
    r = _report(containers={"available": False, "reason": "x"})
    assert _codes(r) == ["driver_sandbox_fenced"]


@pytest.mark.parametrize("mode", ["task", "none"])
def test_task_and_host_modes_are_not_reported_as_fenced(mode, monkeypatch):
    monkeypatch.setattr(settings, "driver_claude_sandbox", mode)
    assert "driver_sandbox_fenced" not in _codes(_report())


def test_the_report_carries_no_task_data():
    d = _report(tasks={"stale_leases": 1}).as_dict()
    text = str(d)
    assert "instruction" not in text and "error" not in d["tasks"]
    assert set(d) == {"status", "checked_at", "runner", "tasks", "containers", "issues"}


async def test_container_view_counts_aged_orphans_and_reads_usage(monkeypatch):
    live = "11111111-1111-1111-1111-111111111111"
    dead = "22222222-2222-2222-2222-222222222222"
    ps = (
        f"lg-rt-a|{live}|driver|running|2026-11-19 09:00:00 +0000 UTC\n"
        f"lg-rt-egress-a|{live}|egress|running|2026-11-19 09:00:00 +0000 UTC\n"
        f"lg-rt-egress-b|{dead}|egress|running|2026-11-19 09:00:00 +0000 UTC\n"
        f"lg-rt-c|{dead}|driver|exited|2026-11-19 09:59:00 +0000 UTC\n"
    )
    nets = f"{dead}|2026-11-19 09:00:00.1 +0000 UTC\n{live}|2026-11-19 09:00:00 +0000 UTC\n"
    stats = "lg-rt-a|153.20%|41.5%|1.66GiB / 4GiB|37\n"
    calls = []

    async def fake_exec(argv, timeout=30, **kw):
        calls.append(argv)
        if argv[1] == "ps":
            return SandboxResult(0, ps, "")
        if argv[1] == "network":
            return SandboxResult(0, nets, "")
        return SandboxResult(0, stats, "")

    monkeypatch.setattr(sandbox, "_exec", fake_exec)
    monkeypatch.setattr(
        task_runtime, "_age_seconds", lambda c, now=None, f=task_runtime._age_seconds: f(c, NOW)
    )
    view = await rh._container_view({live})

    assert view["total"] == 4
    assert view["agents_running"] == 1
    assert view["orphan_containers"] == 1  # the young exited one is still inside the age floor
    assert view["orphan_networks"] == 1
    assert view["agent_usage"] == [
        {
            "cpu_percent": 153.2,
            "memory_percent": 41.5,
            "memory_usage": "1.66GiB / 4GiB",
            "pids": "37",
        }
    ]
    assert any("label=life-graph.runtime.instance=" in " ".join(c) for c in calls)


def test_one_alert_per_issue_per_six_hours():
    a = job.dedup_key("runner_down", datetime(2026, 11, 19, 0, 1, tzinfo=UTC))
    b = job.dedup_key("runner_down", datetime(2026, 11, 19, 5, 59, tzinfo=UTC))
    c = job.dedup_key("runner_down", datetime(2026, 11, 19, 6, 0, tzinfo=UTC))
    d = job.dedup_key("orphans", datetime(2026, 11, 19, 0, 1, tzinfo=UTC))
    assert a == b != c
    assert a != d


async def test_the_dashboard_panel_never_breaks_the_page(monkeypatch):
    from life_graph.services import observability

    async def boom(*a, **k):
        raise RuntimeError("db gone")

    monkeypatch.setattr(rh, "collect", boom)
    out = await observability._runtime_health()
    assert out["status"] == "unknown"


def test_the_alert_job_is_scheduled_in_the_arq_worker():
    from life_graph.workers.settings import WorkerSettings

    names = {
        getattr(c, "name", "") or str(getattr(c, "coroutine", "")) for c in WorkerSettings.cron_jobs
    }
    assert any("check_runtime_health" in n for n in names)
