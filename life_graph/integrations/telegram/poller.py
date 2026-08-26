"""Single-consumer long-poll loop over ``getUpdates``.

Telegram hands each update to exactly one ``getUpdates`` call. Two pollers
against the same bot token do not duplicate a conversation — they *split* it,
each receiving a different half, which is far harder to notice than an outage.
A Redis lease makes one instance the leader and the others standbys.

Long-polling rather than a webhook because this deployment is self-hosted
behind NAT: a webhook would need a public HTTPS endpoint and a tunnel to keep
alive, while polling only makes outbound calls.

The loop is written to fail loudly in the logs and quietly to the user: a
network blip backs off and retries, and the offset only advances past an update
once it has been handled, so a crash replays rather than drops. Replays are
safe because the capture spine deduplicates on a content hash.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import uuid
from datetime import UTC, datetime

import httpx

from life_graph.config import settings
from life_graph.integrations.telegram.client import TelegramClient, TelegramError
from life_graph.integrations.telegram.router import handle_update
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

LEASE_KEY = "telegram:poller:lease"
OFFSET_KEY = "telegram:poller:offset"

# The API process cannot see this object — the poller runs in the ARQ worker —
# so liveness has to be published somewhere both can read. The lease already
# proves *a* leader exists, but not that its loop is still turning: these two
# stamps are what /status reports.
#
# HEARTBEAT is written every completed poll cycle and expires, so a stopped
# poller stops answering rather than leaving a stale "last seen" behind.
# LAST_UPDATE is written only when a batch actually contained something and
# never expires, because "nothing since Tuesday" is a fact worth keeping.
HEARTBEAT_KEY = "telegram:poller:heartbeat"
LAST_UPDATE_KEY = "telegram:poller:last_update"

# The lease must outlive one long poll or the leader loses it mid-call and a
# standby starts a competing getUpdates. Renewed every loop, so the only way it
# expires is a leader that actually stopped.
LEASE_TTL_SECONDS = 90
STANDBY_SLEEP_SECONDS = 15

BACKOFF_START_SECONDS = 1.0
BACKOFF_MAX_SECONDS = 60.0


class TelegramPoller:
    """Owns the update loop for one process.

    Start with :meth:`start` (fire-and-forget task) and stop with :meth:`stop`,
    which releases the lease so another instance can take over immediately
    rather than after the TTL.
    """

    def __init__(self, client: TelegramClient | None = None):
        self._client = client
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()
        self._leading = False
        # Identifies this process in the lease so we only ever release our own.
        self._holder = f"{os.getpid()}:{uuid.uuid4().hex[:8]}"

    # ── Lifecycle ─────────────────────────────────────────────

    @property
    def status(self) -> str:
        """One of ``leading``, ``standby`` or ``stopped`` — surfaced by /health."""
        if self._task is None or self._task.done():
            return "stopped"
        return "leading" if self._leading else "standby"

    async def start(self) -> bool:
        """Begin polling. Returns False when the bridge is not configured."""
        if not settings.telegram_bot_token:
            logger.info("telegram: no bot token — bridge disabled")
            return False
        if self._task is not None and not self._task.done():
            return True
        self._stopping.clear()
        self._task = asyncio.create_task(self.run_forever(), name="telegram-poller")
        return True

    async def stop(self) -> None:
        """Stop the loop and hand the lease on."""
        self._stopping.set()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        await self._release_lease()
        self._leading = False

    # ── The loop ──────────────────────────────────────────────

    async def run_forever(self) -> None:
        backoff = BACKOFF_START_SECONDS
        async with (
            TelegramClient() if self._client is None else _BorrowedClient(self._client) as client
        ):
            while not self._stopping.is_set():
                if not await self._acquire_lease():
                    self._leading = False
                    await self._sleep(STANDBY_SLEEP_SECONDS)
                    continue
                self._leading = True

                try:
                    offset = await self._load_offset()
                    updates = await client.get_updates(
                        offset=offset, timeout=settings.telegram_poll_timeout
                    )
                    for update in updates:
                        await self._dispatch(update)
                        # After handling, never before: a crash mid-handler
                        # replays the update instead of losing it.
                        await self._store_offset(int(update["update_id"]) + 1)
                    await self._stamp(HEARTBEAT_KEY, ttl=LEASE_TTL_SECONDS)
                    if updates:
                        await self._stamp(LAST_UPDATE_KEY)
                    backoff = BACKOFF_START_SECONDS

                except asyncio.CancelledError:
                    raise
                except TelegramError as exc:
                    if exc.retry_after:
                        # Telegram told us exactly how long to wait; guessing
                        # would only earn a longer penalty.
                        logger.warning("telegram: rate limited, waiting %ss", exc.retry_after)
                        await self._sleep(exc.retry_after)
                        continue
                    if exc.error_code in (401, 404):
                        # A bad token never fixes itself by retrying.
                        logger.error(
                            "telegram: bot token rejected (%s) — stopping", exc.description
                        )
                        self._stopping.set()
                        break
                    logger.warning("telegram: API error — %s", exc.description)
                    backoff = await self._backoff(backoff)
                except (httpx.HTTPError, OSError) as exc:
                    logger.warning("telegram: network error — %s", exc)
                    backoff = await self._backoff(backoff)
                except Exception:  # noqa: BLE001 - the loop must survive a handler bug
                    logger.exception("telegram: unexpected error in poll loop")
                    backoff = await self._backoff(backoff)

        self._leading = False

    async def _dispatch(self, update: dict) -> None:
        """Handle one update in its own session and transaction."""
        async with async_session() as session:
            try:
                await handle_update(update, session)
            except Exception:  # noqa: BLE001 - one bad message must not stop the queue
                await session.rollback()
                logger.exception("telegram: handler failed for update %s", update.get("update_id"))

    async def _backoff(self, current: float) -> float:
        await self._sleep(current)
        return min(current * 2, BACKOFF_MAX_SECONDS)

    async def _sleep(self, seconds: float) -> None:
        """Sleep, but wake immediately on stop."""
        with contextlib.suppress(TimeoutError, asyncio.TimeoutError):
            await asyncio.wait_for(self._stopping.wait(), timeout=seconds)

    # ── Lease ─────────────────────────────────────────────────

    async def _acquire_lease(self) -> bool:
        """Become (or stay) the leader.

        With no Redis there is nothing to coordinate through, so a single
        instance proceeds. That is the right call for this deployment — one
        self-hosted box — and the failure it risks (two pollers when Redis is
        down *and* two instances run) is logged loudly at startup instead.
        """
        redis = _redis()
        if redis is None:
            return True
        try:
            if await redis.set(LEASE_KEY, self._holder, nx=True, ex=LEASE_TTL_SECONDS):
                logger.info("telegram: acquired poller lease (%s)", self._holder)
                return True
            # Already ours? Renew. Compared by value so we never extend the
            # lease of a different process that took over after we stalled.
            if await redis.get(LEASE_KEY) == self._holder:
                await redis.expire(LEASE_KEY, LEASE_TTL_SECONDS)
                return True
            return False
        except Exception:  # noqa: BLE001 - Redis down: fall back to single-instance
            logger.warning("telegram: lease check failed, proceeding as sole poller")
            return True

    async def _release_lease(self) -> None:
        redis = _redis()
        if redis is None:
            return
        with contextlib.suppress(Exception):
            if await redis.get(LEASE_KEY) == self._holder:
                await redis.delete(LEASE_KEY)

    # ── Offset ────────────────────────────────────────────────

    async def _load_offset(self) -> int | None:
        redis = _redis()
        if redis is None:
            return None
        with contextlib.suppress(Exception):
            raw = await redis.get(OFFSET_KEY)
            if raw is not None:
                return int(raw)
        return None

    async def _store_offset(self, offset: int) -> None:
        redis = _redis()
        if redis is None:
            return
        with contextlib.suppress(Exception):
            await redis.set(OFFSET_KEY, offset)

    # ── Liveness ──────────────────────────────────────────────

    async def _stamp(self, key: str, ttl: int | None = None) -> None:
        """Record "this happened just now" for the status endpoint to read.

        Suppresses everything: a status stamp that fails must never take down
        the loop it exists to describe.
        """
        redis = _redis()
        if redis is None:
            return
        with contextlib.suppress(Exception):
            await redis.set(key, datetime.now(UTC).isoformat(), ex=ttl)


def _redis():  # noqa: ANN202
    from life_graph.storage.redis import get_redis

    return get_redis()


class _BorrowedClient:
    """Use an injected client without taking ownership of its lifecycle."""

    def __init__(self, client: TelegramClient):
        self._client = client

    async def __aenter__(self) -> TelegramClient:
        return self._client

    async def __aexit__(self, *exc: object) -> None:
        return None


# One poller per process, started from the worker's on_startup.
poller = TelegramPoller()
