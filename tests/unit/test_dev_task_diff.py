"""GET /kernel/drivers/tasks/{id}/diff and dev_tasks.task_diff: a landed dev
task's change, read from its newest driver_pr approval, without git by hand.

No DB: the session's execute() is faked, and so is landed_diff (it shells out
to git)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from life_graph.core.tenant import tenant_scope
from life_graph.services import dev_tasks

TASK = str(uuid.uuid4())
PAYLOAD = {
    "task_id": TASK,
    "repo_path": "/repo",
    "branch": f"lg/task-{TASK[:8]}",
    "base_commit": "a" * 40,
    "head_commit": "b" * 40,
}
TWO_FILE_DIFF = (
    "diff --git a/life_graph/x.py b/life_graph/x.py\n"
    "--- a/life_graph/x.py\n+++ b/life_graph/x.py\n@@ -1 +1 @@\n-X = 1\n+X = 2\n"
    "diff --git a/tests/unit/test_x.py b/tests/unit/test_x.py\n"
    "new file mode 100644\n--- /dev/null\n+++ b/tests/unit/test_x.py\n@@ -0,0 +1 @@\n+pass\n"
)


class FakeSession:
    def __init__(self, approval):
        self.approval = approval
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return SimpleNamespace(scalar_one_or_none=lambda: self.approval)


@pytest.fixture
def git(monkeypatch):
    from life_graph.services import github_pr

    calls = []

    def _set(text):
        async def landed_diff(repo_path, base, head):
            calls.append((repo_path, base, head))
            return text

        monkeypatch.setattr(github_pr, "landed_diff", landed_diff)
        return calls

    return _set


# ── task_diff ───────────────────────────────────────────────────────────────


async def test_task_diff_found(git):
    calls = git(TWO_FILE_DIFF)
    session = FakeSession(SimpleNamespace(payload=PAYLOAD))
    result = await dev_tasks.task_diff(session, "t1", TASK)

    assert result == {
        "task_id": TASK,
        "branch": PAYLOAD["branch"],
        "base_commit": "a" * 40,
        "head_commit": "b" * 40,
        "files": ["life_graph/x.py", "tests/unit/test_x.py"],
        "diff": TWO_FILE_DIFF,
        "truncated": False,
    }
    assert calls == [("/repo", "a" * 40, "b" * 40)]
    # Scoped to the tenant and the driver_pr kind, newest first.
    sql = str(session.statements[0].compile(compile_kwargs={"literal_binds": True}))
    assert "'t1'" in sql and "'driver_pr'" in sql and "DESC" in sql


async def test_task_diff_not_found(git):
    calls = git(TWO_FILE_DIFF)
    assert await dev_tasks.task_diff(FakeSession(None), "t1", TASK) is None
    assert calls == []  # no git call without an approval


async def test_task_diff_truncated(git):
    git("diff --git a/big.txt b/big.txt\n" + "+x\n" * dev_tasks.TASK_DIFF_MAX_CHARS)
    result = await dev_tasks.task_diff(FakeSession(SimpleNamespace(payload=PAYLOAD)), "t1", TASK)
    assert len(result["diff"]) == dev_tasks.TASK_DIFF_MAX_CHARS
    assert result["truncated"] is True
    assert result["files"] == ["big.txt"]  # read from the whole diff, not the cut


async def test_task_diff_when_git_fails(git):
    git("")  # landed_diff's answer to any git failure
    result = await dev_tasks.task_diff(FakeSession(SimpleNamespace(payload=PAYLOAD)), "t1", TASK)
    assert result["diff"] == "" and result["files"] == [] and result["truncated"] is False


# ── GET /tasks/{task_id}/diff ───────────────────────────────────────────────


@pytest.fixture
def route(monkeypatch):
    from contextlib import asynccontextmanager

    from life_graph.api import drivers

    seen = {}

    @asynccontextmanager
    async def fake_session():
        yield "session"

    def _set(answer):
        async def task_diff(session, tenant_id, task_id):
            seen.update(session=session, tenant=tenant_id, task=task_id)
            return answer

        monkeypatch.setattr(dev_tasks, "task_diff", task_diff)
        monkeypatch.setattr(drivers, "async_session", fake_session)
        return seen

    return _set


async def test_route_returns_the_diff(route):
    from life_graph.api.drivers import get_dev_task_diff

    seen = route({"task_id": TASK, "files": ["a.py"], "diff": "d", "truncated": False})
    with tenant_scope("acme"):
        response = await get_dev_task_diff(TASK)
    assert response["data"] == {"task_id": TASK, "files": ["a.py"], "diff": "d", "truncated": False}
    assert seen == {"session": "session", "tenant": "acme", "task": TASK}


async def test_route_404_until_the_task_has_landed(route):
    from life_graph.api.drivers import get_dev_task_diff

    route(None)
    with tenant_scope("acme"), pytest.raises(HTTPException) as err:
        await get_dev_task_diff(TASK)
    assert err.value.status_code == 404


async def test_route_400_for_a_bad_id(route):
    from life_graph.api.drivers import get_dev_task_diff

    seen = route({"x": 1})
    with tenant_scope("acme"), pytest.raises(HTTPException) as err:
        await get_dev_task_diff("not-a-uuid")
    assert err.value.status_code == 400 and seen == {}
