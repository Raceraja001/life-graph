"""Idea → app: scaffold a new project and hand it to the dev agent.

docs/specs/autonomous-app-development.md, item 12. One call:
1. copies a template from ``life_graph/templates/apps/<template>/``;
2. ``git init``s it on ``main`` with one commit;
3. gives it a remote. A GitHub repo is created with ``gh`` only when
   ``bootstrap_create_github`` is on, since creating a public-facing repo is
   the operator's call; otherwise it is a local bare repository, which is
   enough for the whole pipeline (worktrees cut from ``origin/main``,
   branches pushed, merges fast-forwarded). Promote it to GitHub later with
   ``git remote set-url``;
4. registers it as a project with the template's verifier settings, so its
   first task is already checked by tests_pass and app_e2e_pass;
5. optionally starts a plan-only dev task from the idea.

Names are validated (lowercase, digits, dashes) and the new directory must
not exist and must sit under the tool roots, so a bootstrap can never
overwrite or reach outside where the agents are allowed to work.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any

from life_graph.config import settings

logger = logging.getLogger(__name__)

TEMPLATES = Path(__file__).resolve().parent.parent / "templates" / "apps"
_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{1,40}$")
_GIT_ID = ["-c", "user.name=Life Graph", "-c", "user.email=life-graph@localhost"]


class BootstrapError(Exception):
    """The app could not be scaffolded; the message says why."""


def list_templates() -> list[dict[str, Any]]:
    """Available templates and what each one sets up."""
    out = []
    for path in sorted(p for p in TEMPLATES.iterdir() if (p / "template.json").is_file()):
        meta = json.loads((path / "template.json").read_text())
        out.append({"name": path.name, "description": meta.get("description", "")})
    return out


def _root() -> Path:
    raw = settings.bootstrap_root or settings.tool_fs_roots_list[0]
    return Path(raw).expanduser().resolve()


async def _git(cwd: Path, *args: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        "git",
        *_GIT_ID,
        *args,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise BootstrapError(
            f"git {' '.join(args[:2])} failed: {err.decode(errors='replace')[-300:]}"
        )
    return out.decode(errors="replace").strip()


async def _github_remote(target: Path, name: str) -> str | None:
    """Create a private GitHub repo with gh and push to it; None when off or unavailable."""
    if not settings.bootstrap_create_github or shutil.which("gh") is None:
        return None
    proc = await asyncio.create_subprocess_exec(
        "gh",
        "repo",
        "create",
        name,
        "--private",
        "--source",
        str(target),
        "--remote",
        "origin",
        "--push",
        cwd=str(target),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise BootstrapError(f"gh repo create failed: {err.decode(errors='replace')[-300:]}")
    return out.decode(errors="replace").strip().splitlines()[-1] if out else "github"


async def bootstrap(
    tenant_id: str,
    *,
    name: str,
    template: str,
    idea: str | None = None,
    start_plan: bool = False,
    persona_name: str = "code-fixer-opencode",
) -> dict[str, Any]:
    """Scaffold, version, register and (optionally) plan a new app."""
    from life_graph.kernel.project_registry import ProjectRegistry
    from life_graph.services import dev_tasks
    from life_graph.storage.database import async_session

    if not _NAME_RE.match(name or ""):
        raise BootstrapError("name must be 2-41 chars: lowercase letters, digits, dashes")
    source = TEMPLATES / template
    if not (source / "template.json").is_file():
        raise BootstrapError(f"unknown template {template!r}")
    root = _root()
    target = root / name
    if target.exists():
        raise BootstrapError(f"{target} already exists")
    meta = json.loads((source / "template.json").read_text())

    shutil.copytree(source, target, ignore=shutil.ignore_patterns("template.json", "node_modules"))
    try:
        if idea:
            (target / "IDEA.md").write_text(f"# {name}\n\n{idea.strip()}\n")
        await _git(target, "init", "-q", "-b", "main")
        await _git(target, "add", "-A")
        await _git(target, "commit", "-q", "-m", f"Start {name} from the {template} template")

        remote = await _github_remote(target, name)
        if remote is None:
            bare = root / ".lg-remotes" / f"{name}.git"
            bare.parent.mkdir(parents=True, exist_ok=True)
            await _git(bare.parent, "init", "-q", "--bare", "-b", "main", bare.name)
            await _git(target, "remote", "add", "origin", str(bare))
            await _git(target, "push", "-q", "-u", "origin", "main")
            remote = str(bare)

        project = await ProjectRegistry(session_factory=async_session).register(
            tenant_id,
            {
                "name": name,
                "path": str(target),
                "description": (idea or meta.get("description") or "")[:500],
                "git_url": remote,
                **meta.get("settings", {}),
            },
        )
    except Exception:
        # Nothing half-made is left behind for the next attempt to trip on.
        shutil.rmtree(target, ignore_errors=True)
        raise

    plan = None
    if start_plan and idea:
        plan = await dev_tasks.create_dev_task(
            async_session,
            tenant_id,
            instruction=(
                f"Plan how to build this application on top of the {template} starting "
                f"point already in the repository:\n\n{idea.strip()}"
            ),
            project=project,
            persona_name=persona_name,
            task_type="plan",
            spec_first=True,
            verify_chain=["no_diff_in_plan"],
        )
    logger.info("Bootstrapped %s from %s at %s (remote %s)", name, template, target, remote)
    return {
        "project": {"id": project["id"], "name": name, "path": str(target)},
        "template": template,
        "remote": remote,
        "remote_kind": "local"
        if remote.endswith(".git") and "/.lg-remotes/" in remote
        else "github",
        "plan_task_id": plan["id"] if plan else None,
    }
