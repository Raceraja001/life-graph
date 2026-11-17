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


# ── Learned procedural skills ─────────────────────────────────
#
# services/skill_distiller.py writes one markdown recipe per session that went
# wrong and then right. Stored, those recipes were only reachable if a persona
# happened to search for them — which a persona about to repeat last week's
# mistake does not do. Personas holding code, shell or git tools now carry the
# active ones in their system prompt, where the local model's prompt cache
# keeps them free to re-read (see the volatile-note comment in
# kernel/process_manager.py).

#: Tags that make a skill worth injecting whatever the project is: toolchain
#: and environment recipes travel, project-specific ones mostly do not.
GENERAL_SKILL_TAGS = frozenset(
    {
        "alembic",
        "bash",
        "build",
        "ci",
        "cli",
        "dev",
        "docker",
        "env",
        "git",
        "lint",
        "migration",
        "node",
        "npm",
        "podman",
        "pytest",
        "python",
        "ruff",
        "shell",
        "test",
        "venv",
    }
)

#: Skills read from the database before ranking, per skill finally kept. The
#: ranking is done in Python (three tiers over tags), so the window has to be
#: wide enough that a project's own skills are in it.
SKILL_WINDOW = 4

#: Hard cap on rows read, whatever ``limit`` asks for.
MAX_SKILL_ROWS = 40

#: Per-skill characters in the prompt. A patched skill grows every time it is
#: reinforced; five unclipped ones could outweigh the persona itself.
SKILL_CHARS = 1500

SKILLS_HEADING = (
    "## Learned Procedural Skills & Workflows\n"
    "Apply these previously distilled fixes and workflow recipes when "
    "encountering related issues:"
)


def _skill_rank(memory, project_name: str | None) -> int:
    """0 this project's, 1 general toolchain, 2 another project's."""
    tags = {str(t).lower() for t in (memory.tags or [])}
    props = memory.properties or {}
    if project_name:
        project = project_name.lower()
        if project in tags or str(props.get("project") or "").lower() == project:
            return 0
    return 1 if tags & GENERAL_SKILL_TAGS else 2


def render_skills(rows, project_name: str | None = None, limit: int = 5) -> str:
    """The prompt block for *rows*, best-matching first; "" when there is nothing."""
    from life_graph.services.skill_distiller import skill_body, skill_title

    ranked = sorted(
        enumerate(rows),  # index keeps the query's order stable inside a tier
        key=lambda pair: (_skill_rank(pair[1], project_name), pair[0]),
    )
    parts: list[str] = []
    for _, memory in ranked[: max(0, limit)]:
        body = skill_body(memory.content)
        if len(body) > SKILL_CHARS:
            body = f"{body[:SKILL_CHARS].rstrip()}… [truncated]"
        parts.append(f"### {skill_title(memory.content, memory.properties)}\n{body}".rstrip())
    return f"{SKILLS_HEADING}\n\n" + "\n\n".join(parts) if parts else ""


async def procedural_skills_block(
    session_factory,
    tenant_id: str,
    project_name: str | None = None,
    limit: int = 5,
) -> str:
    """The active distilled skills for *tenant_id*, as a markdown prompt block.

    Only ``active`` ones: a skill the owner archived in the dashboard
    (``api/skills.py``) must stop reaching the model, and a pending one must
    not reach it before it is approved.
    """
    from sqlalchemy.orm import defer

    from life_graph.models.db import Memory
    from life_graph.services.skill_distiller import skill_clause

    window = min(max(1, limit) * SKILL_WINDOW, MAX_SKILL_ROWS)
    async with session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(Memory)
                    .where(
                        Memory.tenant_id == tenant_id,
                        Memory.status == "active",
                        skill_clause(),
                    )
                    .options(defer(Memory.embedding))
                    .order_by(Memory.importance.desc(), Memory.created_at.desc())
                    .limit(window)
                )
            )
            .scalars()
            .all()
        )
    return render_skills(rows, project_name, limit)


async def task_project_name(session_factory, tenant_id: str, task_id) -> str | None:
    """The name of the project a kernel task runs against, or None."""
    from life_graph.models.db import AgentTask

    async with session_factory() as session:
        return (
            await session.execute(
                select(Project.name)
                .join(AgentTask, AgentTask.project_id == Project.id)
                .where(AgentTask.tenant_id == tenant_id, AgentTask.id == task_id)
            )
        ).scalar_one_or_none()
