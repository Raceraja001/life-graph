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
        --repeat 2 [--task node-remove ...] [--context 32768]

Results go to evals/driver_bench/<UTC timestamp>.json, and a markdown summary
is printed. Engines run one after another: two local models at once do not
fit the GPU.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
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


def fresh_copy(fixture: Path) -> Path:
    repo = Path(tempfile.mkdtemp(prefix="lg-bench-")) / "repo"
    shutil.copytree(
        fixture,
        repo,
        ignore=shutil.ignore_patterns(
            "node_modules", "__pycache__", "template.json", ".pytest_cache"
        ),
    )
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
    raise SystemExit(f"unknown engine kind {kind!r} (use local:<model> or opencode:<model>)")


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
    from life_graph.services.verifiers import verifier_chain

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

    repo = fresh_copy(ROOT / fixture["path"])
    driver, model = make_driver(engine)
    packet = ContextPacket(
        task_id=uuid.uuid4(),
        tenant_id="bench",
        task_type="code_change",
        instruction=task["instruction"] + " Make the change; do not stop at describing it.",
        persona_model=model,
        persona_system_prompt="You are Code Fixer. Make the smallest correct change.",
        project_context={"path": str(repo)},
        allowed_tools=["code_read", "code_search", "code_list", "code_edit"],
    )
    started = time.monotonic()
    try:
        result = await driver.dispatch(packet, repo, timeout=timeout)
        meta = result.metadata or {}
        driver_ok, error = result.success, result.error
    except Exception as exc:  # noqa: BLE001 — one crash is one failed run
        meta, driver_ok, error = {}, False, f"{type(exc).__name__}: {exc}"
    seconds = round(time.monotonic() - started, 1)
    steps = meta.get("steps") or []
    ok_edits, failed_edits = edit_counts(steps)
    diff = (
        subprocess.run(["git", "diff", "--stat"], cwd=repo, capture_output=True, text=True)
        .stdout.strip()
        .splitlines()
    )
    passed, detail = await hidden_test(repo, fixture["toolchain"], task["hidden_test"])
    shutil.rmtree(repo.parent, ignore_errors=True)
    return {
        "engine": engine,
        "task": task["id"],
        "passed": passed,
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
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--engine", action="append", required=True)
    parser.add_argument("--task", action="append")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--context", type=int, help="agent_context_tokens for the local driver")
    args = parser.parse_args()

    from life_graph.config import settings

    if args.context:
        os.environ["LIFE_GRAPH_AGENT_CONTEXT_TOKENS"] = str(args.context)
    settings.verifier_sandbox = "docker"
    import life_graph.tools.code  # noqa: F401  registers the code_* tools

    spec = yaml.safe_load(TASKS.read_text())
    tasks = [t for t in spec["tasks"] if not args.task or t["id"] in args.task]
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
    out.write_text(json.dumps({"context": args.context, "rows": rows}, indent=1))
    print(f"\nresults: {out.relative_to(ROOT)}\n")
    print(summary(rows))


if __name__ == "__main__":
    asyncio.run(main())
