"""Re-check a spec against the code: does the project still satisfy it?

A plan's acceptance criteria are bound to tests (services/acceptance.py) and
checked once, when each task lands. Code keeps changing after that. This
re-runs every criterion's bound test against the project's current code and
records a per-criterion pass/fail/untested report on the task that produced
the spec. Ported from FORGE's conformance check, kept deterministic: a
criterion is only "passing" if its bound test passes, never on an agent's
judgment.

Manual on purpose (API/MCP), not triggered on every change -- a flaky test
firing an alarm on each commit is worse than no check.

Runs in a throwaway git worktree at the project checkout's current HEAD,
never the live checkout (which may have uncommitted work), and through the
same acceptance_tests_pass verifier the dispatch pipeline uses -- sandboxed
when the verifier sandbox is enabled.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from life_graph.drivers.base import ContextPacket
from life_graph.drivers.workdir import remove_worktree, resolve_workdir
from life_graph.models.db import AgentTask, Project
from life_graph.services.acceptance import AcceptanceCriterion, is_safe_test_ref, parse_criteria
from life_graph.services.verifiers import verifier_chain

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)


class ConformanceError(Exception):
    """The check could not be run (no such task, no spec, no project)."""


async def _head_commit(workdir: Path) -> str | None:
    proc = await asyncio.create_subprocess_exec(
        "git",
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "core.fsmonitor=false",
        "rev-parse",
        "HEAD",
        cwd=str(workdir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, _ = await proc.communicate()
    return out.decode().strip() if proc.returncode == 0 else None


async def _check_one(
    criterion: AcceptanceCriterion, workdir: Path, base_ctx: dict[str, Any]
) -> dict[str, Any]:
    row: dict[str, Any] = {"id": criterion.id, "text": criterion.text, "test": criterion.test}
    if not is_safe_test_ref(criterion.test):
        row["status"] = "untested"
        return row
    [result] = await verifier_chain.run_chain(
        ["acceptance_tests_pass"], workdir, {**base_ctx, "acceptance_tests": [criterion.test]}
    )
    if result.inconclusive:
        row["status"] = "inconclusive"
    else:
        row["status"] = "passing" if result.passed else "failing"
    row["evidence"] = result.evidence
    return row


async def check_conformance(
    session_factory: async_sessionmaker[AsyncSession], tenant_id: str, task_id: str
) -> dict[str, Any]:
    """Run every bound acceptance test for *task_id*'s spec; store and return the report."""
    try:
        pk = uuid.UUID(str(task_id))
    except ValueError as exc:
        raise ConformanceError(f"not a task id: {task_id!r}") from exc

    async with session_factory() as session:
        task = await session.get(AgentTask, pk)
        if task is None or task.tenant_id != tenant_id:
            raise ConformanceError(f"no dev task {task_id}")
        spec = ((task.result or {}).get("metadata") or {}).get("spec")
        if not spec:
            raise ConformanceError("this task has no spec to check against")
        criteria = parse_criteria(spec)
        if not criteria:
            raise ConformanceError("this task's spec has no acceptance criteria (AC-n lines)")
        project = await session.get(Project, task.project_id) if task.project_id else None
        if project is None:
            raise ConformanceError("the task's project is no longer registered")
        project_path = project.path
        meta = project.scan_metadata or {}

    base_ctx = {
        "sandbox_setup": meta.get("sandbox_setup"),
        "sandbox_test_timeout": meta.get("sandbox_test_timeout"),
    }
    packet = ContextPacket(
        task_id=pk,
        tenant_id=tenant_id,
        task_type="conformance",
        instruction="",
        project_context={"path": project_path, "isolation": True},
    )
    scratch = Path(tempfile.mkdtemp(prefix=f"lg_conformance_{str(pk)[:8]}_"))
    workdir, worktree = await resolve_workdir(packet, scratch)
    if worktree is None:
        raise ConformanceError("could not create a worktree of the project to test against")
    try:
        commit = await _head_commit(workdir)
        rows = list(await asyncio.gather(*(_check_one(c, workdir, base_ctx) for c in criteria)))
    finally:
        await remove_worktree(packet, worktree, repo_path=project_path)
        shutil.rmtree(scratch, ignore_errors=True)

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    report = {
        "checked_at": datetime.now(UTC).isoformat(),
        "commit": commit,
        "summary": counts,
        "conforms": counts.get("passing", 0) == len(rows),
        "criteria": rows,
    }

    async with session_factory() as session:
        task = await session.get(AgentTask, pk)
        # Reassigned, not mutated: in-place JSONB edits aren't change-tracked.
        task.properties = {**(task.properties or {}), "conformance": report}
        await session.commit()
    logger.info("Conformance for task %s at %s: %s", task_id, (commit or "?")[:8], counts)
    return report
