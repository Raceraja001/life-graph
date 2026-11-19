"""Server-side session timeouts on the app's engine (audit H7, 2026-11-19).

Nothing reclaimed a connection left idle inside an open transaction: a
session held across a slow LLM call pinned a pooled connection for as long
as the call took. The engine now asks Postgres to end such sessions.
"""

from __future__ import annotations

import importlib.util

from life_graph.config import settings
from life_graph.storage import database
from life_graph.storage.database import engine_connect_args

URL = "postgresql+asyncpg://u:p@localhost:5432/db"


def test_asyncpg_engines_get_idle_in_transaction_timeout():
    args = engine_connect_args(URL, 120_000)

    assert args == {"server_settings": {"idle_in_transaction_session_timeout": "120000"}}


def test_no_statement_timeout_is_set():
    """Long consolidation and backfill statements are legitimate."""
    settings_sent = engine_connect_args(URL, 120_000)["server_settings"]

    assert "statement_timeout" not in settings_sent


def test_zero_turns_it_off():
    assert engine_connect_args(URL, 0) == {}


def test_other_drivers_get_nothing():
    """``server_settings`` is asyncpg's; another driver would reject it."""
    assert engine_connect_args("sqlite+aiosqlite:///x.db", 120_000) == {}


def test_the_setting_reaches_the_engine(monkeypatch):
    """Build the module's engine again, in a throwaway module object, and look
    at what it was given. The real ``database`` module is left untouched."""
    import sqlalchemy.ext.asyncio as sa_asyncio

    seen: dict = {}

    def fake_engine(url, **kwargs):
        seen.update(kwargs, url=url)
        return object()

    monkeypatch.setattr(sa_asyncio, "create_async_engine", fake_engine)
    monkeypatch.setattr(sa_asyncio, "async_sessionmaker", lambda *a, **k: None)
    monkeypatch.setattr(settings, "database_url", URL)
    monkeypatch.setattr(settings, "database_idle_in_transaction_timeout_ms", 90_000)

    spec = importlib.util.spec_from_file_location("_lg_database_probe", database.__file__)
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)

    assert seen["connect_args"] == {
        "server_settings": {"idle_in_transaction_session_timeout": "90000"}
    }


def test_the_default_is_on():
    assert settings.database_idle_in_transaction_timeout_ms > 0
