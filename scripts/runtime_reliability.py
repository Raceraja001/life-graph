"""Reliability checks for the dev-task runner and runtime (work order Stage 5).

Runs real processes and containers against a THROWAWAY database -- never the
dev or prod one. A fake ``claude`` binary stands in for the agent (no model,
no cost): it logs a unique token from its instruction plus its working
directory, so "ran exactly once" and "own worktree" can be counted.

    LIFE_GRAPH_DATABASE_URL=postgresql+asyncpg://...@localhost:55499/life_graph \\
        python scripts/runtime_reliability.py --out evals/reliability/<date>.json

Checks (each reported pass/fail with its measurements):

1.  runtime: the agent container killed from outside mid-run -> the run ends,
    teardown removes everything;
2.  runtime: the egress proxy killed mid-run (network interruption) -> the run
    ends, teardown removes everything;
3.  worker: a start from another process is picked up via NOTIFY;
4.  worker: cancel stops the agent's whole process group;
5.  worker: SIGTERM drains the running task before exiting;
6.  worker: SIGKILL mid-run (a crash) -> a standby worker takes the lock,
    recovers the task once its lease goes stale, and runs it exactly once;
7.  duplicate delivery: two workers at once never run a task twice;
8.  concurrency: three tasks at once each get their own worktree.

Refuses to run unless the database name contains "test"/"wo"/"throwaway" or
--i-know-this-is-a-throwaway-db is passed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable

FAKE = r"""#!/bin/sh
# Fake claude: log "<token> <pwd>" then work for $FAKE_SECONDS, with a child.
token=$(printf '%s' "$*" | grep -o 'TOKEN-[a-z0-9]*' | head -1)
echo "$token $(pwd)" >> "$FAKE_LOG"
sleep "${FAKE_SECONDS:-4}" &
echo "$token $!" >> "$FAKE_LOG.children"
printf '%s\n' '{"type":"system","subtype":"init","model":"fake"}'
wait
echo 'x = 1' > reliability_marker.py
printf '%s\n' '{"type":"result","subtype":"success","is_error":false,"result":"done","num_turns":1}'
"""


def _env(scratch: Path, fake_seconds: int, extra: dict | None = None) -> dict:
    return {
        **os.environ,
        "PYTHONPATH": str(ROOT),
        "LIFE_GRAPH_DEV_TASK_RUNNER_MODE": "worker",
        "LIFE_GRAPH_DRIVER_CLAUDE_CODE_BIN": str(scratch / "fake-claude.sh"),
        "LIFE_GRAPH_DRIVER_CLAUDE_SANDBOX": "none",
        "LIFE_GRAPH_DEV_RUNNER_HEARTBEAT_SECONDS": "3",
        "LIFE_GRAPH_DEV_RUNNER_LEASE_STALE_SECONDS": "12",
        "LIFE_GRAPH_DEV_RUNNER_DRAIN_SECONDS": "30",
        # Host-run CLIs get an allowlisted environment (drivers/host_exec.py):
        # the fake's own variables must be passed through explicitly.
        "LIFE_GRAPH_DRIVER_HOST_ENV_PASSTHROUGH": "FAKE_LOG,FAKE_SECONDS",
        "FAKE_LOG": str(scratch / "fake.log"),
        "FAKE_SECONDS": str(fake_seconds),
        **(extra or {}),
    }


class Worker:
    def __init__(self, scratch: Path, name: str, fake_seconds: int = 4, extra: dict | None = None):
        # Lives as long as the worker process it captures.
        self.log = open(scratch / f"worker-{name}.log", "w")  # noqa: SIM115
        self.proc = subprocess.Popen(
            [PY, "-m", "life_graph.workers.dev_runner"],
            env=_env(scratch, fake_seconds, extra), cwd=str(ROOT),
            stdout=self.log, stderr=subprocess.STDOUT,
        )  # fmt: skip

    def stop(self, sig=signal.SIGTERM, timeout=60) -> int | None:
        if self.proc.poll() is None:
            self.proc.send_signal(sig)
            try:
                self.proc.wait(timeout)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        return self.proc.returncode


async def _project(scratch: Path, tenant: str):
    from life_graph.api.dependencies import get_persona_service, get_project_registry
    from life_graph.config import settings

    repo = scratch / f"repo-{uuid.uuid4().hex[:6]}"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "a.py").write_text("x = 0\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=r@r", "-c", "user.name=r", "commit", "-qm", "i"],
        cwd=repo, check=True,
    )  # fmt: skip
    settings.tool_fs_roots = str(scratch)
    await get_persona_service().seed_builtins(tenant)
    return await get_project_registry().register(tenant, {"name": repo.name, "path": str(repo)})


async def _start(tenant, project, token, start=True):
    from life_graph.services.dev import tasks as dev_tasks
    from life_graph.storage.database import async_session

    return (
        await dev_tasks.create_dev_task(
            async_session,
            tenant,
            instruction=f"Make the change {token}",
            project=project,
            persona_name="code-fixer",
            start=start,
        )  # fmt: skip
    )["id"]


async def _status(task_id):
    from sqlalchemy import text

    from life_graph.storage.database import async_session

    async with async_session() as s:
        return (
            await s.execute(
                text("SELECT status FROM agent_tasks WHERE id = CAST(:i AS uuid)"), {"i": task_id}
            )
        ).scalar()


async def _wait(task_id, wanted, timeout=90):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        st = await _status(task_id)
        if st in wanted:
            return st, round(time.monotonic() - t0, 2)
        await asyncio.sleep(0.3)
    return await _status(task_id), None


def _runs(scratch: Path, token: str) -> list[str]:
    log = scratch / "fake.log"
    lines = log.read_text().splitlines() if log.exists() else []
    return [ln.split(" ", 1)[1] for ln in lines if ln.startswith(token + " ")]


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    stat = Path(f"/proc/{pid}/stat")
    return stat.exists() and stat.read_text().split()[2] != "Z"


async def runtime_checks(scratch: Path) -> dict:
    from life_graph.drivers.dispatcher import tenant_scratch_root
    from life_graph.services.dev import sandbox, task_runtime

    out: dict = {}
    image = "life-graph-sandbox-egress:dev"  # python + coreutils; enough here
    for case in ("container_killed", "proxy_killed"):
        wt = Path(tenant_scratch_root("reliability")) / f"lg_dispatch_{uuid.uuid4().hex[:6]}" / "wt"
        wt.mkdir(parents=True)
        task_id = str(uuid.uuid4())
        req = task_runtime.RuntimeRequest(
            task_id=task_id, tenant_id="reliability", driver="probe", image=image,
            command=("sleep", "40"), workspace=wt, egress_allowlist=("api.anthropic.com",),
            memory="128m", cpus="0.5", pids_limit=32, timeout=60,
        )  # fmt: skip
        run = asyncio.get_running_loop().create_task(task_runtime.DockerTaskRuntime().run(req))
        label = f"label=life-graph.runtime.task={task_id}"
        role = "driver" if case == "container_killed" else "egress"
        name = ""
        # Mid-run: wait for the agent container in both cases, then kill.
        for _ in range(60):
            up = subprocess.run(
                ["docker", "ps", "-q", "--filter", label, "--filter", "label=life-graph.runtime.role=driver"],
                capture_output=True, text=True,
            ).stdout.strip()  # fmt: skip
            if up:
                break
            await asyncio.sleep(0.5)
        for _ in range(60):
            name = subprocess.run(
                ["docker", "ps", "--filter", label, "--filter", f"label=life-graph.runtime.role={role}",
                 "--format", "{{.Names}}"], capture_output=True, text=True,
            ).stdout.strip()  # fmt: skip
            if name:
                break
            await asyncio.sleep(0.5)
        t0 = time.monotonic()
        subprocess.run(["docker", "kill", name], capture_output=True)
        try:
            outcome = await asyncio.wait_for(run, 70)
            result = {"exit_code": outcome.returncode, "teardown": outcome.metadata["teardown"]}
        except sandbox.SandboxUnavailableError as exc:
            result = {
                "error": str(exc)[:120],
                "teardown": getattr(exc, "runtime_metadata", {}).get("teardown"),
            }
        left = subprocess.run(
            ["docker", "ps", "-aq", "--filter", label], capture_output=True, text=True
        ).stdout.split()
        nets = subprocess.run(
            ["docker", "network", "ls", "-q", "--filter", label], capture_output=True, text=True
        ).stdout.split()
        result["seconds_after_kill"] = round(time.monotonic() - t0, 1)
        result["leftover_containers"] = len(left)
        result["leftover_networks"] = len(nets)
        # Container killed: the run ends at once. Proxy killed: the agent keeps
        # running without a way out (here: sleep), and teardown still removes all.
        result["pass"] = (
            len(left) == 0 and len(nets) == 0 and (result.get("teardown") or {}).get("ok") is True
        )
        out[case] = result
    return out


async def worker_checks(scratch: Path, tenant: str, project) -> dict:
    from life_graph.services.dev import tasks as dev_tasks
    from life_graph.storage.database import async_session

    out: dict = {}

    # 3 + 4 + 5: pickup, cancel, SIGTERM drain.
    w = Worker(scratch, "a", fake_seconds=6)
    await asyncio.sleep(7)
    tok = f"TOKEN-{uuid.uuid4().hex[:8]}"
    tid = await _start(tenant, project, tok)
    st, secs = await _wait(tid, {"running"}, 30)
    out["pickup_via_notify"] = {
        "status": st,
        "seconds": secs,
        "pass": st == "running" and secs is not None and secs < 10,
    }

    tok_c = f"TOKEN-{uuid.uuid4().hex[:8]}"
    tid_c = await _start(tenant, project, tok_c)
    await _wait(tid_c, {"running"}, 30)
    await asyncio.sleep(1.5)
    await dev_tasks.request_cancel(async_session, tenant, tid_c)
    st, secs = await _wait(tid_c, {"cancelled", "completed", "failed"}, 30)
    await asyncio.sleep(1)
    # Only the cancelled task's own children: another task's may be running.
    child_file = scratch / "fake.log.children"
    children = [
        int(line.split()[1])
        for line in (child_file.read_text().splitlines() if child_file.exists() else [])
        if line.startswith(tok_c + " ")
    ]
    out["cancel_kills_group"] = {
        "status": st, "seconds": secs, "children_alive": [p for p in children if _alive(p)],
        "children_seen": len(children),
        # Children must have been seen, or "none alive" proves nothing.
        "pass": st == "cancelled" and bool(children) and not [p for p in children if _alive(p)],
    }  # fmt: skip
    await _wait(tid, {"completed", "failed"}, 60)

    tok_d = f"TOKEN-{uuid.uuid4().hex[:8]}"
    tid_d = await _start(tenant, project, tok_d)
    await _wait(tid_d, {"running"}, 30)
    t0 = time.monotonic()
    code = w.stop(signal.SIGTERM, timeout=60)
    st = await _status(tid_d)
    out["sigterm_drains"] = {
        "exit": code, "seconds_to_exit": round(time.monotonic() - t0, 1), "task_after": st,
        "pass": st == "completed" and code == 0,
    }  # fmt: skip

    # 6: SIGKILL mid-run; a standby takes over and recovers exactly once.
    a = Worker(scratch, "b1", fake_seconds=8)
    await asyncio.sleep(7)
    b = Worker(scratch, "b2", fake_seconds=1)  # standby: waits for the lock
    tok_k = f"TOKEN-{uuid.uuid4().hex[:8]}"
    tid_k = await _start(tenant, project, tok_k)
    await _wait(tid_k, {"running"}, 30)
    # Kill only once the agent itself is running, so the crash cuts a real run.
    for _ in range(60):
        if _runs(scratch, tok_k):
            break
        await asyncio.sleep(0.5)
    a.stop(signal.SIGKILL)
    t0 = time.monotonic()
    st, secs = await _wait(tid_k, {"completed", "failed"}, 120)
    out["sigkill_standby_recovers"] = {
        "final": st, "seconds_to_done": secs, "agent_runs": len(_runs(scratch, tok_k)),
        "pass": st == "completed" and len(_runs(scratch, tok_k)) == 2,  # killed run + the one re-run
        "note": "2 = the run the SIGKILL cut off, plus exactly one recovery run",
    }  # fmt: skip

    # 7: duplicate delivery -- b holds the lock now; start another worker too.
    c = Worker(scratch, "c", fake_seconds=1)
    await asyncio.sleep(7)
    toks = [f"TOKEN-{uuid.uuid4().hex[:8]}" for _ in range(6)]
    tids = [await _start(tenant, project, t) for t in toks]
    for t in tids:
        await _wait(t, {"completed", "failed"}, 120)
    counts = {t: len(_runs(scratch, t)) for t in toks}
    out["no_duplicate_delivery"] = {
        "runs_per_task": list(counts.values()),
        "pass": all(n == 1 for n in counts.values()),
    }

    # 8: three at once, own worktrees (max concurrency 3 by default).
    for wk in (b, c):
        wk.stop()
    d = Worker(scratch, "d", fake_seconds=5)
    await asyncio.sleep(7)
    toks = [f"TOKEN-{uuid.uuid4().hex[:8]}" for _ in range(3)]
    tids = [await _start(tenant, project, t) for t in toks]
    for t in tids:
        await _wait(t, {"completed", "failed"}, 90)
    dirs = [_runs(scratch, t)[0] for t in toks if _runs(scratch, t)]
    out["concurrent_own_worktrees"] = {
        "worktrees": len(set(dirs)), "tasks": len(toks),
        "pass": len(set(dirs)) == len(toks) == len(dirs),
    }  # fmt: skip
    d.stop()
    return out


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    ap.add_argument("--i-know-this-is-a-throwaway-db", action="store_true")
    args = ap.parse_args()
    url = os.environ.get("LIFE_GRAPH_DATABASE_URL", "")
    if not args.i_know_this_is_a_throwaway_db and not any(
        k in url for k in ("55499", "test", "throwaway")
    ):
        print(
            "refusing: LIFE_GRAPH_DATABASE_URL does not look like a throwaway database",
            file=sys.stderr,
        )
        return 2
    scratch = Path(f"/tmp/lg-reliability-{uuid.uuid4().hex[:6]}")
    scratch.mkdir()
    (scratch / "fake-claude.sh").write_text(FAKE)
    (scratch / "fake-claude.sh").chmod(0o755)
    tenant = f"reliability_{uuid.uuid4().hex[:6]}"
    project = await _project(scratch, tenant)
    report = {
        "runtime": await runtime_checks(scratch),
        "worker": await worker_checks(scratch, tenant, project),
    }
    flat = {**report["runtime"], **report["worker"]}
    report["passed"] = sum(1 for v in flat.values() if v.get("pass"))
    report["total"] = len(flat)
    text = json.dumps(report, indent=2, default=str)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text)
    print(text)
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
