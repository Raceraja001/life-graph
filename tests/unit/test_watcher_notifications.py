"""Unit tests for the watcher notification chain.

``watchers/notification_engine.py``, ``watchers/digest.py`` and the
``/watchers/notifications`` endpoint all had 0% coverage and all imported a
model name — ``Notification`` — that ``life_graph.watchers.models`` does not
define. The table is ``WatcherNotification``. In the engine and the digest
the resulting ImportError was swallowed by a broad ``except``, so the hourly
watcher cron silently persisted nothing; in the API router it surfaced as a
500 on every request.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy import inspect as sa_inspect

from life_graph.watchers.models import WatcherNotification

# ── The model name actually resolves ──────────────────────────────────


def test_watchers_models_has_no_notification_symbol():
    """Guards the root cause: the symbol the broken code reached for."""
    import life_graph.watchers.models as wm

    assert not hasattr(wm, "Notification"), (
        "watchers.models now exports Notification — the modules that import it "
        "should be rechecked, they were written against WatcherNotification"
    )


@pytest.mark.parametrize(
    "module_name",
    [
        "life_graph.watchers.notification_engine",
        "life_graph.watchers.digest",
        "life_graph.api.watchers",
    ],
)
def test_no_module_imports_the_nonexistent_notification(module_name):
    """No source file may import ``Notification`` from watchers.models."""
    import ast
    import importlib
    import pathlib

    mod = importlib.import_module(module_name)
    tree = ast.parse(pathlib.Path(mod.__file__).read_text())

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "life_graph.watchers.models":
            names = {a.name for a in node.names}
            assert "Notification" not in names, (
                f"{module_name}:{node.lineno} imports a name that does not exist"
            )


# ── Constructor / query attributes are real columns ───────────────────


def _attrs(model) -> set[str]:
    return {a.key for a in sa_inspect(model).mapper.attrs}


def test_watcher_notification_column_names():
    """Pins the names the engine got wrong (channel_type/title)."""
    attrs = _attrs(WatcherNotification)
    assert {"channel", "subject", "body", "severity", "status", "event_id"} <= attrs
    assert "channel_type" not in attrs
    assert "title" not in attrs


@pytest.mark.parametrize("module_name", ["life_graph.watchers.notification_engine"])
def test_engine_uses_only_real_columns(module_name):
    """Every WatcherNotification(...) kwarg must be a mapper attribute."""
    import ast
    import importlib
    import pathlib

    mod = importlib.import_module(module_name)
    tree = ast.parse(pathlib.Path(mod.__file__).read_text())
    attrs = _attrs(WatcherNotification)

    bad: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "WatcherNotification"
        ):
            for kw in node.keywords:
                if kw.arg and kw.arg not in attrs:
                    bad.append(f"line {node.lineno}: {kw.arg}")
    assert not bad, f"non-column kwargs: {bad}"


# ── event_id is NOT NULL and a FK — it must be supplied ───────────────


def test_event_id_is_not_nullable():
    col = sa_inspect(WatcherNotification).columns["event_id"]
    assert col.nullable is False
    assert col.foreign_keys, "event_id should be a FK to watch_events.id"


@pytest.mark.asyncio
async def test_queue_event_skips_when_event_has_no_id():
    """Watcher event dicts carry no 'id'; inserting None violates NOT NULL."""
    from life_graph.watchers.notification_engine import NotificationEngine

    added: list = []

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        def add(self, obj):
            added.append(obj)

        async def commit(self):
            return None

    engine = NotificationEngine(lambda: _Session())
    await engine._queue_event(
        "acme",
        {"severity": "info", "title": "no id here", "details": "..."},
        status="digest_pending",
    )

    assert added == [], "queued a notification with a NULL event_id"


@pytest.mark.asyncio
async def test_queue_event_persists_when_event_id_present():
    from life_graph.watchers.notification_engine import NotificationEngine

    added: list = []

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        def add(self, obj):
            added.append(obj)

        async def commit(self):
            return None

    evt_id = uuid.uuid4()
    engine = NotificationEngine(lambda: _Session())
    await engine._queue_event(
        "acme",
        {
            "id": str(evt_id),
            "severity": "important",
            "title": "Coverage dropped",
            "details": "82% -> 61%",
        },
        status="queued",
    )

    assert len(added) == 1
    notif = added[0]
    assert isinstance(notif, WatcherNotification)
    assert notif.tenant_id == "acme"
    assert notif.event_id == evt_id
    assert notif.subject == "Coverage dropped"
    assert notif.body == "82% -> 61%"
    assert notif.severity == "important"
    assert notif.status == "queued"


# ── run_watchers must hand the persisted event id to the router ───────


def test_run_watchers_passes_event_id_to_route_event():
    """The WatchEvent row id must reach route_event, or event_id is NULL."""
    import ast
    import inspect
    import textwrap

    from life_graph.workers import tasks

    src = textwrap.dedent(inspect.getsource(tasks.run_watchers))
    tree = ast.parse(src)

    # find `route_event(...)` and confirm an "id" is injected into the payload
    assert "route_event" in src
    assigns_id = any(
        isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) and n.slice.value == "id"
        for n in ast.walk(tree)
    )
    assert assigns_id, "run_watchers never sets an 'id' on the event dict it routes"


# ── Response schema must actually read the model ──────────────────────


def test_notification_response_reads_model_attributes():
    """``channel_type``/``title`` are wire names; the columns are channel/subject."""
    from life_graph.watchers.schemas import NotificationResponse

    row = WatcherNotification(
        id=uuid.uuid4(),
        tenant_id="acme",
        event_id=uuid.uuid4(),
        channel="terminal",
        severity="info",
        status="queued",
        subject="Hello",
        body="World",
        created_at=datetime.now(UTC),
    )

    out = NotificationResponse.model_validate(row)
    assert out.channel_type == "terminal", "channel_type did not read from .channel"
    assert out.title == "Hello", "title did not read from .subject"
    assert out.body == "World"
    assert out.status == "queued"


# ── digest marks rows on the right table ──────────────────────────────


@pytest.mark.asyncio
async def test_digest_marks_notifications_without_crashing():
    from life_graph.watchers.digest import DigestGenerator

    statements: list = []

    class _Result:
        def scalars(self):
            return self

        def all(self):
            return []

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def execute(self, stmt):
            statements.append(stmt)
            return _Result()

        async def commit(self):
            return None

    gen = DigestGenerator(lambda: _Session())
    gen._notification_engine = MagicMock()

    out = await gen._generate_digest("acme", since=datetime(2020, 1, 1, tzinfo=UTC), period="daily")

    # No events -> early return, but crucially no ImportError was raised.
    assert "error" not in out, f"digest raised: {out.get('error')}"
    assert out["sent"] is False
