"""Broad excepts that hid real failures now say so (audit L7/F12, phase-2 item 10).

Each test drives one fail-open path with a failure and checks two things:
the path still fails open exactly as before (same return value), and the
failure is now logged -- with a traceback where it is a real I/O, DB,
network, LLM or subprocess error.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest


def _records(caplog, level: int) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.levelno == level]


class _BoomError(Exception):
    pass


def _raising_factory():
    raise _BoomError("database down")


# ── notification channels: a load failure meant no notification was sent ──


async def test_channel_load_failure_is_an_error_with_a_traceback(caplog):
    from life_graph.watchers.notification_engine import NotificationEngine

    engine = NotificationEngine(session_factory=_raising_factory)
    with caplog.at_level(logging.WARNING, logger="life_graph.watchers.notification_engine"):
        assert await engine._load_tenant_channels("tenant-1") == []
    errors = _records(caplog, logging.ERROR)
    assert errors, "a channel load failure must be logged at ERROR"
    assert errors[0].exc_info is not None
    assert "tenant-1" in errors[0].getMessage()
    assert "will not be sent" in errors[0].getMessage()


# ── session summary: the LLM fallback logged no cause ──


async def test_session_summary_fallback_logs_the_cause(caplog, monkeypatch):
    from life_graph.services import session_lifecycle

    def no_client():
        raise _BoomError("LLM unreachable")

    monkeypatch.setattr(session_lifecycle.runtime, "get_lm_client", no_client)
    with caplog.at_level(logging.WARNING, logger="life_graph.services.session_lifecycle"):
        out = await session_lifecycle.generate_summary(SimpleNamespace(context=None), 3)
    assert out == "Session with 3 memories created"
    warnings = _records(caplog, logging.WARNING)
    assert warnings and warnings[0].exc_info is not None


# ── dev runner: repeated lease-heartbeat failures were only ever at debug ──


async def test_repeated_heartbeat_failures_escalate_to_warning(caplog):
    from life_graph.services.dev import runner as runner_mod

    r = runner_mod.DevTaskRunner(session_factory=None, listen=False)
    fail = True

    async def beat():
        if fail:
            raise _BoomError("db gone")

    r.heartbeat = beat
    with caplog.at_level(logging.DEBUG, logger="life_graph.services.dev.runner"):
        for _ in range(runner_mod.HEARTBEAT_WARN_AFTER - 1):
            await r._beat()
        assert not _records(caplog, logging.WARNING), "one blip is not worth a warning"
        await r._beat()
        warnings = _records(caplog, logging.WARNING)
        assert len(warnings) == 1
        assert warnings[0].exc_info is not None
        assert str(runner_mod.HEARTBEAT_WARN_AFTER) in warnings[0].getMessage()

        fail = False
        caplog.clear()
        await r._beat()
        assert any("recovered" in rec.getMessage() for rec in caplog.records)
        assert r._heartbeat_failures == 0


async def test_a_single_heartbeat_failure_stays_at_debug(caplog):
    from life_graph.services.dev import runner as runner_mod

    r = runner_mod.DevTaskRunner(session_factory=None, listen=False)

    async def beat():
        raise _BoomError("blip")

    r.heartbeat = beat
    with caplog.at_level(logging.DEBUG, logger="life_graph.services.dev.runner"):
        await r._beat()
    assert [rec.levelno for rec in caplog.records] == [logging.DEBUG]


# ── runner lock check: a failing query read as "lock lost" with no cause ──


async def test_runner_lock_check_failure_is_logged(caplog):
    from life_graph.services.dev import tasks

    class Conn:
        async def execute(self, *a, **k):
            raise _BoomError("connection dropped")

    with caplog.at_level(logging.WARNING, logger="life_graph.services.dev.tasks"):
        assert await tasks.runner_lock_alive(Conn()) is False
    warnings = _records(caplog, logging.WARNING)
    assert warnings and warnings[0].exc_info is not None


# (verifiers._changed_files: a git failure now fails closed, see
# tests/unit/test_diff_fail_closed.py)


# ── server health: the disk projection returned "" with no trace ──


async def test_disk_projection_failure_is_logged(caplog):
    from life_graph.watchers.server_health_watcher import ServerHealthWatcher

    class Conn:
        async def run(self, *a, **k):
            raise _BoomError("ssh dropped")

    with caplog.at_level(logging.WARNING, logger="life_graph.watchers.server_health_watcher"):
        assert await ServerHealthWatcher()._project_disk_full(Conn(), "/") == ""
    warnings = _records(caplog, logging.WARNING)
    assert warnings and warnings[0].exc_info is not None


# ── tech-watch scrapers: every network failure vanished ──


@pytest.mark.parametrize(
    ("module", "empty"),
    [("hackernews", []), ("reddit", []), ("github_trending", []), ("npm", None), ("pypi", None)],
)
async def test_scraper_failures_are_logged(caplog, monkeypatch, module, empty):
    import importlib
    import inspect

    mod = importlib.import_module(f"life_graph.watchers.scrapers.{module}")

    class NoNetwork:
        def __init__(self, *a, **k):
            raise _BoomError("no network")

    monkeypatch.setattr(mod.httpx, "AsyncClient", NoNetwork)
    fn = next(
        f
        for name, f in inspect.getmembers(mod, inspect.iscoroutinefunction)
        if f.__module__ == mod.__name__ and not name.startswith("_")
    )
    params = [
        p for p in inspect.signature(fn).parameters.values() if p.default is inspect.Parameter.empty
    ]
    args = ["x"] * len(params)
    with caplog.at_level(logging.WARNING, logger=mod.__name__):
        assert await fn(*args) == empty
    warnings = _records(caplog, logging.WARNING)
    assert warnings and warnings[0].exc_info is not None


# ── Claude Code hook: a broken spool was silently never drained ──


def test_flush_spool_failure_is_written_to_the_hook_debug_log(monkeypatch, tmp_path):
    from life_graph.integrations.claude_code import transport

    seen: list[tuple[str, dict]] = []

    class BrokenQueue:
        def __init__(self, path):
            raise _BoomError("spool corrupt")

    monkeypatch.setattr(transport, "CaptureQueue", BrokenQueue, raising=False)
    monkeypatch.setattr(transport, "log_debug", lambda cfg, msg, **f: seen.append((msg, f)))
    cfg = SimpleNamespace(spool_path=tmp_path / "spool.db")
    assert transport.flush_spool(cfg) == 0
    assert seen and "spool corrupt" in seen[0][1]["error"]


def test_flush_spool_replay_failure_is_written_to_the_hook_debug_log(monkeypatch, tmp_path):
    from life_graph.integrations.claude_code import transport

    seen: list[tuple[str, dict]] = []

    class Queue:
        def __init__(self, path):
            pass

        def replay(self, send_fn):
            raise _BoomError("replay broke")

    monkeypatch.setattr(transport, "CaptureQueue", Queue, raising=False)
    monkeypatch.setattr(transport, "log_debug", lambda cfg, msg, **f: seen.append((msg, f)))
    assert transport.flush_spool(SimpleNamespace(spool_path=tmp_path / "s.db")) == 0
    assert seen and "replay broke" in seen[0][1]["error"]
