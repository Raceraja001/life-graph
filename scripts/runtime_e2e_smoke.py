"""One real software task through the per-task runtime, end to end.

The work order's definition of success, exercised on a throwaway fixture
repo: the claude_code driver edits code inside its task runtime (no host
execution, egress allowlisted), the verifier chain runs the tests in the
network-less verifier sandbox, and the result is an auditable diff plus the
runtime metadata — the same calls the dispatcher makes (resolve_workdir ->
driver.dispatch -> verifier_chain.run_chain -> diff_against_head).

Needs docker, the driver image, the verifier image and the egress image, plus
a Claude CLI login (OAuth mode stages a throwaway copy of it). It spends one
small Claude Code run on that login. Run only when you mean to:

    python scripts/runtime_e2e_smoke.py \
        --driver-image life-graph-claude-driver:wo-test \
        --verifier-image life-graph-verifier:wo-test
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

CALC = """def add(a, b):
    return a + b
"""
TEST = """from calc import add


def test_add():
    assert add(2, 3) == 5
"""
INSTRUCTION = (
    "In calc.py add a function `mul(a, b)` that returns the product of a and b. "
    "In tests/test_calc.py add a test `test_mul` for it (import mul from calc). "
    "Keep the existing add() and its test unchanged. Do not create other files."
)


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--driver-image", default="life-graph-claude-driver:wo-test")
    ap.add_argument("--verifier-image", default="life-graph-verifier:wo-test")
    ap.add_argument("--timeout", type=int, default=420)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    from life_graph.config import settings

    settings.driver_claude_sandbox = "task"
    settings.driver_claude_sandbox_image = args.driver_image
    settings.verifier_sandbox = "docker"
    settings.verifier_sandbox_image = args.verifier_image

    from life_graph.drivers.base import ContextPacket
    from life_graph.drivers.claude_code import ClaudeCodeDriver
    from life_graph.drivers.dispatcher import tenant_scratch_root
    from life_graph.drivers.workdir import diff_against_head, remove_worktree, resolve_workdir
    from life_graph.services.dev.verifiers import verifier_chain

    tenant = "e2e-smoke"
    root = Path(tenant_scratch_root(tenant))
    origin = root / f"origin_{uuid.uuid4().hex[:6]}"
    (origin / "tests").mkdir(parents=True)
    (origin / "calc.py").write_text(CALC)
    (origin / "tests" / "test_calc.py").write_text(TEST)
    (origin / "conftest.py").write_text("")
    _git("init", "-q", cwd=origin)
    _git("add", ".", cwd=origin)
    _git("-c", "user.email=e@e", "-c", "user.name=e", "commit", "-qm", "init", cwd=origin)

    packet = ContextPacket(
        task_id=uuid.uuid4(),
        tenant_id=tenant,
        task_type="code_change",
        instruction=INSTRUCTION,
        allowed_tools=["code_read", "code_edit", "run_command"],
        project_context={"path": str(origin), "isolation": True},
    )
    scratch = Path(
        __import__("tempfile").mkdtemp(prefix=f"lg_dispatch_{str(packet.task_id)[:8]}_", dir=root)
    )
    workdir, worktree = await resolve_workdir(packet, scratch)
    report: dict = {"task_id": str(packet.task_id), "worktree_isolated": worktree is not None}
    try:
        # As the dispatcher does: the driver sees the already-resolved worktree.
        packet.project_context["path"] = str(workdir)
        packet.project_context["isolation"] = False
        result = await ClaudeCodeDriver().dispatch(packet, workdir, timeout=args.timeout)
        md = result.metadata or {}
        report["driver"] = {
            "success": result.success,
            "error": result.error,
            "exit_status": md.get("exit_status"),
            "boundary": md.get("boundary"),
            "num_turns": md.get("num_turns"),
            "model": md.get("model"),
            "duration_ms": result.duration_ms,
            "cost_usd_reported": result.cost_usd,
            "tool_steps": [s.get("tool") for s in md.get("steps") or [] if s.get("tool")][:30],
            "output_tail": (result.output or "")[-600:],
        }
        report["runtime"] = md.get("runtime")
        chain = await verifier_chain.run_chain(["tests_pass"], workdir, {})
        report["verification"] = [
            {"verifier": r.verifier, "passed": r.passed, "evidence": r.evidence} for r in chain
        ]
        report["diff"] = await diff_against_head(workdir)
        report["origin_untouched"] = _git("status", "--porcelain", cwd=origin) == ""
    finally:
        if worktree is not None:
            await remove_worktree(packet, worktree, repo_path=origin)
        shutil.rmtree(scratch, ignore_errors=True)
        shutil.rmtree(origin, ignore_errors=True)

    text = json.dumps(report, indent=2, default=str)
    if args.out:
        Path(args.out).write_text(text)
    print(text)
    ok = (
        report.get("driver", {}).get("success")
        and report.get("driver", {}).get("boundary") == "task"
        and all(v["passed"] is True for v in report.get("verification", []))
        and "def mul" in report.get("diff", "")
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
