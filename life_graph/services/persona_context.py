"""Context a persona needs before its first tool call: which projects exist.

The 2026-10-12 survey found cody passing a relative path (rejected by the
file guards) and swe-lead asking the user for the repo path. Both hold code
tools but were never told where the code is. Personas whose tools touch files,
code, git or the shell now get a short block naming each registered project,
its absolute path and its base branch.
"""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from life_graph.config import settings
from life_graph.models.db import Project

# Tools whose arguments are paths on this machine.
PATH_TOOLS = frozenset(
    {
        "code_read",
        "code_search",
        "code_list",
        "code_edit",
        "file_read",
        "file_write",
        "git_status",
        "git_log",
        "git_diff",
        "git_branch",
        "run_command",
    }
)
MAX_PROJECTS = 20


def today_line(now: datetime | None = None) -> str:
    """The current date and time in the user's timezone, for the system prompt."""
    try:
        tz = ZoneInfo(settings.user_timezone)
    except Exception:  # noqa: BLE001 — a bad setting must not break every run
        tz = ZoneInfo("UTC")
    local = (now or datetime.now(UTC)).astimezone(tz)
    return f"Current date and time: {local:%A %d %B %Y, %H:%M} ({tz.key})."


def needs_projects(allowed_tools: list[str] | None) -> bool:
    """None means every tool, which includes the path tools."""
    return allowed_tools is None or bool(PATH_TOOLS & set(allowed_tools))


def render(projects: list[dict]) -> str:
    if not projects:
        return ""
    lines = [
        "## Projects you can work on",
        "Use these absolute paths with file, code, git and shell tools:",
    ]
    for p in projects[:MAX_PROJECTS]:
        branch = p.get("base_branch") or p.get("git_branch") or "?"
        desc = f" — {p['description'][:80]}" if p.get("description") else ""
        lines.append(f"- **{p['name']}**: `{p['path']}` (base branch {branch}){desc}")
    return "\n".join(lines)


async def projects_block(session_factory, tenant_id: str) -> str:
    async with session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(Project)
                    .where(Project.tenant_id == tenant_id, Project.is_active.is_(True))
                    .order_by(Project.name)
                    .limit(MAX_PROJECTS)
                )
            )
            .scalars()
            .all()
        )
    return render(
        [
            {
                "name": r.name,
                "path": r.path,
                "description": r.description,
                "git_branch": r.git_branch,
                "base_branch": (r.scan_metadata or {}).get("base_branch"),
            }
            for r in rows
        ]
    )


# Personas that may read only a project's documentation, never its code:
# the support desk answers customers, so its file tools are confined to the
# README and docs/ of the project the task names (no project, no files).
DOCS_ONLY_PERSONAS = frozenset({"support-desk"})


async def docs_roots(session_factory, tenant_id: str, task_id) -> list[str]:
    """The README files and docs/ directory of the task's project, or []."""
    from pathlib import Path

    from life_graph.models.db import AgentTask

    async with session_factory() as session:
        row = (
            await session.execute(
                select(Project.path)
                .join(AgentTask, AgentTask.project_id == Project.id)
                .where(AgentTask.tenant_id == tenant_id, AgentTask.id == task_id)
            )
        ).scalar_one_or_none()
    if not row:
        return []
    base = Path(row)
    roots = [str(p) for p in base.glob("README*") if p.is_file()]
    if (base / "docs").is_dir():
        roots.append(str(base / "docs"))
    return roots
