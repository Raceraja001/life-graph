"""Nightly dev suggestions: find fixable problems, queue agent tasks for them.

For each project that opted in (``scan_metadata.nightly_suggestions``), a
worker cron job looks for problems *without* an LLM, most valuable first:

1. **failing tests** — the project's ``sandbox_test_command`` run in the
   verifier sandbox (only when the project configured one);
2. **lint** — ``ruff check`` in the sandbox, one finding per file;
3. **TODO / FIXME** comments — a plain file scan, no execution;
4. **untested functions** (opt-in, ``nightly_untested``) — short public Python
   functions no test file names, found by parsing, no execution.

Scanning happens in a throwaway detached worktree of ``HEAD``, so local
uncommitted edits in the live checkout never become suggestions, and nothing
from the scan runs on the host.

The top findings become **queued** dev tasks (``origin: "nightly"``) for the
project's ``nightly_persona`` (default ``code-fixer-local``: free and private).
The API process's queue runner (:func:`dev_tasks.run_queue`) works through
them one at a time; each verified result lands as the usual ``driver_pr``
approval, so in the morning there are PRs to review and nothing has been
pushed. A finding is suggested once: its key is stored on the task and
skipped for :data:`RESUGGEST_AFTER_DAYS`, whatever happened to that task.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from life_graph.models.db import AgentTask, Project

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

DEFAULT_PERSONA = "code-fixer-local"
DEFAULT_MAX_TASKS = 2
MAX_TASKS_CAP = 10
RESUGGEST_AFTER_DAYS = 60
MAX_TODO_FINDINGS = 50

_SKIP_DIRS = frozenset(
    {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".next",
        "dist",
        "build",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "migrations",
        "alembic",
    }
)
_SOURCE_SUFFIXES = frozenset({".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".rb"})
_TODO_RE = re.compile(r"(?:#|//)\s*(TODO|FIXME)\b[:\s\-]*(.{8,200})")
_FAILED_RE = re.compile(r"^FAILED (\S+)", re.MULTILINE)


@dataclass
class Finding:
    kind: str  # "tests" | "lint" | "todo" | "untested"
    key: str
    title: str
    instruction: str


def _key(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]


# ── Collectors ───────────────────────────────────────────────


def todo_findings(root: Path) -> list[Finding]:
    """TODO/FIXME comments in source files (no execution)."""
    found: list[Finding] = []

    def walk(d: Path):
        for entry in sorted(d.iterdir()):
            if entry.is_symlink():
                continue
            if entry.is_dir():
                if entry.name not in _SKIP_DIRS:
                    yield from walk(entry)
            elif entry.suffix in _SOURCE_SUFFIXES:
                yield entry

    for path in walk(root):
        try:
            if path.stat().st_size > 1_000_000:
                continue
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        rel = str(path.relative_to(root))
        for n, line in enumerate(lines, 1):
            m = _TODO_RE.search(line)
            if not m:
                continue
            tag, text = m.group(1), m.group(2).strip()
            found.append(
                Finding(
                    kind="todo",
                    # Line numbers excluded: unrelated edits move them.
                    key=_key("todo", rel, " ".join(text.lower().split())),
                    title=f"Resolve {tag} in {rel}: {text[:80]}",
                    instruction=(
                        f"Resolve this {tag} comment in {rel} (around line {n}): "
                        f'"{text}". Make the smallest change that addresses it and '
                        "remove the comment. If resolving it needs a product or design "
                        "decision you cannot infer from the code, make no changes and "
                        "explain why."
                    ),
                )
            )
            if len(found) >= MAX_TODO_FINDINGS:
                return found
    return found


async def lint_findings(root: Path, paths: list[str] | None = None) -> list[Finding]:
    """ruff findings, one per file, run in the verifier sandbox.

    *paths* narrows the scan to what the project actually lints (its
    ``nightly_lint_paths``, e.g. ``["life_graph"]``). Migrations and vendored
    directories are always excluded: rewriting an applied migration to satisfy
    a linter is exactly the change nobody wants to find in the morning.
    """
    from life_graph.services import sandbox

    if not sandbox.enabled():
        return []
    targets = [p for p in (paths or ["."]) if p and not p.startswith("-")]
    try:
        res = await sandbox.run(
            [
                "ruff",
                "check",
                "--no-cache",
                "--output-format",
                "json",
                "--extend-exclude",
                ",".join(sorted(_SKIP_DIRS)),
                "--",
                *targets,
            ],
            root,
            timeout=180,
        )
        issues = json.loads(res.stdout or "[]")
    except (sandbox.SandboxUnavailableError, ValueError) as exc:
        logger.info("lint findings skipped: %s", exc)
        return []
    by_file: dict[str, list[dict]] = {}
    for issue in issues:
        by_file.setdefault(issue.get("filename", "?"), []).append(issue)
    found = []
    for filename, items in sorted(by_file.items()):
        rel = filename.removeprefix("/work/")
        codes = sorted({i.get("code") or "?" for i in items})
        listing = "\n".join(
            f"- line {i.get('location', {}).get('row')}: {i.get('code')} {i.get('message')}"
            for i in items[:20]
        )
        found.append(
            Finding(
                kind="lint",
                key=_key("lint", rel, ",".join(codes)),
                title=f"Fix ruff {', '.join(codes[:4])} in {rel}",
                instruction=(
                    f"Fix these ruff findings in {rel} without changing behaviour:\n{listing}\n"
                    "Change only what the findings require."
                ),
            )
        )
    return found


async def test_findings(root: Path, meta: dict[str, Any]) -> list[Finding]:
    """Failing tests from the project's sandbox test command, if it has one."""
    import shlex

    from life_graph.services import sandbox

    command = meta.get("sandbox_test_command")
    if not command or not sandbox.enabled():
        return []
    try:
        venv = await sandbox.prepare_env(root, meta.get("sandbox_setup"))
        res = await sandbox.run(
            shlex.split(command),
            root,
            venv=venv,
            timeout=int(meta.get("sandbox_test_timeout") or 600),
        )
    except (sandbox.SandboxUnavailableError, ValueError) as exc:
        logger.info("test findings skipped: %s", exc)
        return []
    failed = sorted(set(_FAILED_RE.findall(res.stdout)))
    if res.returncode == 0 or not failed:
        return []
    shown = "\n".join(f"- {t}" for t in failed[:10])
    more = f"\n(and {len(failed) - 10} more)" if len(failed) > 10 else ""
    return [
        Finding(
            kind="tests",
            key=_key("tests", *failed),
            title=f"Fix {len(failed)} failing test(s)",
            instruction=(
                f"These tests fail on the current code:\n{shown}{more}\n"
                "Find the root cause and fix the code (or the test, only if the test "
                "itself is wrong). Do not skip, delete or weaken tests."
            ),
        )
    ]


UNTESTED_MIN_LINES = 6
UNTESTED_MAX_LINES = 40
MAX_UNTESTED_FINDINGS = 30
_TEST_DIRS = ("tests", "test")


def _test_corpus(root: Path) -> str:
    """Every test file's text, to look function names up in."""
    parts = []
    for d in _TEST_DIRS:
        base = root / d
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            if any(p in _SKIP_DIRS for p in path.parts):
                continue
            try:
                parts.append(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
    return "\n".join(parts)


def untested_findings(root: Path, paths: list[str] | None = None) -> list[Finding]:
    """Short public Python functions no test file names (no execution).

    Opt-in per project (``nightly_untested``). Shortest first: the dev agent is
    reliable on small, scoped test tasks (seven of seven, 2026-10-19), not on
    large ones. A function that takes a ``session`` gets pointed at the
    project's shared fakes when it has ``tests/unit/fakes.py``.
    """
    import ast

    corpus = _test_corpus(root)
    if not corpus:
        return []  # no test suite to add to
    has_fakes = (root / "tests" / "unit" / "fakes.py").is_file()
    candidates: list[tuple[int, str, str, bool]] = []
    bases = [root / p for p in paths] if paths else [root]
    for base in bases:
        files = [base] if base.is_file() else sorted(base.rglob("*.py")) if base.is_dir() else []
        for path in files:
            rel = str(path.relative_to(root))
            parts = Path(rel).parts
            if any(p in _SKIP_DIRS for p in parts) or parts[0] in _TEST_DIRS:
                continue
            if path.name.startswith("test_") or path.name == "conftest.py":
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            except (OSError, SyntaxError, ValueError):
                continue
            for node in tree.body:
                if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    continue
                # Private, or framework-bound: a decorated function is a route,
                # a cached dependency, a registered tool... tested through its
                # framework, not as a small unit (the first scan picked FastAPI
                # handlers and DI getters).
                if node.name.startswith("_") or node.decorator_list:
                    continue
                length = (node.end_lineno or node.lineno) - node.lineno + 1
                if not UNTESTED_MIN_LINES <= length <= UNTESTED_MAX_LINES:
                    continue
                if re.search(rf"\b{re.escape(node.name)}\b", corpus):
                    continue
                takes_session = any(a.arg == "session" for a in node.args.args)
                candidates.append((length, rel, node.name, takes_session))
    candidates.sort()
    found = []
    for _length, rel, name, takes_session in candidates[:MAX_UNTESTED_FINDINGS]:
        test_file = f"tests/unit/test_{Path(rel).stem}_{name}.py"
        db = (
            " It queries the database: use the shared fakes in tests/unit/fakes.py as "
            "AGENTS.md describes (FakeSession(rows), session.statements, sql(stmt)); "
            "see tests/unit/test_dev_task_diff.py."
            if takes_session and has_fakes
            else ""
        )
        found.append(
            Finding(
                kind="untested",
                key=_key("untested", rel, name),
                title=f"Add tests for {name} in {rel}",
                instruction=(
                    f"Write unit tests, in a new file {test_file}, for `{name}` in {rel}, "
                    "which has none. Read the function first, then cover its main cases "
                    "and an edge case; each test must call the function and assert on "
                    f"what it returns or does.{db} Put every import at the top of the "
                    "test file. Change no other file."
                ),
            )
        )
    return found


async def collect_findings(repo_path: str, meta: dict[str, Any]) -> list[Finding]:
    """All findings for a project, most valuable first, scanned at ``HEAD``."""
    scratch = Path(tempfile.mkdtemp(prefix="lg_suggest_"))
    worktree = scratch / "wt"
    git = ["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null", "-C", repo_path]
    proc = await asyncio.create_subprocess_exec(
        *git,
        "worktree",
        "add",
        "--detach",
        str(worktree),
        "HEAD",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    if proc.returncode != 0:
        shutil.rmtree(scratch, ignore_errors=True)
        raise RuntimeError(f"could not create scan worktree: {err.decode(errors='replace')[-200:]}")
    try:
        return [
            *await test_findings(worktree, meta),
            *await lint_findings(worktree, meta.get("nightly_lint_paths")),
            *await asyncio.to_thread(todo_findings, worktree),
            # Last: missing tests are worth less than anything broken.
            *(
                await asyncio.to_thread(
                    untested_findings, worktree, meta.get("nightly_untested_paths")
                )
                if meta.get("nightly_untested")
                else []
            ),
        ]
    finally:
        cleanup = await asyncio.create_subprocess_exec(
            *git,
            "worktree",
            "remove",
            "--force",
            str(worktree),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await cleanup.wait()
        shutil.rmtree(scratch, ignore_errors=True)


# ── Queueing ─────────────────────────────────────────────────


async def queue_suggestions(
    session_factory: async_sessionmaker[AsyncSession],
    tenant_id: str,
    project: dict[str, Any],
    findings: list[Finding],
) -> dict[str, Any]:
    """Queue dev tasks for new findings, respecting the per-project cap."""
    from life_graph.api.dependencies import get_persona_service
    from life_graph.services import dev_tasks

    meta = project.get("scan_metadata") or {}
    max_tasks = max(1, min(int(meta.get("nightly_max_tasks") or DEFAULT_MAX_TASKS), MAX_TASKS_CAP))
    persona_name = meta.get("nightly_persona") or DEFAULT_PERSONA
    persona = await get_persona_service().get_by_name(tenant_id, persona_name)
    if not persona or not persona.get("driver"):
        return {"skipped": f"persona {persona_name!r} missing or has no driver"}

    project_id = uuid.UUID(project["id"])
    since = datetime.now(UTC) - timedelta(days=RESUGGEST_AFTER_DAYS)
    async with session_factory() as session:
        seen = set(
            (
                await session.execute(
                    select(AgentTask.properties["finding_key"].astext).where(
                        AgentTask.tenant_id == tenant_id,
                        AgentTask.project_id == project_id,
                        AgentTask.properties["finding_key"].astext.isnot(None),
                        AgentTask.created_at >= since,
                    )
                )
            )
            .scalars()
            .all()
        )
        # Don't pile up: open nightly tasks count against tonight's cap.
        open_nightly = (
            await session.execute(
                select(func.count(AgentTask.id)).where(
                    AgentTask.tenant_id == tenant_id,
                    AgentTask.project_id == project_id,
                    AgentTask.properties["origin"].astext == "nightly",
                    AgentTask.status.in_(["queued", "running"]),
                )
            )
        ).scalar() or 0

    budget = max_tasks - open_nightly
    queued = []
    for f in findings:
        if budget <= 0:
            break
        if f.key in seen:
            continue
        task = await dev_tasks.create_dev_task(
            session_factory,
            tenant_id,
            instruction=f.instruction,
            project=project,
            persona_name=persona_name,
            start=False,
            properties={"origin": "nightly", "finding_key": f.key, "finding_kind": f.kind},
        )
        seen.add(f.key)
        queued.append(task["id"])
        budget -= 1
    return {"findings": len(findings), "queued": len(queued), "open_before": open_nightly}


async def run_nightly(session_factory: async_sessionmaker[AsyncSession]) -> dict[str, Any]:
    """Cron entry point: every active project that opted in, across tenants."""
    from life_graph.core.tenant import set_tenant_context
    from life_graph.kernel.project_registry import ProjectRegistry

    async with session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(Project).where(
                        Project.is_active.is_(True),
                        Project.scan_metadata["nightly_suggestions"].astext == "true",
                    )
                )
            )
            .scalars()
            .all()
        )
        projects = [(p.tenant_id, ProjectRegistry._project_to_dict(p)) for p in rows]

    report: dict[str, Any] = {}
    for tenant_id, project in projects:
        set_tenant_context(tenant_id, "system")
        try:
            findings = await collect_findings(project["path"], project.get("scan_metadata") or {})
            report[project["name"]] = await queue_suggestions(
                session_factory, tenant_id, project, findings
            )
        except Exception as exc:
            logger.warning("Nightly suggestions failed for %s", project["name"], exc_info=True)
            report[project["name"]] = {"error": str(exc)[:300]}
    logger.info("Nightly dev suggestions: %s", report)
    return report
