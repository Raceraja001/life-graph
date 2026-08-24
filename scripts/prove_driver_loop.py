#!/usr/bin/env python
"""Drive one real task through the whole driver pipeline and report what happened.

The unit suite exercises every piece of this path with fakes and passes. It
passed while the escalation path raised CheckViolationError on every call, the
persona driver pin was never read, and verified work was deleted after clearing
its own gates. Each of those needed a real database, a real persona row, and a
real git repo to show up at all.

So this builds all three: a throwaway git repo containing a genuine failing
test, registered as a project, dispatched through TaskDispatcher exactly as the
autonomous pipeline would. Nothing here is mocked.

    python scripts/prove_driver_loop.py

Requires Postgres up (``./start.sh --infra``) and, for the happy path, the
project's toolchain resolvable — ``PATH=.venv/bin:$PATH`` or similar, since
the verifiers deliberately use the *target project's* tools rather than
Life Graph's. Run it with a bare PATH to exercise the inconclusive branch.
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from sqlalchemy import select

from life_graph.core.tenant import set_tenant_context
from life_graph.models.db import Project
from life_graph.storage.database import async_session

TENANT = "loop-proof"
PROJECT_NAME = "sandbox-stats"

# A real bug: median() returns the upper middle value for even-length input.
_STATS_PY = '''"""Small statistics helpers."""


def mean(values):
    """Arithmetic mean of a sequence of numbers."""
    return sum(values) / len(values)


def median(values):
    """Middle value of a sorted sequence."""
    ordered = sorted(values)
    mid = len(ordered) // 2
    # BUG: for an even-length sequence the median is the mean of the two
    # middle values, not the upper one.
    return ordered[mid]
'''

_TEST_PY = """from src.stats import mean, median


def test_mean():
    assert mean([1, 2, 3]) == 2


def test_median_odd():
    assert median([3, 1, 2]) == 2


def test_median_even():
    assert median([1, 2, 3, 4]) == 2.5
"""

_PYPROJECT = (
    '[project]\nname = "sandbox-stats"\nversion = "0.1.0"\n\n[tool.ruff]\nline-length = 100\n'
)

INSTRUCTION = (
    "The test tests/test_stats.py::test_median_even fails: median([1,2,3,4]) returns 3 "
    "but should return 2.5. Fix the median() function in src/stats.py so that for an "
    "even-length sequence it returns the mean of the two middle values. "
    "Do not change the tests."
)


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)


def build_sandbox(root: Path) -> Path:
    """A git repo whose test suite fails for one specific, fixable reason."""
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "src" / "stats.py").write_text(_STATS_PY)
    (root / "tests" / "test_stats.py").write_text(_TEST_PY)
    (root / "pyproject.toml").write_text(_PYPROJECT)
    _git("init", "-q", ".", cwd=root)
    _git("add", "-A", cwd=root)
    _git(
        "-c",
        "user.email=sandbox@localhost",
        "-c",
        "user.name=sandbox",
        "commit",
        "-qm",
        "initial: median is wrong for even-length input",
        cwd=root,
    )
    return root


async def register_project(path: Path) -> uuid.UUID:
    async with async_session() as session:
        existing = (
            (
                await session.execute(
                    select(Project).where(Project.tenant_id == TENANT, Project.name == PROJECT_NAME)
                )
            )
            .scalars()
            .first()
        )
        if existing is not None:
            existing.path = str(path)
            await session.commit()
            return existing.id
        project = Project(tenant_id=TENANT, name=PROJECT_NAME, path=str(path))
        session.add(project)
        await session.commit()
        await session.refresh(project)
        return project.id


async def run(sandbox: Path) -> int:
    set_tenant_context(TENANT)

    project_id = await register_project(sandbox)
    print(f"project        : {project_id}")

    from life_graph.kernel.personas import PersonaService

    seeded = await PersonaService(async_session).seed_builtins(TENANT)
    print(f"personas seeded: {seeded}")

    from life_graph.drivers.claude_code import ClaudeCodeDriver
    from life_graph.drivers.dispatcher import TaskDispatcher
    from life_graph.drivers.local import LocalDriver
    from life_graph.drivers.registry import driver_registry

    driver_registry.register(LocalDriver())
    driver_registry.register(ClaudeCodeDriver())

    task_id = str(uuid.uuid4())
    print(f"dispatching    : {task_id}\n")

    result = await TaskDispatcher(session_factory=async_session).dispatch_task(
        tenant_id=TENANT,
        task_id=task_id,
        instruction=INSTRUCTION,
        task_type="code",
        project_id=str(project_id),
        # Pinned so the run is deterministic: this persona pins claude_code and
        # declares its own verifier_chain. verify_chain is deliberately NOT
        # passed, so the persona's chain is what gets used.
        persona_name="dependency-updater",
        interactive=True,
        isolate_workdir=True,
    )

    print("── DriverResult ──")
    print(f"success        : {result.success}")
    print(f"error          : {result.error}")
    metadata = result.metadata or {}
    print(f"metadata       : {sorted(metadata)}")
    for entry in metadata.get("unverifiable", []):
        print(f"  unverifiable : {entry.get('verifier')} -> {entry.get('evidence')}")

    branch = metadata.get("landed_branch")
    print(f"landed branch  : {branch}")

    if branch:
        diff = _git("diff", "master", branch, "--", "src/stats.py", cwd=sandbox).stdout
        print("\n── landed diff ──")
        print(diff or "(empty)")
        on_master = _git("show", "master:src/stats.py", cwd=sandbox).stdout
        print(f"master still has the bug: {'BUG:' in on_master}")

    return 0 if result.success else 1


def main() -> int:
    keep = "--keep" in sys.argv
    root = Path(tempfile.mkdtemp(prefix="lg_loop_proof_"))
    try:
        sandbox = build_sandbox(root)
        print(f"sandbox        : {sandbox}\n")
        return asyncio.run(run(sandbox))
    finally:
        if keep:
            print(f"\n(kept {root})")
        else:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
