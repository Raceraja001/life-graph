"""GET /kernel/drivers/tasks/{id}/diff and dev_tasks.task_diff: a landed dev
task's change, read from its newest driver_pr approval, without git by hand.

No DB: tests/unit/fakes.py stands in for the session, and for landed_diff (it shells out
to git)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from life_graph.core.tenant import tenant_scope
from life_graph.services import dev_tasks
from tests.unit.fakes import FakeSession, fake_landed_diff, sql

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


# ── task_diff ───────────────────────────────────────────────────────────────


async def test_task_diff_found(monkeypatch):
    calls = fake_landed_diff(monkeypatch, TWO_FILE_DIFF)
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
    text = sql(session.statements[0])
    assert "'t1'" in text and "'driver_pr'" in text and "DESC" in text


async def test_task_diff_not_found(monkeypatch):
    calls = fake_landed_diff(monkeypatch, TWO_FILE_DIFF)
    assert await dev_tasks.task_diff(FakeSession(None), "t1", TASK) is None
    assert calls == []  # no git call without an approval


async def test_task_diff_truncated(monkeypatch):
    fake_landed_diff(
        monkeypatch, "diff --git a/big.txt b/big.txt\n" + "+x\n" * dev_tasks.TASK_DIFF_MAX_CHARS
    )
    result = await dev_tasks.task_diff(FakeSession(SimpleNamespace(payload=PAYLOAD)), "t1", TASK)
    assert len(result["diff"]) == dev_tasks.TASK_DIFF_MAX_CHARS
    assert result["truncated"] is True
    assert result["files"] == ["big.txt"]  # read from the whole diff, not the cut


async def test_task_diff_when_git_fails(monkeypatch):
    fake_landed_diff(monkeypatch, "")  # landed_diff's answer to any git failure
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
