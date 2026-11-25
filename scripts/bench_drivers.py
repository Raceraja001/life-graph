"""Benchmark the coding engines on small, hidden-tested tasks.

Which free engine should do the work: qwen3:14b through the local driver,
a coder model, or OpenCode? Guessing from single trials misled us (one run
"succeeded" without editing anything), so this measures it:

- each task in evals/driver_tasks.yaml runs on a fresh copy of its fixture app;
- afterwards a **hidden test** the engine never saw is written in and run in
  the verifier sandbox. Pass/fail is that test, not the engine's own claims;
- per run: hidden-test result, the driver's own verdict and stop_reason,
  seconds, tool calls, edits made and refused, condensations.

    python scripts/bench_drivers.py \\
        --engine local:ollama_chat/qwen3:14b \\
        --engine local:ollama_chat/qwen2.5-coder:14b \\
        --engine opencode:ollama/qwen3-coder:30b \\
        --engine claude_code \\
        --repeat 2 [--task node-remove ...] [--category bugfix ...] [--context 32768]

Results go to evals/driver_bench/<UTC timestamp>.json, and a markdown summary
is printed. Engines run one after another: two local models at once do not
fit the GPU.

Stage 5 of docs/work-orders/secure-execution-runtime.md added:

- ``claude_code`` engine, run in the per-task runtime (``--runtime task``, the
  default; ``none`` = host), so the benchmark measures the boundary agents
  actually run in. It may use its shell there (tests, builds).
- task ``category`` (feature, bugfix, refactor, multi_file, edge_cases) and
  ``setup`` files written before the fixture's first commit;
- **verification quality**: the project's own verifier chain
  (``build_ok_diff`` + ``tests_pass``) is run BEFORE the hidden test, and the
  report counts how often it agrees with the hidden test -- a chain that
  passes wrong work is a false positive;
- runtime cost and resources: the runtime's own duration/exit/teardown, the
  CLI's reported cost, peak CPU and memory of the agent container (sampled
  with ``docker stats``), and the run's reproducibility metadata (git SHA,
  image ids, models).
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
TASKS = ROOT / "evals" / "driver_tasks.yaml"
OUT_DIR = ROOT / "evals" / "driver_bench"
EDIT_TOOLS = {"code_edit", "file_write", "edit", "write", "Edit", "Write"}


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=bench@localhost", "-c", "user.name=bench", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def fresh_copy(fixture: Path, setup: dict | None = None) -> Path:
    # Under the dispatch scratch root: the task runtime only mounts a
    # workspace from there (services/dev/sandbox.py allowed_bind_roots).
    from life_graph.drivers.dispatcher import tenant_scratch_root

    base = Path(tempfile.mkdtemp(prefix="lg_dispatch_bench_", dir=tenant_scratch_root("bench")))
    repo = base / "repo"
    shutil.copytree(
        fixture,
        repo,
        ignore=shutil.ignore_patterns(
            "node_modules", "__pycache__", "template.json", ".pytest_cache"
        ),
    )
    for rel, content in (setup or {}).items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(content, encoding="utf-8")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "fixture")
    return repo


def make_driver(engine: str):
    kind, _, model = engine.partition(":")
    if kind == "local":
        from life_graph.drivers.local import LocalDriver

        return LocalDriver(), model or None
    if kind == "opencode":
        from life_graph.config import settings
        from life_graph.drivers.opencode import OpencodeDriver

        if model:
            settings.driver_opencode_model = model
        return OpencodeDriver(), None
    if kind == "cloud":
        # A free cloud model, as code-fixer-cloud runs it (drivers/cloud.py).
        from life_graph.drivers.cloud import CloudDriver

        return CloudDriver(), model or None
    if kind == "claude_code":
        from life_graph.drivers.claude_code import ClaudeCodeDriver

        return ClaudeCodeDriver(), None
    raise SystemExit(
        f"unknown engine kind {kind!r} (use local:<model>, opencode:<model> or cloud:<model>)"
    )


async def sample_container(task_id: str, stop: asyncio.Event) -> dict:
    """Peak CPU% and memory (MiB) of the task's agent container, every 2 s."""
    peak = {"cpu_pct": 0.0, "mem_mib": 0.0, "samples": 0}
    units = {
        "B": 1 / 2**20,
        "KiB": 1 / 1024,
        "MiB": 1,
        "GiB": 1024,
        "kB": 1 / 1024,
        "MB": 1,
        "GB": 1024,
    }
    label = f"label=life-graph.runtime.task={task_id}"
    while not stop.is_set():
        proc = await asyncio.create_subprocess_exec(
            "docker", "ps", "-q", "--filter", label, "--filter", "label=life-graph.runtime.role=driver",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        )  # fmt: skip
        ids = (await proc.communicate())[0].decode().split()
        if ids:
            proc = await asyncio.create_subprocess_exec(
                "docker", "stats", "--no-stream", "--format", "{{.CPUPerc}}|{{.MemUsage}}", *ids,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            )  # fmt: skip
            for line in (await proc.communicate())[0].decode().splitlines():
                try:
                    cpu, mem = line.split("|")
                    used = mem.split("/")[0].strip()
                    num = "".join(c for c in used if c.isdigit() or c == ".")
                    unit = used[len(num) :].strip()
                    peak["cpu_pct"] = max(peak["cpu_pct"], float(cpu.strip().rstrip("%")))
                    peak["mem_mib"] = max(peak["mem_mib"], float(num) * units.get(unit, 1))
                    peak["samples"] += 1
                except ValueError:
                    continue
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), 2)
    return {k: round(v, 1) if isinstance(v, float) else v for k, v in peak.items()}


async def own_checks(repo: Path, toolchain: str, spec: dict) -> bool | None:
    """The project's own verifier chain, as the dispatcher would run it."""
    from life_graph.services.dev.verifiers import verifier_chain

    ctx = {"sandbox_toolchain": toolchain, "sandbox_test_timeout": 180}
    results = await verifier_chain.run_chain(["build_ok_diff", "tests_pass"], repo, ctx)
    if verifier_chain.inconclusive(results):
        return None
    return verifier_chain.all_passed(results)


def edit_counts(steps: list[dict]) -> tuple[int, int]:
    """(edits that landed, edits refused) from a run's recorded steps."""
    ok = failed = 0
    for s in steps:
        if s.get("kind") != "tool_result" or s.get("tool") not in EDIT_TOOLS:
            continue
        content = (s.get("content") or "").lstrip()
        if s.get("is_error") or content.startswith('{"error"'):
            failed += 1
        else:
            ok += 1
    return ok, failed


async def hidden_test(repo: Path, toolchain: str, spec: dict) -> tuple[bool, str]:
    from life_graph.services.dev.verifiers import verifier_chain

    target = repo / spec["path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(spec["content"], encoding="utf-8")
    ctx = {
        "sandbox_toolchain": toolchain,
        "sandbox_test_command": " ".join(spec["command"]),
        "sandbox_test_timeout": 180,
    }
    (result,) = await verifier_chain.run_chain(["tests_pass"], repo, ctx)
    detail = json.dumps(result.evidence)[-400:]
    return bool(result.passed and not result.inconclusive), detail


async def run_one(engine: str, task: dict, fixture: dict, timeout: int) -> dict:
    from life_graph.drivers.base import ContextPacket

    repo = fresh_copy(ROOT / fixture["path"], task.get("setup"))
    driver, model = make_driver(engine)
    tools = ["code_read", "code_search", "code_list", "code_edit"]
    if engine.startswith("claude_code"):
        tools.append("run_command")  # a shell, inside the task runtime
    task_uuid = uuid.uuid4()
    packet = ContextPacket(
        task_id=task_uuid,
        tenant_id="bench",
        task_type="code_change",
        instruction=task["instruction"] + " Make the change; do not stop at describing it.",
        persona_model=model,
        persona_system_prompt="You are Code Fixer. Make the smallest correct change.",
        project_context={"path": str(repo)},
        allowed_tools=tools,
    )
    started = time.monotonic()
    stop = asyncio.Event()
    sampler = asyncio.get_running_loop().create_task(sample_container(str(task_uuid), stop))
    cost = 0.0
    try:
        result = await driver.dispatch(packet, repo, timeout=timeout)
        meta = result.metadata or {}
        driver_ok, error, cost = result.success, result.error, result.cost_usd
    except Exception as exc:  # noqa: BLE001 — one crash is one failed run
        meta, driver_ok, error = {}, False, f"{type(exc).__name__}: {exc}"
    seconds = round(time.monotonic() - started, 1)
    stop.set()
    peak = await sampler
    steps = meta.get("steps") or []
    ok_edits, failed_edits = edit_counts(steps)
    diff = (
        subprocess.run(["git", "diff", "--stat"], cwd=repo, capture_output=True, text=True)
        .stdout.strip()
        .splitlines()
    )
    checks = await own_checks(repo, fixture["toolchain"], task["hidden_test"])
    passed, detail = await hidden_test(repo, fixture["toolchain"], task["hidden_test"])
    shutil.rmtree(repo.parent, ignore_errors=True)
    runtime = meta.get("runtime") or {}
    return {
        "engine": engine,
        "task": task["id"],
        "category": task.get("category", "feature"),
        "passed": passed,
        "own_checks_passed": checks,
        "boundary": meta.get("boundary"),
        "cost_usd": round(cost or 0.0, 4),
        "runtime_seconds": round((runtime.get("duration_ms") or 0) / 1000, 1) or None,
        "runtime_teardown_ok": (runtime.get("teardown") or {}).get("ok"),
        "runtime_image_id": runtime.get("image_id"),
        "model": meta.get("model"),
        "peak_cpu_pct": peak["cpu_pct"],
        "peak_mem_mib": peak["mem_mib"],
        "driver_success": driver_ok,
        "stop_reason": meta.get("stop_reason"),
        "seconds": seconds,
        "tool_calls": meta.get("tool_calls", meta.get("num_turns")),
        "edits_ok": ok_edits,
        "edits_failed": failed_edits,
        "condensed": meta.get("condensed", 0),
        "diff": diff[-1] if diff else "",
        "error": (error or "")[:300],
        "hidden_test_detail": None if passed else detail,
    }


def summary(rows: list[dict]) -> str:
    engines = list(dict.fromkeys(r["engine"] for r in rows))
    tasks = list(dict.fromkeys(r["task"] for r in rows))
    cats = list(dict.fromkeys(r.get("category", "feature") for r in rows))
    qual = [
        "",
        "| engine | own checks agree with hidden test | false positives | inconclusive | cost $ | avg peak MiB |",
        "|---|---|---|---|---|---|",
    ]
    for e in engines:
        mine = [r for r in rows if r["engine"] == e]
        decided = [r for r in mine if r.get("own_checks_passed") is not None]
        agree = sum(r["own_checks_passed"] == r["passed"] for r in decided)
        fp = sum(r["own_checks_passed"] is True and not r["passed"] for r in decided)
        inc = len(mine) - len(decided)
        cost = sum(r.get("cost_usd") or 0 for r in mine)
        mem = [r["peak_mem_mib"] for r in mine if r.get("peak_mem_mib")]
        qual.append(
            f"| {e} | {agree}/{len(decided)} | {fp} | {inc} | {cost:.2f} | "
            f"{(sum(mem) / len(mem)) if mem else 0:.0f} |"
        )
    by_cat = ["", "| category | " + " | ".join(engines) + " |", "|---|" + "---|" * len(engines)]
    for c in cats:
        cells = []
        for e in engines:
            mine = [r for r in rows if r["engine"] == e and r.get("category", "feature") == c]
            cells.append(f"{sum(r['passed'] for r in mine)}/{len(mine)}")
        by_cat.append(f"| {c} | " + " | ".join(cells) + " |")
    lines = [
        "| engine | passed | honest | avg s | edits ok/refused |",
        "|---|---|---|---|---|",
    ]
    for e in engines:
        mine = [r for r in rows if r["engine"] == e]
        passed = sum(r["passed"] for r in mine)
        # "honest": the driver's own verdict agrees with the hidden test.
        honest = sum(r["passed"] == r["driver_success"] for r in mine)
        avg = sum(r["seconds"] for r in mine) / len(mine)
        ok = sum(r["edits_ok"] for r in mine)
        bad = sum(r["edits_failed"] for r in mine)
        lines.append(
            f"| {e} | {passed}/{len(mine)} | {honest}/{len(mine)} | {avg:.0f} | {ok}/{bad} |"
        )
    lines += ["", "| task | " + " | ".join(engines) + " |", "|---|" + "---|" * len(engines)]
    for t in tasks:
        cells = []
        for e in engines:
            mine = [r for r in rows if r["engine"] == e and r["task"] == t]
            cells.append(f"{sum(r['passed'] for r in mine)}/{len(mine)}")
        lines.append(f"| {t} | " + " | ".join(cells) + " |")
    return "\n".join(lines + by_cat + qual)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--engine", action="append", required=True)
    parser.add_argument("--task", action="append")
    parser.add_argument("--category", action="append")
    # No "docker": that driver mode is fenced (D25).
    parser.add_argument("--runtime", default="task", choices=["task", "none"])
    parser.add_argument("--driver-image", help="claude_code runtime image (default: settings)")
    parser.add_argument("--verifier-image", help="python verifier image (default: settings)")
    parser.add_argument("--verifier-node-image", help="node verifier image (default: settings)")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--context", type=int, help="agent_context_tokens for the local driver")
    args = parser.parse_args()

    from life_graph.config import settings

    if args.context:
        os.environ["LIFE_GRAPH_AGENT_CONTEXT_TOKENS"] = str(args.context)
    settings.verifier_sandbox = "docker"
    settings.driver_claude_sandbox = args.runtime
    if args.runtime == "none" and any(e.startswith("claude_code") for e in args.engine):
        print(
            "WARNING: --runtime none runs the real Claude Code CLI ON THIS HOST, with a shell "
            "(run_command) and your CLI login. Use --runtime task unless you mean it.",
            file=sys.stderr,
        )
    # Its own instance label (task_runtime.instance_id): a dev-task worker's
    # startup sweep removes this install's runtimes with no running task row,
    # which a script's runtimes never have (seen 2026-11-18).
    settings.edition = (settings.edition or "") + "-script"
    if args.driver_image:
        settings.driver_claude_sandbox_image = args.driver_image
    if args.verifier_image:
        settings.verifier_sandbox_image = args.verifier_image
    if args.verifier_node_image:
        settings.verifier_sandbox_node_image = args.verifier_node_image
    import life_graph.tools.code  # noqa: F401  registers the code_* tools

    spec = yaml.safe_load(TASKS.read_text())
    tasks = [
        t
        for t in spec["tasks"]
        if (not args.task or t["id"] in args.task)
        and (not args.category or t.get("category", "feature") in args.category)
    ]
    rows: list[dict] = []
    for engine in args.engine:
        for task in tasks:
            for i in range(args.repeat):
                row = await run_one(engine, task, spec["fixtures"][task["fixture"]], args.timeout)
                row["repeat"] = i + 1
                rows.append(row)
                print(
                    f"{engine:40} {task['id']:12} #{i + 1} "
                    f"{'PASS' if row['passed'] else 'fail'} driver={row['stop_reason']} "
                    f"{row['seconds']}s edits={row['edits_ok']}/{row['edits_failed']}",
                    flush=True,
                )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json"
    git_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()
    meta = {
        "context": args.context,
        "git_sha": git_sha,
        "runtime": args.runtime,
        "driver_image": settings.driver_claude_sandbox_image,
        "verifier_image": settings.verifier_sandbox_image,
        "verifier_node_image": settings.verifier_sandbox_node_image,
        "repeat": args.repeat,
    }
    out.write_text(json.dumps({**meta, "rows": rows}, indent=1))
    print(f"\nresults: {out.relative_to(ROOT)}\n")
    print(summary(rows))


if __name__ == "__main__":
    asyncio.run(main())
