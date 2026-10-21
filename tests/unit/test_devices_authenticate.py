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
