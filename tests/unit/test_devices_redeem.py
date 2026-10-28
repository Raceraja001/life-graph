"""Tests for redeem in life_graph/services/devices.py."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from life_graph.services.devices import PairingError, redeem
from tests.unit.fakes import FakeSession


async def test_redeem_valid_code():
    """Test redeem with a valid code."""
    from life_graph.models.assistant import Device, DevicePairingCode

    # Setup
    tenant_id = "test_tenant"
    code = "123456"
    name = "MyPhone"

    # Create a code row with valid datetime
    code_row = DevicePairingCode(
        code=code,
        tenant_id=tenant_id,
        expires_at=datetime.now(UTC) + timedelta(minutes=10),  # Not expired
        used_at=None,  # Not used
    )

    # Setup session with objects to simulate database get behavior
    session = FakeSession(objects={(DevicePairingCode, code): code_row})
    device, token = await redeem(session, code, name)

    # Assert
    assert isinstance(device, Device)
    assert token is not None and len(token) > 0
    assert device.tenant_id == tenant_id
    assert device.name == name
    assert device.token_hash is not None

    # Verify device was added
    assert len(session.added) == 1
    assert isinstance(session.added[0], Device)


async def test_redeem_invalid_code():
    """Test redeem with an invalid code (non-digit)."""
    session = FakeSession()

    with pytest.raises(PairingError):
        await redeem(session, "abc123", "MyPhone")


async def test_redeem_wrong_length_code():
    """Test redeem with a code of wrong length."""
    session = FakeSession()

    with pytest.raises(PairingError):
        await redeem(session, "12345", "MyPhone")  # Too short


async def test_redeem_no_such_code():
    """Test redeem with a non-existent code."""
    session = FakeSession(objects={})  # Empty objects dict

    with pytest.raises(PairingError):
        await redeem(session, "123456", "MyPhone")


async def test_redeem_already_used_code():
    """Test redeem with an already used code."""
    from life_graph.models.assistant import DevicePairingCode

    code_row = DevicePairingCode(
        code="123456",
        tenant_id="test_tenant",
        expires_at=datetime.now(UTC) + timedelta(minutes=10),  # Not expired
        used_at=datetime.now(UTC),  # Already used
    )

    session = FakeSession(objects={(DevicePairingCode, "123456"): code_row})

    with pytest.raises(PairingError):
        await redeem(session, "123456", "MyPhone")


async def test_redeem_expired_code():
    """Test redeem with an expired code."""
    from life_graph.models.assistant import DevicePairingCode

    # Create an expired code row
    expired_time = datetime.now(UTC) - timedelta(hours=1)  # Already expired
    code_row = DevicePairingCode(
        code="123456",
        tenant_id="test_tenant",
        expires_at=expired_time,
        used_at=None,
    )

    session = FakeSession(objects={(DevicePairingCode, "123456"): code_row})

    with pytest.raises(PairingError):
        await redeem(session, "123456", "MyPhone")


async def test_redeem_empty_code():
    """Test redeem with empty code."""
    session = FakeSession()

    with pytest.raises(PairingError):
        await redeem(session, "", "MyPhone")


async def test_redeem_whitespace_code():
    """Test redeem with whitespace-only code."""
    session = FakeSession()

    with pytest.raises(PairingError):
        await redeem(session, "   ", "MyPhone")


async def test_redeem_device_name_truncation():
    """Test that device name gets truncated to 120 characters."""
    from life_graph.models.assistant import DevicePairingCode

    tenant_id = "test_tenant"
    code = "123456"

    code_row = DevicePairingCode(
        code=code,
        tenant_id=tenant_id,
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
        used_at=None,
    )

    session = FakeSession(objects={(DevicePairingCode, code): code_row})
    device, token = await redeem(session, code, "x" * 200)  # Very long name

    # Name should be truncated to 120 characters
    assert len(device.name) == 120


async def test_redeem_device_name_default():
    """Test that device gets default name when empty."""
    from life_graph.models.assistant import DevicePairingCode

    tenant_id = "test_tenant"
    code = "123456"

    code_row = DevicePairingCode(
        code=code,
        tenant_id=tenant_id,
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
        used_at=None,
    )

    session = FakeSession(objects={(DevicePairingCode, code): code_row})
    device, token = await redeem(session, code, "")  # Empty name

    # Should default to "Phone"
    assert device.name == "Phone"


async def test_redeem_tenant_scoped():
    """Test that the function properly handles tenant scoping."""
    from life_graph.models.assistant import DevicePairingCode

    tenant_id = "test_tenant"
    code = "123456"

    code_row = DevicePairingCode(
        code=code,
        tenant_id=tenant_id,
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
        used_at=None,
    )

    session = FakeSession(objects={(DevicePairingCode, code): code_row})
    device, token = await redeem(session, code, "MyPhone")

    # Verify the tenant ID was correctly passed
    assert device.tenant_id == tenant_id
