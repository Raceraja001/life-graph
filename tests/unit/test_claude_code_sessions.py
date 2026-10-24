"""Unit pins for Claude Code memory sessions (services/claude_code_sessions.py).

No database: statements are compiled for PostgreSQL and inspected, and the
session factory is a fake that scripts results. The DB-backed half (a real
upsert, a real link, a real close) is
tests/integration/test_claude_code_sessions_db.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from life_graph.core.tenant import get_current_tenant_id
from life_graph.services import claude_code_sessions as ccs


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


class _Result:
    def __init__(self, scalar=None, rows=None, rowcount=0) -> None:
        self._scalar = scalar
        self._rows = rows or []
        self.rowcount = rowcount

    def scalar(self):
        return self._scalar

    def all(self):
        return self._rows


class _FakeDB:
    """``async_session()`` stand-in: records statements, replays scripted results."""

    def __init__(self, results: list[_Result], scalars: list | None = None) -> None:
        self.results = results
        self.scalars = scalars or []
        self.statements: list = []
        self.commits = 0

    def __call__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    async def execute(self, stmt):
        self.statements.append(stmt)
        return self.results.pop(0)

    async def scalar(self, stmt):
        self.statements.append(stmt)
        return self.scalars.pop(0) if self.scalars else None

    async def commit(self) -> None:
        self.commits += 1


# ── Reading the hook's properties ────────────────────────────────────────


class TestSessionOf:
    def test_reads_the_new_key(self):
        props = {"integration": "claude_code", "claude_code_session_id": "cc-1"}
        assert ccs.claude_code_session_of(props) == "cc-1"

    def test_reads_the_older_hook_spelling(self):
        assert ccs.claude_code_session_of({"integration": "claude_code", "session_id": "cc-1"}) == (
            "cc-1"
        )

    def test_the_new_key_wins(self):
        props = {"integration": "claude_code", "claude_code_session_id": "new", "session_id": "old"}
        assert ccs.claude_code_session_of(props) == "new"

    @pytest.mark.parametrize(
        "props",
        [None, {}, {"session_id": "x"}, {"integration": "mcp", "session_id": "x"}],
    )
    def test_anything_else_has_none(self, props):
        assert ccs.claude_code_session_of(props) is None

    def test_session_end_marker(self):
        props = {"integration": "claude_code", "claude_code_session_id": "cc-1"}
        assert not ccs.is_session_end(props)
        assert ccs.is_session_end({**props, "kind": "session_end"})
        # A marker with no session to end is not one.
        assert not ccs.is_session_end({"integration": "claude_code", "kind": "session_end"})

    def test_the_marker_kind_matches_the_hook(self):
        from life_graph.integrations.claude_code import hook

        assert ccs.SESSION_END_KIND == hook.SESSION_END_KIND


class TestMemorySessionId:
    def test_stable(self):
        assert ccs.memory_session_id("acme", "cc-1") == ccs.memory_session_id("acme", "cc-1")

    def test_tenant_scoped(self):
        assert ccs.memory_session_id("acme", "cc-1") != ccs.memory_session_id("other", "cc-1")

    def test_parts_differ(self):
        ids = {ccs.memory_session_id("acme", "cc-1", part) for part in (1, 2, 3)}
        assert len(ids) == 3


# ── ensure_session ───────────────────────────────────────────────────────


class TestEnsureSession:
    @pytest.mark.asyncio
    async def test_first_sight_creates_part_one(self, monkeypatch):
        part_one = ccs.memory_session_id("acme", "cc-1")
        db = _FakeDB([_Result(scalar=part_one)])
        monkeypatch.setattr(ccs, "async_session", db)

        got = await ccs.ensure_session("acme", "cc-1", project="life-graph", cwd="/w/life-graph")

        assert got == part_one
        assert db.commits == 1
        params = db.statements[0].compile(dialect=postgresql.dialect()).params
        assert params["id"] == part_one
        assert params["tenant_id"] == "acme"
        context = params["context"]
        assert context["source"] == "claude_code"
        assert context["claude_code_session_id"] == "cc-1"
        assert context["project"] == "life-graph"
        assert context["cwd"] == "/w/life-graph"
        assert context["part"] == 1

    @pytest.mark.asyncio
    async def test_the_upsert_only_touches_an_open_row_of_this_tenant(self, monkeypatch):
        db = _FakeDB([_Result(scalar=uuid.uuid4())])
        monkeypatch.setattr(ccs, "async_session", db)

        await ccs.ensure_session("acme", "cc-1")

        sql = _sql(db.statements[0])
        assert "ON CONFLICT (id) DO UPDATE" in sql
        assert "sessions.tenant_id = " in sql
        assert "sessions.ended_at IS NULL" in sql
        assert "RETURNING sessions.id" in sql

    @pytest.mark.asyncio
    async def test_an_ended_part_moves_on_to_the_next(self, monkeypatch):
        """A resumed session, or one closed as idle, goes on in part 2."""
        part_two = ccs.memory_session_id("acme", "cc-1", 2)
        db = _FakeDB([_Result(scalar=None), _Result(scalar=part_two)])
        monkeypatch.setattr(ccs, "async_session", db)

        got = await ccs.ensure_session("acme", "cc-1")

        assert got == part_two
        params = db.statements[1].compile(dialect=postgresql.dialect()).params
        assert params["context"]["part"] == 2

    @pytest.mark.asyncio
    async def test_gives_up_after_max_parts(self, monkeypatch):
        db = _FakeDB([_Result(scalar=None) for _ in range(ccs.MAX_PARTS)])
        monkeypatch.setattr(ccs, "async_session", db)

        assert await ccs.ensure_session("acme", "cc-1") is None
        assert len(db.statements) == ccs.MAX_PARTS


# ── request_end ──────────────────────────────────────────────────────────


class TestRequestEnd:
    @pytest.mark.asyncio
    async def test_marks_the_open_part_of_this_tenants_session(self, monkeypatch):
        db = _FakeDB([_Result(rowcount=1)])
        monkeypatch.setattr(ccs, "async_session", db)

        assert await ccs.request_end("acme", "cc-1", "clear") is True

        stmt = db.statements[0]
        sql = _sql(stmt)
        assert sql.startswith("UPDATE sessions")
        assert "sessions.ended_at IS NULL" in sql
        params = stmt.compile(dialect=postgresql.dialect()).params
        assert "acme" in params.values()
        assert "cc-1" in params.values()
        marker = next(v for v in params.values() if isinstance(v, dict) and "end_reason" in v)
        assert marker["end_reason"] == "clear"
        assert "end_requested_at" in marker

    @pytest.mark.asyncio
    async def test_a_session_never_seen_is_a_noop(self, monkeypatch):
        monkeypatch.setattr(ccs, "async_session", _FakeDB([_Result(rowcount=0)]))
        assert await ccs.request_end("acme", "cc-1", None) is False


# ── Closing ──────────────────────────────────────────────────────────────


class TestDueQuery:
    def test_selects_open_claude_code_sessions_past_grace_or_idle(self):
        now = datetime(2026, 10, 24, tzinfo=UTC)
        stmt = ccs._due_query(now, grace=timedelta(minutes=5), idle=timedelta(hours=4))
        sql = _sql(stmt)
        params = stmt.compile(dialect=postgresql.dialect()).params
        assert "sessions.ended_at IS NULL" in sql
        assert " OR " in sql
        assert "LIMIT" in sql
        values = list(params.values())
        assert {"source", "end_requested_at", "last_seen_at", "claude_code"} <= set(values)
        assert now - timedelta(minutes=5) in values
        assert now - timedelta(hours=4) in values


class TestSummarize:
    @pytest.mark.asyncio
    async def test_no_memories_is_a_plain_line_and_no_model_call(self, monkeypatch):
        monkeypatch.setattr(ccs, "async_session", _FakeDB([_Result(rows=[])]))
        lm = SimpleNamespace(chat=AsyncMock(), chat_local_only=AsyncMock())
        monkeypatch.setattr("life_graph.api.dependencies.get_lm_client", lambda: lm)

        got = await ccs.summarize(uuid.uuid4(), "acme", "life-graph")

        assert got == "Claude Code session in life-graph: 0 memories."
        lm.chat.assert_not_awaited()
        lm.chat_local_only.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_uses_the_local_model_only(self, monkeypatch):
        """The owner's prompts: never routed to a cloud chain."""
        monkeypatch.setattr(ccs, "async_session", _FakeDB([_Result(rows=[("Uses pgvector",)])]))
        lm = SimpleNamespace(
            chat=AsyncMock(), chat_local_only=AsyncMock(return_value=" Worked on recall. ")
        )
        monkeypatch.setattr("life_graph.api.dependencies.get_lm_client", lambda: lm)

        got = await ccs.summarize(uuid.uuid4(), "acme", "life-graph")

        assert got == "Worked on recall."
        lm.chat.assert_not_awaited()
        lm.chat_local_only.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_a_model_failure_falls_back(self, monkeypatch):
        monkeypatch.setattr(ccs, "async_session", _FakeDB([_Result(rows=[("a",), ("b",)])]))
        lm = SimpleNamespace(chat_local_only=AsyncMock(side_effect=RuntimeError("down")))
        monkeypatch.setattr("life_graph.api.dependencies.get_lm_client", lambda: lm)

        got = await ccs.summarize(uuid.uuid4(), "acme", None)

        assert got == "Claude Code session: 2 memories."


class TestCloseDue:
    @pytest.fixture
    def wired(self, monkeypatch):
        from life_graph.api import sessions as sessions_api

        due = [(uuid.uuid4(), "acme"), (uuid.uuid4(), "other")]
        db = _FakeDB(
            [_Result(rows=due)],
            scalars=[{"project": "life-graph"}, {"project": "uzhavu"}],
        )
        monkeypatch.setattr(ccs, "async_session", db)
        seen_tenants: list[str] = []

        async def _summarize(session_id, tenant_id, project):
            return f"summary of {project}"

        async def _close(session_id, **kwargs):
            seen_tenants.append(get_current_tenant_id())
            return SimpleNamespace(id=session_id)

        close = AsyncMock(side_effect=_close)
        consolidate = AsyncMock()
        monkeypatch.setattr(ccs, "summarize", _summarize)
        monkeypatch.setattr(sessions_api, "close_session", close)
        monkeypatch.setattr(sessions_api, "_run_micro_consolidation", consolidate)
        return SimpleNamespace(
            due=due, close=close, consolidate=consolidate, seen_tenants=seen_tenants
        )

    @pytest.mark.asyncio
    async def test_closes_and_consolidates_each_in_its_tenant(self, wired):
        closed = await ccs.close_due()

        assert closed == [sid for sid, _ in wired.due]
        assert wired.seen_tenants == ["acme", "other"]
        assert [c.args[0] for c in wired.consolidate.await_args_list] == closed

    @pytest.mark.asyncio
    async def test_a_summary_is_always_passed(self, wired):
        """So the API's own generator, which may use a cloud model, never runs."""
        await ccs.close_due()

        summaries = [c.kwargs["summary"] for c in wired.close.await_args_list]
        assert summaries == ["summary of life-graph", "summary of uzhavu"]

    @pytest.mark.asyncio
    async def test_one_already_ended_is_skipped_and_the_rest_go_on(self, wired):
        async def _close(session_id, **kwargs):
            if session_id == wired.due[0][0]:
                raise HTTPException(status_code=409, detail="already ended")
            return SimpleNamespace(id=session_id)

        wired.close.side_effect = _close

        closed = await ccs.close_due()

        assert closed == [wired.due[1][0]]
        assert wired.consolidate.await_count == 1

    @pytest.mark.asyncio
    async def test_an_error_does_not_stop_the_sweep(self, wired):
        wired.consolidate.side_effect = [RuntimeError("boom"), None]

        closed = await ccs.close_due()

        assert closed == [wired.due[1][0]]


def test_the_cron_is_registered():
    from life_graph.workers.settings import WorkerSettings

    name = "life_graph.workers.claude_code_sessions.close_claude_code_sessions"
    assert name in WorkerSettings.functions
    assert any(job.name.removeprefix("cron:") == name for job in WorkerSettings.cron_jobs)
