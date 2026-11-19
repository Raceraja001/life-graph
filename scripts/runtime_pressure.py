"""Many task runtimes at once under CPU, memory and process pressure.

Starts N real runtime containers concurrently (DockerTaskRuntime, the same
code path as a dev task, no agent and no database):

- ``burn``: CPU spinners for --seconds (one per core of their --cpus share);
- ``hog``: allocates past its memory limit, so it must be OOM-killed alone;
- ``bomb``: forks without bound, so it must hit its pids limit;
- ``ok``: a small task that must finish normally despite the others.

While they run it samples the host's MemAvailable and ``docker stats`` for
the runtime containers. It passes when the hog was killed (137), the bomb
stayed at its pids cap, every burner and "ok" finished, every teardown
succeeded, nothing was left behind, and the host kept at least
--min-available-gb free. The runtimes carry their own instance label
("-script"), so a dev-task worker's sweep never touches them.

    python scripts/runtime_pressure.py --burners 3 --out evals/reliability/<date>-pressure.json
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

IMAGE_DEFAULT = "life-graph-sandbox-egress:dev"  # python + coreutils; no CLI needed


def _mem_available_gb() -> float:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) / 1024 / 1024
    return -1.0


def _stats(instance: str) -> list[dict]:
    names = subprocess.run(
        ["docker", "ps", "--filter", f"label=life-graph.runtime.instance={instance}",
         "--filter", "label=life-graph.runtime.role=driver", "--format", "{{.Names}}"],
        capture_output=True, text=True,
    ).stdout.split()  # fmt: skip
    if not names:
        return []
    out = subprocess.run(
        ["docker", "stats", "--no-stream", "--format",
         "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}|{{.PIDs}}", *names],
        capture_output=True, text=True,
    ).stdout  # fmt: skip
    rows = []
    for line in out.splitlines():
        name, cpu, usage, mem, pids = (line.split("|") + [""] * 5)[:5]
        rows.append({"name": name, "cpu": cpu, "mem": usage, "mem_pct": mem, "pids": pids})
    return rows


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default=IMAGE_DEFAULT)
    ap.add_argument("--burners", type=int, default=3)
    ap.add_argument("--fillers", type=int, default=0, help="containers that hold --fill-mb")
    ap.add_argument("--fill-mb", type=int, default=400)
    ap.add_argument("--seconds", type=int, default=45)
    ap.add_argument("--memory", default="512m")
    ap.add_argument("--cpus", default="2")
    ap.add_argument("--pids", type=int, default=128)
    ap.add_argument("--min-available-gb", type=float, default=4.0)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    from life_graph.config import settings

    settings.edition = (settings.edition or "") + "-script"
    from life_graph.drivers.dispatcher import tenant_scratch_root
    from life_graph.services.dev import sandbox, task_runtime

    instance = task_runtime.instance_id()
    rt = task_runtime.DockerTaskRuntime()
    scratch = Path(tenant_scratch_root("pressure")) / f"lg_dispatch_pressure_{uuid.uuid4().hex[:6]}"
    cpus = max(1, int(float(args.cpus)))
    burn = (
        f"for i in $(seq {cpus}); do timeout {args.seconds} sh -c 'while :; do :; done' & done; "
        "wait; echo burned"
    )
    hog = "python3 -c \"b=[]\nwhile True: b.append(bytearray(64*1024*1024))\""
    bomb = (
        "python3 -c \"import os,time\nn=0\nwhile True:\n"
        "    try:\n        p=os.fork()\n    except OSError:\n        print('capped', n); break\n"
        "    if p==0:\n        time.sleep(30); os._exit(0)\n    n+=1\""
    )
    fill = (
        f"python3 -c \"import time\nb=bytearray({args.fill_mb}*1024*1024)\n"
        f"for i in range(0, len(b), 4096): b[i]=1\nprint('filled'); time.sleep({args.seconds})\""
    )
    jobs = (
        [("burn", burn)] * args.burners
        + [("fill", fill)] * args.fillers
        + [("hog", hog), ("bomb", bomb), ("ok", "echo ok")]
    )

    async def one(kind: str, command: str) -> dict:
        wt = scratch / f"wt_{kind}_{uuid.uuid4().hex[:6]}"
        wt.mkdir(parents=True)
        t0 = time.monotonic()
        try:
            out = await rt.run(task_runtime.RuntimeRequest(
                task_id=str(uuid.uuid4()), tenant_id="pressure", driver="probe", image=args.image,
                command=("sh", "-c", command), workspace=wt, memory=args.memory, cpus=args.cpus,
                pids_limit=args.pids, timeout=args.seconds + 60, tmp_size="64m",
            ))  # fmt: skip
            return {"kind": kind, "exit": out.returncode, "stdout": out.stdout.strip()[-120:],
                    "seconds": round(time.monotonic() - t0, 1),
                    "teardown": out.metadata.get("teardown", {}).get("ok")}  # fmt: skip
        except sandbox.SandboxUnavailableError as exc:
            meta = getattr(exc, "runtime_metadata", {}) or {}
            return {"kind": kind, "error": str(exc)[:200], "seconds": round(time.monotonic() - t0, 1),
                    "teardown": (meta.get("teardown") or {}).get("ok")}  # fmt: skip

    before = _mem_available_gb()
    samples: list[dict] = []
    stop = asyncio.Event()

    async def sampler() -> None:
        while not stop.is_set():
            samples.append({"t": round(time.monotonic(), 1), "mem_available_gb": round(_mem_available_gb(), 2),
                            "containers": await asyncio.to_thread(_stats, instance)})  # fmt: skip
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), 5)

    s = asyncio.create_task(sampler())
    results = await asyncio.gather(*(one(k, c) for k, c in jobs))
    stop.set()
    await s
    import shutil

    shutil.rmtree(scratch, ignore_errors=True)
    left = subprocess.run(
        ["docker", "ps", "-aq", "--filter", f"label=life-graph.runtime.instance={instance}"],
        capture_output=True, text=True,
    ).stdout.split()  # fmt: skip
    nets = subprocess.run(
        ["docker", "network", "ls", "-q", "--filter", f"label=life-graph.runtime.instance={instance}"],
        capture_output=True, text=True,
    ).stdout.split()  # fmt: skip
    min_avail = min([x["mem_available_gb"] for x in samples] or [before])
    peak_running = max([len(x["containers"]) for x in samples] or [0])
    by = {k: [r for r in results if r["kind"] == k] for k in ("burn", "fill", "hog", "bomb", "ok")}
    checks = {
        "burners_finished": all(r.get("exit") == 0 and "burned" in r.get("stdout", "") for r in by["burn"]),
        "fillers_held_memory": all(r.get("exit") == 0 and "filled" in r.get("stdout", "") for r in by["fill"]),
        "hog_oom_killed_alone": all(r.get("exit") == 137 for r in by["hog"]),
        "bomb_capped": all("capped" in r.get("stdout", "") for r in by["bomb"]),
        "ok_finished": all(r.get("exit") == 0 for r in by["ok"]),
        "all_teardowns_ok": all(r.get("teardown") for r in results),
        "nothing_left": not left and not nets,
        "host_headroom": min_avail >= args.min_available_gb,
    }  # fmt: skip
    report = {
        "jobs": len(jobs), "limits": {"memory": args.memory, "cpus": args.cpus, "pids": args.pids},
        "mem_available_gb": {"before": round(before, 2), "min": min_avail},
        "peak_concurrent_agents": peak_running, "results": results, "checks": checks,
        "passed": all(checks.values()), "samples": samples,
    }  # fmt: skip
    text = json.dumps(report, indent=1)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text)
    summary = {k: v for k, v in report.items() if k != "samples"}
    print(json.dumps(summary, indent=1))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
