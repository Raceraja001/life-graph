"""Housekeeping for the Telegram bridge.

Pairing codes are short-lived by design — a code is spent the moment a chat
uses it, and expires a few minutes later whether or not anyone typed it. Both
outcomes leave a row behind, so without a sweep the ``telegram_pairing_codes``
table grows for the lifetime of the deployment and never shrinks.

The sweep deliberately runs across every tenant rather than per-tenant: an
expired code is dead regardless of who asked for it, and the table is keyed by
a code that must be globally unique anyway. That makes this one of the few
places in the codebase that legitimately queries without a ``tenant_id``
filter, alongside the other nightly crons.
"""

from __future__ import annotations

import logging

from life_graph.services.telegram_binding import TelegramBindingService
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)


async def purge_telegram_pairing_codes(ctx: dict) -> dict:
    """Nightly cron: delete pairing codes that have passed their expiry.

    Args:
        ctx: ARQ context.

    Returns:
        Dict with the number of rows ``deleted``.
    """
    async with async_session() as session:
        deleted = await TelegramBindingService(session).purge_expired_codes()
        await session.commit()

    if deleted:
        logger.info("Purged %d expired Telegram pairing code(s)", deleted)
    return {"deleted": deleted}
