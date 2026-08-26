"""Unit tests for the nightly Telegram pairing-code sweep.

The job itself is four lines, but two of them are load-bearing: without the
``commit`` the delete is rolled back when the session closes and the table
never shrinks, and the delete must stay scoped to *expired* codes — a sweep
that widened to every row would revoke pairing codes people are mid-way
through typing.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import life_graph.workers.telegram as purge_mod


class _FakeSession:
    def __init__(self, rowcount: int = 0):
        self._rowcount = rowcount
        self.commits = 0
        self.statements: list[object] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        return False

    async def execute(self, stmt):
        self.statements.append(stmt)
        return SimpleNamespace(rowcount=self._rowcount)

    async def commit(self):
        self.commits += 1


@pytest.fixture
def session(monkeypatch):
    fake = _FakeSession(rowcount=3)
    monkeypatch.setattr(purge_mod, "async_session", lambda: fake)
    return fake


@pytest.mark.asyncio
async def test_reports_how_many_rows_it_removed(session):
    assert await purge_mod.purge_telegram_pairing_codes({}) == {"deleted": 3}


@pytest.mark.asyncio
async def test_commits_or_the_delete_is_rolled_back(session):
    await purge_mod.purge_telegram_pairing_codes({})
    assert session.commits == 1


@pytest.mark.asyncio
async def test_deletes_only_expired_codes_from_the_pairing_table(session):
    await purge_mod.purge_telegram_pairing_codes({})
    assert len(session.statements) == 1
    sql = str(session.statements[0].compile(compile_kwargs={"literal_binds": False}))
    assert "DELETE FROM telegram_pairing_codes" in sql
    assert "expires_at <=" in sql


@pytest.mark.asyncio
async def test_empty_sweep_is_not_an_error(monkeypatch):
    fake = _FakeSession(rowcount=0)
    monkeypatch.setattr(purge_mod, "async_session", lambda: fake)
    assert await purge_mod.purge_telegram_pairing_codes({}) == {"deleted": 0}
    assert fake.commits == 1
