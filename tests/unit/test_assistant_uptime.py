"""Phase E: uptime state transitions, certificate thresholds, HTTP probes."""

from __future__ import annotations

import httpx
import pytest

from life_graph.watchers import app_uptime_watcher as up

OK = {"ok": True, "status": 200, "latency_ms": 40}
BAD = {"ok": False, "status": 502}


def test_one_blip_is_not_an_outage_and_recovery_is_reported_once():
    state, change = up.next_state({}, BAD)
    assert change is None and state["failures"] == 1
    state, change = up.next_state(state, BAD)
    assert change == "down" and state["down"]
    state, change = up.next_state(state, BAD)
    assert change is None  # already reported
    state, change = up.next_state(state, OK)
    assert change == "up" and state["failures"] == 0
    state, change = up.next_state(state, OK)
    assert change is None


def test_a_blip_then_recovery_never_alerts():
    state, change = up.next_state({}, BAD)
    state, change = up.next_state(state, OK)
    assert change is None and not state.get("down")


@pytest.mark.parametrize(
    ("days", "sent", "expected"),
    [
        (30, [], None),
        (14, [], 14),
        (10, [14], None),
        (5, [14], 7),
        (2, [], 3),
        (0, [14, 7, 3, 1], None),
        (None, [], None),
    ],
)
def test_cert_alert(days, sent, expected):
    assert up.cert_alert(days, sent) == expected


@pytest.mark.asyncio
async def test_probe_http_records_status_latency_and_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/down":
            return httpx.Response(503)
        if request.url.path == "/boom":
            raise httpx.ConnectError("refused")
        return httpx.Response(200, text="ok")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        good = await up.probe_http("https://app.example/health", client)
        down = await up.probe_http("https://app.example/down", client)
        boom = await up.probe_http("https://app.example/boom", client)
    assert good["ok"] and good["status"] == 200 and good["latency_ms"] >= 0
    assert not down["ok"] and down["status"] == 503
    assert not boom["ok"] and boom["status"] is None and "ConnectError" in boom["error"]


@pytest.mark.asyncio
async def test_cert_days_left_is_none_for_plain_http():
    assert await up.cert_days_left("http://localhost:8080/health") is None


@pytest.mark.asyncio
async def test_the_state_remembers_when_an_outage_began(monkeypatch):
    """down_since feeds "down since 06:12" on the phone's Today screen."""
    from datetime import UTC, datetime

    probes = iter([BAD, OK])

    async def probe(_url):
        return next(probes)

    async def no_cert(*_a):
        return None

    async def no_fix(*_a, **_k):
        return None

    monkeypatch.setattr(up, "probe_http", probe)
    monkeypatch.setattr(up, "cert_days_left", no_cert)
    watcher = up.AppUptimeWatcher("t1", session_factory=None)
    monkeypatch.setattr(watcher, "_file_fix", no_fix)
    project = {"id": "p1", "name": "app", "path": "/x", "scan_metadata": {}}
    now = datetime(2026, 10, 25, 0, 42, tzinfo=UTC)

    state = await watcher._check_health(project, "https://app.example", {"failures": 1}, now)
    assert state["down"] and state["down_since"] == now.isoformat()
    state = await watcher._check_health(project, "https://app.example", state, now)
    assert not state["down"] and "down_since" not in state
