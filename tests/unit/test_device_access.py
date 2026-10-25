"""What a paired phone's token opens (api/device_access.py, docs/specs/device-access.md).

The allowlist is checked against the app's real routes, then driven through
the real AuthMiddleware and TenantMiddleware with hand-built ASGI scopes, so
the path is exactly what a server hands Starlette (already percent-decoded)
and no client library tidies a trick away first. The device lookup is faked;
nothing here touches the database.
"""

from __future__ import annotations

import time
import uuid
from types import SimpleNamespace

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from life_graph.api import device_access as da

KEY = "svc-key"
TOKEN = "phone-token"
TENANT = "t-phone"
DEVICE = "d-1"
PHONE = {"Authorization": f"Bearer {TOKEN}"}
ID = str(uuid.uuid4())

#: A sample of what stays service-key only (method, path).
REFUSED = [
    ("POST", "/api/v1/memories/"),
    ("PATCH", f"/api/v1/memories/{ID}"),
    ("DELETE", f"/api/v1/memories/{ID}"),
    ("POST", f"/api/v1/memories/{ID}/approve"),  # the phone's is /jarvis/memories/{id}/approve
    ("DELETE", f"/api/v1/devices/{ID}"),
    ("GET", "/api/v1/devices"),
    ("POST", "/api/v1/devices/codes"),
    ("POST", f"/api/v1/kernel/tasks/{ID}/cancel"),
    ("POST", "/api/v1/kernel/tasks"),
    ("POST", "/api/v1/kernel/drivers/tasks"),
    ("POST", "/api/v1/kernel/drivers/dispatch"),
    ("GET", f"/api/v1/kernel/drivers/tasks/{ID}/diff"),
    ("PUT", "/api/v1/money/budgets/food"),
    ("POST", "/api/v1/money/import"),
    ("PUT", "/api/v1/connectors/google-client"),
    ("POST", "/api/v1/connectors/accounts"),
    ("GET", "/api/v1/connectors"),
    ("POST", f"/api/v1/connectors/items/{ID}/bill"),  # dismiss/remind too; phone has /jarvis/bills
    ("PATCH", f"/api/v1/kernel/personas/{ID}"),
    ("PATCH", "/api/v1/watchers/configs/app_uptime"),
    ("POST", "/api/v1/autonomy/safety/kill-switch/resume"),
    ("POST", "/api/v1/research"),
    ("POST", "/api/v1/study/generate"),
    ("DELETE", f"/api/v1/study/cards/{ID}"),
    ("POST", f"/api/v1/invoices/{ID}/send"),
    ("POST", f"/api/v1/llm-offers/{ID}/evaluate"),
    ("GET", "/api/v1/admin/stats"),
    ("GET", "/api/v1/admin/export"),
    ("POST", "/api/v1/admin/tenants/provision"),
    ("DELETE", f"/api/v1/admin/tenants/{TENANT}"),
    ("GET", "/api/v1/integrations/telegram/bindings"),
]

#: Spellings that must not reach an allowed route (method, path as Starlette sees it).
TRICKS = [
    ("GET", "/api/v1/jarvis/../memories/"),  # what %2E%2E or a raw .. decodes to
    ("GET", "/api/v1/jarvis/../../api/v1/memories/"),
    ("POST", f"/api/v1/jarvis/../approvals/{ID}/approve"),
    ("GET", "/api/v1/jarvis/./today"),
    ("GET", "/api/v1/jarvis%2F..%2Fmemories/"),  # double-encoded: still %2F after decoding
    ("GET", "/api/v1/jarvis/%2e%2e/memories/"),
    ("GET", "/api/v1//money/summary"),
    ("GET", "/api/v1/money/summary/"),  # trailing slash
    ("GET", "/api/v1/memories"),  # the route is /memories/
    ("GET", "/api/v1/money/summary/x"),  # prefix only
    ("GET", "/api/v1/money/summary.json"),
    ("GET", "/API/v1/money/summary"),  # case
    ("GET", "/api/v1/Money/summary"),
    ("GET", "/api/v1/kernel/drivers/tasks/auto-merge-status"),  # not an id
    ("GET", "/api/v1/kernel/drivers/tasks/dependency-audit-readiness"),
    ("GET", f"/api/v1/kernel/drivers/tasks/{ID}x"),
    ("POST", f"/api/v1/approvals/{ID}/approve/"),
    ("POST", f"/api/v1/approvals/{ID}/approve/../reject"),
    ("POST", "/api/v1/approvals/not-a-uuid/approve"),
    ("HEAD", "/api/v1/money/summary"),  # GET does not admit HEAD
    ("OPTIONS", "/api/v1/money/summary"),
    ("POST", "/api/v1/money/summary"),
    ("GET", f"/api/v1/approvals/{ID}/approve"),
    ("GET", "/api/v1/jarvis/today?x"),  # a decoded '?' in the path
    ("GET", "/api/v1/jarvis/today#x"),
    ("GET", "/api/v1/jarvis/to day"),
    ("GET", "/api/v1/jarvis\\..\\memories"),
]


def _sample(entry: da.Allowed) -> str:
    return da._PARAM.sub(ID, entry.route)


# ── The table ─────────────────────────────────────────────────────────


def test_every_entry_is_a_real_route_with_that_method():
    from life_graph.main import app

    paths = app.openapi()["paths"]
    for e in da.DEVICE_ALLOWLIST:
        assert e.route in paths, e.route
        assert e.method.lower() in paths[e.route], (e.method, e.route)


def test_the_table_is_reads_plus_the_named_actions_only():
    actions = sorted((e.method, e.route) for e in da.DEVICE_ALLOWLIST if e.method != "GET")
    assert actions == [
        ("POST", "/api/v1/approvals/{approval_id}/approve"),
        ("POST", "/api/v1/approvals/{approval_id}/reject"),
        ("POST", "/api/v1/study/cards/{card_id}/grade"),
    ]
    assert all(e.method in ("GET", "POST") for e in da.DEVICE_ALLOWLIST)
    assert not any(e.route.startswith("/api/v1/admin") for e in da.DEVICE_ALLOWLIST)
    assert len({(e.method, e.route) for e in da.DEVICE_ALLOWLIST}) == len(da.DEVICE_ALLOWLIST)


def test_the_spec_lists_every_entry():
    from pathlib import Path

    spec = (Path(__file__).parents[2] / "docs/specs/device-access.md").read_text(encoding="utf-8")
    for e in da.DEVICE_ALLOWLIST:
        assert f"`{e.method} {e.route}`" in spec, e.route


@pytest.mark.parametrize("entry", da.DEVICE_ALLOWLIST, ids=lambda e: f"{e.method} {e.route}")
def test_each_entry_matches_its_route_only(entry):
    path = _sample(entry)
    assert da.device_may_call(entry.method, path)
    for other in ("HEAD", "OPTIONS", "PUT", "PATCH", "DELETE", "POST", "GET"):
        if other != entry.method and not any(
            e.method == other and e.pattern.fullmatch(path) for e in da.DEVICE_ALLOWLIST
        ):
            assert not da.device_may_call(other, path), (other, path)
    variants = [path + "x", path + "/x", path.upper(), path.rstrip("/") + "/../x"]
    variants.append(path[:-1] if path.endswith("/") else path + "/")
    for v in variants:
        assert not da.device_may_call(entry.method, v), v


@pytest.mark.parametrize(("method", "path"), REFUSED)
def test_others_are_not_on_the_list(method, path):
    assert not da.device_may_call(method, path)


def test_jarvis_paths_take_any_method():
    for method in ("GET", "POST", "DELETE"):
        assert da.device_may_call(method, "/api/v1/jarvis/today")
    assert not da.device_may_call("GET", "/api/v1/jarvis")
    assert not da.device_may_call("GET", None)


def _req(path: str, url_path: str | None = None, root_path: str = ""):
    scope = {"path": path, "root_path": root_path}
    return SimpleNamespace(scope=scope, url=SimpleNamespace(path=url_path or path))


def test_route_path_wants_a_plain_path_equal_to_the_url():
    assert da.route_path(_req("/api/v1/jarvis/today")) == "/api/v1/jarvis/today"
    assert da.route_path(_req("/api/v1/memories/")) == "/api/v1/memories/"
    assert da.route_path(_req("/api/v1/jarvis/app/download/jarvis-1.2.0.apk"))
    assert da.route_path(_req("/api/v1/jarvis/today", url_path="/api/v1/jarvis/x")) is None
    assert da.route_path(_req("/api/v1/jarvis/today", root_path="/lg")) is None
    for bad in ("/api/v1/jarvis/../x", "/api/v1/jarvis/./x", "/a//b", "/a/%2F", "/a/.b", "/a/b."):
        assert da.route_path(_req(bad)) is None, bad


# ── Through the real middleware ───────────────────────────────────────


async def _echo(request):
    return JSONResponse({"tenant": request.state.tenant_id, "user": request.state.user_id})


def _app():
    from life_graph.api.middleware import AuthMiddleware, TenantMiddleware

    methods = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    app = Starlette(routes=[Route("/{rest:path}", _echo, methods=methods)])
    app.add_middleware(TenantMiddleware)
    app.add_middleware(AuthMiddleware)
    return app


@pytest.fixture
def app(monkeypatch):
    from life_graph.api import middleware
    from life_graph.config import settings
    from life_graph.services import devices

    async def authenticate(token):
        return (TENANT, DEVICE) if token == TOKEN else None

    monkeypatch.setattr(settings, "service_api_keys", KEY)
    monkeypatch.setattr(settings, "api_key", "")
    monkeypatch.setattr(devices, "authenticate", authenticate)
    # No database: the tenant's status (checked on writes) is already known.
    monkeypatch.setitem(middleware._tenant_status_cache, TENANT, (time.monotonic() + 600, "active"))
    monkeypatch.setitem(
        middleware._tenant_status_cache, "other", (time.monotonic() + 600, "active")
    )
    return _app()


async def _call(app, method: str, path: str, headers: dict[str, str]) -> tuple[int, bytes]:
    """One request with ``scope["path"]`` exactly *path*, as a server would pass it."""
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8", "surrogateescape"),
        "root_path": "",
        "query_string": b"",
        "headers": [(b"host", b"test")]
        + [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": ("127.0.0.1", 5000),
        "server": ("test", 80),
    }
    sent: list[dict] = []
    calls = 0

    async def receive():
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"type": "http.request", "body": b"", "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    await app(scope, receive, send)
    status = next(m["status"] for m in sent if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return status, body


@pytest.mark.asyncio
@pytest.mark.parametrize("entry", da.DEVICE_ALLOWLIST, ids=lambda e: f"{e.method} {e.route}")
async def test_every_allowed_route_answers_a_device_as_its_tenant(app, entry):
    import json

    headers = {**PHONE, "X-Tenant-ID": "other", "X-User-ID": "someone"}
    status, body = await _call(app, entry.method, _sample(entry), headers)
    assert status == 200
    # The tenant is the device's, whatever the phone's headers claim.
    assert json.loads(body) == {"tenant": TENANT, "user": f"device:{DEVICE}"}


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "path"), REFUSED + TRICKS)
async def test_everything_else_refuses_a_device_token(app, method, path):
    status, _ = await _call(app, method, path, PHONE)
    assert status == 401


@pytest.mark.asyncio
async def test_jarvis_still_open_and_a_wrong_token_still_refused(app):
    import json

    status, body = await _call(app, "GET", "/api/v1/jarvis/today", {**PHONE, "X-Tenant-ID": "x"})
    assert status == 200 and json.loads(body)["tenant"] == TENANT
    assert (await _call(app, "POST", "/api/v1/jarvis/chat", PHONE))[0] == 200
    wrong = {"Authorization": "Bearer someone-elses"}
    assert (await _call(app, "GET", "/api/v1/money/summary", wrong))[0] == 401
    assert (await _call(app, "GET", "/api/v1/money/summary", {}))[0] == 401


@pytest.mark.asyncio
async def test_the_service_key_is_unchanged(app):
    import json

    owner = {"Authorization": f"Bearer {KEY}", "X-Tenant-ID": "other"}
    for method, path in REFUSED[:5]:
        status, body = await _call(app, method, path, owner)
        assert status == 200 and json.loads(body)["tenant"] == "other"


# ── Who decided, and what the phone sees of local_only accounts ───────


def test_an_approval_decided_on_the_phone_says_so():
    from life_graph.api.approvals import ResolveBody, resolver

    phone = SimpleNamespace(state=SimpleNamespace(device_id="d-9"))
    owner = SimpleNamespace(state=SimpleNamespace())
    spoof = ResolveBody(resolved_by="raja")
    assert resolver(phone, spoof) == "phone:d-9"  # the body cannot name someone else
    assert resolver(phone, None) == "phone:d-9"
    assert resolver(owner, spoof) == "raja" and resolver(owner, None) is None


def _row(exposure, **over):
    row = {
        "id": "i1",
        "account_name": "Bank mail",
        "account_exposure": exposure,
        "kind": "email",
        "title": "Your HDFC statement",
        "summary": "Rs 5,000 due",
        "sender_name": "HDFC",
        "sender_addr": "alerts@hdfc.example",
        "location": "Office",
        "attendees": ["a@b.example"],
        "emails": ["a@b.example"],
        "local_detail": "secret",
        "flags": {
            "bill": {"kind": "bill", "payee": "HDFC", "amount": 5000.0, "currency": "INR"},
            "commitment": "pay",
            "birthday": "10-26",
            "needs_reply": True,
        },
    }
    row["bill"] = row["flags"]["bill"]
    row.update(over)
    return row


def test_phone_rows_keep_when_and_kind_of_a_local_only_account():
    from life_graph.connectors.exposure import phone_rows

    standard, private = _row("standard"), _row("local_only")
    out = phone_rows([standard, private])
    assert out[0] is standard
    masked = out[1]
    for key in ("title", "summary", "sender_name", "sender_addr", "location", "local_detail"):
        assert masked[key] is None, key
    assert masked["attendees"] == [] and masked["emails"] == []
    assert masked["flags"] == {"bill": {"kind": "bill"}, "needs_reply": True}
    assert masked["bill"] == {"kind": "bill"}
    assert private["title"] == "Your HDFC statement"  # the input is not modified
    assert private["flags"]["bill"]["payee"] == "HDFC"


@pytest.mark.asyncio
async def test_connectors_today_from_a_phone_masks_local_only(monkeypatch):
    from datetime import datetime

    from life_graph.api import connectors as api
    from life_graph.connectors import brief
    from life_graph.core.tenant import tenant_scope

    when = "2026-10-25T04:30:00+00:00"

    def event(exposure):
        return _row(
            exposure,
            kind="event",
            title=f"{exposure} meeting",
            starts_at=datetime.fromisoformat(when),
            ends_at=None,
            flags={},
        )

    private_contact = {"title": "Secret Name", "account_exposure": "local_only", "flags": {}}
    raw = {
        "today": [event("standard"), event("local_only")],
        "tomorrow_early": [],
        "waiting": [],
        "promises": [],
        "birthdays": [],
        "code": [],
        "bills": [],
        "tasks": [],
        "people": {"a@b.example": private_contact},
    }

    async def collect(tenant_id, now=None):
        assert tenant_id == "t-own"
        return {k: (list(v) if isinstance(v, list) else dict(v)) for k, v in raw.items()}

    monkeypatch.setattr(brief, "collect", collect)
    phone = SimpleNamespace(state=SimpleNamespace(device_id="d-1"))
    with tenant_scope("t-own"):
        data = (await api.today(phone, tenant_id="t-own"))["data"]
    titles = [e["title"] for e in data["today"]["items"]]
    assert titles == ["standard meeting", "(no title)"]
    assert "Secret Name" not in str(data) and "local_only meeting" not in str(data)

    owner = SimpleNamespace(state=SimpleNamespace())
    with tenant_scope("t-own"):
        full = (await api.today(owner, tenant_id="t-own"))["data"]
    assert [e["title"] for e in full["today"]["items"]] == [
        "standard meeting",
        "local_only meeting",
    ]
