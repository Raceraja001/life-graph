"""Pairing and binding between Telegram chats and Life Graph tenants.

An inbound Telegram update carries a ``chat_id`` and no authentication of its
own. This module is where a chat acquires a tenant, and therefore where the
multi-tenant boundary is drawn for the whole bridge: everything downstream
(capture, recall, approvals) trusts the tenant this module returns.

The flow is a one-time code. An authenticated API caller asks for a code, the
user sends ``/start <code>`` to the bot, and redeeming it creates the binding.
The code is the only secret between a stranger and a write into someone else's
memory, so it is generated with :mod:`secrets`, short-lived, and single-use.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import delete, select, update

from life_graph.models.db import TelegramBinding, TelegramPairingCode

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Crockford-style: no I, L, O, U — the code is read off one screen and typed
# into another by hand, and those are the characters people get wrong. U is
# dropped as well so the alphabet cannot spell short words by accident.
_CODE_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_CODE_LENGTH = 6

# 32 symbols ** 6 ≈ 1.07e9. Combined with a ten-minute window and single use,
# guessing is not a practical attack; the window is the real control, so it is
# deliberately short rather than convenient.
DEFAULT_CODE_TTL = timedelta(minutes=10)


class PairingError(Exception):
    """A pairing code could not be redeemed. The message is user-facing."""


class TelegramBindingService:
    """Issues pairing codes and resolves chats to tenants.

    Operates on a caller-provided ``AsyncSession``; the caller commits.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Pairing ───────────────────────────────────────────────

    async def issue_code(self, tenant_id: str, ttl: timedelta | None = None) -> TelegramPairingCode:
        """Mint a single-use pairing code for ``tenant_id``.

        Retries on the astronomically unlikely collision with a live code
        rather than trusting one draw, because a collision would hand the
        second caller the first caller's tenant.
        """
        expires_at = datetime.now(UTC) + (ttl or DEFAULT_CODE_TTL)

        for _ in range(5):
            code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
            existing = await self.session.get(TelegramPairingCode, code)
            if existing is not None:
                continue
            row = TelegramPairingCode(code=code, tenant_id=tenant_id, expires_at=expires_at)
            self.session.add(row)
            await self.session.flush()
            return row

        raise PairingError("Could not allocate a pairing code. Please try again.")

    async def redeem_code(
        self,
        code: str,
        chat_id: int,
        chat_type: str = "private",
        username: str | None = None,
    ) -> TelegramBinding:
        """Bind ``chat_id`` to the tenant that owns ``code``.

        Raises :class:`PairingError` with a user-facing message for every
        rejection. The messages deliberately do not distinguish "no such code"
        from "expired" from "already used": all three are the same answer to
        someone probing codes, and the distinction helps only an attacker.
        """
        if chat_type != "private":
            raise PairingError(
                "Pairing only works in a direct message with the bot, not in a group."
            )

        row = await self.session.get(
            TelegramPairingCode, (code or "").strip().upper(), with_for_update=True
        )
        now = datetime.now(UTC)

        if row is None or row.used_at is not None or _as_utc(row.expires_at) <= now:
            raise PairingError("That pairing code is not valid. Generate a fresh one.")

        # Spend the code before creating the binding: if the insert below fails
        # the transaction rolls both back together, but if this ordering were
        # reversed a partial failure could leave a live code behind.
        row.used_at = now

        existing = await self._active_binding_for_chat(chat_id)
        if existing is not None:
            if existing.tenant_id == row.tenant_id:
                # Re-pairing the same chat to the same tenant is a no-op rather
                # than an error — the user most likely lost track of the state.
                existing.last_seen_at = now
                existing.username = username or existing.username
                await self.session.flush()
                return existing
            raise PairingError(
                "This chat is already linked to another account. Unlink it there first."
            )

        binding = TelegramBinding(
            tenant_id=row.tenant_id,
            chat_id=chat_id,
            chat_type=chat_type,
            username=username,
            active=True,
            bound_at=now,
            last_seen_at=now,
        )
        self.session.add(binding)
        await self.session.flush()
        return binding

    # ── Lookup ────────────────────────────────────────────────

    async def tenant_for_chat(self, chat_id: int) -> str | None:
        """The tenant this chat writes to, or ``None`` when unbound.

        ``None`` means drop the message. It must never be treated as "use the
        default tenant" — an unbound chat is an unknown party.
        """
        binding = await self._active_binding_for_chat(chat_id)
        return binding.tenant_id if binding else None

    async def touch(self, chat_id: int) -> None:
        """Record that the chat was heard from, for the status endpoint."""
        await self.session.execute(
            update(TelegramBinding)
            .where(TelegramBinding.chat_id == chat_id, TelegramBinding.active.is_(True))
            .values(last_seen_at=datetime.now(UTC))
        )

    async def list_bindings(self, tenant_id: str) -> list[TelegramBinding]:
        """Active bindings for a tenant, newest first."""
        result = await self.session.execute(
            select(TelegramBinding)
            .where(
                TelegramBinding.tenant_id == tenant_id,
                TelegramBinding.active.is_(True),
            )
            .order_by(TelegramBinding.bound_at.desc())
        )
        return list(result.scalars().all())

    async def revoke(self, tenant_id: str, binding_id) -> bool:  # noqa: ANN001
        """Deactivate a binding. Returns False when it is not this tenant's.

        Deactivates rather than deletes, so the record of which chat had access
        survives; the partial unique index is on ``active``, so the same chat
        can be paired again afterwards.
        """
        result = await self.session.execute(
            update(TelegramBinding)
            .where(
                TelegramBinding.id == binding_id,
                TelegramBinding.tenant_id == tenant_id,
                TelegramBinding.active.is_(True),
            )
            .values(active=False)
        )
        return bool(result.rowcount)

    # ── Housekeeping ──────────────────────────────────────────

    async def purge_expired_codes(self) -> int:
        """Delete spent and expired codes. Returns the number removed."""
        result = await self.session.execute(
            delete(TelegramPairingCode).where(TelegramPairingCode.expires_at <= datetime.now(UTC))
        )
        return int(result.rowcount or 0)

    # ── Internals ─────────────────────────────────────────────

    async def _active_binding_for_chat(self, chat_id: int) -> TelegramBinding | None:
        result = await self.session.execute(
            select(TelegramBinding).where(
                TelegramBinding.chat_id == chat_id,
                TelegramBinding.active.is_(True),
            )
        )
        return result.scalar_one_or_none()


def _as_utc(value: datetime) -> datetime:
    """Postgres may hand back a naive datetime depending on the driver."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)
