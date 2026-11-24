"""A task_request message never reports a task id that was not saved (audit L8).

send() used to commit three times (message, task, link) with no rollback, so a
failed link write left the returned message pointing at a task the stored row
never recorded. Now everything goes in one commit, the task + link share a
savepoint, and a failure comes back as ``task_error``.
"""

from __future__ import annotations

import uuid

import pytest

from life_graph.models.db import AgentMessage, AgentTask
from life_graph.services import agent_messaging as am


class _Savepoint:
    def __init__(self, session):
        self._session = session
        self._mark = len(session.pending)

    async def commit(self):
        return None

    async def rollback(self):
        del self._session.pending[self._mark :]


class _FakeSession:
    """Just enough AsyncSession: tracks what each commit actually stored."""

    def __init__(self, *, reject_link: bool = False):
        self.reject_link = reject_link
        self.pending: list = []
        self.commits = 0
        self.saved_msg_task_id = None
        self.saved_task_ids: list = []

    def add(self, obj):
        self.pending.append(obj)

    async def _write(self):
        for obj in self.pending:
            if obj.id is None:
                obj.id = uuid.uuid4()
            if self.reject_link and isinstance(obj, AgentMessage) and obj.task_id is not None:
                raise RuntimeError("database rejected the task link")

    async def flush(self):
        await self._write()

    async def begin_nested(self):
        return _Savepoint(self)

    async def commit(self):
        await self._write()
        self.commits += 1
        for obj in self.pending:
            if isinstance(obj, AgentMessage):
                self.saved_msg_task_id = obj.task_id
            elif isinstance(obj, AgentTask) and obj.id not in self.saved_task_ids:
                self.saved_task_ids.append(obj.id)

    async def rollback(self):
        self.pending.clear()

    async def refresh(self, obj):
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _Bus:
    async def emit(self, *a, **k):
        return None


@pytest.fixture(autouse=True)
def _quiet(monkeypatch):
    monkeypatch.setattr(am, "event_bus", _Bus())
    import life_graph.storage.redis as redis_mod

    monkeypatch.setattr(redis_mod, "get_redis", lambda: None)


DATA = {
    "recipient_agent": "builder",
    "message_type": "task_request",
    "subject": "Do it",
    "payload": {"title": "Fix the thing"},
}


async def test_failed_link_is_reported_not_returned():
    session = _FakeSession(reject_link=True)
    svc = am.AgentMessagingService(session_factory=lambda: session)

    msg = await svc.send("t1", "planner", dict(DATA))

    # The reply matches what was stored: no task id, and it says why.
    assert msg.task_id == session.saved_msg_task_id
    assert msg.task_id is None
    assert session.saved_task_ids == []
    assert msg.task_error
    assert session.commits == 1


async def test_task_request_links_task_in_one_commit():
    session = _FakeSession()
    svc = am.AgentMessagingService(session_factory=lambda: session)

    msg = await svc.send("t1", "planner", dict(DATA))

    assert session.commits == 1
    assert msg.task_id is not None
    assert msg.task_id == session.saved_msg_task_id
    assert session.saved_task_ids == [msg.task_id]
    assert msg.task_error is None
