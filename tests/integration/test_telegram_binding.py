"""Pairing is the multi-tenant boundary of the Telegram bridge.

An inbound Telegram update carries a ``chat_id`` and no authentication. Every
guarantee downstream — that a message writes to the right tenant, that a
stranger's chat writes to nobody — rests on ``TelegramBindingService``. These
tests run against a real database on purpose: the "one active binding per chat"
rule is a partial unique index, and a mocked session would assert only that the
Python happy path was taken while the constraint went untested.

See docs/specs/telegram-bridge.md.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import delete

from life_graph.models.db import TelegramBinding, TelegramPairingCode
from life_graph.services.telegram_binding import PairingError, TelegramBindingService
from life_graph.storage.database import async_session
from tests.integration.conftest import skip_on_db_error

TENANT = "test_tg_tenant"
OTHER_TENANT = "test_tg_other"

# Distinct per test so a leaked row cannot make an unrelated test pass.
CHAT = 4210001
CHAT_B = 4210002
CHAT_C = 4210003


@pytest_asyncio.fixture
async def clean_slate():
    """Remove this module's rows before and after, leaving other tenants alone."""

    async def _purge():
        async with async_session() as session:
            await session.execute(
                delete(TelegramBinding).where(TelegramBinding.tenant_id.in_([TENANT, OTHER_TENANT]))
            )
            await session.execute(
                delete(TelegramPairingCode).where(
                    TelegramPairingCode.tenant_id.in_([TENANT, OTHER_TENANT])
                )
            )
            await session.commit()

    await _purge()
    yield
    await _purge()


async def _issue(tenant: str = TENANT, ttl: timedelta | None = None) -> str:
    async with async_session() as session:
        svc = TelegramBindingService(session)
        row = await svc.issue_code(tenant, ttl=ttl)
        code = row.code
        await session.commit()
    return code


# ── The happy path ────────────────────────────────────────────────


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_redeemed_code_binds_the_chat_to_its_tenant(clean_slate):
    code = await _issue()
    async with async_session() as session:
        svc = TelegramBindingService(session)
        binding = await svc.redeem_code(code, CHAT, username="raja")
        await session.commit()
        assert binding.tenant_id == TENANT
        assert binding.chat_id == CHAT
        assert binding.active is True

    async with async_session() as session:
        assert await TelegramBindingService(session).tenant_for_chat(CHAT) == TENANT


@pytest.mark.asyncio
@skip_on_db_error
async def test_an_unbound_chat_resolves_to_no_tenant(clean_slate):
    """None must mean 'drop the message', never 'use a default tenant'."""
    async with async_session() as session:
        assert await TelegramBindingService(session).tenant_for_chat(999_999_999) is None


# ── Rejections ────────────────────────────────────────────────────


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_code_cannot_be_redeemed_twice(clean_slate):
    code = await _issue()
    async with async_session() as session:
        await TelegramBindingService(session).redeem_code(code, CHAT)
        await session.commit()

    async with async_session() as session:
        with pytest.raises(PairingError):
            await TelegramBindingService(session).redeem_code(code, CHAT_B)

    # The second chat must not have been bound by the failed attempt.
    async with async_session() as session:
        assert await TelegramBindingService(session).tenant_for_chat(CHAT_B) is None


@pytest.mark.asyncio
@skip_on_db_error
async def test_an_expired_code_is_refused(clean_slate):
    code = await _issue(ttl=timedelta(seconds=-1))
    async with async_session() as session:
        with pytest.raises(PairingError):
            await TelegramBindingService(session).redeem_code(code, CHAT)


@pytest.mark.asyncio
@skip_on_db_error
async def test_an_unknown_code_is_refused(clean_slate):
    async with async_session() as session:
        with pytest.raises(PairingError):
            await TelegramBindingService(session).redeem_code("ZZZZZZ", CHAT)


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_chat_bound_to_one_tenant_cannot_be_claimed_by_another(clean_slate):
    """The core isolation guarantee: no cross-tenant capture of a live chat."""
    async with async_session() as session:
        await TelegramBindingService(session).redeem_code(await _issue(TENANT), CHAT)
        await session.commit()

    async with async_session() as session:
        with pytest.raises(PairingError):
            await TelegramBindingService(session).redeem_code(await _issue(OTHER_TENANT), CHAT)

    async with async_session() as session:
        assert await TelegramBindingService(session).tenant_for_chat(CHAT) == TENANT


@pytest.mark.asyncio
@skip_on_db_error
async def test_pairing_is_refused_outside_a_direct_message(clean_slate):
    code = await _issue()
    async with async_session() as session:
        with pytest.raises(PairingError):
            await TelegramBindingService(session).redeem_code(code, CHAT, chat_type="supergroup")


@pytest.mark.asyncio
@skip_on_db_error
async def test_rebinding_the_same_chat_to_the_same_tenant_is_a_no_op(clean_slate):
    """A user who lost track of the state should not be told they are locked out."""
    async with async_session() as session:
        first = await TelegramBindingService(session).redeem_code(await _issue(), CHAT)
        first_id = first.id
        await session.commit()

    async with async_session() as session:
        again = await TelegramBindingService(session).redeem_code(
            await _issue(), CHAT, username="renamed"
        )
        await session.commit()
        assert again.id == first_id
        assert again.username == "renamed"


# ── Revocation ────────────────────────────────────────────────────


@pytest.mark.asyncio
@skip_on_db_error
async def test_revoking_frees_the_chat_to_be_bound_again(clean_slate):
    """Revoke deactivates rather than deletes; the partial index must allow reuse."""
    async with async_session() as session:
        svc = TelegramBindingService(session)
        binding = await svc.redeem_code(await _issue(), CHAT_C)
        binding_id = binding.id
        await session.commit()

    async with async_session() as session:
        assert await TelegramBindingService(session).revoke(TENANT, binding_id) is True
        await session.commit()

    async with async_session() as session:
        assert await TelegramBindingService(session).tenant_for_chat(CHAT_C) is None

    # The freed chat can now be bound to a different tenant.
    async with async_session() as session:
        rebound = await TelegramBindingService(session).redeem_code(
            await _issue(OTHER_TENANT), CHAT_C
        )
        await session.commit()
        assert rebound.tenant_id == OTHER_TENANT


@pytest.mark.asyncio
@skip_on_db_error
async def test_one_tenant_cannot_revoke_another_tenants_binding(clean_slate):
    async with async_session() as session:
        binding = await TelegramBindingService(session).redeem_code(await _issue(), CHAT)
        binding_id = binding.id
        await session.commit()

    async with async_session() as session:
        assert await TelegramBindingService(session).revoke(OTHER_TENANT, binding_id) is False
        await session.commit()

    async with async_session() as session:
        assert await TelegramBindingService(session).tenant_for_chat(CHAT) == TENANT


# ── Listing and housekeeping ──────────────────────────────────────


@pytest.mark.asyncio
@skip_on_db_error
async def test_listing_shows_only_this_tenants_active_bindings(clean_slate):
    async with async_session() as session:
        svc = TelegramBindingService(session)
        await svc.redeem_code(await _issue(TENANT), CHAT)
        await svc.redeem_code(await _issue(OTHER_TENANT), CHAT_B)
        await session.commit()

    async with async_session() as session:
        rows = await TelegramBindingService(session).list_bindings(TENANT)
        assert [r.chat_id for r in rows] == [CHAT]


@pytest.mark.asyncio
@skip_on_db_error
async def test_expired_codes_are_purged_and_live_ones_are_not(clean_slate):
    stale = await _issue(ttl=timedelta(seconds=-1))
    live = await _issue(ttl=timedelta(minutes=10))
    async with async_session() as session:
        await TelegramBindingService(session).purge_expired_codes()
        await session.commit()

    async with async_session() as session:
        assert await session.get(TelegramPairingCode, stale) is None
        assert await session.get(TelegramPairingCode, live) is not None


@pytest.mark.asyncio
@skip_on_db_error
async def test_issued_codes_are_unpredictable_and_unambiguous(clean_slate):
    """Confusable characters are excluded: the code is retyped by hand."""
    codes = {await _issue() for _ in range(25)}
    assert len(codes) == 25, "issued codes collided"
    assert all(len(c) == 6 for c in codes)
    assert not (set("".join(codes)) & set("ILOU")), "confusable characters in code"


@pytest.mark.asyncio
@skip_on_db_error
async def test_touch_records_activity_without_changing_the_tenant(clean_slate):
    async with async_session() as session:
        await TelegramBindingService(session).redeem_code(await _issue(), CHAT)
        await session.commit()

    before = datetime.now(UTC)
    async with async_session() as session:
        await TelegramBindingService(session).touch(CHAT)
        await session.commit()

    async with async_session() as session:
        rows = await TelegramBindingService(session).list_bindings(TENANT)
        seen = rows[0].last_seen_at
        assert seen is not None
        assert (seen if seen.tzinfo else seen.replace(tzinfo=UTC)) >= before
        assert rows[0].tenant_id == TENANT
