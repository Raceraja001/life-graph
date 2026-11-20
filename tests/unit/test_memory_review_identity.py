"""Approving or rejecting a pending memory is decided like any approval.

``/memories/{id}/approve|reject``, ``/memories/approvals/bulk`` and the
phone's ``/jarvis/memories/{id}/approve|reject`` record who decided, from the
server's view of the caller (api/approval_identity.resolver), in
``properties.review``; with ``approvals_require_owner`` on only the owner may
decide (403 otherwise, nothing written).
"""

from __future__ import annotations

import hashlib
import uuid
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from life_graph.config import settings
from life_graph.core import evidence as ev
from tests.conftest import fake_request

OWNER_KEY = "owner-key-0123456789"
SERVICE_KEY = "mcp-key-9876543210"
SERVICE_LABEL = f"service-key:{hashlib.sha256(SERVICE_KEY.encode()).hexdigest()[:8]}"


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setattr(settings, "api_key", None)
    monkeypatch.setattr(settings, "service_api_keys", f"{SERVICE_KEY},{OWNER_KEY}")
    monkeypatch.setattr(settings, "owner_api_keys", OWNER_KEY)
    monkeypatch.setattr(settings, "approvals_require_owner", False)


def _row(status="pending"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id="t1",
        status=status,
        content="The owner likes tea.",
        source_type="mcp",
        trust_tier="external",
        properties={"fact_type": "preference"},
    )


def _store(row):
    store = MagicMock()
    store.retrieve = AsyncMock(return_value=row)
    store.update = AsyncMock(return_value=row)
    return store


@pytest.fixture
def quiet():
    """Silence the side effects _transition has beyond the store."""
    with ExitStack() as stack:
        for target, value in (
            ("life_graph.api.memories.MemoryResponse", MagicMock()),
            ("life_graph.services.memory.transitions.settle_contradictions", AsyncMock()),
            ("life_graph.services.memory.transitions.learn_names", AsyncMock()),
            (
                "life_graph.services.memory.transitions.get_current_tenant_id",
                MagicMock(return_value="t1"),
            ),
            ("life_graph.services.profile_card.invalidate", MagicMock()),
        ):
            stack.enter_context(patch(target, value))
        yield


def _written(store):
    call = store.update.await_args
    return call.args[1], call.kwargs


@pytest.mark.parametrize("action", ["approve", "reject"])
async def test_the_decider_is_recorded_from_the_caller(quiet, action):
    from life_graph.api import memories

    row = _row()
    store = _store(row)
    req = fake_request(api_key=SERVICE_KEY)
    if action == "approve":
        await memories.approve_memory(req, memory_id=row.id, body=None, store=store)
    else:
        await memories.reject_memory(req, memory_id=row.id, store=store)

    update, kwargs = _written(store)
    assert update.properties["review"]["by"] == SERVICE_LABEL
    assert update.properties["review"]["action"] == action
    assert update.properties["fact_type"] == "preference"  # the rest kept
    assert kwargs.get("server_side") is True  # a PATCH can't forge it ...
    assert "review" in ev.SERVER_ONLY_PROPS  # ... nor rewrite it later


@pytest.mark.parametrize("action", ["approve", "reject"])
async def test_owner_only_when_the_setting_is_on(quiet, monkeypatch, action):
    from life_graph.api import memories

    monkeypatch.setattr(settings, "approvals_require_owner", True)
    row = _row()
    store = _store(row)
    with pytest.raises(HTTPException) as exc:
        if action == "approve":
            await memories.approve_memory(
                fake_request(api_key=SERVICE_KEY), memory_id=row.id, body=None, store=store
            )
        else:
            await memories.reject_memory(
                fake_request(api_key=SERVICE_KEY), memory_id=row.id, store=store
            )
    assert exc.value.status_code == 403
    store.update.assert_not_awaited()

    if action == "approve":
        await memories.approve_memory(
            fake_request(api_key=OWNER_KEY), memory_id=row.id, body=None, store=store
        )
    else:
        await memories.reject_memory(fake_request(api_key=OWNER_KEY), memory_id=row.id, store=store)
    assert _written(store)[0].properties["review"]["by"] == "owner"


async def test_bulk_is_gated_and_recorded_too(quiet, monkeypatch):
    from life_graph.api import memories

    row = _row()
    store = _store(row)
    body = memories.BulkApprovalBody(approve=[row.id])

    monkeypatch.setattr(settings, "approvals_require_owner", True)
    with pytest.raises(HTTPException) as exc:
        await memories.bulk_approvals(fake_request(api_key=SERVICE_KEY), body, store=store)
    assert exc.value.status_code == 403
    store.update.assert_not_awaited()

    await memories.bulk_approvals(fake_request(device_id="phone-1"), body, store=store)
    assert _written(store)[0].properties["review"]["by"] == "phone:phone-1"


@pytest.mark.parametrize("action", ["approve", "reject"])
async def test_the_phone_routes_record_and_gate(quiet, monkeypatch, action):
    from life_graph.api import jarvis

    row = _row()
    store = _store(row)
    route = jarvis.approve_memory if action == "approve" else jarvis.reject_memory
    with patch("life_graph.api.dependencies.get_store", return_value=store):
        out = await route(row.id, fake_request(device_id="phone-1"))
        assert out["data"]["id"] == str(row.id)
        assert _written(store)[0].properties["review"]["by"] == "phone:phone-1"

        store.update.reset_mock()
        monkeypatch.setattr(settings, "approvals_require_owner", True)
        with pytest.raises(HTTPException) as exc:
            await route(row.id, fake_request(api_key=SERVICE_KEY))
        assert exc.value.status_code == 403
        store.update.assert_not_awaited()


async def test_an_idempotent_approve_writes_nothing(quiet):
    from life_graph.api import memories

    row = _row(status="active")
    store = _store(row)
    await memories.approve_memory(
        fake_request(api_key=SERVICE_KEY), memory_id=row.id, body=None, store=store
    )
    store.update.assert_not_awaited()
