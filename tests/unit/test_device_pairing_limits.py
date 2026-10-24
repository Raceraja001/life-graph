"""Pairing a phone: the guess cap holds under concurrency, and a new code
retires the old ones (security review 2026-10-24, M1)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from life_graph.services import devices
from tests.unit.fakes import FakeSession, session_factory, sql


def test_an_attempt_counts_before_it_is_decided():
    lim = devices.PairingLimiter(per_client=2, total=10)
    assert lim.allowed("a") and lim.allowed("a")
    assert not lim.allowed("a")  # two in flight already use the allowance
    assert lim.allowed("b")


def test_a_success_gives_its_attempt_back():
    lim = devices.PairingLimiter(per_client=1, total=10)
    assert lim.allowed("a")
    lim.succeeded("a")
    assert lim.allowed("a")
    assert not lim.allowed("a")


def test_the_total_cap_counts_every_client():
    lim = devices.PairingLimiter(per_client=5, total=3)
    assert all(lim.allowed(c) for c in ("a", "b", "c"))
    assert not lim.allowed("d")


@pytest.mark.asyncio
async def test_concurrent_guesses_cannot_pass_the_cap(monkeypatch):
    """Twenty guesses at once, each lookup awaiting the database: only the
    limiter's five may reach redeem(); the rest are refused up front."""
    from life_graph.api import devices as api

    lookups = []

    async def slow_redeem(session, code, name):
        lookups.append(code)
        await asyncio.sleep(0.01)
        raise devices.PairingError

    monkeypatch.setattr(devices, "pairing_limiter", devices.PairingLimiter())
    monkeypatch.setattr(devices, "redeem", slow_redeem)
    monkeypatch.setattr(api, "async_session", session_factory(FakeSession()))
    request = SimpleNamespace(client=SimpleNamespace(host="10.0.0.9"))

    async def guess(n):
        try:
            await api.pair(api.PairRequest(code=f"{n:06d}"), request)
        except HTTPException as exc:
            return exc.status_code
        return 200

    statuses = await asyncio.gather(*(guess(n) for n in range(20)))
    assert sorted(statuses) == [400] * 5 + [429] * 15
    assert len(lookups) == 5


@pytest.mark.asyncio
async def test_a_successful_pairing_does_not_use_up_the_allowance(monkeypatch):
    from life_graph.api import devices as api

    async def redeem(session, code, name):
        return SimpleNamespace(id="d1"), "tok"

    monkeypatch.setattr(devices, "pairing_limiter", devices.PairingLimiter(per_client=1))
    monkeypatch.setattr(devices, "redeem", redeem)
    monkeypatch.setattr(api, "async_session", session_factory(FakeSession()))
    request = SimpleNamespace(client=SimpleNamespace(host="10.0.0.9"))
    for _ in range(3):
        await api.pair(api.PairRequest(code="123456"), request)


@pytest.mark.asyncio
async def test_a_new_code_retires_the_tenants_unused_codes():
    session = FakeSession()
    row = await devices.issue_code(session, "t_pair")
    first = sql(session.statements[0])
    assert first.startswith("DELETE FROM device_pairing_codes")
    assert "tenant_id = 't_pair'" in first and "used_at IS NULL" in first
    assert len(row.code) == devices.CODE_DIGITS and row.tenant_id == "t_pair"
