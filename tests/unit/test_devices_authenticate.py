# Tests for life_graph.services.devices.authenticate

import time
from datetime import UTC, datetime, timedelta

import pytest

from life_graph.services.devices import _cache, authenticate, hash_token
from tests.unit.fakes import FakeResult, FakeSession, session_factory


# Helper to create a fake device object
class DummyDevice:
    def __init__(self, tenant_id, device_id, revoked_at=None, last_seen_at=None):
        self.tenant_id = tenant_id
        self.id = device_id
        self.revoked_at = revoked_at
        self.last_seen_at = last_seen_at


# Monkeypatch the async_session import in authenticate
@pytest.fixture
def patch_async_session(monkeypatch, fake_session):
    monkeypatch.setattr("life_graph.storage.database.async_session", session_factory(fake_session))


# Fixture for a fresh fake session
@pytest.fixture
def fake_session():
    return FakeSession()


# Test empty token returns None
@pytest.mark.asyncio
async def test_authenticate_empty_token(fake_session, patch_async_session):
    result = await authenticate("")
    assert result is None


# Test token longer than 200 chars returns None
@pytest.mark.asyncio
async def test_authenticate_long_token(fake_session, patch_async_session):
    long_token = "a" * 201
    result = await authenticate(long_token)
    assert result is None


# Test cache hit returns cached values without DB query
@pytest.mark.asyncio
async def test_authenticate_cache_hit(fake_session, patch_async_session):
    token = "validtoken"
    digest = hash_token(token)
    now = time.monotonic()
    _cache[digest] = (now + 60.0, "tenant123", "device456")
    result = await authenticate(token)
    assert result == ("tenant123", "device456")
    # No DB query should have been made
    assert fake_session.statements == []


# Test no device found returns None and clears cache
@pytest.mark.asyncio
async def test_authenticate_no_device(fake_session, patch_async_session):
    token = "notfound"
    # execute returns None
    fake_session._results = [FakeResult([])]
    result = await authenticate(token)
    assert result is None
    # Cache should be cleared if present
    assert hash_token(token) not in _cache


# Test revoked device returns None and clears cache
@pytest.mark.asyncio
async def test_authenticate_revoked(fake_session, patch_async_session):
    token = "revoked"
    device = DummyDevice("tenant", "device", revoked_at=datetime.now(UTC))
    fake_session._results = [FakeResult([device])]
    result = await authenticate(token)
    assert result is None
    assert hash_token(token) not in _cache


# Test device seen long ago triggers update and commit
@pytest.mark.asyncio
async def test_authenticate_seen_update(fake_session, patch_async_session, monkeypatch):
    token = "seenupdate"
    past = datetime.now(UTC) - timedelta(minutes=10)
    device = DummyDevice("tenant", "device", revoked_at=None, last_seen_at=past)
    fake_session._results = [FakeResult([device])]
    # Fix time.monotonic
    monkeypatch.setattr(
        "life_graph.services.devices.time", type("_", (), {"monotonic": lambda: 1000.0})
    )
    await authenticate(token)
    assert fake_session.commits == 1
    assert device.last_seen_at > past
    assert hash_token(token) in _cache


# Test device seen recently does not commit
@pytest.mark.asyncio
async def test_authenticate_seen_recent(fake_session, patch_async_session, monkeypatch):
    token = "seenrecent"
    recent = datetime.now(UTC) - timedelta(minutes=1)
    device = DummyDevice("tenant", "device", revoked_at=None, last_seen_at=recent)
    fake_session._results = [FakeResult([device])]
    monkeypatch.setattr(
        "life_graph.services.devices.time", type("_", (), {"monotonic": lambda: 2000.0})
    )
    await authenticate(token)
    assert fake_session.commits == 0


# Review 2026-10-24 (M5): a token unused for device_token_idle_days stops working
@pytest.mark.asyncio
async def test_authenticate_refuses_a_long_idle_device(fake_session, patch_async_session):
    token = "idle"
    device = DummyDevice("tenant", "device", last_seen_at=datetime.now(UTC) - timedelta(days=61))
    fake_session._results = [FakeResult([device])]
    assert await authenticate(token) is None
    assert hash_token(token) not in _cache
    assert fake_session.commits == 0  # last_seen_at is not refreshed by a refused try


@pytest.mark.asyncio
async def test_idle_expiry_can_be_switched_off(fake_session, patch_async_session, monkeypatch):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "device_token_idle_days", 0)
    device = DummyDevice("tenant", "device", last_seen_at=datetime.now(UTC) - timedelta(days=400))
    fake_session._results = [FakeResult([device])]
    assert await authenticate("idle-but-allowed") == ("tenant", "device")
    _cache.pop(hash_token("idle-but-allowed"), None)


@pytest.mark.asyncio
async def test_revoke_leaves_the_cache_until_the_commit():
    """The cache is dropped after the revocation commits, not before: a request
    between the two would re-read the unrevoked row and cache it again."""
    import uuid

    from life_graph.models.assistant import Device
    from life_graph.services.devices import forget_cached, revoke

    dev_id = uuid.uuid4()
    row = DummyDevice("tenant", dev_id)
    session = FakeSession(objects={(Device, dev_id): row})
    _cache["h-revoke"] = (time.monotonic() + 60, "tenant", str(dev_id))
    assert await revoke(session, "tenant", dev_id) is True
    assert row.revoked_at is not None and "h-revoke" in _cache
    forget_cached(dev_id)
    assert "h-revoke" not in _cache
    assert await revoke(session, "someone-else", dev_id) is False


@pytest.mark.asyncio
async def test_the_revoke_route_drops_the_cache_after_committing(monkeypatch):
    import uuid

    from life_graph.api import devices as api
    from life_graph.core.tenant import tenant_scope
    from life_graph.services import devices

    order = []

    class _Session(FakeSession):
        async def commit(self):
            order.append("commit")

    async def fake_revoke(session, tenant_id, device_id):
        order.append("revoke")
        return True

    monkeypatch.setattr(api, "async_session", session_factory(_Session()))
    monkeypatch.setattr(devices, "revoke", fake_revoke)
    monkeypatch.setattr(devices, "forget_cached", lambda d: order.append("forget"))
    with tenant_scope("tenant"):
        await api.revoke_device(str(uuid.uuid4()))
    assert order == ["revoke", "commit", "forget"]


# Test that a successful authentication sets cache correctly
@pytest.mark.asyncio
async def test_authenticate_cache_set(fake_session, patch_async_session, monkeypatch):
    token = "cacheset"
    device = DummyDevice("tenant", "device", revoked_at=None, last_seen_at=None)
    fake_session._results = [FakeResult([device])]
    monkeypatch.setattr(
        "life_graph.services.devices.time", type("_", (), {"monotonic": lambda: 3000.0})
    )
    result = await authenticate(token)
    assert result == ("tenant", "device")
    digest = hash_token(token)
    assert digest in _cache
    expire, cached_tenant, cached_id = _cache[digest]
    assert cached_tenant == "tenant"
    assert cached_id == "device"
    assert expire > 3000.0
