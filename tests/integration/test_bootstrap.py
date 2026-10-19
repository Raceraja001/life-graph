"""Idea -> app: a bootstrapped project is a real git repo with a remote,
registered with its template's verifier settings, and passes those checks
in the sandbox from its first commit -- for both templates.
"""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

import pytest

from tests.integration.conftest import skip_on_db_error


def _image(image: str) -> bool:
    try:
        r = subprocess.run(["docker", "image", "inspect", image], capture_output=True, timeout=30)
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


@pytest.fixture
def roots(tmp_path, monkeypatch):
    from life_graph.config import settings

    root = tmp_path / "apps"
    root.mkdir()
    monkeypatch.setattr(settings, "bootstrap_root", str(root))
    monkeypatch.setattr(settings, "tool_fs_roots", str(root))
    monkeypatch.setattr(settings, "bootstrap_create_github", False)
    return root


@pytest.mark.asyncio
async def test_templates_are_listed():
    from life_graph.services.bootstrap import list_templates

    names = {t["name"] for t in list_templates()}
    assert {"node-api", "python-api"} <= names


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_bootstrapped_app_is_versioned_registered_and_planned(roots):
    from life_graph.models.db import AgentTask, Project
    from life_graph.services.bootstrap import bootstrap
    from life_graph.storage.database import async_session

    tenant = f"boot_{uuid.uuid4().hex[:8]}"
    out = await bootstrap(
        tenant,
        name="todo-app",
        template="node-api",
        idea="A shared shopping list.",
        start_plan=True,
    )

    target = Path(out["project"]["path"])
    assert target == roots / "todo-app"
    assert (target / "IDEA.md").read_text().startswith("# todo-app")
    assert not (target / "template.json").exists()
    log = subprocess.run(["git", "log", "--oneline"], cwd=target, capture_output=True, text=True)
    assert "Start todo-app from the node-api template" in log.stdout
    assert out["remote_kind"] == "local"
    remote_head = subprocess.run(
        ["git", "ls-remote", "origin", "main"], cwd=target, capture_output=True, text=True
    ).stdout
    assert (
        remote_head.split()[0]
        == subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=target, capture_output=True, text=True
        ).stdout.strip()
    )

    async with async_session() as s:
        project = await s.get(Project, uuid.UUID(out["project"]["id"]))
        meta = project.scan_metadata
        plan = await s.get(AgentTask, uuid.UUID(out["plan_task_id"]))
    assert meta["sandbox_toolchain"] == "node" and meta["base_branch"] == "main"
    assert "app_e2e_pass" in meta["required_checks"]
    assert plan.task_type == "plan" and "shopping list" in plan.instructions


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_bad_or_taken_name_is_refused_and_leaves_nothing(roots):
    from life_graph.services.bootstrap import BootstrapError, bootstrap

    tenant = f"boot_{uuid.uuid4().hex[:8]}"
    for bad in ("../escape", "Has Caps", "x"):
        with pytest.raises(BootstrapError):
            await bootstrap(tenant, name=bad, template="node-api")
    with pytest.raises(BootstrapError):
        await bootstrap(tenant, name="fine-name", template="no-such-template")
    (roots / "taken").mkdir()
    with pytest.raises(BootstrapError):
        await bootstrap(tenant, name="taken", template="node-api")
    assert sorted(p.name for p in roots.iterdir()) == ["taken"]


@pytest.mark.asyncio
@skip_on_db_error
@pytest.mark.parametrize("template", ["node-api", "python-api"])
async def test_each_template_passes_its_own_checks_from_the_first_commit(
    roots, template, monkeypatch
):
    from life_graph.config import settings
    from life_graph.models.db import Project
    from life_graph.services.bootstrap import bootstrap
    from life_graph.services.verifiers import verifier_chain
    from life_graph.storage.database import async_session

    image = (
        settings.verifier_sandbox_node_image
        if template == "node-api"
        else settings.verifier_sandbox_image
    )
    if not _image(image):
        pytest.skip(f"{image} not built")
    monkeypatch.setattr(settings, "verifier_sandbox", "docker")
    monkeypatch.setattr(settings, "verifier_sandbox_cache_dir", "/tmp/lg-bootstrap-test-cache")

    out = await bootstrap(f"boot_{uuid.uuid4().hex[:8]}", name=f"app-{template}", template=template)
    async with async_session() as s:
        meta = (await s.get(Project, uuid.UUID(out["project"]["id"]))).scan_metadata

    results = await verifier_chain.run_chain(
        ["tests_pass", "app_e2e_pass"], Path(out["project"]["path"]), dict(meta)
    )
    assert all(r.passed for r in results), [(r.verifier, r.evidence) for r in results]
