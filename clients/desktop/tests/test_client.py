import httpx

from clients.desktop.client import (
    CaptureClient,
    SendStatus,
    build_payload,
)


def test_build_payload_shape():
    p = build_payload(
        content="urllib3 CVE",
        app="Code.exe",
        window_title="dispatcher.py",
        source="selection",
        tags=["security"],
        client_capture_id="cid-1",
        captured_at="2026-07-12T00:00:00Z",
    )
    assert p["surface"] == "desktop"
    assert p["modality"] == "text"
    assert p["content"] == "urllib3 CVE"
    assert p["properties"]["app"] == "Code.exe"
    assert p["properties"]["source"] == "selection"
    assert p["properties"]["client_capture_id"] == "cid-1"
    assert p["properties"]["tags"] == ["security"]


def test_build_payload_redacts_content():
    p = build_payload(
        content="token ghp_0123456789abcdefghij0123456789",
        app="x", window_title="y", source="note",
    )
    assert "ghp_0123456789abcdefghij0123456789" not in p["content"]


def test_build_payload_generates_id_when_absent():
    p = build_payload(content="x", app="a", window_title="b", source="note")
    assert p["properties"]["client_capture_id"]


def _client_with(handler):
    transport = httpx.MockTransport(handler)
    return CaptureClient("http://x", "key", "tenant", transport=transport)


def test_send_success():
    c = _client_with(lambda req: httpx.Response(201, json={"ok": True}))
    assert c.send({"surface": "desktop"}).status == SendStatus.SENT


def test_send_auth_failure():
    c = _client_with(lambda req: httpx.Response(401, text="bad key"))
    assert c.send({}).status == SendStatus.AUTH


def test_send_server_error_is_transient():
    c = _client_with(lambda req: httpx.Response(503, text="down"))
    assert c.send({}).status == SendStatus.TRANSIENT


def test_send_bad_request_is_bad():
    c = _client_with(lambda req: httpx.Response(422, text="nope"))
    assert c.send({}).status == SendStatus.BAD


def test_send_network_error_is_transient():
    def boom(req):
        raise httpx.ConnectError("refused")
    assert _client_with(boom).send({}).status == SendStatus.TRANSIENT


def test_send_sets_auth_and_tenant_headers():
    seen = {}

    def handler(req):
        seen["auth"] = req.headers.get("authorization")
        seen["tenant"] = req.headers.get("x-tenant-id")
        return httpx.Response(201)

    _client_with(handler).send({"surface": "desktop"})
    assert seen["auth"] == "Bearer key"
    assert seen["tenant"] == "tenant"
