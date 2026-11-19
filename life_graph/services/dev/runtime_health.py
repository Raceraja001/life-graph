"""Health of the dev-task runtime: runner, leases, queue, failures, containers.

One report for the dashboard (``GET /kernel/observability/system`` -> ``runtime``) and the
alert job (workers/runtime_health.py). Install-wide by design: the runner is
one per database and claims across tenants, so this returns **counts and
issue codes only**, never task ids, instructions or errors.

What it watches, and why each matters:

- ``runner_down``: nobody holds the runner lock, so nothing runs queued work.
  The worker unit restarts on its own; this catches it staying down.
- ``stale_leases``: a running task whose lease stopped heartbeating, so its
  runner died. Recovery picks it up after the stale window; this says it
  did not.
- ``queue_stuck``: the oldest queued "start now" task has waited too long.
- ``failures``: many failed tasks in the last 24 hours.
- ``orphans``: runtime containers or networks whose task is not running,
  older than the periodic sweep's age floor, so the sweep missed them.
- ``memory_pressure``: a runtime container near its memory limit.
- ``docker_unavailable``: the checks above could not look at containers.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, text

from life_graph.config import settings
from life_graph.models.db import AgentTask
from life_graph.services.dev import sandbox, task_runtime
from life_graph.services.dev.tasks import RUNNER_LOCK_KEY, _kind_filter

logger = logging.getLogger(__name__)

FAILURES_24H_WARN = 5
QUEUE_WAIT_WARN = timedelta(minutes=30)
MEMORY_PERCENT_WARN = 90.0

CRITICAL = "critical"
WARNING = "warning"


@dataclass
class Issue:
    code: str
    severity: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "severity": self.severity, "detail": self.detail}


@dataclass
class Report:
    checked_at: str
    runner: dict[str, Any] = field(default_factory=dict)
    tasks: dict[str, Any] = field(default_factory=dict)
    containers: dict[str, Any] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)

    @property
    def status(self) -> str:
        if any(i.severity == CRITICAL for i in self.issues):
            return CRITICAL
        return WARNING if self.issues else "ok"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "checked_at": self.checked_at,
            "runner": self.runner,
            "tasks": self.tasks,
            "containers": self.containers,
            "issues": [i.as_dict() for i in self.issues],
        }


def _percent(raw: str) -> float | None:
    try:
        return float(raw.strip().rstrip("%"))
    except ValueError:
        return None


async def _container_view(running_ids: set[str]) -> dict[str, Any]:
    """Runtime containers of this install: counts, orphans, CPU/memory. Raises on docker errors."""
    mine = [
        "--filter",
        f"label={task_runtime.RUNTIME_LABEL}=1",
        "--filter",
        f"label={task_runtime.RUNTIME_LABEL}.instance={task_runtime.instance_id()}",
    ]
    fmt = (
        f'{{{{.Names}}}}|{{{{.Label "{task_runtime.RUNTIME_LABEL}.task"}}}}'
        f'|{{{{.Label "{task_runtime.RUNTIME_LABEL}.role"}}}}|{{{{.State}}}}|{{{{.CreatedAt}}}}'
    )
    res = await sandbox._exec(["docker", "ps", "-a", *mine, "--format", fmt], timeout=30)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip()[-200:] or "docker ps failed")
    floor = task_runtime.PERIODIC_MIN_AGE_SECONDS
    running_names: list[str] = []
    orphans = 0
    total = 0
    for line in (res.stdout or "").splitlines():
        name, task, role, state, created = (line.split("|", 4) + [""] * 4)[:5]
        if not name:
            continue
        total += 1
        if state == "running" and role == "driver":
            running_names.append(name)
        age = task_runtime._age_seconds(created)
        if task not in running_ids and age is not None and age >= floor:
            orphans += 1
    nres = await sandbox._exec(
        [
            "docker",
            "network",
            "ls",
            *mine,
            "--format",
            f'{{{{.Label "{task_runtime.RUNTIME_LABEL}.task"}}}}|{{{{.CreatedAt}}}}',
        ],
        timeout=30,
    )
    orphan_networks = 0
    if nres.returncode == 0:
        for line in (nres.stdout or "").splitlines():
            task, _, created = line.partition("|")
            age = task_runtime._age_seconds(created)
            if task and task not in running_ids and age is not None and age >= floor:
                orphan_networks += 1
    stats: list[dict[str, Any]] = []
    if running_names:
        sres = await sandbox._exec(
            [
                "docker",
                "stats",
                "--no-stream",
                "--format",
                "{{.Name}}|{{.CPUPerc}}|{{.MemPerc}}|{{.MemUsage}}|{{.PIDs}}",
                *running_names,
            ],
            timeout=30,
        )
        for line in (sres.stdout or "").splitlines() if sres.returncode == 0 else []:
            _name, cpu, mem, usage, pids = (line.split("|", 4) + [""] * 4)[:5]
            stats.append(
                {
                    "cpu_percent": _percent(cpu),
                    "memory_percent": _percent(mem),
                    "memory_usage": usage.strip(),
                    "pids": pids.strip(),
                }
            )
    return {
        "total": total,
        "agents_running": len(running_names),
        "orphan_containers": orphans,
        "orphan_networks": orphan_networks,
        "agent_usage": stats,
    }


async def collect(session_factory, *, now: datetime | None = None) -> Report:
    """Build the report. Never raises: a check that cannot run becomes an issue."""
    now = now or datetime.now(UTC)
    report = Report(checked_at=now.isoformat())
    running_ids: set[str] = set()
    try:
        async with session_factory() as session:
            holders = (
                await session.execute(
                    text(
                        "SELECT count(*) FROM pg_locks l WHERE l.locktype = 'advisory' "
                        "AND l.granted AND ((l.classid::bigint << 32) | l.objid::bigint) = :k"
                    ),
                    {"k": RUNNER_LOCK_KEY},
                )
            ).scalar() or 0
            running = (
                await session.execute(
                    select(AgentTask.id, AgentTask.properties).where(
                        _kind_filter(), AgentTask.status == "running"
                    )
                )
            ).all()
            oldest_queued = (
                await session.execute(
                    select(func.min(AgentTask.created_at)).where(
                        _kind_filter(),
                        AgentTask.status == "queued",
                        AgentTask.properties["start_now"].astext == "true",
                    )
                )
            ).scalar()
            queued = (
                await session.execute(
                    select(func.count()).where(_kind_filter(), AgentTask.status == "queued")
                )
            ).scalar() or 0
            failed_24h = (
                await session.execute(
                    select(func.count()).where(
                        _kind_filter(),
                        AgentTask.status == "failed",
                        # completed_at, not updated_at: PR sync and other jobs
                        # touch old rows (prod showed 11 by updated_at vs 1).
                        func.coalesce(AgentTask.completed_at, AgentTask.created_at)
                        >= now - timedelta(hours=24),
                    )
                )
            ).scalar() or 0
    except Exception as exc:  # noqa: BLE001
        report.issues.append(Issue("db_unavailable", CRITICAL, f"database check failed: {exc}"))
        return report

    from life_graph.services.dev.runner import lease_is_stale

    stale = 0
    for task_id, props in running:
        running_ids.add(str(task_id))
        lease = (props or {}).get("lease")
        if isinstance(lease, dict) and lease_is_stale(lease, now):
            stale += 1
    report.runner = {
        "enabled": settings.dev_task_runner_enabled,
        "mode": settings.dev_task_runner_mode,
        "lock_holders": int(holders),
    }
    wait = None
    if oldest_queued is not None:
        oq = oldest_queued if oldest_queued.tzinfo else oldest_queued.replace(tzinfo=UTC)
        wait = max(0, int((now - oq).total_seconds()))
    report.tasks = {
        "running": len(running),
        "stale_leases": stale,
        "queued": int(queued),
        "oldest_start_now_wait_seconds": wait,
        "failed_24h": int(failed_24h),
    }

    if shutil.which("docker") is None:
        report.containers = {"available": False, "reason": "docker CLI not found"}
    else:
        try:
            report.containers = {"available": True, **await _container_view(running_ids)}
        except Exception as exc:  # noqa: BLE001
            report.containers = {"available": False, "reason": f"docker check failed: {exc}"}
    evaluate(report)
    return report


def evaluate(report: Report) -> None:
    """Turn the collected numbers into issues (pure: no I/O)."""
    runner, tasks, containers = report.runner, report.tasks, report.containers
    if runner.get("enabled") and not runner.get("lock_holders"):
        report.issues.append(
            Issue("runner_down", CRITICAL, "no process holds the dev-task runner lock")
        )
    if tasks.get("stale_leases"):
        report.issues.append(
            Issue(
                "stale_leases",
                CRITICAL,
                f"{tasks['stale_leases']} running task(s) stopped heartbeating",
            )
        )
    wait = tasks.get("oldest_start_now_wait_seconds")
    if wait is not None and wait > QUEUE_WAIT_WARN.total_seconds():
        report.issues.append(
            Issue("queue_stuck", WARNING, f"a start-now task has waited {wait // 60} min")
        )
    if tasks.get("failed_24h", 0) >= FAILURES_24H_WARN:
        report.issues.append(
            Issue("failures", WARNING, f"{tasks['failed_24h']} dev tasks failed in the last 24 h")
        )
    if not containers.get("available", True):
        if settings.driver_claude_sandbox in ("task", "docker"):
            report.issues.append(
                Issue("docker_unavailable", WARNING, containers.get("reason", "docker unavailable"))
            )
        return
    if containers.get("orphan_containers") or containers.get("orphan_networks"):
        report.issues.append(
            Issue(
                "orphans",
                WARNING,
                f"{containers.get('orphan_containers', 0)} container(s) and "
                f"{containers.get('orphan_networks', 0)} network(s) left by tasks that are "
                "not running",
            )
        )
    hot = [
        s
        for s in containers.get("agent_usage", [])
        if (s.get("memory_percent") or 0) >= MEMORY_PERCENT_WARN
    ]
    if hot:
        report.issues.append(
            Issue("memory_pressure", WARNING, f"{len(hot)} agent container(s) at >=90% memory")
        )
