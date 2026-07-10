"""Project Registry — codebase registration and scanning.

Manages registered project codebases with git info, dependency
detection, file counting, and scan metadata. Provides project
context to agents for project-aware task execution.
"""

from __future__ import annotations

import logging
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)

from life_graph.models.db import Project

logger = logging.getLogger(__name__)


# ── Language Detection ─────────────────────────────────────


_LANG_MARKERS: dict[str, tuple[str, str | None]] = {
    "pyproject.toml": ("python", "pyproject.toml"),
    "setup.py": ("python", "setup.py"),
    "requirements.txt": ("python", "requirements.txt"),
    "Pipfile": ("python", "Pipfile"),
    "package.json": ("typescript", "package.json"),
    "tsconfig.json": ("typescript", "package.json"),
    "Cargo.toml": ("rust", "Cargo.toml"),
    "go.mod": ("go", "go.mod"),
    "pom.xml": ("java", "pom.xml"),
    "build.gradle": ("java", "build.gradle"),
    "Gemfile": ("ruby", "Gemfile"),
    "mix.exs": ("elixir", "mix.exs"),
}

_FRAMEWORK_MARKERS: dict[str, str] = {
    "fastapi": "fastapi",
    "django": "django",
    "flask": "flask",
    "nextjs": "nextjs",
    "next": "nextjs",
    "nestjs": "nestjs",
    "express": "express",
    "actix": "actix",
    "axum": "axum",
    "gin": "gin",
    "rails": "rails",
    "phoenix": "phoenix",
}

# File extensions to count
_CODE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx",
    ".rs", ".go", ".java", ".rb", ".ex",
    ".html", ".css", ".sql", ".md",
    ".yaml", ".yml", ".toml", ".json",
}


def detect_language(project_path: str) -> tuple[str | None, str | None]:
    """Detect the primary language and dependency file.

    Scans the project root for known marker files.

    Returns:
        Tuple of (language, dependency_file) or (None, None).
    """
    root = Path(project_path)
    for marker, (lang, dep_file) in _LANG_MARKERS.items():
        if (root / marker).exists():
            return lang, dep_file
    return None, None


def detect_framework(project_path: str) -> str | None:
    """Detect the framework from dependency files.

    Reads pyproject.toml or package.json looking for
    framework keywords.

    Returns:
        Framework name or None.
    """
    root = Path(project_path)

    # Check pyproject.toml
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(
                encoding="utf-8", errors="ignore",
            ).lower()
            for keyword, framework in _FRAMEWORK_MARKERS.items():
                if keyword in content:
                    return framework
        except OSError:
            pass

    # Check package.json
    pkg_json = root / "package.json"
    if pkg_json.exists():
        try:
            content = pkg_json.read_text(
                encoding="utf-8", errors="ignore",
            ).lower()
            for keyword, framework in _FRAMEWORK_MARKERS.items():
                if keyword in content:
                    return framework
        except OSError:
            pass

    return None


def count_files(project_path: str) -> int:
    """Count code files in a project directory.

    Only counts files with known code extensions,
    ignoring hidden directories, node_modules, __pycache__,
    .git, and virtual environments.

    Returns:
        Number of code files found.
    """
    skip_dirs = {
        ".git", "node_modules", "__pycache__",
        ".venv", "venv", ".tox", "dist", "build",
        ".next", ".nuxt", "target",
    }
    count = 0
    root = Path(project_path)

    try:
        for dirpath, dirnames, filenames in os.walk(root):
            # Skip hidden and excluded dirs
            dirnames[:] = [
                d for d in dirnames
                if d not in skip_dirs
                and not d.startswith(".")
            ]
            for f in filenames:
                if Path(f).suffix in _CODE_EXTENSIONS:
                    count += 1
    except OSError:
        pass

    return count


def count_dependencies(
    project_path: str, dep_file: str | None,
) -> int:
    """Count dependencies from a dependency file.

    Supports pyproject.toml and package.json.

    Returns:
        Approximate dependency count, or 0.
    """
    if not dep_file:
        return 0

    dep_path = Path(project_path) / dep_file
    if not dep_path.exists():
        return 0

    try:
        content = dep_path.read_text(
            encoding="utf-8", errors="ignore",
        )

        if dep_file == "pyproject.toml":
            # Count lines in [project.dependencies]
            # or [tool.poetry.dependencies]
            count = 0
            in_deps = False
            for line in content.splitlines():
                stripped = line.strip()
                if "dependencies" in stripped and "[" not in stripped:
                    in_deps = True
                    continue
                if in_deps:
                    if stripped.startswith("["):
                        in_deps = False
                    elif stripped and not stripped.startswith("#"):
                        count += 1
            return max(count, 1)

        elif dep_file == "package.json":
            import json
            data = json.loads(content)
            deps = data.get("dependencies", {})
            dev_deps = data.get("devDependencies", {})
            return len(deps) + len(dev_deps)

    except (OSError, ValueError, json.JSONDecodeError):
        pass

    return 0


def get_git_info(
    project_path: str,
) -> tuple[str | None, list[dict[str, str]]]:
    """Get git branch and recent commits.

    Returns:
        Tuple of (branch_name, list of commit dicts).
    """
    branch = None
    commits: list[dict[str, str]] = []

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass

    try:
        result = subprocess.run(
            [
                "git", "log", "--oneline", "-10",
                "--format=%h|%s|%an|%aI",
            ],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                parts = line.split("|", 3)
                if len(parts) == 4:
                    commits.append({
                        "hash": parts[0],
                        "message": parts[1],
                        "author": parts[2],
                        "date": parts[3],
                    })
    except (OSError, subprocess.TimeoutExpired):
        pass

    return branch, commits


# ── Project Registry Service ──────────────────────────────


class ProjectRegistry:
    """Manages registered project codebases.

    Handles project CRUD, scanning (git, deps, file count),
    and context building for agent system prompts.

    Args:
        session_factory: Async session factory for DB access.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    # ── CRUD ──────────────────────────────────────────────

    async def register(
        self,
        tenant_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Register a new project and auto-scan it.

        Args:
            tenant_id: Tenant scope.
            data: Project fields (name, path, etc.).

        Returns:
            Dict of the registered project with scan data.

        Raises:
            ValueError: If name already exists or path invalid.
        """
        name = data["name"]
        path = data["path"]

        # Validate path exists
        if not Path(path).is_dir():
            raise ValueError(
                f"Path does not exist: {path!r}"
            )

        async with self._session_factory() as session:
            # Check uniqueness
            existing = await session.execute(
                select(Project.id).where(
                    Project.tenant_id == tenant_id,
                    Project.name == name,
                )
            )
            if existing.scalar_one_or_none() is not None:
                raise ValueError(
                    f"Project '{name}' already exists"
                )

            # Auto-scan
            lang, dep_file = detect_language(path)
            framework = detect_framework(path)
            file_cnt = count_files(path)
            dep_cnt = count_dependencies(path, dep_file)
            branch, commits = get_git_info(path)
            now = datetime.now(timezone.utc)

            project = Project(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                name=name,
                path=path,
                description=data.get("description"),
                git_url=data.get("git_url"),
                git_branch=branch,
                language=lang,
                framework=framework,
                dependency_file=dep_file,
                dependency_count=dep_cnt,
                file_count=file_cnt,
                recent_commits=commits,
                last_scanned_at=now,
            )
            session.add(project)
            await session.commit()
            await session.refresh(project)

            logger.info(
                "Registered project '%s' (%s/%s, %d files)",
                name, lang, framework, file_cnt,
            )
            return self._project_to_dict(project)

    async def list_all(
        self,
        tenant_id: str,
        *,
        language: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """List all active projects for a tenant.

        Args:
            tenant_id: Tenant scope.
            language: Optional language filter.

        Returns:
            Tuple of (project dicts, total count).
        """
        async with self._session_factory() as session:
            base = select(Project).where(
                Project.tenant_id == tenant_id,
                Project.is_active.is_(True),
            )
            count_base = (
                select(func.count())
                .select_from(Project)
                .where(
                    Project.tenant_id == tenant_id,
                    Project.is_active.is_(True),
                )
            )

            if language:
                base = base.where(
                    Project.language == language,
                )
                count_base = count_base.where(
                    Project.language == language,
                )

            count_result = await session.execute(count_base)
            total = count_result.scalar() or 0

            stmt = base.order_by(
                Project.name.asc(),
            )
            result = await session.execute(stmt)
            projects = [
                self._project_to_summary(p)
                for p in result.scalars().all()
            ]
            return projects, total

    async def get_by_id(
        self, tenant_id: str, project_id: str,
    ) -> dict[str, Any] | None:
        """Get full project details by UUID."""
        async with self._session_factory() as session:
            stmt = select(Project).where(
                Project.id == uuid.UUID(project_id),
                Project.tenant_id == tenant_id,
            )
            result = await session.execute(stmt)
            project = result.scalar_one_or_none()
            if project is None:
                return None
            return self._project_to_dict(project)

    async def scan(
        self, tenant_id: str, project_id: str,
    ) -> dict[str, Any] | None:
        """Re-scan a project for updated metadata.

        Refreshes git branch, commits, file count,
        dependency count, and framework detection.

        Returns:
            Updated project dict, or None if not found.
        """
        async with self._session_factory() as session:
            stmt = select(Project).where(
                Project.id == uuid.UUID(project_id),
                Project.tenant_id == tenant_id,
            )
            result = await session.execute(stmt)
            project = result.scalar_one_or_none()
            if project is None:
                return None

            path = project.path

        # Run scan outside of DB session
        if not Path(path).is_dir():
            return await self.get_by_id(
                tenant_id, project_id,
            )

        lang, dep_file = detect_language(path)
        framework = detect_framework(path)
        file_cnt = count_files(path)
        dep_cnt = count_dependencies(path, dep_file)
        branch, commits = get_git_info(path)
        now = datetime.now(timezone.utc)

        scan_meta = {
            "total_lines": 0,
            "test_files": 0,
            "has_docker": (
                Path(path) / "Dockerfile"
            ).exists() or (
                Path(path) / "docker-compose.yml"
            ).exists(),
            "has_ci": any(
                (Path(path) / d).exists()
                for d in [
                    ".github/workflows",
                    ".gitlab-ci.yml",
                    "Jenkinsfile",
                ]
            ),
        }

        values: dict[str, Any] = {
            "language": lang,
            "framework": framework,
            "dependency_file": dep_file,
            "dependency_count": dep_cnt,
            "file_count": file_cnt,
            "git_branch": branch,
            "recent_commits": commits,
            "scan_metadata": scan_meta,
            "last_scanned_at": now,
            "updated_at": now,
        }

        async with self._session_factory() as session:
            await session.execute(
                update(Project)
                .where(
                    Project.id == uuid.UUID(project_id),
                )
                .values(**values)
            )
            await session.commit()

        logger.info(
            "Scanned project %s (%d files, %d deps)",
            project_id, file_cnt, dep_cnt,
        )
        return await self.get_by_id(
            tenant_id, project_id,
        )

    async def delete(
        self, tenant_id: str, project_id: str,
    ) -> dict[str, Any] | None:
        """Soft-delete a project."""
        project = await self.get_by_id(
            tenant_id, project_id,
        )
        if project is None:
            return None

        async with self._session_factory() as session:
            await session.execute(
                update(Project)
                .where(
                    Project.id == uuid.UUID(project_id),
                    Project.tenant_id == tenant_id,
                )
                .values(
                    is_active=False,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()

        return {
            "id": project_id,
            "name": project["name"],
            "message": "Project removed",
        }

    # ── Context Builder ───────────────────────────────────

    async def build_context(
        self, tenant_id: str, project_id: str,
    ) -> str | None:
        """Build a project context string for agent prompts.

        Returns a formatted context block with project
        metadata for injection into agent system prompts.

        Returns:
            Context string, or None if project not found.
        """
        project = await self.get_by_id(
            tenant_id, project_id,
        )
        if project is None:
            return None

        lines = [
            f"## Project: {project['name']}",
            f"- Path: {project['path']}",
        ]
        if project.get("description"):
            lines.append(
                f"- Description: {project['description']}"
            )
        if project.get("language"):
            lines.append(
                f"- Language: {project['language']}"
            )
        if project.get("framework"):
            lines.append(
                f"- Framework: {project['framework']}"
            )
        if project.get("git_branch"):
            lines.append(
                f"- Branch: {project['git_branch']}"
            )
        lines.append(
            f"- Files: {project.get('file_count', 0)}"
        )
        lines.append(
            f"- Dependencies: "
            f"{project.get('dependency_count', 0)}"
        )

        commits = project.get("recent_commits", [])
        if commits:
            lines.append("- Recent commits:")
            for c in commits[:5]:
                lines.append(
                    f"  - {c['hash']} {c['message']}"
                )

        return "\n".join(lines)

    # ── Helpers ───────────────────────────────────────────

    @staticmethod
    def _project_to_dict(
        project: Project,
    ) -> dict[str, Any]:
        """Convert a Project ORM instance to full dict."""
        return {
            "id": str(project.id),
            "tenant_id": project.tenant_id,
            "name": project.name,
            "path": project.path,
            "description": project.description,
            "git_url": project.git_url,
            "git_branch": project.git_branch,
            "language": project.language,
            "framework": project.framework,
            "dependency_file": project.dependency_file,
            "dependency_count": project.dependency_count,
            "file_count": project.file_count,
            "recent_commits": project.recent_commits or [],
            "scan_metadata": project.scan_metadata or {},
            "last_scanned_at": (
                project.last_scanned_at.isoformat()
                if project.last_scanned_at else None
            ),
            "is_active": project.is_active,
            "created_at": project.created_at.isoformat(),
            "updated_at": project.updated_at.isoformat(),
        }

    @staticmethod
    def _project_to_summary(
        project: Project,
    ) -> dict[str, Any]:
        """Convert a Project to summary dict for list view."""
        return {
            "id": str(project.id),
            "name": project.name,
            "language": project.language,
            "framework": project.framework,
            "git_branch": project.git_branch,
            "file_count": project.file_count,
            "last_scanned_at": (
                project.last_scanned_at.isoformat()
                if project.last_scanned_at else None
            ),
        }
