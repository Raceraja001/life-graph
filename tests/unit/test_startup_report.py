"""Tests for startup-subsystem reporting in ``life_graph/main.py``.

The lifespan wires ~15 optional subsystems — the judgment engine, capture
processors, the webhook handler, agent drivers, EventBus subscribers. Each was
wrapped in its own ``try/except Exception: logger.warning(...)``, so a
subsystem that failed to wire left no trace anywhere a probe could see:
``/health`` checked Postgres and Redis and reported "healthy" while half the
event-driven behaviour was silently absent.

Startup failures still never abort the process — that part was correct. They
are now recorded, and ``/health`` reports ``degraded`` and names them.
"""

from __future__ import annotations

import pytest

from life_graph.main import StartupReport, startup_step

# ── StartupReport ─────────────────────────────────────────────────────


def test_empty_report_is_ok():
    r = StartupReport()
    assert r.ok
    assert r.failed == []
    assert r.as_dict() == {}


def test_records_success_and_failure():
    r = StartupReport()
    r.record("alpha", ok=True)
    r.record("beta", ok=False, error="RuntimeError: nope")

    assert not r.ok
    assert r.failed == ["beta"]
    assert r.as_dict()["alpha"] == {"status": "ok"}
    assert r.as_dict()["beta"] == {"status": "failed", "error": "RuntimeError: nope"}


def test_failed_list_is_sorted():
    r = StartupReport()
    for name in ("zulu", "alpha", "mike"):
        r.record(name, ok=False, error="x")
    assert r.failed == ["alpha", "mike", "zulu"]


def test_record_overwrites_same_name():
    r = StartupReport()
    r.record("x", ok=False, error="first")
    r.record("x", ok=True)
    assert r.ok


# ── startup_step ──────────────────────────────────────────────────────


def test_startup_step_records_success():
    r = StartupReport()
    with startup_step(r, "thing"):
        pass
    assert r.as_dict()["thing"]["status"] == "ok"


def test_startup_step_swallows_and_records():
    """Startup must continue — that behaviour is deliberate and unchanged."""
    r = StartupReport()

    with startup_step(r, "thing"):
        raise RuntimeError("subsystem exploded")

    assert r.failed == ["thing"]
    assert "RuntimeError: subsystem exploded" in r.as_dict()["thing"]["error"]


def test_startup_step_swallows_importerror():
    """The failure mode that hid five real bugs in this codebase."""
    r = StartupReport()

    with startup_step(r, "importer"):
        from life_graph.watchers.models import DoesNotExist  # noqa: F401

    assert r.failed == ["importer"]
    assert "ImportError" in r.as_dict()["importer"]["error"]


def test_nested_startup_steps_record_independently():
    """webhook_arq_pool is nested inside webhook_handler."""
    r = StartupReport()

    with startup_step(r, "outer"), startup_step(r, "inner"):
        raise RuntimeError("inner only")

    assert r.failed == ["inner"], "an inner failure must not fail the outer step"
    assert r.as_dict()["outer"]["status"] == "ok"


def test_startup_step_does_not_catch_baseexception():
    """KeyboardInterrupt/CancelledError must still propagate."""
    r = StartupReport()

    with pytest.raises(KeyboardInterrupt), startup_step(r, "thing"):
        raise KeyboardInterrupt


# ── /health reflects the report ───────────────────────────────────────


@pytest.mark.asyncio
async def test_health_reports_degraded_when_a_subsystem_failed(monkeypatch):
    """The regression this whole change exists for."""
    import httpx
    from httpx import ASGITransport

    from life_graph.main import app

    report = StartupReport()
    report.record("judgment_engine", ok=False, error="ImportError: gone")
    report.record("capture_processors", ok=True)
    monkeypatch.setattr(app.state, "startup_report", report, raising=False)

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/health")

    body = r.json()
    startup = body["checks"]["startup"]

    assert startup["status"] == "degraded"
    assert startup["failed"] == ["judgment_engine"]
    assert startup["subsystems"]["judgment_engine"]["error"] == "ImportError: gone"
    assert startup["subsystems"]["capture_processors"] == {"status": "ok"}

    # Postgres is the only critical dependency, so still a 200 — but the
    # overall status must no longer claim "healthy".
    assert body["status"] != "healthy"
    if body["checks"]["postgres"]["status"] == "healthy":
        assert r.status_code == 200
        assert body["status"] == "degraded"


@pytest.mark.asyncio
async def test_health_healthy_when_all_subsystems_ok(monkeypatch):
    import httpx
    from httpx import ASGITransport

    from life_graph.main import app

    report = StartupReport()
    report.record("judgment_engine", ok=True)
    monkeypatch.setattr(app.state, "startup_report", report, raising=False)

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/health")

    body = r.json()
    assert body["checks"]["startup"]["status"] == "healthy"
    assert body["checks"]["startup"]["failed"] == []


@pytest.mark.asyncio
async def test_health_tolerates_lifespan_never_having_run(monkeypatch):
    """ASGITransport does not run lifespan; /health must not 500."""
    import httpx
    from httpx import ASGITransport

    from life_graph.main import app

    monkeypatch.delattr(app.state, "startup_report", raising=False)

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/health")

    assert r.status_code in (200, 503)
    assert r.json()["checks"]["startup"]["total"] == 0


# ── Every lifespan step is tracked ────────────────────────────────────


def test_lifespan_has_no_untracked_bare_except():
    """Startup steps must go through startup_step(), not a bare try/except.

    A new subsystem wrapped in its own try/except would silently reintroduce
    the invisible-failure problem this module exists to prevent.
    """
    import ast
    import inspect
    import textwrap

    from life_graph import main

    src = textwrap.dedent(inspect.getsource(main.lifespan))
    tree = ast.parse(src)

    # The shutdown path legitimately keeps one try/except (it runs after
    # `yield`, where no report is reported on any more).
    startup_tries = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            startup_tries.append(node.lineno)

    yield_line = next(n.lineno for n in ast.walk(tree) if isinstance(n, ast.Yield))
    before_yield = [ln for ln in startup_tries if ln < yield_line]

    assert not before_yield, (
        f"bare try/except in startup at line(s) {before_yield} — "
        "use `with startup_step(report, '<name>'):` so the failure is visible"
    )


def test_all_lifespan_step_names_are_unique():
    import ast
    import inspect
    import textwrap

    from life_graph import main

    src = textwrap.dedent(inspect.getsource(main.lifespan))
    tree = ast.parse(src)

    names = [
        node.args[1].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "startup_step"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
    ]

    assert names, "no startup_step() calls found in lifespan"
    assert len(names) == len(set(names)), f"duplicate step names: {names}"
