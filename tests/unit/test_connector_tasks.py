"""Google Tasks connector (docs/specs/connector-tasks.md): mapping and sync
against a fake Tasks API, what leaves the machine, the brief's Tasks section,
and promises already on the to-do list."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from life_graph.config import settings
from life_graph.connectors import google_oauth
from life_graph.connectors.base import (
    AUTH_OAUTH,
    Account,
    ConnectorError,
    ReauthRequiredError,
)
from life_graph.connectors.exposure import EXPOSURE_LOCAL_ONLY, view_items
from life_graph.connectors.locality import CLOUD, LOCAL

NOW = datetime(2026, 9, 19, 6, 0, tzinfo=UTC)


def _task(tid, title, due=None, status="needsAction", **kw):
    t = {
        "id": tid,
        "title": title,
        "status": status,
        "updated": "2026-09-18T10:00:00.000Z",
        "webViewLink": f"https://tasks.google.com/task/{tid}",
    }
    if due:
        t["due"] = f"{due}T00:00:00.000Z"
    return {**t, **kw}


class FakeTasks:
    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.error: tuple[int, dict] | None = None
        recent = (datetime.now(UTC) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        old = (datetime.now(UTC) - timedelta(days=20)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        self.full = [
            _task("t1", "Renew car insurance", "2026-09-15", notes="Policy 123456789, agent Ravi"),
            _task("t2", "Send invoice to Acme", "2026-09-19"),
            _task("t3", "Book tickets", "2026-09-23"),
            _task("t4", "Pick up dry cleaning"),
            _task("t5", "Old done thing", status="completed", completed=old),
            _task("t6", "Pay school fee", "2026-09-20", status="completed", completed=recent),
            _task("t7", "Sub step", "2026-09-19", parent="t2"),
            {"id": "t8", "title": "", "status": "needsAction"},
        ]
        self.delta = [
            _task("t3", "Book tickets", "2026-09-23", status="completed", completed=recent),
            {"id": "t4", "deleted": True},
        ]

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        assert request.method == "GET"
        if self.error:
            return httpx.Response(self.error[0], json=self.error[1])
        if request.url.path.endswith("/users/@me/lists"):
            return httpx.Response(200, json={"items": [{"id": "L1", "title": "My Tasks"}]})
        assert request.url.path.endswith("/lists/L1/tasks")
        params = dict(request.url.params)
        items = self.delta if "updatedMin" in params else self.full
        return httpx.Response(200, json={"items": items})


@pytest.fixture
def fake_tasks(monkeypatch):
    from plugins.tasks import google_source

    fake = FakeTasks()
    real = httpx.AsyncClient
    monkeypatch.setattr(
        google_source.httpx,
        "AsyncClient",
        lambda **kw: real(transport=httpx.MockTransport(fake.handler), **kw),
    )
    monkeypatch.setattr(settings, "user_timezone", "Asia/Kolkata")
    return fake


def _account():
    return Account(
        id="acc-t",
        tenant_id="raja",
        connector="tasks",
        account_key="tasks",
        display_name="Tasks",
        auth_method=AUTH_OAUTH,
    )


async def test_full_then_incremental_sync(fake_tasks):
    from plugins.tasks import CONNECTOR

    first = await CONNECTOR.sync(_account(), {"access_token": "at"}, {})
    assert first.complete
    by_id = {i.external_id: i for i in first.items}
    assert set(by_id) == {"L1:t1", "L1:t2", "L1:t3", "L1:t4", "L1:t6", "L1:t7"}
    assert "L1:t5" in first.deleted  # completed three weeks ago
    t1 = by_id["L1:t1"]
    assert t1.kind == "task" and t1.flags["due"] == "2026-09-15" and t1.flags["list"] == "My Tasks"
    # Midnight of the due day in the user's zone.
    assert t1.starts_at == datetime(2026, 9, 14, 18, 30, tzinfo=UTC)
    assert t1.detail == "Policy 123456789, agent Ravi"
    assert by_id["L1:t6"].flags["status"] == "completed"
    assert by_id["L1:t7"].flags["parent"] == "L1:t2"
    assert "due" not in by_id["L1:t4"].flags

    second = await CONNECTOR.sync(_account(), {"access_token": "at"}, first.cursor)
    assert not second.complete and second.deleted == ["L1:t4"]
    assert [i.flags["status"] for i in second.items] == ["completed"]
    assert "updatedMin" in dict(fake_tasks.requests[-1].url.params)


async def test_errors(fake_tasks):
    from plugins.tasks import CONNECTOR

    fake_tasks.error = (
        403,
        {
            "error": {
                "message": "Tasks API has not been used",
                "errors": [{"reason": "accessNotConfigured"}],
            }
        },
    )
    with pytest.raises(ConnectorError, match="Tasks API is not enabled") as err:
        await CONNECTOR.sync(_account(), {"access_token": "at"}, {})
    assert not isinstance(err.value, ReauthRequiredError)
    fake_tasks.error = (401, {"error": {"message": "Invalid Credentials"}})
    with pytest.raises(ReauthRequiredError):
        await CONNECTOR.sync(_account(), {"access_token": "at"}, {})


def test_scope_is_read_only():
    assert google_oauth.scopes_for("tasks") == ["https://www.googleapis.com/auth/tasks.readonly"]


# ── exposure + brief ─────────────────────────────────────────


async def _rows(fake, **kw):
    from plugins.tasks import CONNECTOR

    result = await CONNECTOR.sync(_account(), {"access_token": "at"}, {})
    return [
        {
            "id": i.external_id,
            "kind": "task",
            "external_id": i.external_id,
            "account_name": "Tasks",
            "account_exposure": "standard",
            "title": i.title,
            "local_detail": i.detail,
            "flags": i.flags,
            "occurred_at": i.occurred_at,
            **kw,
        }
        for i in result.items
    ]


async def test_notes_never_leave_the_machine(fake_tasks):
    rows = await _rows(fake_tasks)
    cloud = view_items(rows, CLOUD)
    assert all("notes" not in t and "url" not in t for t in cloud["items"])
    assert "123456789" not in str(cloud)
    local = view_items(rows, LOCAL)
    assert any(t.get("notes") for t in local["items"])
    hidden = view_items(await _rows(fake_tasks, account_exposure=EXPOSURE_LOCAL_ONLY), CLOUD)
    assert hidden == {"items": [], "withheld": {"Tasks": 6}}


async def test_brief_tasks_section(fake_tasks):
    from life_graph.connectors.brief import render

    raw = {
        "today": [],
        "tomorrow_early": [],
        "waiting": [],
        "promises": [],
        "tasks": await _rows(fake_tasks),
    }
    text = render(raw, CLOUD, NOW)["text"]
    assert "## Tasks" in text
    assert "- Overdue: Renew car insurance (Tue 15 Sep)" in text
    assert "- Today: Send invoice to Acme" in text
    assert "Sub step" not in text  # subtasks fold under their parent
    assert "- This week: Book tickets (Wed)" in text
    assert "- +1 with no date" in text and "- Done this week: 1" in text


def test_promise_matching():
    from life_graph.connectors.store import _same_task, _words

    assert _same_task(_words("Send the invoice to Acme"), _words("Send invoice to Acme"))
    assert _same_task(_words("Book the tickets"), _words("Book tickets for Goa"))
    assert _same_task(_words("Call the plumber"), _words("plumber"))
    assert not _same_task(_words("Send the deck to Priya"), _words("Send invoice to Acme"))
    assert not _same_task(_words("Review the budget"), _words("Pay school fee"))


def test_task_intent():
    from life_graph.connectors.chat_context import wants_tasks

    assert wants_tasks("what's on my to-do list?")
    assert wants_tasks("any tasks due today")
    assert not wants_tasks("write a poem about rain")
