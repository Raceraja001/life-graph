"""check_conformance: re-run a spec's bound acceptance tests against the
project's current code -- a real git repo, real pytest, a real task row.
"""

from __future__ import annotations

import subprocess
import sys
import uuid

import pytest

from life_graph.services import verifiers as verifiers_mod
from tests.integration.conftest import skip_on_db_error

TENANT = f"conformance_{uuid.uuid4().hex[:8]}"

SPEC = (
    "**Requirements:**\n"
    "AC-1: adding works — test: tests/test_feature.py::test_ok\n"
    "AC-2: the broken thing works — test: tests/test_feature.py::test_broken\n"
    "AC-3: nobody wrote a test for this\n"
    "**Tasks:** 1. do it (AC-1, AC-2, AC-3)"
)


@pytest.fixture(autouse=True)
def _host_mode(monkeypatch):
    monkeypatch.setattr(verifiers_mod.sandbox, "enabled", lambda: False)
    monkeypatch.setattr(verifiers_mod, "_project_python", lambda _workdir: sys.executable)


def _git(repo, *args):
    return subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", *args],
        cwd=str(repo), check=True, capture_output=True, text=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_feature.py").write_text(
        "def test_ok():\n    assert 1 + 1 == 2\n\ndef test_broken():\n    assert 1 + 1 == 3\n",
        encoding="utf-8",
    )
    _git(repo, "init")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init")
    return repo


async def _task_with_spec(repo, spec=SPEC):
    from life_graph.models.db import AgentTask, Project
    from life_graph.storage.database import async_session

    project_id, task_id = uuid.uuid4(), uuid.uuid4()
    async with async_session() as s:
        s.add(Project(id=project_id, tenant_id=TENANT, name=f"p-{project_id.hex[:6]}",
                      path=str(repo), scan_metadata={}))
        await s.flush()
        s.add(AgentTask(
            id=task_id, tenant_id=TENANT, agent_name="dev_task", task_name="plan",
            title="plan", instructions="plan it", task_type="plan",
            assigned_agent="code-fixer-local", project_id=project_id, status="completed",
            properties={"kind": "dev_task"},
            result={"metadata": {"spec": spec}} if spec else {},
        ))
        await s.commit()
    return str(task_id)


@pytest.mark.asyncio
@skip_on_db_error
async def test_reports_each_criterion_and_stores_the_report(repo):
    from life_graph.models.db import AgentTask
    from life_graph.services.conformance import check_conformance
    from life_graph.storage.database import async_session

    task_id = await _task_with_spec(repo)
    report = await check_conformance(async_session, TENANT, task_id)

    status = {c["id"]: c["status"] for c in report["criteria"]}
    assert status == {"AC-1": "passing", "AC-2": "failing", "AC-3": "untested"}
    assert report["conforms"] is False
    assert report["commit"] == _git(repo, "rev-parse", "HEAD")

    async with async_session() as s:
        task = await s.get(AgentTask, uuid.UUID(task_id))
        assert task.properties["conformance"]["summary"] == report["summary"]
        assert task.properties["kind"] == "dev_task"  # existing properties kept


@pytest.mark.asyncio
@skip_on_db_error
async def test_checks_committed_code_not_the_live_checkouts_uncommitted_edits(repo):
    """Uncommitted work in the live checkout must not leak into the check."""
    from life_graph.services.conformance import check_conformance
    from life_graph.storage.database import async_session

    (repo / "tests" / "test_feature.py").write_text(
        "def test_ok():\n    assert False\n", encoding="utf-8"
    )
    task_id = await _task_with_spec(repo)
    report = await check_conformance(async_session, TENANT, task_id)

    assert {c["id"]: c["status"] for c in report["criteria"]}["AC-1"] == "passing"


@pytest.mark.asyncio
@skip_on_db_error
async def test_the_worktree_is_cleaned_up(repo):
    from life_graph.services.conformance import check_conformance
    from life_graph.storage.database import async_session

    task_id = await _task_with_spec(repo)
    await check_conformance(async_session, TENANT, task_id)

    assert len(_git(repo, "worktree", "list").splitlines()) == 1


@pytest.mark.asyncio
@skip_on_db_error
@pytest.mark.parametrize(
    ("spec", "message"),
    [(None, "no spec"), ("**Tasks:** 1. do it", "no acceptance criteria")],
)
async def test_refuses_without_a_spec_or_criteria(repo, spec, message):
    from life_graph.services.conformance import ConformanceError, check_conformance
    from life_graph.storage.database import async_session

    task_id = await _task_with_spec(repo, spec)
    with pytest.raises(ConformanceError, match=message):
        await check_conformance(async_session, TENANT, task_id)


@pytest.mark.asyncio
@skip_on_db_error
async def test_unknown_task_is_refused():
    from life_graph.services.conformance import ConformanceError, check_conformance
    from life_graph.storage.database import async_session

    with pytest.raises(ConformanceError, match="no dev task"):
        await check_conformance(async_session, TENANT, str(uuid.uuid4()))
