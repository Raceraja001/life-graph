"""Telegram notification channel for the Ambient AI watcher framework.

Unlike the other channels, a Telegram "address" is not something the user can
type into a config form — it is a ``chat_id`` that only exists once they have
paired a chat with a one-time code. So this channel resolves its destinations
from ``telegram_bindings`` using the tenant, and treats ``config["chat_id"]``
as an optional override for the unusual case of pinning one specific chat.

Config dict keys (all optional):
    chat_id   — send only to this chat instead of every active binding.
    silent    — force ``disable_notification`` regardless of severity.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from life_graph.integrations.telegram.client import TelegramClient, TelegramError
from life_graph.models.db import TelegramBinding
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

_SEVERITY_PREFIX = {
    "critical": "🔴 CRITICAL",
    "important": "🟠 Important",
    "info": "🔵",
}


class TelegramChannel:
    """Sends watcher notifications to a tenant's paired Telegram chats."""

    def __init__(self, session_factory=None, client_factory=None):  # noqa: ANN001
        self._session_factory = session_factory or async_session
        self._client_factory = client_factory or TelegramClient

    async def send(
        self,
        config: dict[str, Any],
        tenant_id: str,
        severity: str,
        title: str,
        details: str | None = None,
        watcher_name: str | None = None,
    ) -> bool:
        """Deliver one notification to every paired chat for ``tenant_id``.

        Args:
            config: Channel config (``chat_id`` and ``silent`` optional).
            tenant_id: Tenant whose bindings supply the destinations.
            severity: 'critical', 'important' or 'info'.
            title: Notification headline.
            details: Optional body text.
            watcher_name: Originating watcher, shown as attribution.

        Returns:
            True if at least one chat received the message.
        """
        chat_ids = await self._resolve_chats(config, tenant_id)
        if not chat_ids:
            logger.info("No paired Telegram chat for tenant %s — skipping", tenant_id)
            return False

        text = self._format(severity, title, details, watcher_name)
        # INFO is the daily-brief tier and fires on a 03:00 UTC cron. Delivering
        # it silently means the message is waiting in the morning rather than
        # buzzing overnight; anything above INFO is meant to interrupt.
        silent = bool(config.get("silent")) or severity.lower() == "info"

        delivered = 0
        async with self._client_factory() as client:
            if not client.configured:
                logger.warning("Telegram channel used but no bot token configured")
                return False
            for chat_id in chat_ids:
                try:
                    await client.send_message(chat_id, text, disable_notification=silent)
                    delivered += 1
                except TelegramError as e:
                    # One blocked or deleted chat must not stop the others.
                    logger.warning("Telegram send to chat %s failed: %s", chat_id, e)
                except Exception:
                    logger.warning("Telegram send to chat %s failed", chat_id, exc_info=True)

        return delivered > 0

    async def _resolve_chats(self, config: dict[str, Any], tenant_id: str) -> list[int]:
        """Chat ids to notify: the config override, else the tenant's bindings."""
        override = config.get("chat_id")
        if override:
            try:
                return [int(override)]
            except (TypeError, ValueError):
                logger.warning("Telegram channel config has non-numeric chat_id %r", override)
                return []

        try:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(TelegramBinding.chat_id).where(
                        TelegramBinding.tenant_id == tenant_id,
                        TelegramBinding.active.is_(True),
                    )
                )
                return [int(row) for row in result.scalars().all()]
        except Exception:
            logger.warning("Failed to load Telegram bindings for %s", tenant_id, exc_info=True)
            return []

    @staticmethod
    def _format(
        severity: str,
        title: str,
        details: str | None,
        watcher_name: str | None,
    ) -> str:
        """Render a notification as plain text.

        Deliberately not Markdown or HTML: titles and details are arbitrary
        content from watchers and captured memories, and an unescaped ``_`` or
        ``*`` makes Telegram reject the whole message with a 400 rather than
        merely render it oddly. Plain text cannot fail that way.
        """
        prefix = _SEVERITY_PREFIX.get(severity.lower(), "🔵")
        lines = [f"{prefix} {title}".strip()]
        if details:
            lines.append("")
            lines.append(details)
        if watcher_name and watcher_name not in ("unknown", "queued"):
            lines.append("")
            lines.append(f"— {watcher_name}")
        return "\n".join(lines)
