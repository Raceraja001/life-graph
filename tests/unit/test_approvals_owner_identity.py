"""H3 (audit 2026-11-19): who approved is the server's to say, not the body's.

``POST /approvals/{id}/approve|reject`` took ``resolved_by`` from the request
body unless a paired phone was calling, so any client holding a service key
could record the owner's name on its own decision. Now ``resolved_by`` comes
from how the server recognised the caller (api/auth.py ``ingress_for``):

* a paired phone          -> ``phone:<device id>``
* an owner key            -> ``owner``
* any other service key   -> ``service-key:<fingerprint>`` (never the key)

and a name in the body is kept only as an unverified line in the note.

``approvals_require_owner`` (default off) additionally refuses approve and
reject with 403 unless the caller is the owner (owner key or paired phone).
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from life_graph.api import approvals as api
from life_graph.config import settings
from life_graph.services import approvals as approvals_mod

OWNER_KEY = "owner-key-0123456789"
SERVICE_KEY = "mcp-key-9876543210"


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setattr(settings, "api_key", None)
    monkeypatch.setattr(settings, "service_api_keys", f"{SERVICE_KEY},{OWNER_KEY}")
    monkeypatch.setattr(settings, "owner_api_keys", OWNER_KEY)
    monkeypatch.setattr(settings, "approvals_require_owner", False)


def _request(key: str | None = None, device_id: str | None = None) -> Request:
    headers = [(b"authorization", f"Bearer {key}".encode())] if key else []
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/approvals/x/approve",
            "headers": headers,
            "query_string": b"",
        }
    )
    if device_id:
        request.state.device_id = device_id
    return request


@pytest.fixture
def resolved(monkeypatch):
    """Capture what the route hands the service, and skip the database."""
    calls: list[dict] = []

    async def fake_resolve(self, tenant_id, approval_id, decision, note=None, resolved_by=None):
        calls.append({"decision": decision, "note": note, "resolved_by": resolved_by})
        return {"id": approval_id, "kind": "merge", "status": decision + "d", "title": "x"}

    async def no_emit(*_a, **_k):
        return None

    class _Session:
        async def commit(self):
            pass

        async def rollback(self):
            pass

    async def nobody_asked(*_a):
        return None  # no dev task behind these approvals (self-approval guard)

    monkeypatch.setattr(approvals_mod.ApprovalService, "resolve", fake_resolve)
    monkeypatch.setattr(api, "_requested_by", nobody_asked)
    monkeypatch.setattr(api.event_bus, "emit", no_emit)
    return calls, _Session()


async def _approve(request, body=None, session=None):
    return await api.approve_approval(str(uuid.uuid4()), request, body, "t", session)


async def _reject(request, body=None, session=None):
    return await api.reject_approval(str(uuid.uuid4()), request, body, "t", session)


# ── resolved_by comes from the caller's identity ─────────────────────────


def test_a_paired_phone_is_recorded_as_that_phone():
    spoof = api.ResolveBody(resolved_by="owner")
    assert api.resolver(_request(device_id="d-9"), spoof) == "phone:d-9"


def test_an_owner_key_is_recorded_as_the_owner_whatever_the_body_says():
    spoof = api.ResolveBody(resolved_by="someone else")
    assert api.resolver(_request(OWNER_KEY), spoof) == "owner"
    assert api.resolver(_request(OWNER_KEY), None) == "owner"


def test_another_service_key_cannot_claim_to_be_the_owner():
    spoof = api.ResolveBody(resolved_by="owner")
    who = api.resolver(_request(SERVICE_KEY), spoof)

    assert who.startswith("service-key:") and who != "owner"
    assert SERVICE_KEY not in who  # a fingerprint, never the secret
    # Stable per key, and different keys are told apart.
    assert who == api.resolver(_request(SERVICE_KEY), None)
    assert who != api.resolver(_request("another-key-000"), None)


async def test_the_body_name_is_kept_only_as_an_unverified_note(resolved):
    calls, session = resolved
    body = api.ResolveBody(note="looks fine", resolved_by="owner")

    await _approve(_request(SERVICE_KEY), body, session)

    assert calls[0]["resolved_by"].startswith("service-key:")
    assert calls[0]["note"] == "looks fine\n(client said: owner)"


async def test_a_body_without_a_name_keeps_its_note_as_is(resolved):
    calls, session = resolved
    await _approve(_request(OWNER_KEY), api.ResolveBody(note="ok"), session)
    await _reject(_request(OWNER_KEY), None, session)
    assert [c["note"] for c in calls] == ["ok", None]
    assert [c["resolved_by"] for c in calls] == ["owner", "owner"]


# ── approvals_require_owner ───────────────────────────────────────────────


async def test_off_by_default_any_service_key_may_still_decide(resolved):
    calls, session = resolved
    assert settings.approvals_require_owner is False

    await _approve(_request(SERVICE_KEY), None, session)
    await _reject(_request(SERVICE_KEY), None, session)

    assert [c["decision"] for c in calls] == ["approve", "reject"]


@pytest.mark.parametrize("route", [_approve, _reject])
async def test_on_a_non_owner_key_is_refused_and_nothing_runs(monkeypatch, resolved, route):
    calls, session = resolved
    monkeypatch.setattr(settings, "approvals_require_owner", True)

    with pytest.raises(HTTPException) as info:
        await route(_request(SERVICE_KEY), api.ResolveBody(resolved_by="owner"), session)

    assert info.value.status_code == 403
    assert calls == []


@pytest.mark.parametrize("route", [_approve, _reject])
async def test_on_the_owner_key_and_a_paired_phone_may_decide(monkeypatch, resolved, route):
    calls, session = resolved
    monkeypatch.setattr(settings, "approvals_require_owner", True)

    await route(_request(OWNER_KEY), None, session)
    await route(_request(device_id="d-9"), None, session)

    assert [c["resolved_by"] for c in calls] == ["owner", "phone:d-9"]
